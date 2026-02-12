"""
DC运营时间缩短仿真模型 - 基于FG和R&P业务流程的离散事件仿真
"""

import simpy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os
import re
import math

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'results')
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'figures')

# Cache for large generated_orders.json to avoid repeated IO during multi-scenario / multi-month runs
_CACHED_ORDERS_PATH = None
_CACHED_ORDERS_DATA = None

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

def load_simulation_config(config_path='outputs/simulation_configs/simulation_config.json'):
    """加载仿真配置文件，不存在则使用默认参数"""
    config_file = os.path.join(PROJECT_ROOT, config_path)
    if os.path.exists(config_file):
        print(f"加载配置文件: {config_file}")
        with open(config_file, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        print("配置文件加载成功")
        return loaded_config
    else:
        print(f"警告: 配置文件未找到: {config_file}")
        print("  使用硬编码默认参数")
        return None

LOADED_CONFIG = load_simulation_config()

SIMULATION_CONFIG = {
    'baseline': {
        'name': 'Baseline (06:00-24:00)',
        'dc_open_time': 6,
        'dc_close_time': 24,
        'operating_hours': 18,
        'arrival_smoothing': False 
    },
    # Group A: 固定开始时间 06:00，逐步缩短结束时间
    'fixed_06_23': {
        'name': 'Fixed Start (06:00-23:00)',
        'dc_open_time': 6,
        'dc_close_time': 23,
        'operating_hours': 17,
        'arrival_smoothing': False
    },
    'fixed_06_22': {
        'name': 'Fixed Start (06:00-22:00)',
        'dc_open_time': 6,
        'dc_close_time': 22,
        'operating_hours': 16,
        'arrival_smoothing': False
    },
    'fixed_06_21': {
        'name': 'Fixed Start (06:00-21:00)',
        'dc_open_time': 6,
        'dc_close_time': 21,
        'operating_hours': 15,
        'arrival_smoothing': False
    },
    'fixed_06_20': {
        'name': 'Fixed Start (06:00-20:00)',
        'dc_open_time': 6,
        'dc_close_time': 20,
        'operating_hours': 14,
        'arrival_smoothing': False
    },

    # Group B: 不固定开始时间（07:00 / 08:00）
    'shift_07_23': {
        'name': 'Shifted (07:00-23:00)',
        'dc_open_time': 7,
        'dc_close_time': 23,
        'operating_hours': 16,
        'arrival_smoothing': False
    },
    'shift_07_22': {
        'name': 'Shifted (07:00-22:00)',
        'dc_open_time': 7,
        'dc_close_time': 22,
        'operating_hours': 15,
        'arrival_smoothing': False
    },
    'shift_07_21': {
        'name': 'Shifted (07:00-21:00)',
        'dc_open_time': 7,
        'dc_close_time': 21,
        'operating_hours': 14,
        'arrival_smoothing': False
    },
    'shift_08_23': {
        'name': 'Shifted (08:00-23:00)',
        'dc_open_time': 8,
        'dc_close_time': 23,
        'operating_hours': 15,
        'arrival_smoothing': False
    },
    'shift_08_22': {
        'name': 'Shifted (08:00-22:00)',
        'dc_open_time': 8,
        'dc_close_time': 22,
        'operating_hours': 14,
        'arrival_smoothing': False
    },
    'shift_08_21': {
        'name': 'Shifted (08:00-21:00)',
        'dc_open_time': 8,
        'dc_close_time': 21,
        'operating_hours': 13,
        'arrival_smoothing': False
    },
    'shift_08_20': {
        'name': 'Shifted (08:00-20:00)',
        'dc_open_time': 8,
        'dc_close_time': 20,
        'operating_hours': 12,
        'arrival_smoothing': False
    }
}


def _compute_daily_open_windows(dc_config: dict, day_index: int):
    """Return a list of (open_hour, close_hour) windows for a given simulation day.

    Default behavior: one window [dc_open_time, dc_close_time).

        Supported override rules (in-memory only; can be injected via scenario transform):

            Single-rule (backward compatible):
                dc_config['biweekly_shift_cancel'] = {
                        'day1_weekday': 0,          # 0=Mon..6=Sun
                        'weekday': 4,               # Friday
                        'start_week_index': 1,      # start from 2nd Friday (week_index=1)
                        'every_n_weeks': 2,
                        'cancel_start_hour': 15,
                        'cancel_end_hour': 24       # optional; defaults to dc_close_time
                }

            Multi-rule (preferred for multiple weekdays):
                dc_config['shift_cancel_rules'] = [ {..rule..}, {..rule..}, ... ]
    """
    dc_open = int(dc_config.get('dc_open_time', 0))
    dc_close = int(dc_config.get('dc_close_time', 24))
    if dc_close <= dc_open:
        return []

    windows = [(dc_open, dc_close)]

    # Collect rules (multi-rule preferred)
    rules = []
    multi = dc_config.get('shift_cancel_rules')
    if isinstance(multi, list) and multi:
        rules = [r for r in multi if isinstance(r, dict)]
    else:
        single = dc_config.get('biweekly_shift_cancel')
        if isinstance(single, dict):
            rules = [single]

    if not rules:
        return windows

    def _rule_applies(rule: dict) -> bool:
        day1_weekday = int(rule.get('day1_weekday', dc_config.get('day1_weekday', 0)))
        weekday = (day1_weekday + int(day_index)) % 7
        target_weekday = int(rule.get('weekday', 4))
        if weekday != target_weekday:
            return False

        week_index = int(day_index) // 7
        start_week_index = int(rule.get('start_week_index', 1))
        every_n_weeks = int(rule.get('every_n_weeks', 2))
        if week_index < start_week_index or every_n_weeks <= 0:
            return False
        if (week_index - start_week_index) % every_n_weeks != 0:
            return False
        return True

    def _subtract_interval(wins, cancel_start: int, cancel_end: int):
        out = []
        for a, b in wins:
            if cancel_end <= a or cancel_start >= b:
                out.append((a, b))
                continue
            if cancel_start > a:
                out.append((a, min(cancel_start, b)))
            if cancel_end < b:
                out.append((max(cancel_end, a), b))
        return [(a, b) for a, b in out if b > a]

    for rule in rules:
        if not _rule_applies(rule):
            continue
        cancel_start = int(rule.get('cancel_start_hour', 15))
        cancel_end = int(rule.get('cancel_end_hour', dc_close))
        cancel_start = max(0, min(24, cancel_start))
        cancel_end = max(0, min(24, cancel_end))
        if cancel_end <= cancel_start:
            continue
        windows = _subtract_interval(windows, cancel_start, cancel_end)
        if not windows:
            break

    return windows


def _is_dc_open_at_time(time_abs: float, dc_config: dict) -> bool:
    if time_abs is None:
        return False
    # Sim time starts at 0 (Day1 00:00). Support negative times deterministically.
    day_index = int(math.floor(float(time_abs) / 24.0))
    hour_of_day = int(time_abs) % 24
    for a, b in _compute_daily_open_windows(dc_config, day_index):
        if a <= hour_of_day < b:
            return True
    return False

if LOADED_CONFIG:
    SYSTEM_PARAMETERS = {
        'efficiency': LOADED_CONFIG['efficiency'],
        'factory_production': LOADED_CONFIG['factory_production'],
        'buffer_capacity': {  # 使用默认配置
            'rp_trailers': 4,
            'fg_trailers': 9,
            'pallets_per_trailer': 33
        },
        'truck_arrival_rates_outbound': LOADED_CONFIG.get('truck_arrival_rates_outbound', 
                                                           LOADED_CONFIG.get('truck_arrival_rates', {})),
        'truck_arrival_rates_inbound': LOADED_CONFIG.get('truck_arrival_rates_inbound', {}),
    }
    
    # 加载码头容量
    if 'hourly_dock_capacity' in LOADED_CONFIG:
        loaded_capacity = LOADED_CONFIG['hourly_dock_capacity']
        SYSTEM_PARAMETERS['hourly_dock_capacity'] = {
            'FG': loaded_capacity['FG'],
            'R&P': loaded_capacity.get('R&P', loaded_capacity.get('RP', {}))
        }
    else:
        SYSTEM_PARAMETERS['hourly_dock_capacity'] = {
            'FG': {
                'loading': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                           6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1,
                           12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1,
                           18: 1, 19: 1, 20: 1, 21: 1, 22: 1, 23: 1},
                'reception': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                             6: 2, 7: 2, 8: 2, 9: 2, 10: 2, 11: 2,
                             12: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 2,
                             18: 2, 19: 2, 20: 2, 21: 2, 22: 1, 23: 0}
            },
            'R&P': {
                'loading': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                           6: 4, 7: 6, 8: 5, 9: 5, 10: 5, 11: 6,
                           12: 5, 13: 6, 14: 6, 15: 5, 16: 5, 17: 4,
                           18: 4, 19: 4, 20: 3, 21: 3, 22: 3, 23: 3},
                'reception': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                             6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1,
                             12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1,
                             18: 1, 19: 1, 20: 1, 21: 1, 22: 1, 23: 1}
            }
        }
    
    # 加载托盘数分布
    if 'pallets_distribution' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['pallets_distribution'] = LOADED_CONFIG['pallets_distribution']
    else:
        SYSTEM_PARAMETERS['pallets_distribution'] = {
            'FG': {'type': 'triangular', 'min': 1, 'mode': 33, 'max': 276, 'mean': 30.0, 'std': 12.3},
            'R&P': {'type': 'triangular', 'min': 1, 'mode': 22, 'max': 560, 'mean': 22.7, 'std': 9.7}
        }
    
    # 加载人力资源数据
    if 'fte_total' in LOADED_CONFIG and 'fte_allocation' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['fte_total'] = LOADED_CONFIG['fte_total']
        SYSTEM_PARAMETERS['fte_allocation'] = LOADED_CONFIG['fte_allocation']
    else:
        SYSTEM_PARAMETERS['fte_total'] = 125
        SYSTEM_PARAMETERS['fte_allocation'] = {'rp_baseline': 28, 'fg_baseline': 97}
    
    # 加载订单数据和opening hour coefficient
    if 'generated_orders_path' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['generated_orders_path'] = LOADED_CONFIG['generated_orders_path']
    if 'opening_hour_coefficient' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['opening_hour_coefficient'] = LOADED_CONFIG['opening_hour_coefficient']
    else:
        SYSTEM_PARAMETERS['opening_hour_coefficient'] = 1.0

else:
    # 使用硬编码默认参数
    SYSTEM_PARAMETERS = {
        # 生产效率参数（托盘/小时）
        'efficiency': {
            'rp_mean': 5.81,      # R&P 平均效率
            'rp_std': 0.416,      # R&P 效率标准差
            'fg_mean': 3.5,       # FG 平均效率（估算）
            'fg_std': 0.5         # FG 效率标准差（估算）
        },
        
        # 工厂生产速率（托盘/小时，24/7 连续）
        'factory_production': {
            'rp_rate': 23,        # R&P: 16,500/月 ≈ 23/小时
            'fg_rate': 46         # FG: 33,000/月 ≈ 46/小时
        },
        
        # 缓冲区容量
        'buffer_capacity': {
            'rp_trailers': 15,
            'fg_trailers': 20,
            'pallets_per_trailer': 33
        },
        
        # 码头容量（按小时）
        'hourly_dock_capacity': {
            'FG': {
                'loading': {
                    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                    6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1,
                    12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1,
                    18: 1, 19: 1, 20: 1, 21: 1, 22: 1, 23: 1
                },
                'reception': {  # FG Reception（入库）
                    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                    6: 2, 7: 2, 8: 2, 9: 2, 10: 2, 11: 2,
                    12: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 2,
                    18: 2, 19: 2, 20: 2, 21: 2, 22: 1, 23: 0
                }
            },
            'R&P': {
                'loading': {
                    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                    6: 4, 7: 6, 8: 5, 9: 5, 10: 5, 11: 6,
                    12: 5, 13: 6, 14: 6, 15: 5, 16: 5, 17: 4,
                    18: 4, 19: 4, 20: 3, 21: 3, 22: 3, 23: 3
                },
                'reception': {  # R&P Reception（入库）
                    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                    6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1,
                    12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1,
                    18: 1, 19: 1, 20: 1, 21: 1, 22: 1, 23: 1
                }
            }
        },
        
        'fte_total': 125,
        'fte_allocation': {
            'rp_baseline': 28,
            'fg_baseline': 97
        },
        
        'truck_arrival_rates_outbound': {
            'FG': {
                6: 1.62, 7: 2.8, 8: 2.47, 9: 2.61, 10: 3.15,
                11: 3.21, 12: 3.16, 13: 3.01, 14: 2.9, 15: 2.6,
                16: 2.65, 17: 2.11, 18: 1.82, 19: 1.59, 20: 0.7,
                21: 0.23, 22: 0.15
            },
            'R&P': {
                4: 0.0, 5: 0.0, 6: 0.77, 7: 1.13, 8: 1.13,
                9: 1.14, 10: 0.96, 11: 1.08, 12: 0.78, 13: 0.83,
                14: 0.95, 15: 0.99, 16: 0.87, 17: 0.87, 18: 0.94,
                19: 1.42, 20: 0.77, 21: 0.75, 22: 0.52, 23: 0.36
            }
        },
        
        'truck_arrival_rates_inbound': {
            'FG': {
                6: 1.0, 7: 1.5, 8: 1.2, 9: 1.3, 10: 1.5,
                11: 1.6, 12: 1.5, 13: 1.4, 14: 1.3, 15: 1.2,
                16: 1.2, 17: 1.0, 18: 0.8, 19: 0.7, 20: 0.3
            },
            'R&P': {
                6: 0.5, 7: 0.8, 8: 0.8, 9: 0.8, 10: 0.7,
                11: 0.8, 12: 0.6, 13: 0.6, 14: 0.7, 15: 0.7,
                16: 0.6, 17: 0.6, 18: 0.7, 19: 1.0, 20: 0.5
            }
        },
        
        'pallets_distribution': {
            'FG': {
                'type': 'triangular',
                'min': 1,
                'mode': 33,
                'max': 276,
                'mean': 30.0,
                'std': 12.3
            },
            'R&P': {
                'type': 'triangular',
                'min': 1,
                'mode': 22,
                'max': 560,
                'mean': 22.7,
                'std': 9.7
            }
        }
    }

class Order:
    """订单实体（新逻辑：基于预生成数据）"""
    _id_counter = 0
    
    def __init__(self, order_data):
        """
        Args:
            order_data: dict，从generated_orders.json加载的订单记录
        """
        Order._id_counter += 1
        self.id = Order._id_counter
        
        # 基础属性
        self.order_id = order_data['order_id']
        self.month = order_data['month']
        self.day = order_data['day']
        self.category = order_data['category']
        self.direction = order_data['direction']
        self.pallets = order_data['pallets']
        
        # Outbound特有属性
        if self.direction == 'Outbound':
            self.region = order_data.get('region')  # 'G2_same_day', 'G2_next_day', 'ROW_next_day'
            self.creation_hour = order_data.get('creation_hour')  # 相对当天的小时
            # data_preparation.py 可能会写入绝对时间字段（非严格JSON也会被python json解析）
            self.creation_time_abs = order_data.get('creation_time_abs')
            self.creation_time = None  # 绝对仿真时间，后续计算
            self.preparation_started = False
            self.preparation_completed = False
            self.preparation_pallets_done = 0
        
        # Inbound/Outbound通用
        self.timeslot_hour = order_data.get('timeslot_hour')
        self.timeslot_abs = order_data.get('timeslot_abs')
        self.timeslot_time = None  # 绝对仿真时间，后续计算
        
        # 状态跟踪
        self.actual_timeslot = None  # 实际分配的timeslot（可能因延误改变）
        self.on_time = True  # 是否按原timeslot完成
        self.delay_hours = 0
        self.processing_start_time = None
        self.processing_end_time = None
        self.completed = False
        
    def __repr__(self):
        if self.direction == 'Outbound':
            return f"Order-{self.id}({self.category}-OUT, {self.pallets}p, {self.region}, slot={self.timeslot_hour})"
        return f"Order-{self.id}({self.category}-IN, {self.pallets}p, slot={self.timeslot_hour})"


class FTEManager:
    """人力资源管理器 - FTE 按运营时长调整"""
    def __init__(self, operating_hours=18, efficiency_multiplier=1.0, fte_adjustment_ratio=None):
        if LOADED_CONFIG and 'fte_config' in LOADED_CONFIG:
            fte_config = LOADED_CONFIG['fte_config']
            self.baseline_fte = {
                'FG': {
                    'Inbound': fte_config['FG']['Inbound'],
                    'Outbound': fte_config['FG']['Outbound']
                },
                'R&P': {
                    'Inbound': fte_config['R&P']['Inbound'],
                    'Outbound': fte_config['R&P']['Outbound']
                }
            }
            self.efficiency_per_fte = {
                'FG': fte_config['FG']['efficiency'],
                'R&P': fte_config['R&P']['efficiency']
            }
        else:
            # 使用硬编码默认值
            self.baseline_fte = {
                'FG': {'Inbound': 44.75, 'Outbound': 44.75},
                'R&P': {'Inbound': 10.025, 'Outbound': 10.025}
            }
            self.efficiency_per_fte = {
                'FG': 665.43,
                'R&P': 1308.83
            }
            print("  使用硬编码FTE默认值")
        
        # 月度工时和运营参数
        self.hours_per_month = 176
        self.baseline_hours = 18
        self.operating_hours = operating_hours
        self.operating_ratio = operating_hours / self.baseline_hours
        self.fte_adjustment_ratio = fte_adjustment_ratio  # 显式FTE调整比例
        self.adjusted_fte = self._calculate_adjusted_fte()
        self.efficiency_multiplier = float(efficiency_multiplier) if efficiency_multiplier is not None else 1.0
        
    def _calculate_adjusted_fte(self):
        """根据运营时长调整FTE
        
        注意：FTE是Full-Time Equivalent，表示标准工作量单位
        营业时间缩短时，可用FTE工作量应该按比例减少
        """
        adjusted = {}
        for category in ['FG', 'R&P']:
            adjusted[category] = {}
            for direction in ['Inbound', 'Outbound']:
                base = self.baseline_fte[category][direction]
                
                # 优先使用显式的FTE调整比例（用于班次灵活性分析）
                if self.fte_adjustment_ratio is not None:
                    adjustment_ratio = self.fte_adjustment_ratio
                else:
                    # 默认按营业时间比例调整（用于时间窗口分析）
                    adjustment_ratio = self.operating_ratio
                    
                adjusted[category][direction] = base * adjustment_ratio
        return adjusted
    
    def get_hourly_capacity(self, category, direction, coefficient=1.0):
        """每小时处理能力（托盘/小时）
        
        公式: (调整FTE × 效率) / 月度工时 × coefficient
        """
        fte = self.adjusted_fte[category][direction]
        efficiency = self.efficiency_per_fte[category]
        base_capacity = (fte * efficiency) / self.hours_per_month
        adjusted_capacity = base_capacity * coefficient * self.efficiency_multiplier
        # 随机波动 ±5%
        actual_capacity = adjusted_capacity * np.random.uniform(0.95, 1.05)
        
        return actual_capacity
    
    def get_daily_capacity(self, category, direction):
        """获取每天总处理能力（托盘/天）"""
        hourly = self.get_hourly_capacity(category, direction)
        return hourly * self.operating_hours
    
    def get_fte_allocation(self):
        """返回当前FTE配置（用于报告）"""
        return self.adjusted_fte
    
    def get_cost_savings(self):
        """计算成本节约比例"""
        return 1 - self.operating_ratio
    
    def get_efficiency(self, category, direction='Outbound'):
        """获取团队实际效率（兼容旧接口）
        
        返回: 团队总效率（托盘/小时）
        """
        return self.get_hourly_capacity(category, direction)


# ==================== KPI 收集器 ====================

class KPICollector:
    """KPI 数据收集和分析"""
    def __init__(self, operating_hours=18):
        self.buffer_overflows = []
        self.truck_wait_times = []
        self.sla_misses = []
        self.completed_orders = []
        self.inbound_operations = []
        self.outbound_operations = []
        self.hourly_buffer_occupancy = defaultdict(list)
        self.midnight_backlogs = []
        self.inbound_delays = []
        self.dock_usage = []
        self.fte_usage = []  # 新增：FTE使用记录
        self.operating_hours = operating_hours  # 营业时间
    
    def record_dock_usage(self, hour, dock_type, category, used, available):
        """记录码头使用情况"""
        if available > 0:
            utilization = min(used / available, 1.0)
        else:
            utilization = 0
            
        self.dock_usage.append({
            'hour': hour,
            'dock_type': dock_type,  # 'loading' or 'reception'
            'category': category,
            'used': used,
            'available': available,
            'utilization': utilization,
            'over_capacity': max(0, used - available)
        })
    
    def record_fte_usage(self, category, direction, processing_time, pallets_processed, available_fte, hourly_capacity):
        """记录FTE使用情况
        
        FTE是硬限制：实际使用的FTE不能超过配置的FTE数量
        如果工作需求超过配置FTE能力，超出部分会导致延期，而不是超额使用FTE
        """
        # FTE效率：每个FTE每月能处理的托盘数（基线18小时营业时间标准）
        if category == 'FG':
            fte_efficiency = 665.43  # FG效率：665.43托盘/FTE/月
        else:  # R&P
            fte_efficiency = 1308.83  # R&P效率：1308.83托盘/FTE/月
            
        # 理论需要的FTE工作量 = 处理的托盘数 / 单FTE处理能力
        fte_required = pallets_processed / fte_efficiency if fte_efficiency > 0 else 0
        
        # 实际使用的FTE = min(理论需求, 配置FTE) - FTE是硬限制，不能超过配置值
        fte_used = min(fte_required, available_fte)
        
        # FTE利用率 = 实际使用的FTE / 配置的FTE（最高100%）
        fte_utilization = fte_used / available_fte if available_fte > 0 else 0
        
        self.fte_usage.append({
            'category': category,
            'direction': direction,
            'processing_time': processing_time,  # 实际处理时间（小时）
            'pallets_processed': pallets_processed,  # 处理的托盘数
            'available_fte': available_fte,  # 配置的FTE工作量（已按营业时间调整）
            'fte_required': fte_required,  # 理论需要的FTE（可能超过配置）
            'fte_used': fte_used,  # 实际使用的FTE（不超过配置）
            'fte_utilization': fte_utilization,  # 本次操作的FTE利用率（最高100%）
            'fte_efficiency': fte_efficiency,  # 单FTE处理能力（基线标准）
            'actual_efficiency': pallets_processed / processing_time if processing_time > 0 else 0,  # 实际处理效率（托盘/小时）
            'timestamp': self.env.now if hasattr(self, 'env') else 0  # 添加时间戳
        })
    
    def record_inbound_delay(self, category, pallets, arrival_time, processing_end, delay_hours):
        """记录Inbound处理超过24小时的情况"""
        self.inbound_delays.append({
            'category': category,
            'pallets': pallets,
            'arrival_time': arrival_time,
            'processing_end': processing_end,
            'delay_hours': delay_hours,
            'processing_deadline': arrival_time + 24
        })
        
    def record_buffer_overflow(self, category, timestamp, pallets):
        self.buffer_overflows.append({
            'category': category,
            'timestamp': timestamp,
            'hour': int(timestamp) % 24,
            'pallets': pallets
        })
    
    def record_truck_wait(self, truck, dc_config):
        """记录卡车等待时间（排除DC关闭时间）"""
        total_wait = truck.service_start_time - truck.actual_arrival_time
        
        # 计算跨越了多少个完整的DC关闭周期
        arrival_time = truck.actual_arrival_time
        service_start = truck.service_start_time
        
        # 计算实际业务等待时间：只累计“开门窗口”内的等待
        business_wait = 0.0
        if service_start > arrival_time:
            start_day = int(arrival_time) // 24
            end_day = int(service_start) // 24
            for day_index in range(start_day, end_day + 1):
                for a, b in _compute_daily_open_windows(dc_config, day_index):
                    win_start = day_index * 24 + a
                    win_end = day_index * 24 + b
                    overlap_start = max(arrival_time, win_start)
                    overlap_end = min(service_start, win_end)
                    if overlap_end > overlap_start:
                        business_wait += (overlap_end - overlap_start)

        # 标记是否跨夜（使用“常规”关门长度近似，便于对比）
        dc_open = int(dc_config.get('dc_open_time', 0))
        dc_close = int(dc_config.get('dc_close_time', 24))
        daily_closure_hours = 24 - dc_close + dc_open
        
        self.truck_wait_times.append({
            'category': truck.category,
            'direction': truck.direction,
            'wait_time': business_wait,  # 只记录业务等待时间
            'total_wait': total_wait,     # 保留总等待时间用于分析
            'overnight': total_wait >= daily_closure_hours  # 标记是否跨夜
        })
    
    def record_sla_miss(self, order, actual_completion):
        self.sla_misses.append({
            'order_id': order.id,
            'scheduled_departure': order.departure_time,
            'actual_completion': actual_completion,
            'delay': actual_completion - order.departure_time,
            'pallets': order.pallets
        })
    
    def record_order_completion(self, order):
        self.completed_orders.append({
            'order_id': order.id,
            'pallets': order.pallets,
            'order_time': order.order_time,
            'completion_time': order.completion_time,
            'departure_time': order.departure_time,
            'has_time_constraint': order.has_time_constraint,
            'region': order.region,  # 添加地区信息
            'on_time': order.completion_time <= order.departure_time if order.has_time_constraint else True
        })
    
    def record_inbound_operation(self, category, pallets, start_time, end_time, from_buffer):
        self.inbound_operations.append({
            'category': category,
            'pallets': pallets,
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'from_buffer': from_buffer,
            'order_count': 1  # 每个inbound operation对应一个订单
        })
    
    def record_outbound_operation(self, truck):
        self.outbound_operations.append({
            'category': truck.category,
            'pallets': truck.pallets,
            'scheduled_time': truck.scheduled_time,
            'start_time': truck.service_start_time,
            'end_time': truck.service_end_time,
            'region': truck.region,  # 添加地区信息（仅FG）
            'order_count': 1  # 每个truck代表一个订单
        })
    
    def record_buffer_occupancy(self, hour, category, occupancy_rate):
        self.hourly_buffer_occupancy[category].append({
            'hour': hour,
            'occupancy_rate': occupancy_rate
        })
    
    def record_midnight_backlog(self, day, pending_orders_count, pending_pallets):
        self.midnight_backlogs.append({
            'day': day,
            'pending_orders': pending_orders_count,
            'pending_pallets': pending_pallets
        })
    
    def record_outbound_truck(self, order_data):
        """记录Outbound订单完成（新逻辑）"""
        self.outbound_operations.append({
            'category': order_data['category'],
            'pallets': order_data['pallets'],
            'region': order_data['region'],
            'on_time': order_data['on_time'],
            'delay_hours': order_data.get('delay_hours', 0),
            'service_time': order_data['service_time'],
            'completion_time': order_data['completion_time'],
            'order_count': 1
        })
    
    def record_inbound_truck(self, order_data):
        """记录Inbound订单完成（新逻辑）"""
        self.inbound_operations.append({
            'category': order_data['category'],
            'pallets': order_data['pallets'],
            'arrival_time': order_data['arrival_time'],
            'processing_time': order_data['processing_time'],
            'missed_deadline': order_data.get('missed_deadline', False),
            'order_count': 1,
            'from_buffer': False  # 新逻辑中无buffer
        })
    
    def generate_summary(self, adjusted_fte=None):
        """生成汇总报告
        
        Args:
            adjusted_fte: 场景调整后的FTE配置 {'FG': {'Inbound': x, 'Outbound': y}, 'R&P': ...}
        """
        summary = {}
        
        summary['buffer_overflow_events'] = len(self.buffer_overflows)
        summary['total_overflow_pallets'] = sum(e['pallets'] for e in self.buffer_overflows)
        
        if self.truck_wait_times:
            wait_times = [w['wait_time'] for w in self.truck_wait_times]
            summary['avg_truck_wait_time'] = np.mean(wait_times)
            summary['max_truck_wait_time'] = np.max(wait_times)
            summary['p95_truck_wait_time'] = np.percentile(wait_times, 95)
        else:
            summary['avg_truck_wait_time'] = 0
            summary['max_truck_wait_time'] = 0
            summary['p95_truck_wait_time'] = 0
        
        # 按地区统计准时率（FG Outbound）
        fg_outbound_completed = [o for o in self.outbound_operations if o['category'] == 'FG']
        for region in ['G2', 'ROW']:
            # 匹配region前缀（G2_same_day, G2_next_day, ROW_next_day都应该匹配）
            region_orders = [o for o in fg_outbound_completed 
                            if o.get('region', '').startswith(region)]
            if region_orders:
                region_on_time = sum(1 for o in region_orders if o['on_time'])
                summary[f'{region}_on_time_rate'] = region_on_time / len(region_orders)
                summary[f'{region}_total_orders'] = len(region_orders)
            else:
                summary[f'{region}_on_time_rate'] = 0.0
                summary[f'{region}_total_orders'] = 0
        
        # Inbound 24h 延期统计
        if self.inbound_delays:
            summary['total_inbound_delays'] = len(self.inbound_delays)
            summary['total_delayed_pallets'] = sum(d['pallets'] for d in self.inbound_delays)
            summary['avg_inbound_delay_hours'] = np.mean([d['delay_hours'] for d in self.inbound_delays])
            summary['max_inbound_delay_hours'] = max([d['delay_hours'] for d in self.inbound_delays])
            fg_delays = [d for d in self.inbound_delays if d['category'] == 'FG']
            rp_delays = [d for d in self.inbound_delays if d['category'] == 'R&P']
            summary['fg_inbound_delays'] = len(fg_delays)
            summary['rp_inbound_delays'] = len(rp_delays)
        else:
            summary['total_inbound_delays'] = 0
            summary['total_delayed_pallets'] = 0
            summary['avg_inbound_delay_hours'] = 0
            summary['max_inbound_delay_hours'] = 0
            summary['fg_inbound_delays'] = 0
            summary['rp_inbound_delays'] = 0
        
        # 午夜积压统计
        if self.midnight_backlogs:
            summary['avg_midnight_backlog_orders'] = np.mean([b['pending_orders'] for b in self.midnight_backlogs])
            summary['avg_midnight_backlog_pallets'] = np.mean([b['pending_pallets'] for b in self.midnight_backlogs])
            summary['max_midnight_backlog_pallets'] = max([b['pending_pallets'] for b in self.midnight_backlogs])
        else:
            summary['avg_midnight_backlog_orders'] = 0
            summary['avg_midnight_backlog_pallets'] = 0
            summary['max_midnight_backlog_pallets'] = 0
        
        # 流量统计（托盘和订单）
        summary['total_inbound_pallets'] = sum(o['pallets'] for o in self.inbound_operations)
        summary['total_outbound_pallets'] = sum(o['pallets'] for o in self.outbound_operations)
        summary['total_inbound_orders'] = sum(o.get('order_count', 1) for o in self.inbound_operations)
        summary['total_outbound_orders'] = sum(o.get('order_count', 1) for o in self.outbound_operations)
        
        for category in ['FG', 'R&P']:
            inbound_cat = [o for o in self.inbound_operations if o['category'] == category]
            outbound_cat = [o for o in self.outbound_operations if o['category'] == category]
            summary[f'{category}_inbound_pallets'] = sum(o['pallets'] for o in inbound_cat)
            summary[f'{category}_outbound_pallets'] = sum(o['pallets'] for o in outbound_cat)
            summary[f'{category}_inbound_orders'] = sum(o.get('order_count', 1) for o in inbound_cat)
            summary[f'{category}_outbound_orders'] = sum(o.get('order_count', 1) for o in outbound_cat)
        
        # 按地区统计 FG 出库
        fg_outbound = [o for o in self.outbound_operations if o['category'] == 'FG']
        for region in ['G2', 'ROW']:
            # 匹配region前缀（G2_same_day, G2_next_day, ROW_next_day都应该匹配）
            fg_region = [o for o in fg_outbound if o.get('region', '').startswith(region)]
            summary[f'FG_{region}_outbound_pallets'] = sum(o['pallets'] for o in fg_region)
            summary[f'FG_{region}_outbound_orders'] = sum(o.get('order_count', 1) for o in fg_region)
        
        # ========== FTE利用率统计（简化版）==========
        # 逻辑很简单：
        # 1. 统计一个月处理了多少托盘（分FG和R&P）
        # 2. 根据FTE效率算出需要多少FTE
        # 3. 和场景调整后的可用FTE比较
        
        # FTE效率（托盘/FTE/月）- 考虑alpha效应
        base_efficiency = {'FG': 665.43, 'R&P': 1308.83}
        
        # 从配置中计算alpha效应（通过analyze_results方法参数传递）
        if hasattr(self, 'alpha_config') and self.alpha_config:
            alpha = self.alpha_config.get('alpha', 1.0)
            baseline_hours = self.alpha_config.get('baseline_hours', 18)
            operating_hours = self.alpha_config.get('operating_hours', 18)
            
            if baseline_hours > 0 and operating_hours > 0:
                r = operating_hours / baseline_hours
                efficiency_multiplier = (r ** (alpha - 1.0)) if (alpha != 1.0) else 1.0
            else:
                efficiency_multiplier = 1.0
                
            # 使用调整后的效率（考虑alpha效应）
            FTE_EFFICIENCY = {
                'FG': base_efficiency['FG'] * efficiency_multiplier,
                'R&P': base_efficiency['R&P'] * efficiency_multiplier
            }
        else:
            # 默认效率
            FTE_EFFICIENCY = base_efficiency
        
        # 使用仿真实例中的FTEManager调整后的FTE配置（包含alpha效应）
        if hasattr(self, 'fte_manager') and self.fte_manager:
            FTE_AVAILABLE = {
                'FG_inbound': self.fte_manager.adjusted_fte['FG']['Inbound'],
                'FG_outbound': self.fte_manager.adjusted_fte['FG']['Outbound'],
                'R&P_inbound': self.fte_manager.adjusted_fte['R&P']['Inbound'],
                'R&P_outbound': self.fte_manager.adjusted_fte['R&P']['Outbound']
            }
        # 使用场景调整后的FTE配置（如果传入），否则用全局配置
        elif adjusted_fte:
            FTE_AVAILABLE = {
                'FG_inbound': adjusted_fte['FG']['Inbound'],
                'FG_outbound': adjusted_fte['FG']['Outbound'],
                'R&P_inbound': adjusted_fte['R&P']['Inbound'],
                'R&P_outbound': adjusted_fte['R&P']['Outbound']
            }
        elif LOADED_CONFIG and 'fte_config' in LOADED_CONFIG:
            fte_cfg = LOADED_CONFIG['fte_config']
            FTE_AVAILABLE = {
                'FG_inbound': fte_cfg['FG']['Inbound'],
                'FG_outbound': fte_cfg['FG']['Outbound'],
                'R&P_inbound': fte_cfg['R&P']['Inbound'],
                'R&P_outbound': fte_cfg['R&P']['Outbound']
            }
        else:
            # 默认配置
            FTE_AVAILABLE = {
                'FG_inbound': 44.75, 'FG_outbound': 44.75,
                'R&P_inbound': 10.025, 'R&P_outbound': 10.025
            }
        
        # 从已记录的操作中统计托盘数
        fg_inbound_pallets = sum(o['pallets'] for o in self.inbound_operations if o['category'] == 'FG')
        fg_outbound_pallets = sum(o['pallets'] for o in self.outbound_operations if o['category'] == 'FG')
        rp_inbound_pallets = sum(o['pallets'] for o in self.inbound_operations if o['category'] == 'R&P')
        rp_outbound_pallets = sum(o['pallets'] for o in self.outbound_operations if o['category'] == 'R&P')
        
        # 理论需求FTE = 托盘数 / 效率（如果要按标准效率完成这些工作，理论上需要多少FTE）
        fg_inbound_fte_needed = fg_inbound_pallets / FTE_EFFICIENCY['FG']
        fg_outbound_fte_needed = fg_outbound_pallets / FTE_EFFICIENCY['FG']
        rp_inbound_fte_needed = rp_inbound_pallets / FTE_EFFICIENCY['R&P']
        rp_outbound_fte_needed = rp_outbound_pallets / FTE_EFFICIENCY['R&P']
        
        # 实际使用FTE = min(需求, 可用) — FTE是硬限制，不可能超过配置人数
        fg_inbound_fte_used = min(fg_inbound_fte_needed, FTE_AVAILABLE['FG_inbound'])
        fg_outbound_fte_used = min(fg_outbound_fte_needed, FTE_AVAILABLE['FG_outbound'])
        rp_inbound_fte_used = min(rp_inbound_fte_needed, FTE_AVAILABLE['R&P_inbound'])
        rp_outbound_fte_used = min(rp_outbound_fte_needed, FTE_AVAILABLE['R&P_outbound'])
        
        # 利用率 = 实际使用 / 可用（最高100%）
        summary['FG_inbound_fte_utilization_rate'] = fg_inbound_fte_used / FTE_AVAILABLE['FG_inbound'] if FTE_AVAILABLE['FG_inbound'] > 0 else 0
        summary['FG_outbound_fte_utilization_rate'] = fg_outbound_fte_used / FTE_AVAILABLE['FG_outbound'] if FTE_AVAILABLE['FG_outbound'] > 0 else 0
        summary['R&P_inbound_fte_utilization_rate'] = rp_inbound_fte_used / FTE_AVAILABLE['R&P_inbound'] if FTE_AVAILABLE['R&P_inbound'] > 0 else 0
        summary['R&P_outbound_fte_utilization_rate'] = rp_outbound_fte_used / FTE_AVAILABLE['R&P_outbound'] if FTE_AVAILABLE['R&P_outbound'] > 0 else 0
        
        # 保存详细数据
        summary['FG_inbound_fte_needed'] = fg_inbound_fte_needed
        summary['FG_outbound_fte_needed'] = fg_outbound_fte_needed
        summary['R&P_inbound_fte_needed'] = rp_inbound_fte_needed
        summary['R&P_outbound_fte_needed'] = rp_outbound_fte_needed
        
        summary['FG_inbound_fte_used'] = fg_inbound_fte_used
        summary['FG_outbound_fte_used'] = fg_outbound_fte_used
        summary['R&P_inbound_fte_used'] = rp_inbound_fte_used
        summary['R&P_outbound_fte_used'] = rp_outbound_fte_used
        
        summary['FG_inbound_fte_available'] = FTE_AVAILABLE['FG_inbound']
        summary['FG_outbound_fte_available'] = FTE_AVAILABLE['FG_outbound']
        summary['R&P_inbound_fte_available'] = FTE_AVAILABLE['R&P_inbound']
        summary['R&P_outbound_fte_available'] = FTE_AVAILABLE['R&P_outbound']
        
        # 整体FTE统计
        total_fte_needed = fg_inbound_fte_needed + fg_outbound_fte_needed + rp_inbound_fte_needed + rp_outbound_fte_needed
        total_fte_used = fg_inbound_fte_used + fg_outbound_fte_used + rp_inbound_fte_used + rp_outbound_fte_used
        total_fte_available = FTE_AVAILABLE['FG_inbound'] + FTE_AVAILABLE['FG_outbound'] + FTE_AVAILABLE['R&P_inbound'] + FTE_AVAILABLE['R&P_outbound']
        
        summary['overall_fte_utilization_rate'] = total_fte_used / total_fte_available if total_fte_available > 0 else 0
        summary['total_fte_needed'] = total_fte_needed
        summary['total_fte_used'] = total_fte_used
        summary['total_fte_available'] = total_fte_available
        
        # 缓冲区平均占用率
        for category in ['R&P', 'FG']:
            if category in self.hourly_buffer_occupancy:
                occupancy_rates = [o['occupancy_rate'] for o in self.hourly_buffer_occupancy[category]]
                summary[f'{category.lower()}_avg_buffer_occupancy'] = np.mean(occupancy_rates)
            else:
                summary[f'{category.lower()}_avg_buffer_occupancy'] = 0
        
        # Timeslot利用率统计（新增）
        if self.dock_usage:
            df_usage = pd.DataFrame(self.dock_usage)

            # 总体利用率（加权口径）：sum(used) / sum(available)
            total_available = df_usage['available'].sum()
            total_used = df_usage['used'].sum()
            summary['avg_dock_utilization'] = (total_used / total_available) if total_available > 0 else 0
            
            # 按小时统计利用率（保留hourly数据用于可视化，包含used和available原始数值）
            hourly_utilization = {}
            for category in ['FG', 'R&P']:
                for direction in ['inbound', 'outbound']:
                    dock_type = 'reception' if direction == 'inbound' else 'loading'
                    key = f'{category}_{direction}'
                    
                    # 筛选对应的数据
                    filtered_data = df_usage[(df_usage['category'] == category) & 
                                            (df_usage['dock_type'] == dock_type)]
                    
                    if len(filtered_data) > 0:
                        # 按小时分组，计算平均used和available（以及utilization）
                        hourly_stats = {}
                        for hour in sorted(filtered_data['hour'].unique()):
                            hour_data = filtered_data[filtered_data['hour'] == hour]
                            hourly_stats[hour] = {
                                'utilization': hour_data['utilization'].mean(),
                                'used': hour_data['used'].mean(),
                                'available': hour_data['available'].mean()
                            }
                        hourly_utilization[key] = hourly_stats
                    else:
                        hourly_utilization[key] = {}
            
            summary['hourly_dock_utilization'] = hourly_utilization
            
            # 按码头类型统计
            for dock_type in ['loading', 'reception']:
                type_data = df_usage[df_usage['dock_type'] == dock_type]
                if len(type_data) > 0:
                    type_avail = type_data['available'].sum()
                    type_used = type_data['used'].sum()
                    summary[f'{dock_type}_avg_utilization'] = (type_used / type_avail) if type_avail > 0 else 0
                    summary[f'{dock_type}_peak_utilization'] = type_data['utilization'].max()
                else:
                    summary[f'{dock_type}_avg_utilization'] = 0
                    summary[f'{dock_type}_peak_utilization'] = 0
            
            # 按类别统计
            for category in ['FG', 'R&P']:
                cat_data = df_usage[df_usage['category'] == category]
                if len(cat_data) > 0:
                    cat_avail = cat_data['available'].sum()
                    cat_used = cat_data['used'].sum()
                    summary[f'{category}_dock_avg_utilization'] = (cat_used / cat_avail) if cat_avail > 0 else 0
                else:
                    summary[f'{category}_dock_avg_utilization'] = 0
            
            # 按类别和方向统计（FG/R&P × Inbound/Outbound）
            for category in ['FG', 'R&P']:
                # Inbound = Reception码头
                inbound_data = df_usage[(df_usage['category'] == category) & (df_usage['dock_type'] == 'reception')]
                if len(inbound_data) > 0:
                    in_avail = inbound_data['available'].sum()
                    in_used = inbound_data['used'].sum()
                    summary[f'{category}_inbound_utilization'] = (in_used / in_avail) if in_avail > 0 else 0
                else:
                    summary[f'{category}_inbound_utilization'] = 0
                
                # Outbound = Loading码头
                outbound_data = df_usage[(df_usage['category'] == category) & (df_usage['dock_type'] == 'loading')]
                if len(outbound_data) > 0:
                    out_avail = outbound_data['available'].sum()
                    out_used = outbound_data['used'].sum()
                    summary[f'{category}_outbound_utilization'] = (out_used / out_avail) if out_avail > 0 else 0
                else:
                    summary[f'{category}_outbound_utilization'] = 0
        else:
            summary['avg_dock_utilization'] = 0
            summary['hourly_dock_utilization'] = {}
            summary['loading_avg_utilization'] = 0
            summary['loading_peak_utilization'] = 0
            summary['reception_avg_utilization'] = 0
            summary['reception_peak_utilization'] = 0
            summary['FG_dock_avg_utilization'] = 0
            summary['R&P_dock_avg_utilization'] = 0
            summary['FG_inbound_utilization'] = 0
            summary['FG_outbound_utilization'] = 0
            summary['R&P_inbound_utilization'] = 0
            summary['R&P_outbound_utilization'] = 0
        
        return summary
    
    def export_to_excel(self, filename):
        """导出详细数据到 Excel"""
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 确保至少有一个sheet - 创建汇总表
            summary = self.generate_summary()
            summary_df = pd.DataFrame([summary])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # 其他详细数据（如果有）
            if self.buffer_overflows:
                pd.DataFrame(self.buffer_overflows).to_excel(writer, sheet_name='Buffer_Overflows', index=False)
            if self.truck_wait_times:
                pd.DataFrame(self.truck_wait_times).to_excel(writer, sheet_name='Truck_Wait_Times', index=False)
            if self.sla_misses:
                pd.DataFrame(self.sla_misses).to_excel(writer, sheet_name='SLA_Misses', index=False)
            if self.completed_orders:
                pd.DataFrame(self.completed_orders).to_excel(writer, sheet_name='Completed_Orders', index=False)
            if self.midnight_backlogs:
                pd.DataFrame(self.midnight_backlogs).to_excel(writer, sheet_name='Midnight_Backlogs', index=False)
            if self.fte_usage:
                pd.DataFrame(self.fte_usage).to_excel(writer, sheet_name='FTE_Usage', index=False)
                
                # 创建FTE汇总统计表
                fte_summary_data = []
                fte_summary_data.append({'Metric': 'Overall FTE Utilization Rate', 'Value': summary.get('overall_fte_utilization_rate', 0)})
                
                for category in ['FG', 'R&P']:
                    for direction in ['Inbound', 'Outbound']:
                        prefix = f'{category.lower()}_{direction.lower()}'
                        fte_summary_data.append({
                            'Metric': f'{category} {direction} FTE Utilization Rate',
                            'Value': summary.get(f'{prefix}_fte_utilization_rate', 0)
                        })
                        fte_summary_data.append({
                            'Metric': f'{category} {direction} Total FTE Used',
                            'Value': summary.get(f'{prefix}_total_fte_used', 0)
                        })
                        fte_summary_data.append({
                            'Metric': f'{category} {direction} Total Pallets Processed',
                            'Value': summary.get(f'{prefix}_total_pallets_processed', 0)
                        })
                        fte_summary_data.append({
                            'Metric': f'{category} {direction} Average Efficiency (pallets/hour)',
                            'Value': summary.get(f'{prefix}_avg_efficiency', 0)
                        })
                
                # 总体统计
                total_fte_used = sum(f['fte_used'] for f in self.fte_usage)
                
                # 正确的总可用FTE计算
                unique_fte_configs = {}
                for f in self.fte_usage:
                    key = f"{f['category']}_{f['direction']}"
                    if key not in unique_fte_configs:
                        unique_fte_configs[key] = f['available_fte']
                total_fte_available = sum(unique_fte_configs.values())
                
                total_pallets = sum(f['pallets_processed'] for f in self.fte_usage)
                
                fte_summary_data.append({'Metric': 'Total FTE Used', 'Value': total_fte_used})
                fte_summary_data.append({'Metric': 'Total FTE Available (Configured)', 'Value': total_fte_available})
                fte_summary_data.append({'Metric': 'Total Pallets Processed', 'Value': total_pallets})
                fte_summary_data.append({'Metric': 'Overall FTE Utilization Rate', 'Value': total_fte_used / total_fte_available if total_fte_available > 0 else 0})
                
                fte_summary_df = pd.DataFrame(fte_summary_data)
                fte_summary_df.to_excel(writer, sheet_name='FTE_Summary', index=False)
            if self.dock_usage:
                pd.DataFrame(self.dock_usage).to_excel(writer, sheet_name='Dock_Usage', index=False)
            if self.inbound_operations:
                pd.DataFrame(self.inbound_operations).to_excel(writer, sheet_name='Inbound_Operations', index=False)
            if self.outbound_operations:
                pd.DataFrame(self.outbound_operations).to_excel(writer, sheet_name='Outbound_Operations', index=False)


# ==================== 订单流程追踪器 ====================

class OrderTracker:
    """订单全流程追踪器 - 记录每个订单从生成到完成的完整事件日志
    
    用于演示/展示时详细展示单个订单的生命周期。
    """
    
    def __init__(self, enabled=False, track_order_ids=None):
        """
        Args:
            enabled: 是否启用追踪
            track_order_ids: 要追踪的订单ID列表（None=追踪所有订单）
        """
        self.enabled = enabled
        self.track_order_ids = set(track_order_ids) if track_order_ids else None
        self.event_log = []  # 详细事件日志
        self.order_summary = {}  # 每个订单的关键时间戳汇总
    
    def _should_track(self, order):
        """判断是否需要追踪该订单"""
        if not self.enabled:
            return False
        if self.track_order_ids is None:
            return True
        return order.order_id in self.track_order_ids
    
    def _sim_time_to_str(self, sim_time):
        """将仿真时间（小时）转换为可读字符串 Day X, HH:00"""
        if sim_time is None:
            return 'N/A'
        day = int(sim_time) // 24 + 1
        hour = int(sim_time) % 24
        minute = int((sim_time % 1) * 60)
        return f'Day {day}, {hour:02d}:{minute:02d}'
    
    def log_event(self, order, event_type, sim_time, details='', **extra):
        """记录一个追踪事件"""
        if not self._should_track(order):
            return
        
        event = {
            'order_id': order.order_id,
            'category': order.category,
            'direction': order.direction,
            'event_type': event_type,
            'sim_time_h': round(sim_time, 3),
            'readable_time': self._sim_time_to_str(sim_time),
            'details': details,
        }
        event.update(extra)
        self.event_log.append(event)
        
        # 初始化汇总记录
        oid = order.order_id
        if oid not in self.order_summary:
            self.order_summary[oid] = {
                'order_id': oid,
                'category': order.category,
                'direction': order.direction,
                'pallets': order.pallets,
                'region': getattr(order, 'region', None),
            }
        
        # 更新汇总时间戳
        ts_key = event_type.lower().replace(' ', '_')
        self.order_summary[oid][f'{ts_key}_time'] = round(sim_time, 3)
        self.order_summary[oid][f'{ts_key}_readable'] = self._sim_time_to_str(sim_time)
    
    def finalize_order(self, order, sim_time):
        """订单完成时的最终汇总"""
        if not self._should_track(order):
            return
        oid = order.order_id
        if oid in self.order_summary:
            s = self.order_summary[oid]
            s['completed'] = order.completed
            s['on_time'] = getattr(order, 'on_time', None)
            s['delay_hours'] = getattr(order, 'delay_hours', 0)
            s['actual_timeslot'] = getattr(order, 'actual_timeslot', None)
            s['scheduled_timeslot'] = int(order.timeslot_time) if order.timeslot_time is not None else None
            s['final_time'] = round(sim_time, 3)
            s['final_readable'] = self._sim_time_to_str(sim_time)
    
    def export_to_excel(self, filepath):
        """导出追踪日志到Excel"""
        if not self.event_log:
            print('OrderTracker: 无事件日志可导出')
            return
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Sheet 1: 订单汇总概览
            summary_df = pd.DataFrame(list(self.order_summary.values()))
            if not summary_df.empty:
                summary_df.to_excel(writer, sheet_name='Order_Summary', index=False)
            
            # Sheet 2: 完整事件日志
            log_df = pd.DataFrame(self.event_log)
            log_df.to_excel(writer, sheet_name='Event_Log', index=False)
            
            # Sheet 3: 单个订单详细叙事（取第一个追踪的订单作为示例）
            if self.event_log:
                example_id = self.event_log[0]['order_id']
                example_events = [e for e in self.event_log if e['order_id'] == example_id]
                example_df = pd.DataFrame(example_events)
                example_df.to_excel(writer, sheet_name='Example_Order_Detail', index=False)
                
                # Sheet 4: 叙述性描述
                narrative = self._generate_narrative(example_id)
                narrative_df = pd.DataFrame({'Order Flow Narrative': narrative})
                narrative_df.to_excel(writer, sheet_name='Example_Narrative', index=False)
        
        print(f'OrderTracker: 日志已导出到 {filepath}')
        print(f'  - 追踪订单数: {len(self.order_summary)}')
        print(f'  - 总事件数: {len(self.event_log)}')
    
    def _generate_narrative(self, order_id):
        """为单个订单生成叙述性流程描述"""
        events = [e for e in self.event_log if e['order_id'] == order_id]
        if not events:
            return ['No events found']
        
        summary = self.order_summary.get(order_id, {})
        narrative = []
        narrative.append(f'=== Order Flow Narrative: {order_id} ===')
        narrative.append(f'Category: {summary.get("category", "?")} | Direction: {summary.get("direction", "?")} | Pallets: {summary.get("pallets", "?")} | Region: {summary.get("region", "N/A")}')
        narrative.append('')
        
        step = 1
        for e in events:
            line = f'Step {step}: [{e["readable_time"]}] {e["event_type"]} - {e["details"]}'
            narrative.append(line)
            step += 1
        
        narrative.append('')
        if summary.get('on_time') is True:
            narrative.append(f'✅ Result: Order completed ON TIME')
        elif summary.get('on_time') is False:
            narrative.append(f'⚠️ Result: Order DELAYED by {summary.get("delay_hours", 0)} hours')
        else:
            narrative.append(f'Result: {"Completed" if summary.get("completed") else "Incomplete"}')
        
        return narrative


# ==================== 主仿真类 ====================

class DCSimulation:
    """配送中心仿真主控制器"""
    
    def __init__(self, env, scenario_config, run_id=1, order_tracker=None):
        self.env = env
        self.config = scenario_config
        self.dc_config = self.config
        self.run_id = run_id
        self._init_resources()
        # 传递营业时间给KPICollector
        operating_hours = scenario_config.get('operating_hours', 18)
        self.kpi = KPICollector(operating_hours=operating_hours)
        self.orders = self._load_orders()
        self.pending_orders = []
        # 订单追踪器（可选）
        self.order_tracker = order_tracker if order_tracker else OrderTracker(enabled=False)
        # Opening hour coefficient（可手动调节）
        self.opening_hour_coefficient = scenario_config.get('opening_hour_coefficient', 
                                                             SYSTEM_PARAMETERS.get('opening_hour_coefficient', 1.0))
        
        # 如果启用到达平滑化，计算优化后的到达率
        if self.config.get('arrival_smoothing', False):
            self.arrival_rates = self._smooth_arrival_rates(self.config)
        else:
            self.arrival_rates = SYSTEM_PARAMETERS.get('truck_arrival_rates_outbound', 
                                                       SYSTEM_PARAMETERS.get('truck_arrival_rates', {}))
        
        print(f"初始化仿真: {scenario_config['name']}")
        print(f"  运营时间: {scenario_config['dc_open_time']:02d}:00 - {scenario_config['dc_close_time']:02d}:00")
        print(f"  运营小时数: {scenario_config['operating_hours']} 小时/天")
        print(f"  Opening Hour Coefficient: {self.opening_hour_coefficient}")

        rule = scenario_config.get('biweekly_shift_cancel')
        if isinstance(rule, dict):
            cancel_start = int(rule.get('cancel_start_hour', 15))
            cancel_end = int(rule.get('cancel_end_hour', scenario_config.get('dc_close_time', 24)))
            start_week_index = int(rule.get('start_week_index', 1))
            print(f"  例外关门: 每两周周五 {cancel_start:02d}:00-{cancel_end:02d}:00 关闭（从第{start_week_index + 1}个周五开始）")
        
        # 打印订单加载情况
        if self.orders:
            total_orders = sum(len(orders) for orders in self.orders.values())
            print(f"  已加载订单: {total_orders} 个")
        
        # 打印FTE配置信息  
        print(f"  FTE调整比例: {self.fte_manager.operating_ratio:.1%}")
        print(f"  成本节约预期: {self.fte_manager.get_cost_savings():.1%}")
        print(f"\n调整后的FTE配置:")
        for category in ['FG', 'R&P']:
            for direction in ['Inbound', 'Outbound']:
                fte = self.fte_manager.adjusted_fte[category][direction]
                capacity = self.fte_manager.get_hourly_capacity(category, direction)
                daily_cap = capacity * scenario_config['operating_hours']
                print(f"  {category} {direction}: {fte:.2f} FTE → {capacity:.1f} pallet/h ({daily_cap:.0f} pallet/天)")
        
        if self.config.get('arrival_smoothing', False):
            print(f"  到达优化: 已启用（平滑高峰流量）")
    
    def _load_orders(self):
        """加载预生成的订单数据"""
        orders_path = SYSTEM_PARAMETERS.get('generated_orders_path')
        
        if not orders_path:
            print("警告: 未找到订单数据路径，将使用旧的动态生成逻辑")
            return None
        
        try:
            import json
            from pathlib import Path
            
            # 处理相对路径
            if not Path(orders_path).is_absolute():
                orders_path = Path(__file__).parent.parent / orders_path
            else:
                orders_path = Path(orders_path)
            
            if not orders_path.exists():
                print(f"警告: 订单文件不存在: {orders_path}")
                return None

            with open(orders_path, 'r', encoding='utf-8') as f:
                orders_data = json.load(f)

            # 转换为Order对象，按category+direction分组
            orders_dict = {}
            for key, order_list in orders_data.items():
                orders_dict[key] = [Order(order_data) for order_data in order_list]

                # 计算绝对仿真时间
                for order in orders_dict[key]:
                    # 仿真从 day=1 的 00:00 开始 -> time=0
                    base_time = (order.day - 1) * 24

                    # Outbound: 计算creation_time
                    if order.direction == 'Outbound':
                        # creation_hour可能是负数（表示前一天）
                        if order.creation_hour < 0:
                            # 例如：day=2, creation_hour=-24 → 第1天0点
                            order.creation_time = base_time + order.creation_hour
                        else:
                            # 例如：day=2, creation_hour=10 → 第2天10点
                            order.creation_time = base_time + order.creation_hour

                    # 计算timeslot_time
                    if order.timeslot_hour is not None:
                        order.timeslot_time = base_time + order.timeslot_hour
            
            print(f"✓ 订单数据加载成功: {len(orders_dict)} 个月度分组")
            return orders_dict
            
        except Exception as e:
            print(f"错误: 加载订单数据失败 - {e}")
            import traceback
            traceback.print_exc()
            return None

    def _init_resources(self):
        """初始化仿真资源（Timeslot预约系统）"""
        # Timeslot配置：每小时可预约的slot数量
        hourly_config = SYSTEM_PARAMETERS['hourly_dock_capacity']
        
        # 当前小时的可用timeslot数量（每小时动态更新）
        self.hourly_timeslot_capacity = {
            'fg_reception': 0,
            'fg_loading': 0,
            'rp_reception': 0,
            'rp_loading': 0
        }
        
        # 当前小时已使用的timeslot计数器（每小时重置）
        self.hourly_timeslot_used = {
            'fg_reception': 0,
            'fg_loading': 0,
            'rp_reception': 0,
            'rp_loading': 0
        }
        
        # 记录当前小时（用于检测小时变化）
        self.current_hour = -1
        
        # 启动timeslot容量更新和重置进程
        self.env.process(self.timeslot_capacity_manager())
        
        # 人力资源管理器（传入operating_hours以调整FTE）
        operating_hours = self.config['operating_hours']

        # Scenario A: FTE hourly efficiency follows a power-law with operating hours
        # - baseline hours H0 defaults to 18
        # - alpha=1.0 keeps original behavior
        alpha = float(self.config.get('fte_efficiency_alpha', 1.0))
        baseline_hours = float(self.config.get('fte_efficiency_baseline_hours', 18))
        if baseline_hours > 0 and operating_hours > 0:
            r = operating_hours / baseline_hours
        else:
            r = 1.0
        efficiency_multiplier = (r ** (alpha - 1.0)) if (alpha != 1.0) else 1.0

        self.fte_manager = FTEManager(
            operating_hours=operating_hours,
            efficiency_multiplier=efficiency_multiplier,
            fte_adjustment_ratio=self.config.get('fte_adjustment_ratio')
        )
    
    def _smooth_arrival_rates(self, dc_config):
        """
        根据DC运营时间动态平滑到达率：限制高峰流量，分散到非高峰时段
        
        策略：
        - FG高峰（10-13点）：从3.15降至1.75（服务能力）
        - 超出部分**仅分配到DC开放时段内的低谷时段**
        - R&P保持不变（无明显瓶颈）
        """
        original_rates = SYSTEM_PARAMETERS.get('truck_arrival_rates_outbound',
                                               SYSTEM_PARAMETERS.get('truck_arrival_rates', {}))
        smoothed_rates = {
            'FG': {},
            'R&P': {}
        }
        
        # R&P保持不变
        smoothed_rates['R&P'] = original_rates['R&P'].copy()
        
        # FG平滑化
        fg_rates = original_rates['FG'].copy()
        
        # 识别高峰时段
        peak_hours = [10, 11, 12, 13]  # 10-13点（高峰拥堵）
        
        # **根据DC运营时间确定可转移的低谷时段**
        dc_open = dc_config['dc_open_time']
        dc_close = dc_config['dc_close_time']
        
        # 候选低谷时段：DC开放时间内，且到达率<2.0的时段
        candidate_hours = []
        for hour in range(dc_open, dc_close):
            if hour in fg_rates and hour not in peak_hours:
                # 排除已经接近高峰的时段（>2.0）和接近关门前2小时的时段
                if fg_rates[hour] < 2.0 and hour < dc_close - 2:
                    candidate_hours.append(hour)
        
        # 如果没有合适的候选时段，则不进行平滑
        if not candidate_hours:
            print("\n警告：当前运营时间内没有合适的低谷时段用于流量转移")
            print(f"   运营时间: {dc_open}:00-{dc_close}:00")
            print("   建议：延长运营时间或不启用到达优化")
            return original_rates
        
        # 服务能力：1.75辆/小时
        service_capacity = 1.75
        
        # 计算高峰超出量
        total_excess = 0
        for hour in peak_hours:
            if hour in fg_rates and dc_open <= hour < dc_close:  # 仅处理DC开放时段的高峰
                if fg_rates[hour] > service_capacity:
                    excess = fg_rates[hour] - service_capacity
                    total_excess += excess
                    fg_rates[hour] = service_capacity
        
        # 将超出量**均匀**分配到候选低谷时段
        if total_excess > 0 and candidate_hours:
            per_hour_addition = total_excess / len(candidate_hours)
            for hour in candidate_hours:
                fg_rates[hour] += per_hour_addition
        
        smoothed_rates['FG'] = fg_rates
        
        # 打印优化效果
        print("\n=== 到达率优化（根据运营时间动态调整） ===")
        print(f"运营时间: {dc_open}:00-{dc_close}:00 ({dc_config['operating_hours']}小时)")
        print(f"候选低谷时段: {candidate_hours}")
        print(f"FG Loading 平滑化:")
        for hour in sorted(fg_rates.keys()):
            if dc_open <= hour < dc_close:  # 只显示运营时间内的调整
                orig = original_rates['FG'].get(hour, 0)
                smooth = fg_rates[hour]
                if abs(orig - smooth) > 0.01:
                    print(f"  {hour:02d}:00 - {orig:.2f} → {smooth:.2f} 辆/小时")
        
        return smoothed_rates
    
    def timeslot_capacity_manager(self):
        """Timeslot容量管理器：每小时更新容量并重置计数器"""
        hourly_config = SYSTEM_PARAMETERS['hourly_dock_capacity']
        
        while True:
            current_hour = int(self.env.now) % 24
            
            # 检测小时变化
            if current_hour != self.current_hour and self.current_hour >= 0:
                # 在重置之前，先记录上一小时的使用情况
                prev_hour = self.current_hour
                for category in ['FG', 'R&P']:
                    for dock_type in ['loading', 'reception']:
                        # 构建slot_key
                        if category == 'R&P':
                            slot_key = f'rp_{dock_type.lower()}'
                        else:
                            slot_key = f'{category.lower()}_{dock_type.lower()}'
                        
                        # 获取上一小时的配置容量和实际使用数
                        available = self.hourly_timeslot_capacity.get(slot_key, 0)
                        used = self.hourly_timeslot_used.get(slot_key, 0)
                        
                        # 记录到KPI
                        self.kpi.record_dock_usage(prev_hour, dock_type, category, used, available)
                
                # 然后重置所有类别的已使用计数器
                for key in self.hourly_timeslot_used:
                    self.hourly_timeslot_used[key] = 0
            
            # 更新当前小时标记
            self.current_hour = current_hour
            
            # 更新当前小时的timeslot容量配置
            if self.is_dc_open():
                # 从配置读取该小时的slot数量（支持字符串和整数键）
                self.hourly_timeslot_capacity['fg_loading'] = hourly_config['FG']['loading'].get(current_hour, hourly_config['FG']['loading'].get(str(current_hour), 0))
                self.hourly_timeslot_capacity['rp_loading'] = hourly_config['R&P']['loading'].get(current_hour, hourly_config['R&P']['loading'].get(str(current_hour), 0))
                self.hourly_timeslot_capacity['fg_reception'] = hourly_config['FG']['reception'].get(current_hour, hourly_config['FG']['reception'].get(str(current_hour), 0))
                self.hourly_timeslot_capacity['rp_reception'] = hourly_config['R&P']['reception'].get(current_hour, hourly_config['R&P']['reception'].get(str(current_hour), 0))
            else:
                # DC关闭，所有timeslot容量为0
                for key in self.hourly_timeslot_capacity:
                    self.hourly_timeslot_capacity[key] = 0
            
            # 等待到下一个小时
            next_hour = (int(self.env.now) // 1 + 1) * 1
            yield self.env.timeout(next_hour - self.env.now)
    
    def is_dc_open(self, time=None):
        """检查 DC 是否在运营时间内"""
        if time is None:
            time = self.env.now
        return _is_dc_open_at_time(time, self.config)

    def _next_open_time(self, time=None):
        """返回下一个开门时刻（绝对仿真时间，小时制）。"""
        if time is None:
            time = self.env.now

        if self.is_dc_open(time):
            return float(time)

        start_day = int(time) // 24
        for day_index in range(start_day, start_day + 60):
            windows = _compute_daily_open_windows(self.config, day_index)
            for a, b in windows:
                start_abs = day_index * 24 + a
                end_abs = day_index * 24 + b
                if time < start_abs:
                    return float(start_abs)
                if start_abs <= time < end_abs:
                    return float(time)

        return float(time)

    def _time_until_close(self, time=None):
        """返回距离本日关门还有多少小时（若已关门则返回0）。"""
        if time is None:
            time = self.env.now
        if not self.is_dc_open(time):
            return 0.0

        day_index = int(time) // 24
        hour_of_day = int(time) % 24
        day_start = day_index * 24
        for a, b in _compute_daily_open_windows(self.config, day_index):
            if a <= hour_of_day < b:
                close_abs = day_start + b
                return max(0.0, float(close_abs) - float(time))
        return 0.0
    
    # ==================== 优先级计算辅助方法 ====================
    
    def _calculate_prep_time(self, order):
        """计算订单的预估备货时间（小时）"""
        hourly_capacity = self.fte_manager.get_hourly_capacity(
            order.category,
            'Outbound',
            coefficient=self.opening_hour_coefficient
        )
        
        if hourly_capacity <= 0:
            return 999
        
        est_prep_time = order.pallets / hourly_capacity
        return est_prep_time
    
    def _calculate_latest_start_time(self, order):
        """计算订单的最晚备货开始时间 = timeslot_time - est_prep_time"""
        est_prep_time = self._calculate_prep_time(order)
        latest_start = order.timeslot_time - est_prep_time
        return latest_start
    
    # ==================== 新逻辑：订单驱动流程 ====================
    
    def outbound_order_scheduler(self, target_month=1):
        """Outbound订单调度器 - 动态优先级队列调度
        
        订单按creation_time逐步到达，FTE选择队列中优先级最高的订单处理。
        """
        import heapq
        
        if not self.orders:
            print("警告: 无订单数据，跳过Outbound订单调度")
            return
        
        # 收集该月的所有Outbound订单，按creation_time排序
        all_outbound_orders = []
        for key, orders_list in self.orders.items():
            if f'M{target_month:02d}' in key and 'Outbound' in key:
                all_outbound_orders.extend(orders_list)
        
        if not all_outbound_orders:
            print(f"警告: 月份{target_month}无Outbound订单")
            return
        
        # 按creation_time排序（确保按到达顺序处理）
        all_outbound_orders.sort(key=lambda o: o.creation_time)
        
        print(f"\n{'='*110}")
        print(f"Outbound订单调度 - 共 {len(all_outbound_orders)} 个订单")
        print(f"调度方式：动态优先级队列 (按creation_time逐步到达，FTE动态选择最优先级订单)")
        print(f"优先级规则：latest_start_time 越早 → 优先级越高（deadline越近越优先）")
        print(f"{'='*110}\n")
        
        ready_queue = []  # 优先级队列：(latest_start_time, order_id_for_tiebreak, order)
        order_index = 0   # 追踪下一个要到达的订单索引
        
        # 统计信息
        arrival_count = 0
        dispatch_count = 0
        
        # 启动调度主循环
        while order_index < len(all_outbound_orders) or ready_queue:
            # 1️⃣ 检查是否有订单到达
            while (order_index < len(all_outbound_orders) and 
                   all_outbound_orders[order_index].creation_time <= self.env.now):
                
                order = all_outbound_orders[order_index]
                latest_start = self._calculate_latest_start_time(order)
                est_prep = self._calculate_prep_time(order)
                
                # 加入优先级队列（使用order_index作为二级排序键避免heapq比较对象）
                heapq.heappush(ready_queue, 
                              (latest_start, order_index, order))
                
                arrival_count += 1
                
                # 日志：订单到达
                status = "⚠️超紧急" if latest_start < order.creation_time else "✓正常"
                # print(f"[时刻{self.env.now:7.1f}h] 订单到达: {order.order_id:8s} | "
                #       f"Category={order.category} | Pallets={order.pallets:3d} | "
                #       f"Est.Prep={est_prep:5.2f}h | Latest_Start={latest_start:7.1f}h | "
                #       f"Timeslot={order.timeslot_time:7.1f}h | 状态={status}")
                
                # 追踪：订单到达调度器
                self.order_tracker.log_event(
                    order, 'ORDER_ARRIVED', self.env.now,
                    f'Order enters scheduler queue. Pallets={order.pallets}, '
                    f'Region={order.region}, Timeslot={self.order_tracker._sim_time_to_str(order.timeslot_time)}, '
                    f'Est.Prep={est_prep:.2f}h, Latest_Start={self.order_tracker._sim_time_to_str(latest_start)}, '
                    f'Status={status}',
                    queue_size=len(ready_queue)
                )
                
                order_index += 1
            
            # 2️⃣ 从队列中选择优先级最高的订单（latest_start最早）
            if ready_queue:
                latest_start, _, order = heapq.heappop(ready_queue)
                dispatch_count += 1
                
                est_prep = self._calculate_prep_time(order)
                priority_rank = len(ready_queue) + 1  # 剩余队列中还有多少个比它优先级低
                
                # print(f"[时刻{self.env.now:7.1f}h] 开始处理: {order.order_id:8s} | "
                #       f"Latest_Start={latest_start:7.1f}h | Est.Prep={est_prep:5.2f}h | "
                #       f"队列剩余={len(ready_queue):3d} | 处理序号={dispatch_count}")
                
                # 追踪：订单从优先级队列中取出
                self.order_tracker.log_event(
                    order, 'DISPATCHED', self.env.now,
                    f'Dispatched from priority queue (#{dispatch_count}). '
                    f'Queue remaining={len(ready_queue)}, '
                    f'Latest_Start={self.order_tracker._sim_time_to_str(latest_start)}',
                    dispatch_rank=dispatch_count
                )
                
                # 启动备货和装货流程
                self.env.process(self.outbound_preparation_process(order))
                self.env.process(self.outbound_loading_process(order))
            
            else:
                # 队列为空，等待下一个订单到达
                if order_index < len(all_outbound_orders):
                    wait_time = all_outbound_orders[order_index].creation_time - self.env.now
                    if wait_time > 0:
                        yield self.env.timeout(wait_time)
                else:
                    # 所有订单都已处理，退出
                    break
        
        print(f"\n{'='*110}")
        print(f"Outbound订单调度完成!")
        print(f"  - 总订单数: {len(all_outbound_orders)}")
        print(f"  - 已到达订单: {arrival_count}")
        print(f"  - 已开始处理: {dispatch_count}")
        print(f"{'='*110}\n")
    
    def outbound_preparation_process(self, order):
        """Outbound备货流程（从creation_time开始）"""
        order.preparation_started = True
        order.processing_start_time = self.env.now
        total_pallets = order.pallets
        processed_pallets = 0

        # 追踪：备货开始
        self.order_tracker.log_event(
            order, 'PREP_START', self.env.now,
            f'Preparation started. Total pallets={total_pallets}, '
            f'DC open={self.is_dc_open()}, '
            f'Timeslot={self.order_tracker._sim_time_to_str(order.timeslot_time)}'
        )

        # 逐步处理直到完成或到达timeslot；仅在DC开门时推进备货
        _prep_loop_count = 0
        while processed_pallets < total_pallets:
            # 检查是否已到timeslot时刻
            if order.timeslot_time is not None and self.env.now >= order.timeslot_time:
                # 追踪：timeslot到达但备货未完成
                self.order_tracker.log_event(
                    order, 'PREP_TIMESLOT_REACHED', self.env.now,
                    f'Timeslot reached before prep complete. Processed={processed_pallets:.0f}/{total_pallets} pallets '
                    f'({processed_pallets/total_pallets*100:.1f}%)'
                )
                break

            # DC关门：直接跳到下一个开门时刻
            if not self.is_dc_open():
                next_open = self._next_open_time()
                if next_open > self.env.now:
                    self.order_tracker.log_event(
                        order, 'PREP_DC_CLOSED', self.env.now,
                        f'DC closed. Waiting until next open={self.order_tracker._sim_time_to_str(next_open)}. '
                        f'Progress={processed_pallets:.0f}/{total_pallets} pallets'
                    )
                    yield self.env.timeout(next_open - self.env.now)
                continue

            # DC开门：获取当下每小时FTE处理能力（含随机波动）
            hourly_capacity = self.fte_manager.get_hourly_capacity(
                order.category,
                'Outbound',
                coefficient=self.opening_hour_coefficient
            )
            if hourly_capacity <= 0:
                # 理论上不该发生；给一个很小的推进避免死循环
                yield self.env.timeout(min(0.1, self._time_until_close()))
                continue

            # 本次最多可工作到：关门/到达timeslot（二者取最早）
            time_budget = self._time_until_close()
            if order.timeslot_time is not None:
                time_budget = min(time_budget, max(0.0, order.timeslot_time - self.env.now))

            if time_budget <= 0:
                # 可能正好临近关门或已到timeslot
                yield self.env.timeout(0.0)
                continue

            remaining_pallets = total_pallets - processed_pallets
            time_needed = remaining_pallets / hourly_capacity
            actual_time = min(time_needed, time_budget)

            pallets_before = processed_pallets
            yield self.env.timeout(actual_time)
            processed_pallets += hourly_capacity * actual_time
            if processed_pallets > total_pallets:
                processed_pallets = total_pallets
            order.preparation_pallets_done = processed_pallets

            # 追踪：备货进度（每个工作段记录一次，跳过微量工作段）
            _prep_loop_count += 1
            pallets_added = processed_pallets - pallets_before
            if pallets_added > 0.01:
                self.order_tracker.log_event(
                    order, 'PREP_PROGRESS', self.env.now,
                    f'Work session #{_prep_loop_count}: +{pallets_added:.1f} pallets in {actual_time:.2f}h '
                    f'(capacity={hourly_capacity:.1f}p/h). Total={processed_pallets:.0f}/{total_pallets} '
                    f'({processed_pallets/total_pallets*100:.1f}%)',
                    pallets_done=round(processed_pallets, 1),
                    hourly_capacity=round(hourly_capacity, 1)
                )

        # 检查是否完成
        if processed_pallets >= total_pallets:
            order.preparation_completed = True
            order.processing_end_time = self.env.now
            
            # 追踪：备货完成
            prep_duration = self.env.now - order.processing_start_time
            self.order_tracker.log_event(
                order, 'PREP_COMPLETE', self.env.now,
                f'Preparation completed! All {total_pallets} pallets ready. '
                f'Duration={prep_duration:.2f}h. '
                f'Time until timeslot={order.timeslot_time - self.env.now:.2f}h' if order.timeslot_time else f'Duration={prep_duration:.2f}h'
            )
            
            # 记录FTE使用情况
            total_processing_time = self.env.now - order.processing_start_time
            available_fte = self.fte_manager.adjusted_fte[order.category]['Outbound']
            hourly_capacity = self.fte_manager.get_hourly_capacity(order.category, 'Outbound', coefficient=self.opening_hour_coefficient)
            
            self.kpi.record_fte_usage(
                category=order.category,
                direction='Outbound',
                processing_time=total_processing_time,
                pallets_processed=total_pallets,
                available_fte=available_fte,
                hourly_capacity=hourly_capacity
            )
    
    def outbound_loading_process(self, order):
        """Outbound装货流程（在timeslot时刻）"""
        # 追踪：等待timeslot
        self.order_tracker.log_event(
            order, 'LOADING_WAIT_TIMESLOT', self.env.now,
            f'Waiting for scheduled timeslot={self.order_tracker._sim_time_to_str(order.timeslot_time)}. '
            f'Prep completed={order.preparation_completed}'
        )
        
        # 等待到timeslot时刻
        if order.timeslot_time and order.timeslot_time > self.env.now:
            yield self.env.timeout(order.timeslot_time - self.env.now)
        
        # 检查备货是否完成
        if not order.preparation_completed:
            # 备货未完成：该订单不可能按原timeslot完成
            order.on_time = False
            
            # 追踪：timeslot到达但备货未完成
            self.order_tracker.log_event(
                order, 'LOADING_PREP_NOT_READY', self.env.now,
                f'Timeslot reached but preparation NOT complete! '
                f'Prepared={order.preparation_pallets_done:.0f}/{order.pallets} pallets. '
                f'Order will be DELAYED and rescheduled.'
            )

            # 继续等待备货完成
            while not order.preparation_completed:
                yield self.env.timeout(0.1)  # 每6分钟检查一次

            # 重新分配到下一个可用的整点timeslot（并尽量避开DC关闭时段/零容量时段）
            new_slot = self.reschedule_delayed_order(order)
            
            # 追踪：重新分配timeslot
            self.order_tracker.log_event(
                order, 'LOADING_RESCHEDULED', self.env.now,
                f'Rescheduled to new timeslot={self.order_tracker._sim_time_to_str(new_slot)} '
                f'(original={self.order_tracker._sim_time_to_str(order.timeslot_time)})'
            )

            # 等待到新timeslot（new_slot 保证不早于当前时间，且为整点）
            if new_slot > self.env.now:
                yield self.env.timeout(new_slot - self.env.now)
        else:
            # 备货完成：按原timeslot执行（如果容量满，后续仍可能顺延）
            self.order_tracker.log_event(
                order, 'LOADING_PREP_READY', self.env.now,
                f'Preparation already complete. Ready for loading at scheduled timeslot.'
            )
            if order.timeslot_time is not None:
                # timeslot_time是整点，但为了稳妥仍做一次对齐
                slot = int(order.timeslot_time)
                if slot > self.env.now:
                    yield self.env.timeout(slot - self.env.now)
        
        # 检查timeslot容量
        slot_key = f'{order.category.lower()}_loading' if order.category == 'FG' else 'rp_loading'
        
        # 等待可用slot（如果当前小时已满）
        _waited_for_capacity = False
        while True:
            available = self.hourly_timeslot_capacity.get(slot_key, 0)
            used = self.hourly_timeslot_used.get(slot_key, 0)
            
            if used < available:
                break
            
            if not _waited_for_capacity:
                self.order_tracker.log_event(
                    order, 'LOADING_WAIT_CAPACITY', self.env.now,
                    f'Dock capacity full (used={used}/{available}). Waiting for next hour.'
                )
                _waited_for_capacity = True
            
            # 等待下一个小时
            yield self.env.timeout(1)

        # 真实开始装货的timeslot（整点小时）
        actual_slot = int(self.env.now)
        order.actual_timeslot = actual_slot

        # 如果因容量/重排导致开始时间超过原timeslot，则视为不准时，并记录延误
        if order.timeslot_time is not None:
            scheduled_slot = int(order.timeslot_time)
            if actual_slot > scheduled_slot:
                order.on_time = False
                order.delay_hours = actual_slot - scheduled_slot
            else:
                order.delay_hours = 0
        
        # 占用timeslot
        self.hourly_timeslot_used[slot_key] = self.hourly_timeslot_used.get(slot_key, 0) + 1
        
        # 追踪：装货开始
        self.order_tracker.log_event(
            order, 'LOADING_START', self.env.now,
            f'Loading started at dock. Actual timeslot={self.order_tracker._sim_time_to_str(self.env.now)}, '
            f'Scheduled={self.order_tracker._sim_time_to_str(order.timeslot_time)}, '
            f'On-time={order.on_time}'
        )
        
        # 装货（1小时）
        loading_start = self.env.now
        yield self.env.timeout(1)
        
        order.completed = True
        
        # 追踪：装货完成 + 最终汇总
        self.order_tracker.log_event(
            order, 'LOADING_COMPLETE', self.env.now,
            f'Loading complete! Truck departs. Pallets={order.pallets}, '
            f'On-time={order.on_time}, Delay={order.delay_hours}h'
        )
        self.order_tracker.finalize_order(order, self.env.now)
        
        # 记录KPI
        self.kpi.record_outbound_truck({
            'category': order.category,
            'pallets': order.pallets,
            'region': order.region,
            'on_time': order.on_time,
            'delay_hours': order.delay_hours,
            'service_time': loading_start,
            'completion_time': self.env.now
        })
    
    def inbound_order_scheduler(self, target_month=1):
        """Inbound订单调度器（新逻辑）
        
        Args:
            target_month: 仿真的目标月份
        """
        if not self.orders:
            print("警告: 无订单数据，跳过Inbound订单调度")
            return
        
        # 收集该月的所有Inbound订单
        inbound_orders = []
        for key, orders_list in self.orders.items():
            if f'M{target_month:02d}' in key and 'Inbound' in key:
                inbound_orders.extend(orders_list)
        
        if not inbound_orders:
            print(f"警告: 月份{target_month}无Inbound订单")
            return
        
        print(f"调度{len(inbound_orders)}个Inbound订单")
        
        # 按timeslot_time排序
        inbound_orders.sort(key=lambda o: o.timeslot_time)
        
        for order in inbound_orders:
            # 等待到timeslot时刻
            if order.timeslot_time and order.timeslot_time > self.env.now:
                yield self.env.timeout(order.timeslot_time - self.env.now)
            
            # 启动接收流程
            self.env.process(self.inbound_receiving_process(order))
    
    def inbound_receiving_process(self, order):
        """Inbound接收流程（在timeslot时刻）"""
        # 追踪：到达码头
        self.order_tracker.log_event(
            order, 'INBOUND_ARRIVAL', self.env.now,
            f'Truck arrives at reception dock. Pallets={order.pallets}, '
            f'Timeslot={self.order_tracker._sim_time_to_str(order.timeslot_time)}'
        )
        
        # 检查timeslot容量
        slot_key = f'{order.category.lower()}_reception' if order.category == 'FG' else 'rp_reception'
        
        # 等待可用slot
        _waited_inbound = False
        while True:
            available = self.hourly_timeslot_capacity.get(slot_key, 0)
            used = self.hourly_timeslot_used.get(slot_key, 0)
            
            if used < available:
                break
            
            if not _waited_inbound:
                self.order_tracker.log_event(
                    order, 'INBOUND_WAIT_CAPACITY', self.env.now,
                    f'Reception dock full (used={used}/{available}). Waiting.'
                )
                _waited_inbound = True
            yield self.env.timeout(1)
        
        # 占用timeslot
        self.hourly_timeslot_used[slot_key] = self.hourly_timeslot_used.get(slot_key, 0) + 1
        
        # 追踪：开始卸货
        self.order_tracker.log_event(
            order, 'INBOUND_UNLOADING', self.env.now,
            f'Unloading started (1 hour). Pallets={order.pallets}'
        )
        
        # 卸货（1小时）
        unloading_start = self.env.now
        yield self.env.timeout(1)
        
        # 记录24小时处理deadline
        order.processing_deadline = self.env.now + 24
        order.processing_start_time = self.env.now
        
        # 追踪：卸货完成，开始FTE处理
        self.order_tracker.log_event(
            order, 'INBOUND_PROCESSING_START', self.env.now,
            f'Unloading complete. FTE processing starts. '
            f'Deadline={self.order_tracker._sim_time_to_str(order.processing_deadline)} (24h window)'
        )
        
        # FTE处理（24小时内完成）
        total_pallets = order.pallets
        processed_pallets = 0

        while processed_pallets < total_pallets:
            # 检查是否超过deadline（deadline使用绝对时间，不因关门而暂停）
            if self.env.now >= order.processing_deadline:
                self.order_tracker.log_event(
                    order, 'INBOUND_DEADLINE_EXCEEDED', self.env.now,
                    f'24h processing deadline exceeded! Processed={processed_pallets:.0f}/{total_pallets}'
                )
                print(f"警告: 订单{order.order_id}超过24h处理deadline")
                break

            # DC关门：等待到下次开门（但如果deadline先到，会在下一轮break）
            if not self.is_dc_open():
                next_open = self._next_open_time()
                if next_open > self.env.now:
                    self.order_tracker.log_event(
                        order, 'INBOUND_DC_CLOSED', self.env.now,
                        f'DC closed. Wait until {self.order_tracker._sim_time_to_str(next_open)}. '
                        f'Progress={processed_pallets:.0f}/{total_pallets}'
                    )
                    yield self.env.timeout(next_open - self.env.now)
                continue

            hourly_capacity = self.fte_manager.get_hourly_capacity(
                order.category,
                'Inbound',
                coefficient=self.opening_hour_coefficient
            )
            if hourly_capacity <= 0:
                yield self.env.timeout(min(0.1, self._time_until_close()))
                continue

            # 本次最多可工作到：关门/deadline（二者取最早）
            time_budget = self._time_until_close()
            time_budget = min(time_budget, max(0.0, order.processing_deadline - self.env.now))
            if time_budget <= 0:
                yield self.env.timeout(0.0)
                continue

            remaining_pallets = total_pallets - processed_pallets
            time_needed = remaining_pallets / hourly_capacity
            actual_time = min(time_needed, time_budget)

            yield self.env.timeout(actual_time)
            processed_pallets += hourly_capacity * actual_time
            if processed_pallets > total_pallets:
                processed_pallets = total_pallets
        
        order.processing_end_time = self.env.now
        order.completed = True
        
        # 追踪：处理完成
        self.order_tracker.log_event(
            order, 'INBOUND_COMPLETE', self.env.now,
            f'Inbound processing complete. Pallets={total_pallets}, '
            f'Total time={self.env.now - unloading_start:.2f}h, '
            f'Within deadline={self.env.now <= order.processing_deadline}'
        )
        self.order_tracker.finalize_order(order, self.env.now)
        
        # 记录FTE使用情况
        total_processing_time = self.env.now - order.processing_start_time
        available_fte = self.fte_manager.adjusted_fte[order.category]['Inbound']
        hourly_capacity = self.fte_manager.get_hourly_capacity(order.category, 'Inbound', coefficient=self.opening_hour_coefficient)
        
        self.kpi.record_fte_usage(
            category=order.category,
            direction='Inbound',
            processing_time=total_processing_time,
            pallets_processed=processed_pallets,
            available_fte=available_fte,
            hourly_capacity=hourly_capacity
        )
        
        # 记录KPI
        self.kpi.record_inbound_truck({
            'category': order.category,
            'pallets': order.pallets,
            'arrival_time': unloading_start,
            'processing_time': self.env.now - order.processing_start_time,
            'missed_deadline': self.env.now > order.processing_deadline
        })
    
    def reschedule_delayed_order(self, order):
        """为延误订单重新分配timeslot"""
        hourly_config = SYSTEM_PARAMETERS['hourly_dock_capacity']

        def _hourly_capacity(hour_of_day: int) -> int:
            if order.category == 'FG':
                cap_map = hourly_config['FG']['loading']
            else:
                cap_map = hourly_config['R&P']['loading']
            return cap_map.get(hour_of_day, cap_map.get(str(hour_of_day), 0))

        # 从下一整点开始查找（避免返回小数时间导致非整点装货）
        search_start = int(np.ceil(self.env.now))

        # 扫描更长窗口，避免尾部时段“无解”
        for abs_hour in range(search_start, search_start + 24 * 30):  # 最多搜索30天
            if not self.is_dc_open(abs_hour):
                continue
            hour_of_day = abs_hour % 24
            if _hourly_capacity(hour_of_day) > 0:
                return abs_hour

        # 极端情况下仍找不到（比如配置异常）：回退到下一整点，交给容量等待逻辑推进
        return search_start
    
    # ==================== 结束新逻辑 ====================
    
    def run(self, duration_days=30, target_month=1):
        """运行仿真
        
        Args:
            duration_days: 仿真持续天数
            target_month: 目标月份（1-12），用于选择订单数据
        """
        print(f"\n开始仿真运行，持续 {duration_days} 天，目标月份: {target_month}...")
        
        # 启动timeslot容量管理器（必需）
        self.env.process(self.timeslot_capacity_manager())
        
        # 订单驱动流程
        if not self.orders:
            raise ValueError("未找到订单数据！请先运行data_preparation.py生成订单。")
        
        print("使用订单驱动流程")
        # 启动订单调度器
        self.env.process(self.inbound_order_scheduler(target_month))
        self.env.process(self.outbound_order_scheduler(target_month))
        
        # 运行仿真
        self.env.run(until=duration_days * 24)
        
        # 统计延误订单
        if self.orders:
            delayed_count = sum(1 for orders_list in self.orders.values() 
                              for order in orders_list 
                              if order.direction == 'Outbound' and not order.on_time and order.completed)
            if delayed_count > 0:
                print(f"\n共有 {delayed_count} 个Outbound订单因备货延误而重排timeslot")
        
        print(f"仿真运行完成！")
        
        # 生成汇总报告，传入实际使用的FTE配置和alpha配置
        adjusted_fte = self.fte_manager.adjusted_fte
        alpha_config = {
            'alpha': self.config.get('fte_efficiency_alpha', 1.0),
            'baseline_hours': self.config.get('fte_efficiency_baseline_hours', 18),
            'operating_hours': self.config.get('operating_hours', 18)
        }
        # 将alpha配置传递给KPICollector
        self.kpi.alpha_config = alpha_config
        summary = self.kpi.generate_summary(adjusted_fte=adjusted_fte)
        
        # 添加订单统计（新逻辑）
        if self.orders:
            order_stats = self._generate_order_statistics(target_month=target_month, duration_days=duration_days)
            summary['order_statistics'] = order_stats

            # 用“所有订单口径”覆盖/补全区域准时率（避免只统计已完成订单导致乐观偏差）
            region_stats = order_stats.get('fg_outbound_region_stats', {})
            for region in ['G2', 'ROW']:
                rs = region_stats.get(region, {})
                total = rs.get('total_orders', 0)
                on_time_all_pct = rs.get('on_time_rate_all', 0.0) / 100.0
                completion_pct = rs.get('completion_rate', 0.0) / 100.0
                # 保持历史字段名（值为0-1的小数，供 comparison_df *100 使用）
                summary[f'{region}_on_time_rate'] = on_time_all_pct
                summary[f'{region}_total_orders'] = total
                # 新增：区域完成率（0-1）
                summary[f'{region}_completion_rate'] = completion_pct
        
        return summary
    
    def _generate_order_statistics(self):
        """生成订单统计信息（新逻辑）

        注意：
        - completion_rate 的分母是“仿真窗口内、目标月份的订单”（否则会把全年订单都算进来，导致完成率虚低）
        - on_time_* 默认只针对 Outbound（按原 timeslot 准时）
        """
        stats = {
            # 统计范围信息
            'target_month': None,
            'horizon_days': None,
            'horizon_hours': None,

            # 全部订单（Inbound+Outbound）完成率（在范围内）
            'total_orders': 0,
            'completed_orders': 0,
            'incomplete_orders': 0,
            'completion_rate': 0.0,

            # Outbound（按原 timeslot 准时）
            'total_outbound_orders': 0,
            'completed_outbound_orders': 0,
            'on_time_outbound_orders': 0,
            'delayed_outbound_orders': 0,
            'outbound_completion_rate': 0.0,
            'on_time_rate_all': 0.0,
            'on_time_rate_completed': 0.0,

            # 延误统计（Outbound）
            'total_delay_hours': 0,
            'avg_delay_hours': 0.0,

            # 兼容字段：历史代码读取 on_time_rate
            'on_time_rate': 0.0
        }
        
        return stats

    def _generate_order_statistics(self, target_month=1, duration_days=30):
        """生成订单统计信息（新逻辑）

        统计范围 = 目标月份 + 仿真时长窗口（0 ~ duration_days*24）。

        completion_rate:
          已完成订单数 / 范围内订单总数

        on_time（Outbound）:
          订单完成且 actual_timeslot <= 原定 timeslot_time（整点小时比较）
        """
        stats = {
            'target_month': int(target_month),
            'horizon_days': int(duration_days),
            'horizon_hours': int(duration_days * 24),

            'total_orders': 0,
            'completed_orders': 0,
            'incomplete_orders': 0,
            'completion_rate': 0.0,

            'total_outbound_orders': 0,
            'completed_outbound_orders': 0,
            'on_time_outbound_orders': 0,
            'delayed_outbound_orders': 0,
            'outbound_completion_rate': 0.0,
            'on_time_rate_all': 0.0,
            'on_time_rate_completed': 0.0,

            'total_delay_hours': 0,
            'avg_delay_hours': 0.0,

            'on_time_rate': 0.0
        }

        if not self.orders:
            return stats

        horizon = duration_days * 24

        # 只取目标月份的订单
        month_orders = []
        month_token = f'M{target_month:02d}'
        for key, orders_list in self.orders.items():
            if month_token in key:
                month_orders.extend(orders_list)

        # 进一步限制到仿真窗口内（以 timeslot_time 为主；Outbound 没有 timeslot_time 的也忽略）
        scoped_orders = []
        for o in month_orders:
            if o.timeslot_time is None:
                continue
            if 0 <= o.timeslot_time < horizon:
                scoped_orders.append(o)

        stats['total_orders'] = len(scoped_orders)
        stats['completed_orders'] = sum(1 for o in scoped_orders if o.completed)
        stats['incomplete_orders'] = stats['total_orders'] - stats['completed_orders']
        if stats['total_orders'] > 0:
            stats['completion_rate'] = stats['completed_orders'] / stats['total_orders'] * 100

        # Completion / On-time by flow (FG/R&P × Inbound/Outbound)
        # 说明：
        # - Completion = completed / total (在scoped范围内)
        # - On-time:
        #   - Outbound: 使用 order.on_time（按原定timeslot是否准时开始装车）
        #   - Inbound: 使用 24h 处理deadline（processing_end_time <= processing_deadline）
        #     对应 inbound_receiving_process 中的 missed_deadline 逻辑。
        flow_defs = [
            ('FG', 'Inbound', 'FG_inbound'),
            ('FG', 'Outbound', 'FG_outbound'),
            ('R&P', 'Inbound', 'RP_inbound'),
            ('R&P', 'Outbound', 'RP_outbound'),
        ]
        for cat, direction, prefix in flow_defs:
            flow_orders = [o for o in scoped_orders if o.category == cat and o.direction == direction]
            total = len(flow_orders)
            completed = sum(1 for o in flow_orders if o.completed)
            stats[f'{prefix}_total_orders'] = total
            stats[f'{prefix}_completed_orders'] = completed
            stats[f'{prefix}_completion_rate'] = (completed / total * 100) if total else 0.0

            if direction == 'Outbound':
                on_time = sum(1 for o in flow_orders if o.completed and getattr(o, 'on_time', False))
            else:
                on_time = sum(
                    1 for o in flow_orders
                    if o.completed
                    and getattr(o, 'processing_end_time', None) is not None
                    and getattr(o, 'processing_deadline', None) is not None
                    and o.processing_end_time <= o.processing_deadline
                )

            stats[f'{prefix}_on_time_orders'] = on_time
            stats[f'{prefix}_on_time_rate_all'] = (on_time / total * 100) if total else 0.0
            stats[f'{prefix}_on_time_rate_completed'] = (on_time / completed * 100) if completed else 0.0

        # Outbound on-time（按 timeslot）
        outbound = [o for o in scoped_orders if o.direction == 'Outbound']
        stats['total_outbound_orders'] = len(outbound)
        stats['completed_outbound_orders'] = sum(1 for o in outbound if o.completed)
        stats['on_time_outbound_orders'] = sum(1 for o in outbound if o.completed and o.on_time)
        stats['delayed_outbound_orders'] = sum(1 for o in outbound if o.completed and not o.on_time)

        # Day1 -> Day2 reschedule (基于原定timeslot的“第1天”与实际装车/完成的“第2天”)
        # 口径：仅Outbound；分母=原定timeslot在第1天(0-24h)的Outbound订单数；
        # 分子=其中已完成且实际装车开始(actual_timeslot)落在第2天(24-48h)的订单数。
        day1_outbound = [
            o for o in outbound
            if o.timeslot_time is not None and (int(o.timeslot_time) // 24) == 0
        ]
        day1_to_day2_completed = [
            o for o in day1_outbound
            if o.completed and o.actual_timeslot is not None and (int(o.actual_timeslot) // 24) == 1
        ]
        stats['day1_outbound_orders'] = len(day1_outbound)
        stats['day1_to_day2_outbound_orders'] = len(day1_to_day2_completed)
        stats['day1_to_day2_outbound_rate'] = (
            stats['day1_to_day2_outbound_orders'] / stats['day1_outbound_orders'] * 100
            if stats['day1_outbound_orders'] > 0 else 0.0
        )

        if stats['total_outbound_orders'] > 0:
            stats['outbound_completion_rate'] = stats['completed_outbound_orders'] / stats['total_outbound_orders'] * 100
            stats['on_time_rate_all'] = stats['on_time_outbound_orders'] / stats['total_outbound_orders'] * 100
            stats['on_time_rate'] = stats['on_time_rate_all']  # 兼容字段

        if stats['completed_outbound_orders'] > 0:
            stats['on_time_rate_completed'] = stats['on_time_outbound_orders'] / stats['completed_outbound_orders'] * 100

        stats['total_delay_hours'] = sum(o.delay_hours for o in outbound if o.completed)
        if stats['delayed_outbound_orders'] > 0:
            stats['avg_delay_hours'] = stats['total_delay_hours'] / stats['delayed_outbound_orders']

        # FG Outbound：按地区统计（同样使用 scoped 范围）
        region_stats = {}
        fg_outbound = [o for o in outbound if o.category == 'FG']
        for region_prefix in ['G2', 'ROW']:
            region_orders = [o for o in fg_outbound if (o.region or '').startswith(region_prefix)]
            total = len(region_orders)
            completed = sum(1 for o in region_orders if o.completed)
            on_time = sum(1 for o in region_orders if o.completed and o.on_time)
            delayed = sum(1 for o in region_orders if o.completed and not o.on_time)

            rs = {
                'total_orders': total,
                'completed_orders': completed,
                'on_time_orders': on_time,
                'delayed_orders': delayed,
                'completion_rate': (completed / total * 100) if total else 0.0,
                'on_time_rate_all': (on_time / total * 100) if total else 0.0,
                'on_time_rate_completed': (on_time / completed * 100) if completed else 0.0,
            }
            region_stats[region_prefix] = rs

        stats['fg_outbound_region_stats'] = region_stats
        return stats


def _extract_available_months_from_orders_data(orders_data: dict):
    """从generated_orders.json顶层key中提取可用月份列表（例如 *_M01, *_M02 ...）。"""
    months = set()
    if not isinstance(orders_data, dict):
        return []
    for key in orders_data.keys():
        if not isinstance(key, str):
            continue
        idx = key.rfind('_M')
        if idx >= 0 and idx + 3 < len(key):
            token = key[idx + 2: idx + 4]
            if token.isdigit():
                m = int(token)
                if 1 <= m <= 12:
                    months.add(m)
    return sorted(months)


def _flatten_order_statistics(os_dict: dict, prefix: str = 'os_'):
    """把order_statistics（含地区子结构）扁平化为列，便于写入Excel/对比。"""
    if not isinstance(os_dict, dict):
        return {}
    flat = {}
    for k, v in os_dict.items():
        if k == 'fg_outbound_region_stats':
            continue
        if isinstance(v, (int, float, np.number)):
            flat[prefix + str(k)] = float(v)

    region_stats = os_dict.get('fg_outbound_region_stats', {})
    if isinstance(region_stats, dict):
        for region, rs in region_stats.items():
            if not isinstance(rs, dict):
                continue
            for k, v in rs.items():
                if isinstance(v, (int, float, np.number)):
                    flat[f'{prefix}fg_outbound_{region}_{k}'] = float(v)
    return flat


def _run_one_scenario_one_month(scenario_config, num_replications=5, duration_days=30, target_month=1):
    """运行单个场景、单个月份，返回跨replication平均后的结果(dict)。"""
    scenario_results = []
    for rep in range(num_replications):
        env = simpy.Environment()
        sim = DCSimulation(env, scenario_config, run_id=rep + 1)
        result = sim.run(duration_days=duration_days, target_month=target_month)
        scenario_results.append(result)

    avg_result = {}
    for key in scenario_results[0].keys():
        if key in ['hourly_dock_utilization', 'order_statistics']:
            if key == 'order_statistics':
                dicts = [r.get('order_statistics', {}) for r in scenario_results]
                numeric_keys = [
                    'target_month', 'horizon_days', 'horizon_hours',
                    'total_orders', 'completed_orders', 'incomplete_orders',
                    'completion_rate',
                    'total_outbound_orders', 'completed_outbound_orders',
                    'on_time_outbound_orders', 'delayed_outbound_orders',
                    'outbound_completion_rate', 'on_time_rate', 'on_time_rate_all', 'on_time_rate_completed',
                    'total_delay_hours', 'avg_delay_hours',
                    'day1_outbound_orders', 'day1_to_day2_outbound_orders', 'day1_to_day2_outbound_rate'
                ]
                for prefix in ['FG_inbound', 'FG_outbound', 'RP_inbound', 'RP_outbound']:
                    numeric_keys.extend([
                        f'{prefix}_total_orders',
                        f'{prefix}_completed_orders',
                        f'{prefix}_completion_rate',
                        f'{prefix}_on_time_orders',
                        f'{prefix}_on_time_rate_all',
                        f'{prefix}_on_time_rate_completed',
                    ])

                merged = {}
                for nk in numeric_keys:
                    vals = [d.get(nk, 0) for d in dicts]
                    merged[nk] = float(np.mean(vals))

                # 地区统计：取均值
                region_out = {}
                for rk in ['G2', 'ROW']:
                    rs_list = [d.get('fg_outbound_region_stats', {}).get(rk, {}) for d in dicts]
                    if any(rs_list):
                        region_out[rk] = {
                            'total_orders': float(np.mean([rs.get('total_orders', 0) for rs in rs_list])),
                            'completed_orders': float(np.mean([rs.get('completed_orders', 0) for rs in rs_list])),
                            'on_time_orders': float(np.mean([rs.get('on_time_orders', 0) for rs in rs_list])),
                            'delayed_orders': float(np.mean([rs.get('delayed_orders', 0) for rs in rs_list])),
                            'completion_rate': float(np.mean([rs.get('completion_rate', 0.0) for rs in rs_list])),
                            'on_time_rate_all': float(np.mean([rs.get('on_time_rate_all', 0.0) for rs in rs_list])),
                            'on_time_rate_completed': float(np.mean([rs.get('on_time_rate_completed', 0.0) for rs in rs_list])),
                        }
                if region_out:
                    merged['fg_outbound_region_stats'] = region_out
                avg_result[key] = merged
            else:
                avg_result[key] = scenario_results[0].get(key)
            continue

        values = [r.get(key) for r in scenario_results]
        if isinstance(values[0], (int, float, np.number)):
            avg_result[key] = float(np.mean(values))
        else:
            avg_result[key] = values[0]

    return avg_result


def run_yearly_scenario_summary(scenarios_to_run=None, months=None, num_replications=3, duration_days=30):
    """全年汇总：按月运行仿真，所有KPI对月份取平均（每个scenario一行）。

    注意：这里的“全年平均”=对所选 months 的月度结果取算术平均（不是求和）。
    """
    if scenarios_to_run is None:
        scenarios_to_run = list(SIMULATION_CONFIG.keys())

    # 自动识别有哪些月份
    global _CACHED_ORDERS_DATA
    if months is None:
        if _CACHED_ORDERS_DATA is not None:
            months = _extract_available_months_from_orders_data(_CACHED_ORDERS_DATA)
        else:
            # 触发一次读取（构造一个临时sim只为load）
            try:
                _ = DCSimulation(simpy.Environment(), SIMULATION_CONFIG[scenarios_to_run[0]], run_id=0)
                if _CACHED_ORDERS_DATA is not None:
                    months = _extract_available_months_from_orders_data(_CACHED_ORDERS_DATA)
            except Exception:
                months = []
        if not months:
            months = list(range(1, 13))

    print("=" * 70)
    print("DC 全年（多月）汇总仿真")
    print("=" * 70)
    print(f"场景数量: {len(scenarios_to_run)}")
    print(f"月份范围: {months}")
    print(f"每月每场景重复次数: {num_replications}")
    print(f"每月仿真天数: {duration_days}")
    print("=" * 70)

    yearly_rows = {}

    for scenario_name in scenarios_to_run:
        scenario_config = SIMULATION_CONFIG[scenario_name]
        print(f"\n{'='*70}")
        print(f"全年汇总 - 运行场景: {scenario_config['name']}")
        print(f"{'='*70}")

        per_month_results = []
        for m in months:
            print(f"\n--- Month {m:02d} ---")
            avg_month = _run_one_scenario_one_month(
                scenario_config,
                num_replications=num_replications,
                duration_days=duration_days,
                target_month=m
            )
            per_month_results.append(avg_month)

        yearly_avg = {}
        all_keys = set()
        for r in per_month_results:
            all_keys.update(r.keys())

        for key in sorted(all_keys):
            if key in ['hourly_dock_utilization']:
                continue
            if key == 'order_statistics':
                dicts = [r.get('order_statistics', {}) for r in per_month_results]
                merged = {}
                numeric_keys = set()
                for d in dicts:
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if k == 'fg_outbound_region_stats':
                                continue
                            if isinstance(v, (int, float, np.number)):
                                numeric_keys.add(k)
                for nk in numeric_keys:
                    merged[nk] = float(np.mean([d.get(nk, 0) for d in dicts]))

                region_out = {}
                for rk in ['G2', 'ROW']:
                    rs_list = [d.get('fg_outbound_region_stats', {}).get(rk, {}) for d in dicts]
                    if any(rs_list):
                        region_out[rk] = {}
                        rs_keys = set()
                        for rs in rs_list:
                            if isinstance(rs, dict):
                                for k, v in rs.items():
                                    if isinstance(v, (int, float, np.number)):
                                        rs_keys.add(k)
                        for k in rs_keys:
                            region_out[rk][k] = float(np.mean([rs.get(k, 0) for rs in rs_list]))
                if region_out:
                    merged['fg_outbound_region_stats'] = region_out
                yearly_avg[key] = merged
                continue

            vals = [r.get(key) for r in per_month_results if key in r]
            if vals and isinstance(vals[0], (int, float, np.number)):
                yearly_avg[key] = float(np.mean(vals))
            else:
                yearly_avg[key] = vals[0] if vals else None

        yearly_rows[scenario_name] = yearly_avg

    flat_rows = {}
    for scenario_name, row in yearly_rows.items():
        flat = {}
        for k, v in row.items():
            if k == 'order_statistics':
                flat.update(_flatten_order_statistics(v, prefix='os_'))
            else:
                if isinstance(v, (int, float, np.number)) or v is None:
                    flat[k] = v
        flat_rows[scenario_name] = flat

    yearly_df = pd.DataFrame(flat_rows).T
    yearly_path = os.path.join(RESULTS_DIR, 'simulation_results_yearly_comparison.xlsx')
    yearly_df.to_excel(yearly_path)
    print(f"\nYearly average results saved to: {yearly_path}")

    return yearly_rows, yearly_df


# ==================== 多场景对比运行 ====================
def run_scenario_comparison(
    scenarios_to_run=None,
    num_replications=5,
    duration_days=30,
    target_month=1,
    scenario_config_transform=None,
    output_suffix='',
    details_suffix=''
):
    """运行多场景对比分析"""

    def _print_closed_timeslot_exposure(sim: 'DCSimulation', base_cfg: dict, scen_cfg: dict):
        """Print how many scheduled timeslots become unavailable due to scenario-specific closures.

        This is mainly for diagnosing Friday late-shift cancellations.
        """
        has_rules = bool(scen_cfg.get('biweekly_shift_cancel')) or bool(scen_cfg.get('shift_cancel_rules'))
        if not has_rules:
            return

        if not getattr(sim, 'orders', None):
            return

        horizon = duration_days * 24
        month_token = f'M{target_month:02d}'

        month_orders = []
        for key, orders_list in sim.orders.items():
            if month_token in key:
                month_orders.extend(orders_list)

        scoped = [o for o in month_orders if getattr(o, 'timeslot_time', None) is not None and 0 <= o.timeslot_time < horizon]
        if not scoped:
            return

        affected = [
            o for o in scoped
            if _is_dc_open_at_time(o.timeslot_time, base_cfg) and (not _is_dc_open_at_time(o.timeslot_time, scen_cfg))
        ]

        total = len(scoped)
        n_aff = len(affected)
        if n_aff == 0:
            print("\n  [诊断] 本场景的额外关门不影响任何订单的原定timeslot（baseline开门而本场景关门的订单数=0）。")
            return

        by_flow = defaultdict(int)
        by_hour = defaultdict(int)
        for o in affected:
            by_flow[(o.category, o.direction)] += 1
            di = int(o.timeslot_time) // 24
            hod = int(o.timeslot_time) % 24
            day1_weekday = int(scen_cfg.get('day1_weekday', 0))
            weekday = (day1_weekday + di) % 7
            by_hour[(weekday, hod)] += 1

        weekday_names = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}

        print("\n  [诊断] 额外关门导致‘原定timeslot落在关门时段’的订单：")
        print(f"    - 影响订单数: {n_aff}/{total} ({n_aff / total * 100:.2f}%)")
        for (cat, direction), cnt in sorted(by_flow.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
            print(f"    - {cat} {direction}: {cnt}")

        top_hours = sorted(by_hour.items(), key=lambda x: -x[1])[:8]
        if top_hours:
            hh = ", ".join([f"{weekday_names.get(w, str(w))} {h:02d}:00({c})" for (w, h), c in top_hours])
            print(f"    - Top受影响时段: {hh}")
    
    if scenarios_to_run is None:
        scenarios_to_run = list(SIMULATION_CONFIG.keys())
    
    print("=" * 70)
    print("DC 运营时间缩短仿真分析")
    print("=" * 70)
    print(f"场景数量: {len(scenarios_to_run)}")
    print(f"每场景重复次数: {num_replications}")
    print(f"仿真天数: {duration_days}")
    print(f"目标月份: {target_month}")
    print("=" * 70)
    
    all_results = {}
    
    for scenario_name in scenarios_to_run:
        base_scenario_config = SIMULATION_CONFIG[scenario_name]
        scenario_config = base_scenario_config
        if scenario_config_transform is not None:
            scenario_config = scenario_config_transform(scenario_config)
        print(f"\n{'='*70}")
        print(f"运行场景: {scenario_config['name']}")
        print(f"{'='*70}")
        
        scenario_results = []
        
        for rep in range(num_replications):
            print(f"\n--- 重复 {rep + 1}/{num_replications} ---")
            
            # 创建新的仿真环境
            env = simpy.Environment()
            sim = DCSimulation(env, scenario_config, run_id=rep+1)

            # 诊断：本场景的额外关门到底影响了多少“原定timeslot”订单
            if rep == 0:
                _print_closed_timeslot_exposure(sim, base_scenario_config, scenario_config)
            
            # 运行仿真
            result = sim.run(duration_days=duration_days, target_month=target_month)
            scenario_results.append(result)
            
            # 打印关键指标
            print(f"\n  === 流量统计 ===")
            print(f"  Inbound总量: {result.get('total_inbound_pallets', 0):.0f} pallets")
            print(f"    - FG: {result.get('FG_inbound_pallets', 0):.0f}")
            print(f"    - R&P: {result.get('R&P_inbound_pallets', 0):.0f}")
            print(f"  Outbound总量: {result.get('total_outbound_pallets', 0):.0f} pallets")
            print(f"    - FG: {result.get('FG_outbound_pallets', 0):.0f}")
            print(f"    - R&P: {result.get('R&P_outbound_pallets', 0):.0f}")
            
            print(f"\n  === 延期情况 ===")
            print(f"  Inbound 24h延期: {result.get('total_inbound_delays', 0)} 订单 ({result.get('total_delayed_pallets', 0):.0f} pallets)")
            if result.get('total_inbound_delays', 0) > 0:
                print(f"    - 平均延期: {result.get('avg_inbound_delay_hours', 0):.2f}h")
                print(f"    - FG延期: {result.get('fg_inbound_delays', 0)}, R&P延期: {result.get('rp_inbound_delays', 0)}")
            os_ = result.get('order_statistics', {})
            print(f"  完成率: {os_.get('completion_rate', 0):.1f}%")
            print(f"  准时率(所有订单): {os_.get('on_time_rate_all', os_.get('on_time_rate', 0)):.1f}%")
            print(f"  准时率(仅已完成订单): {os_.get('on_time_rate_completed', 0):.1f}%")
            
            print(f"\n  === 资源利用 ===")
            print(f"  平均卡车等待时间: {result['avg_truck_wait_time']:.2f} 小时")
            print(f"  平均午夜积压: {result['avg_midnight_backlog_pallets']:.1f} 托盘")
            
            # 显示FTE利用率（简化版）
            if 'overall_fte_utilization_rate' in result:
                print(f"\n  === FTE利用情况 ===")
                print(f"  整体FTE利用率: {result['overall_fte_utilization_rate']:.1%}")
                print(f"  实际使用: {result.get('total_fte_used', 0):.1f} FTE, 可用: {result.get('total_fte_available', 0):.1f} FTE")
                for category in ['FG', 'R&P']:
                    for direction in ['inbound', 'outbound']:
                        key_util = f'{category}_{direction}_fte_utilization_rate'
                        key_used = f'{category}_{direction}_fte_used'
                        key_available = f'{category}_{direction}_fte_available'
                        
                        if key_util in result:
                            used = result.get(key_used, 0)
                            available = result.get(key_available, 0)
                            util = result[key_util]
                            print(f"    {category} {direction.capitalize()}: {util:.1%} (使用{used:.1f} / 可用{available:.1f} FTE)")
            
            # 显示码头利用率
            if result.get('avg_dock_utilization', 0) > 0:
                print(f"\n  === Timeslot利用率 ===")
                print(f"  整体平均利用率: {result['avg_dock_utilization']:.1%}")
                print(f"  Loading码头: 平均 {result['loading_avg_utilization']:.1%}, 峰值 {result['loading_peak_utilization']:.1%}")
                print(f"  Reception码头: 平均 {result['reception_avg_utilization']:.1%}, 峰值 {result['reception_peak_utilization']:.1%}")
                print(f"    - FG码头: {result['FG_dock_avg_utilization']:.1%}")
                print(f"    - R&P码头: {result['R&P_dock_avg_utilization']:.1%}")
            
            # 导出详细数据（仅第一次重复）- 已禁用以减少文件数量
            # if rep == 0:
            #     output_path = os.path.join(RESULTS_DIR, f'simulation_details_{scenario_name}{details_suffix}.xlsx')
            #     sim.kpi.export_to_excel(output_path)
        
        # 计算平均结果
        avg_result = {}
        for key in scenario_results[0].keys():
            # 跳过字典类型的数据（如hourly_dock_utilization, order_statistics）
            if key in ['hourly_dock_utilization', 'order_statistics']:
                if key == 'order_statistics':
                    # 对常用KPI做跨重复平均，避免“只看第一次重复”的偏差
                    dicts = [r.get('order_statistics', {}) for r in scenario_results]
                    numeric_keys = [
                        'total_orders', 'completed_orders', 'incomplete_orders',
                        'on_time_orders', 'delayed_orders', 'total_delay_hours',
                        'completion_rate', 'on_time_rate', 'on_time_rate_all', 'on_time_rate_completed',
                        'avg_delay_hours',
                        'day1_outbound_orders', 'day1_to_day2_outbound_orders', 'day1_to_day2_outbound_rate'
                    ]

                    # Flow-level metrics (FG/R&P × Inbound/Outbound)
                    for prefix in ['FG_inbound', 'FG_outbound', 'RP_inbound', 'RP_outbound']:
                        numeric_keys.extend([
                            f'{prefix}_total_orders',
                            f'{prefix}_completed_orders',
                            f'{prefix}_completion_rate',
                            f'{prefix}_on_time_orders',
                            f'{prefix}_on_time_rate_all',
                            f'{prefix}_on_time_rate_completed',
                        ])
                    merged = {}
                    for nk in numeric_keys:
                        vals = [d.get(nk, 0) for d in dicts]
                        merged[nk] = float(np.mean(vals))
                    # 地区统计：同样做均值（如果存在）
                    region_keys = ['G2', 'ROW']
                    region_out = {}
                    for rk in region_keys:
                        rs_list = [d.get('fg_outbound_region_stats', {}).get(rk, {}) for d in dicts]
                        if any(rs_list):
                            region_out[rk] = {
                                'total_orders': float(np.mean([rs.get('total_orders', 0) for rs in rs_list])),
                                'completed_orders': float(np.mean([rs.get('completed_orders', 0) for rs in rs_list])),
                                'on_time_orders': float(np.mean([rs.get('on_time_orders', 0) for rs in rs_list])),
                                'delayed_orders': float(np.mean([rs.get('delayed_orders', 0) for rs in rs_list])),
                                'completion_rate': float(np.mean([rs.get('completion_rate', 0.0) for rs in rs_list])),
                                'on_time_rate_all': float(np.mean([rs.get('on_time_rate_all', 0.0) for rs in rs_list])),
                                'on_time_rate_completed': float(np.mean([rs.get('on_time_rate_completed', 0.0) for rs in rs_list])),
                            }
                    if region_out:
                        merged['fg_outbound_region_stats'] = region_out
                    avg_result[key] = merged
                else:
                    # hourly_dock_utilization 目前不做跨重复平均（结构较复杂）
                    avg_result[key] = scenario_results[0][key]
                continue
            
            # 检查值是否为数值类型
            values = [r[key] for r in scenario_results]
            if isinstance(values[0], (int, float, np.number)):
                avg_result[key] = np.mean(values)
                avg_result[f'{key}_std'] = np.std(values)
            else:
                # 非数值类型，使用第一个值
                avg_result[key] = values[0]
        
        all_results[scenario_name] = avg_result
        
        print(f"\n{scenario_config['name']} - 平均结果 ({num_replications} 次重复):")
        aos = avg_result.get('order_statistics', {})
        print(f"  完成率: {aos.get('completion_rate', 0):.1f}%")
        print(f"  准时率(所有订单): {aos.get('on_time_rate_all', aos.get('on_time_rate', 0)):.1f}%")
        print(f"  平均卡车等待时间: {avg_result['avg_truck_wait_time']:.2f} ± {avg_result['avg_truck_wait_time_std']:.2f} 小时")
        print(f"  平均午夜积压: {avg_result['avg_midnight_backlog_pallets']:.1f} ± {avg_result['avg_midnight_backlog_pallets_std']:.1f} 托盘")
    
    # 生成对比表格
    comparison_df = pd.DataFrame(all_results).T
    comparison_path = os.path.join(RESULTS_DIR, f'simulation_results_comparison{output_suffix}.xlsx')
    comparison_df.to_excel(comparison_path)
    
    # 导出FTE专用结果文件
    export_fte_results_to_excel(comparison_df, output_suffix)
    
    print(f"\n{'='*70}")
    print("所有场景仿真完成！")
    print(f"Comparison results saved to: {comparison_path}")
    print(f"{'='*70}")
    
    return all_results, comparison_df


def _scenario_transform_fte_power(alpha=0.8, baseline_hours=18):
    """Scenario-A transform: keep everything same, only apply power-law FTE hourly efficiency."""
    def _t(cfg: dict):
        new_cfg = dict(cfg)
        new_cfg['fte_efficiency_alpha'] = float(alpha)
        new_cfg['fte_efficiency_baseline_hours'] = float(baseline_hours)
        return new_cfg
    return _t


def _scenario_transform_biweekly_cancel_friday_late_shift_with_fte_adjustment(
    day1_weekday=0,
    start_week_index=1,
    cancel_start_hour=15,
    every_n_weeks=2,
    baseline_hours=18
):
    """Enhanced scenario transform: cancel Friday late shift AND adjust FTE accordingly.
    
    Combines shift cancellation with proportional FTE reduction based on lost operating hours.
    """
    def _t(cfg: dict):
        new_cfg = dict(cfg)
        
        # Apply shift cancellation logic
        new_cfg['day1_weekday'] = int(day1_weekday)
        new_cfg['biweekly_shift_cancel'] = {
            'day1_weekday': int(day1_weekday),
            'weekday': 4,  # Friday
            'start_week_index': int(start_week_index),
            'every_n_weeks': int(every_n_weeks),
            'cancel_start_hour': int(cancel_start_hour),
            'cancel_end_hour': int(new_cfg.get('dc_close_time', 24)),
        }
        
        # Calculate FTE adjustment based on reduced hours
        # Estimate: if Friday late shift (15-24 = 9h) is cancelled biweekly,
        # effective weekly reduction = 9h / 2 weeks = 4.5h per week
        # Weekly operating hours reduction = 4.5 / (7 * original_daily_hours)
        dc_open = int(new_cfg.get('dc_open_time', 6))
        dc_close = int(new_cfg.get('dc_close_time', 24))
        daily_hours = dc_close - dc_open
        
        cancelled_hours_per_day = int(new_cfg.get('dc_close_time', 24)) - cancel_start_hour
        # Biweekly cancellation = 0.5 * cancelled_hours per week on average  
        avg_weekly_reduction = cancelled_hours_per_day / every_n_weeks
        avg_daily_reduction = avg_weekly_reduction / 7
        
        # New effective daily hours
        effective_daily_hours = daily_hours - avg_daily_reduction
        
        # FTE adjustment ratio
        fte_adjustment = effective_daily_hours / baseline_hours
        new_cfg['fte_adjustment_ratio'] = max(0.1, min(1.0, fte_adjustment))
        
        return new_cfg
    return _t


def _scenario_transform_weekly_cancel_friday_late_shift_with_fte_adjustment(
    day1_weekday=0,
    cancel_start_hour=15,
    baseline_hours=18
):
    """Weekly Friday late shift cancellation with FTE adjustment."""
    return _scenario_transform_biweekly_cancel_friday_late_shift_with_fte_adjustment(
        day1_weekday=day1_weekday,
        start_week_index=0,
        cancel_start_hour=cancel_start_hour,
        every_n_weeks=1,
        baseline_hours=baseline_hours
    )


def _scenario_transform_weekly_cancel_friday_full_day_with_fte_adjustment(
    day1_weekday=0,
    baseline_hours=18
):
    """Weekly Friday full day cancellation with FTE adjustment."""
    def _t(cfg: dict):
        # Apply full day cancellation
        base_transform = _scenario_transform_weekly_cancel_friday_full_day(day1_weekday)
        new_cfg = base_transform(cfg)
        
        # Calculate FTE adjustment for full day cancellation
        # Friday is completely off = lose 1/7 of weekly capacity
        dc_open = int(new_cfg.get('dc_open_time', 6)) 
        dc_close = int(new_cfg.get('dc_close_time', 24))
        daily_hours = dc_close - dc_open
        
        # Weekly reduction = 1 full day out of 7
        effective_weekly_hours = 6 * daily_hours  # 6 days instead of 7
        effective_daily_hours = effective_weekly_hours / 7
        
        # FTE adjustment ratio
        fte_adjustment = effective_daily_hours / baseline_hours
        new_cfg['fte_adjustment_ratio'] = max(0.1, min(1.0, fte_adjustment))
        
        return new_cfg
    return _t


def _scenario_transform_weekly_cancel_tue_thu_late_shift_with_fte_adjustment(
    day1_weekday=0,
    cancel_start_hour=15,
    baseline_hours=18
):
    """Weekly Tue+Thu late shift cancellation with FTE adjustment."""
    def _t(cfg: dict):
        # Apply Tue+Thu late shift cancellation
        base_transform = _scenario_transform_weekly_cancel_tue_thu_late_shift(day1_weekday, cancel_start_hour)
        new_cfg = base_transform(cfg)
        
        # Calculate FTE adjustment for 2 days per week late shift cancellation
        dc_close = int(new_cfg.get('dc_close_time', 24))
        cancelled_hours_per_day = dc_close - cancel_start_hour
        
        # 2 days per week cancellation
        weekly_cancelled_hours = 2 * cancelled_hours_per_day
        daily_reduction = weekly_cancelled_hours / 7
        
        dc_open = int(new_cfg.get('dc_open_time', 6))
        daily_hours = dc_close - dc_open
        effective_daily_hours = daily_hours - daily_reduction
        
        # FTE adjustment ratio
        fte_adjustment = effective_daily_hours / baseline_hours
        new_cfg['fte_adjustment_ratio'] = max(0.1, min(1.0, fte_adjustment))
        
        return new_cfg
    return _t


def _scenario_transform_biweekly_cancel_friday_late_shift(
    day1_weekday=0,
    start_week_index=1,
    cancel_start_hour=15,
    every_n_weeks=2
):
    """Scenario transform: keep baseline open hours, but cancel Friday late shift every N weeks.

    Assumptions per user:
    - Day1 is Monday (day1_weekday=0)
    - start from the 2nd Friday (start_week_index=1)
    - cancel window [15:00, dc_close_time)

    Note: This does NOT compress/shift demand timeslots; it only changes availability.
    """
    def _t(cfg: dict):
        new_cfg = dict(cfg)
        new_cfg['day1_weekday'] = int(day1_weekday)
        new_cfg['biweekly_shift_cancel'] = {
            'day1_weekday': int(day1_weekday),
            'weekday': 4,  # Friday
            'start_week_index': int(start_week_index),
            'every_n_weeks': int(every_n_weeks),
            'cancel_start_hour': int(cancel_start_hour),
            'cancel_end_hour': int(new_cfg.get('dc_close_time', 24)),
        }
        return new_cfg
    return _t


def _scenario_transform_weekly_cancel_friday_late_shift(
    day1_weekday=0,
    cancel_start_hour=15
):
    """Scenario transform: cancel Friday late shift every week (more aggressive)."""
    return _scenario_transform_biweekly_cancel_friday_late_shift(
        day1_weekday=day1_weekday,
        start_week_index=0,
        cancel_start_hour=cancel_start_hour,
        every_n_weeks=1
    )


def _scenario_transform_weekly_cancel_friday_full_day(
    day1_weekday=0,
):
    """Scenario transform: cancel the whole Friday operating window every week.

    For a scenario with open window [dc_open_time, dc_close_time), this sets Friday to be closed
    for the entire window.
    """
    def _t(cfg: dict):
        new_cfg = dict(cfg)
        dc_open = int(new_cfg.get('dc_open_time', 0))
        new_cfg['day1_weekday'] = int(day1_weekday)
        new_cfg['biweekly_shift_cancel'] = {
            'day1_weekday': int(day1_weekday),
            'weekday': 4,  # Friday
            'start_week_index': 0,
            'every_n_weeks': 1,
            'cancel_start_hour': dc_open,
            'cancel_end_hour': int(new_cfg.get('dc_close_time', 24)),
        }
        return new_cfg
    return _t


def _scenario_transform_weekly_cancel_tue_thu_late_shift(
    day1_weekday=0,
    cancel_start_hour=15,
):
    """Scenario transform: cancel Tue+Thu late shift every week.

    Weekday mapping: 0=Mon, 1=Tue, 3=Thu.
    Cancel window: [cancel_start_hour, dc_close_time).
    """
    def _t(cfg: dict):
        new_cfg = dict(cfg)
        new_cfg['day1_weekday'] = int(day1_weekday)
        cancel_end = int(new_cfg.get('dc_close_time', 24))
        new_cfg['shift_cancel_rules'] = [
            {
                'day1_weekday': int(day1_weekday),
                'weekday': 1,  # Tuesday
                'start_week_index': 0,
                'every_n_weeks': 1,
                'cancel_start_hour': int(cancel_start_hour),
                'cancel_end_hour': cancel_end,
            },
            {
                'day1_weekday': int(day1_weekday),
                'weekday': 3,  # Thursday
                'start_week_index': 0,
                'every_n_weeks': 1,
                'cancel_start_hour': int(cancel_start_hour),
                'cancel_end_hour': cancel_end,
            },
        ]
        return new_cfg
    return _t


# Alpha comparison charts function moved to scripts/fte_visualization.py


def visualize_fte_power_overlay_multi(
    all_results_base,
    all_results_by_label,
    label_base='Original',
    out_name='compare_fte_power_overlay_multi.png',
    show_value_labels=False,
    suptitle=None
):
    """Overlay comparison plot: baseline vs multiple FTE-adjusted variants.

    Note: scenario x-axis labels stay clean (no alpha); alpha appears only in the legend.
    """
    if not isinstance(all_results_by_label, dict) or not all_results_by_label:
        return

    # Keep scenario order stable and only include scenarios that exist in all series.
    scenario_set = set(all_results_base.keys())
    for res in all_results_by_label.values():
        scenario_set &= set(res.keys())
    scenarios = [s for s in all_results_base.keys() if s in scenario_set]

    def _clean_label(raw_name: str) -> str:
        m = re.search(r'\((\d{2}:\d{2}\s*-\s*\d{2}:\d{2})\)', raw_name or '')
        tr = m.group(1).replace(' ', '') if m else None
        if (raw_name or '').lower().startswith('baseline'):
            return f'Baseline {tr}' if tr else 'Baseline'
        return tr or (raw_name or '')

    def _get_completion(res, s):
        return float(res.get(s, {}).get('order_statistics', {}).get('completion_rate', 0.0))

    def _get_ot(res, s):
        os_ = res.get(s, {}).get('order_statistics', {})
        return float(os_.get('on_time_rate_all', os_.get('on_time_rate', 0.0)))

    labels = [_clean_label(SIMULATION_CONFIG[s]['name']) for s in scenarios]
    x = np.arange(len(labels))

    series_labels = [label_base] + list(all_results_by_label.keys())
    series_results = [all_results_base] + [all_results_by_label[k] for k in all_results_by_label.keys()]

    n = len(series_results)
    width = min(0.8 / max(n, 1), 0.25)
    offsets = (np.arange(n) - (n - 1) / 2.0) * width

    colors = ['#3498db', '#2ecc71', '#e67e22', '#9b59b6', '#34495e', '#1abc9c', '#e74c3c']

    fig_width = max(12, min(32, 1.7 * len(labels)))
    fig_height = 6.0
    if n >= 4:
        fig_height = 7.2
    fig, axes = plt.subplots(1, 2, figsize=(fig_width, fig_height), sharex=True)

    def _fmt_pct(v: float) -> str:
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return ''
        vv = float(v)
        if abs(vv - round(vv)) < 0.05:
            return f"{int(round(vv))}%"
        return f"{vv:.1f}%"

    def _annotate_containers(ax, containers, values_list):
        # Keep labels horizontal; avoid overlap by:
        # - smaller font
        # - light bbox for contrast
        # - staggering both dx and dy per series
        for idx, (cont, vals) in enumerate(zip(containers, values_list)):
            # dx in points, centered around 0
            dx = int(round((idx - (len(containers) - 1) / 2.0) * 3))
            dy = 2 + idx
            for rect, v in zip(cont, vals):
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    continue
                h = rect.get_height()
                ax.annotate(
                    _fmt_pct(v),
                    (rect.get_x() + rect.get_width() / 2.0, h),
                    xytext=(dx, dy),
                    textcoords='offset points',
                    ha='center',
                    va='bottom',
                    rotation=0,
                    fontsize=6 if n >= 4 else 8,
                    color='#2c3e50',
                    bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.75) if n >= 4 else None
                )

    ax = axes[0]
    containers_c = []
    values_c = []
    for i, (lbl, res) in enumerate(zip(series_labels, series_results)):
        vals = [_get_completion(res, s) for s in scenarios]
        cont = ax.bar(x + offsets[i], vals, width, label=lbl, color=colors[i % len(colors)])
        containers_c.append(cont)
        values_c.append(vals)
    ax.set_title('Completion Rate', fontweight='bold')
    ax.set_ylabel('Rate (%)')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)
    # Legend is handled at the figure level for multi-series plots.
    if n <= 3:
        ax.legend(fontsize=10, loc='upper right')

    if show_value_labels:
        _annotate_containers(ax, containers_c, values_c)

    ax = axes[1]
    containers_ot = []
    values_ot = []
    for i, (lbl, res) in enumerate(zip(series_labels, series_results)):
        vals = [_get_ot(res, s) for s in scenarios]
        cont = ax.bar(x + offsets[i], vals, width, label=lbl, color=colors[i % len(colors)])
        containers_ot.append(cont)
        values_ot.append(vals)
    ax.set_title('On-Time Rate (All Orders)', fontweight='bold')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)

    if show_value_labels:
        _annotate_containers(ax, containers_ot, values_ot)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha='right')

    if suptitle:
        fig.suptitle(str(suptitle), fontsize=14, fontweight='bold', y=0.995)

    if n >= 4:
        # Shared legend between title and plots (not on top of title).
        fig.legend(
            series_labels,
            loc='upper center',
            bbox_to_anchor=(0.5, 0.955),
            ncol=min(3, n),
            fontsize=10,
            frameon=False
        )
        plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
    else:
        plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.95] if suptitle else None)
    out_path = os.path.join(FIGURES_DIR, out_name)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"FTE power-law multi overlay chart saved: {out_path}")
    plt.close(fig)


def visualize_flow_kpis_overlay_across_scenarios_2x2_by_category(
    all_results_base,
    all_results_by_label,
    scenarios,
    category,
    label_base='Baseline',
    out_name='compare_flow_kpis_across_scenarios_2x2.png',
    show_value_labels=False
):
    """Bigger, readable by-flow plot: 2x2 panels per category.

    Layout:
      Row 0: Completion (Inbound, Outbound)
      Row 1: On-time (Inbound, Outbound)
    X-axis: scenarios (time windows)
    Bars: strategies (baseline + variants)
    """
    if not scenarios:
        return
    if category not in ('FG', 'RP'):
        return

    scenario_set = set(all_results_base.keys())
    for res in (all_results_by_label or {}).values():
        scenario_set &= set(res.keys())
    scenarios = [s for s in scenarios if s in scenario_set]
    if not scenarios:
        return

    def _get_os(res, s):
        return (res.get(s, {}) or {}).get('order_statistics', {}) or {}

    def _get(os_dict, key):
        try:
            v = os_dict.get(key)
            return float(v) if v is not None else np.nan
        except Exception:
            return np.nan

    def _fmt_pct(v: float) -> str:
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return ''
        vv = float(v)
        if abs(vv - round(vv)) < 0.05:
            return f"{int(round(vv))}%"
        return f"{vv:.1f}%"

    def _clean_scenario_name(scenario_key: str) -> str:
        raw = SIMULATION_CONFIG.get(scenario_key, {}).get('name', scenario_key)
        m = re.search(r'\((\d{2}:\d{2}\s*-\s*\d{2}:\d{2})\)', raw or '')
        tr = m.group(1).replace(' ', '') if m else None
        return tr or raw

    x_labels = [_clean_scenario_name(s) for s in scenarios]
    x = np.arange(len(scenarios))

    series_labels = [label_base] + list((all_results_by_label or {}).keys())
    series_results = [all_results_base] + [all_results_by_label[k] for k in (all_results_by_label or {}).keys()]
    n_series = len(series_results)
    width = min(0.8 / max(n_series, 1), 0.18)
    offsets = (np.arange(n_series) - (n_series - 1) / 2.0) * width
    colors = ['#3498db', '#e67e22', '#9b59b6', '#2ecc71', '#34495e', '#1abc9c', '#e74c3c']

    fig, axes = plt.subplots(2, 2, figsize=(16, 9), sharex=True, sharey=True)

    panels = [
        ('Inbound', f'{category}_inbound'),
        ('Outbound', f'{category}_outbound'),
    ]

    for col, (dir_name, prefix) in enumerate(panels):
        ax_c = axes[0, col]
        ax_ot = axes[1, col]

        containers_c, values_c = [], []
        containers_ot, values_ot = [], []
        for i, (lbl, res) in enumerate(zip(series_labels, series_results)):
            comp_vals, ot_vals = [], []
            for s in scenarios:
                os_ = _get_os(res, s)
                comp_vals.append(_get(os_, f'{prefix}_completion_rate'))
                ot_vals.append(_get(os_, f'{prefix}_on_time_rate_all'))
            cont_c = ax_c.bar(x + offsets[i], comp_vals, width, label=lbl, color=colors[i % len(colors)])
            cont_ot = ax_ot.bar(x + offsets[i], ot_vals, width, label=lbl, color=colors[i % len(colors)])
            containers_c.append(cont_c)
            values_c.append(comp_vals)
            containers_ot.append(cont_ot)
            values_ot.append(ot_vals)

        ax_c.set_title(f'{category} {dir_name} - Completion', fontweight='bold')
        ax_ot.set_title(f'{category} {dir_name} - On-time (All)', fontweight='bold')
        for ax in (ax_c, ax_ot):
            ax.set_ylim([0, 105])
            ax.grid(axis='y', alpha=0.25)
            ax.set_xticks(x)
            ax.set_xticklabels(x_labels, rotation=25, ha='right')

        if show_value_labels:
            for idx, (cont, vals) in enumerate(zip(containers_c, values_c)):
                dx = int(round((idx - (len(containers_c) - 1) / 2.0) * 3))
                dy = 2 + idx
                for rect, v in zip(cont, vals):
                    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                        continue
                    ax_c.annotate(
                        _fmt_pct(v),
                        (rect.get_x() + rect.get_width() / 2.0, rect.get_height()),
                        xytext=(dx, dy),
                        textcoords='offset points',
                        ha='center',
                        va='bottom',
                        rotation=0,
                        fontsize=7,
                        color='#2c3e50',
                        bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.75)
                    )
            for idx, (cont, vals) in enumerate(zip(containers_ot, values_ot)):
                dx = int(round((idx - (len(containers_ot) - 1) / 2.0) * 3))
                dy = 2 + idx
                for rect, v in zip(cont, vals):
                    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                        continue
                    ax_ot.annotate(
                        _fmt_pct(v),
                        (rect.get_x() + rect.get_width() / 2.0, rect.get_height()),
                        xytext=(dx, dy),
                        textcoords='offset points',
                        ha='center',
                        va='bottom',
                        rotation=0,
                        fontsize=7,
                        color='#2c3e50',
                        bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.75)
                    )

    fig.suptitle(f'{category} Flow KPIs Across Time Windows', fontsize=15, fontweight='bold', y=0.995)
    # Legend below title
    fig.legend(series_labels, loc='upper center', bbox_to_anchor=(0.5, 0.955), ncol=min(3, n_series), frameon=False)
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
    out_path = os.path.join(FIGURES_DIR, out_name)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"Flow KPI 2x2-by-category chart saved: {out_path}")
    plt.close(fig)


def visualize_flow_kpis_overlay_multi_runs(
    all_results_base,
    all_results_by_label,
    label_base='Baseline',
    out_name='compare_flow_kpis_overlay_multi.png',
    show_value_labels=False
):
    """Compare flow-level (category×direction) completion + on-time rates for baseline vs multiple variants."""
    if not isinstance(all_results_by_label, dict) or not all_results_by_label:
        return

    scenario_set = set(all_results_base.keys())
    for res in all_results_by_label.values():
        scenario_set &= set(res.keys())
    common = [s for s in all_results_base.keys() if s in scenario_set]
    if not common:
        return

    scenario = common[0]
    os_base = all_results_base.get(scenario, {}).get('order_statistics', {})

    flows = [
        ('FG Inbound', 'FG_inbound'),
        ('FG Outbound', 'FG_outbound'),
        ('RP Inbound', 'RP_inbound'),
        ('RP Outbound', 'RP_outbound'),
    ]

    def _get(os_dict, key):
        if not isinstance(os_dict, dict):
            return np.nan
        v = os_dict.get(key)
        if v is None:
            return np.nan
        try:
            return float(v)
        except Exception:
            return np.nan

    def _fmt_pct(v: float) -> str:
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return ''
        vv = float(v)
        if abs(vv - round(vv)) < 0.05:
            return f"{int(round(vv))}%"
        return f"{vv:.1f}%"

    labels = [name for name, _p in flows]
    x = np.arange(len(labels))

    series_labels = [label_base] + list(all_results_by_label.keys())
    series_os = [os_base] + [all_results_by_label[k].get(scenario, {}).get('order_statistics', {}) for k in all_results_by_label.keys()]
    n = len(series_os)
    width = min(0.8 / max(n, 1), 0.25)
    offsets = (np.arange(n) - (n - 1) / 2.0) * width
    colors = ['#3498db', '#e67e22', '#9b59b6', '#2ecc71', '#34495e']

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5), sharex=True)

    ax = axes[0]
    containers_c = []
    values_c = []
    for i, (lbl, os_dict) in enumerate(zip(series_labels, series_os)):
        vals = [_get(os_dict, f'{p}_completion_rate') for _n, p in flows]
        cont = ax.bar(x + offsets[i], vals, width, label=lbl, color=colors[i % len(colors)])
        containers_c.append(cont)
        values_c.append(vals)
    ax.set_title('Completion Rate by Flow', fontweight='bold')
    ax.set_ylabel('Rate (%)')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)
    ax.legend(fontsize=10, loc='upper right')

    if show_value_labels:
        for cont, vals in zip(containers_c, values_c):
            for rect, v in zip(cont, vals):
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    continue
                ax.annotate(
                    _fmt_pct(v),
                    (rect.get_x() + rect.get_width() / 2.0, rect.get_height()),
                    xytext=(0, 2),
                    textcoords='offset points',
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    color='#2c3e50'
                )

    ax = axes[1]
    containers_ot = []
    values_ot = []
    for i, (lbl, os_dict) in enumerate(zip(series_labels, series_os)):
        vals = [_get(os_dict, f'{p}_on_time_rate_all') for _n, p in flows]
        cont = ax.bar(x + offsets[i], vals, width, label=lbl, color=colors[i % len(colors)])
        containers_ot.append(cont)
        values_ot.append(vals)
    ax.set_title('On-Time Rate by Flow', fontweight='bold')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)

    if show_value_labels:
        for cont, vals in zip(containers_ot, values_ot):
            for rect, v in zip(cont, vals):
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    continue
                ax.annotate(
                    _fmt_pct(v),
                    (rect.get_x() + rect.get_width() / 2.0, rect.get_height()),
                    xytext=(0, 2),
                    textcoords='offset points',
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    color='#2c3e50'
                )

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha='right')

    plt.tight_layout()
    out_path = os.path.join(FIGURES_DIR, out_name)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"Flow KPI overlay chart saved: {out_path}")
    plt.close(fig)


def visualize_flow_kpis_overlay_multi_runs_per_scenario(
    all_results_base,
    all_results_by_label,
    scenarios,
    label_base='Baseline',
    out_prefix='compare_flow_kpis_overlay',
    show_value_labels=False
):
    """Generate flow KPI overlay charts for multiple scenarios (one figure per scenario).

    The existing `visualize_flow_kpis_overlay_multi_runs` is single-scenario oriented.
    This helper slices results by scenario and calls it repeatedly.
    """
    if not scenarios:
        return

    for s in scenarios:
        if s not in all_results_base:
            continue

        base_slice = {s: all_results_base[s]}
        var_slice = {}
        for lbl, res in (all_results_by_label or {}).items():
            if s in res:
                var_slice[lbl] = {s: res[s]}
        if not var_slice:
            continue

        safe = re.sub(r'[^a-zA-Z0-9_\-]+', '_', str(s))
        out_name = f"{out_prefix}_{safe}.png"
        visualize_flow_kpis_overlay_multi_runs(
            base_slice,
            var_slice,
            label_base=label_base,
            out_name=out_name,
            show_value_labels=show_value_labels
        )


def visualize_flow_kpis_overlay_across_scenarios_big(
    all_results_base,
    all_results_by_label,
    scenarios,
    label_base='Baseline',
    out_name='compare_flow_kpis_across_scenarios_big.png',
    show_value_labels=False
):
    """One big figure: flows as columns, (completion/on-time) as rows, x-axis=scenarios.

    This answers the request to avoid one-figure-per-scenario and instead produce a single large chart.
    """
    if not scenarios:
        return

    # Only keep scenarios that exist in all series.
    scenario_set = set(all_results_base.keys())
    for res in (all_results_by_label or {}).values():
        scenario_set &= set(res.keys())
    scenarios = [s for s in scenarios if s in scenario_set]
    if not scenarios:
        return

    flows = [
        ('FG Inbound', 'FG_inbound'),
        ('FG Outbound', 'FG_outbound'),
        ('RP Inbound', 'RP_inbound'),
        ('RP Outbound', 'RP_outbound'),
    ]

    def _get_os(res, s):
        return (res.get(s, {}) or {}).get('order_statistics', {}) or {}

    def _get(os_dict, key):
        try:
            v = os_dict.get(key)
            return float(v) if v is not None else np.nan
        except Exception:
            return np.nan

    def _fmt_pct(v: float) -> str:
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return ''
        vv = float(v)
        if abs(vv - round(vv)) < 0.05:
            return f"{int(round(vv))}%"
        return f"{vv:.1f}%"

    def _clean_scenario_name(scenario_key: str) -> str:
        raw = SIMULATION_CONFIG.get(scenario_key, {}).get('name', scenario_key)
        m = re.search(r'\((\d{2}:\d{2}\s*-\s*\d{2}:\d{2})\)', raw or '')
        tr = m.group(1).replace(' ', '') if m else None
        if tr:
            return tr
        return raw

    x_labels = [_clean_scenario_name(s) for s in scenarios]
    x = np.arange(len(scenarios))

    series_labels = [label_base] + list((all_results_by_label or {}).keys())
    series_results = [all_results_base] + [all_results_by_label[k] for k in (all_results_by_label or {}).keys()]
    n_series = len(series_results)
    width = min(0.8 / max(n_series, 1), 0.22)
    offsets = (np.arange(n_series) - (n_series - 1) / 2.0) * width
    colors = ['#3498db', '#e67e22', '#9b59b6', '#2ecc71', '#34495e', '#1abc9c', '#e74c3c']

    fig, axes = plt.subplots(2, 4, figsize=(22, 9), sharex=True, sharey='row')

    for col, (flow_name, prefix) in enumerate(flows):
        ax_c = axes[0, col]
        ax_ot = axes[1, col]

        containers_c = []
        values_c = []
        containers_ot = []
        values_ot = []

        for i, (lbl, res) in enumerate(zip(series_labels, series_results)):
            comp_vals = []
            ot_vals = []
            for s in scenarios:
                os_ = _get_os(res, s)
                comp_vals.append(_get(os_, f'{prefix}_completion_rate'))
                ot_vals.append(_get(os_, f'{prefix}_on_time_rate_all'))
            cont_c = ax_c.bar(x + offsets[i], comp_vals, width, label=lbl, color=colors[i % len(colors)])
            cont_ot = ax_ot.bar(x + offsets[i], ot_vals, width, label=lbl, color=colors[i % len(colors)])
            containers_c.append(cont_c)
            values_c.append(comp_vals)
            containers_ot.append(cont_ot)
            values_ot.append(ot_vals)

        ax_c.set_title(f'{flow_name}\nCompletion', fontweight='bold')
        ax_c.set_ylim([0, 105])
        ax_c.grid(axis='y', alpha=0.25)

        ax_ot.set_title(f'{flow_name}\nOn-time (All)', fontweight='bold')
        ax_ot.set_ylim([0, 105])
        ax_ot.grid(axis='y', alpha=0.25)

        if show_value_labels:
            for cont, vals in zip(containers_c, values_c):
                for rect, v in zip(cont, vals):
                    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                        continue
                    ax_c.annotate(
                        _fmt_pct(v),
                        (rect.get_x() + rect.get_width() / 2.0, rect.get_height()),
                        xytext=(0, 2),
                        textcoords='offset points',
                        ha='center',
                        va='bottom',
                        fontsize=7,
                        color='#2c3e50'
                    )
            for cont, vals in zip(containers_ot, values_ot):
                for rect, v in zip(cont, vals):
                    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                        continue
                    ax_ot.annotate(
                        _fmt_pct(v),
                        (rect.get_x() + rect.get_width() / 2.0, rect.get_height()),
                        xytext=(0, 2),
                        textcoords='offset points',
                        ha='center',
                        va='bottom',
                        fontsize=7,
                        color='#2c3e50'
                    )

        for ax in (ax_c, ax_ot):
            ax.set_xticks(x)
            ax.set_xticklabels(x_labels, rotation=25, ha='right')

    axes[0, 0].set_ylabel('Rate (%)')
    axes[1, 0].set_ylabel('Rate (%)')

    # Single shared legend (use the top-left axis)
    axes[0, 0].legend(fontsize=10, loc='upper left', bbox_to_anchor=(0.0, 1.35), ncol=min(4, n_series))

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out_path = os.path.join(FIGURES_DIR, out_name)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"Flow KPI big overlay chart saved: {out_path}")
    plt.close(fig)


def visualize_flow_kpis_overlay_two_runs(
    all_results_base,
    all_results_variant,
    label_base='Baseline',
    label_variant='Variant',
    out_name='compare_flow_kpis_overlay.png'
):
    """Compare flow-level (category×direction) completion + on-time rates for two runs.

    Uses `order_statistics` keys:
      - {prefix}_completion_rate
      - {prefix}_on_time_rate_all
    where prefix ∈ {FG_inbound, FG_outbound, RP_inbound, RP_outbound}.
    """
    common = [s for s in all_results_base.keys() if s in all_results_variant]
    if not common:
        return

    # If multiple scenarios exist, pick the first (this helper is intended for single-scenario overlays).
    scenario = common[0]
    os_base = all_results_base.get(scenario, {}).get('order_statistics', {})
    os_var = all_results_variant.get(scenario, {}).get('order_statistics', {})

    flows = [
        ('FG Inbound', 'FG_inbound'),
        ('FG Outbound', 'FG_outbound'),
        ('RP Inbound', 'RP_inbound'),
        ('RP Outbound', 'RP_outbound'),
    ]

    def _get(os_dict, key):
        if not isinstance(os_dict, dict):
            return np.nan
        v = os_dict.get(key)
        if v is None:
            return np.nan
        try:
            return float(v)
        except Exception:
            return np.nan

    labels = [name for name, _p in flows]
    x = np.arange(len(labels))
    width = 0.38

    base_completion = [_get(os_base, f'{p}_completion_rate') for _n, p in flows]
    var_completion = [_get(os_var, f'{p}_completion_rate') for _n, p in flows]
    base_ot = [_get(os_base, f'{p}_on_time_rate_all') for _n, p in flows]
    var_ot = [_get(os_var, f'{p}_on_time_rate_all') for _n, p in flows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True)

    ax = axes[0]
    ax.bar(x - width/2, base_completion, width, label=label_base, color='#3498db')
    ax.bar(x + width/2, var_completion, width, label=label_variant, color='#e67e22')
    ax.set_title('Completion Rate by Flow', fontweight='bold')
    ax.set_ylabel('Rate (%)')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)
    ax.legend(fontsize=10, loc='upper right')

    ax = axes[1]
    ax.bar(x - width/2, base_ot, width, label=label_base, color='#3498db')
    ax.bar(x + width/2, var_ot, width, label=label_variant, color='#e67e22')
    ax.set_title('On-Time Rate by Flow', fontweight='bold')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha='right')

    plt.tight_layout()
    out_path = os.path.join(FIGURES_DIR, out_name)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"Flow KPI overlay chart saved: {out_path}")
    plt.close(fig)

def visualize_fte_power_overlay(all_results_base, all_results_power, label_base='Original', label_power='FTE-adjusted'):
    """Overlay comparison plot (no alpha in labels): Original vs FTE-adjusted for each scenario."""
    scenarios = [s for s in all_results_base.keys() if s in all_results_power]

    def _clean_label(raw_name: str) -> str:
        m = re.search(r'\((\d{2}:\d{2}\s*-\s*\d{2}:\d{2})\)', raw_name or '')
        tr = m.group(1).replace(' ', '') if m else None
        if (raw_name or '').lower().startswith('baseline'):
            return f'Baseline {tr}' if tr else 'Baseline'
        return tr or (raw_name or '')

    labels = [_clean_label(SIMULATION_CONFIG[s]['name']) for s in scenarios]
    x = np.arange(len(labels))
    width = 0.38

    fig_width = max(12, min(28, 1.7 * len(labels)))
    fig, axes = plt.subplots(1, 2, figsize=(fig_width, 6), sharex=True)

    # Completion rate
    base_c = [float(all_results_base[s].get('order_statistics', {}).get('completion_rate', 0.0)) for s in scenarios]
    pow_c = [float(all_results_power[s].get('order_statistics', {}).get('completion_rate', 0.0)) for s in scenarios]

    ax = axes[0]
    ax.bar(x - width/2, base_c, width, label=label_base, color='#3498db')
    ax.bar(x + width/2, pow_c, width, label=label_power, color='#2ecc71')
    ax.set_title('Completion Rate', fontweight='bold')
    ax.set_ylabel('Rate (%)')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)
    ax.legend(fontsize=10, loc='upper right')

    # On-time rate (all orders)
    def _get_ot(res, s):
        os_ = res.get(s, {}).get('order_statistics', {})
        return float(os_.get('on_time_rate_all', os_.get('on_time_rate', 0.0)))

    base_ot = [_get_ot(all_results_base, s) for s in scenarios]
    pow_ot = [_get_ot(all_results_power, s) for s in scenarios]

    ax = axes[1]
    ax.bar(x - width/2, base_ot, width, label=label_base, color='#3498db')
    ax.bar(x + width/2, pow_ot, width, label=label_power, color='#2ecc71')
    ax.set_title('On-Time Rate (All Orders)', fontweight='bold')
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.25)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha='right')

    plt.tight_layout()
    out_path = os.path.join(FIGURES_DIR, 'compare_fte_power_overlay.png')
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"FTE power-law overlay chart saved: {out_path}")
    plt.close(fig)


# ==================== 可视化 ====================

# FTE utilization charts function moved to scripts/fte_visualization.py


# FTE usage charts function moved to scripts/fte_visualization.py


# FTE results export function moved to scripts/fte_visualization.py

def export_fte_results_to_excel(comparison_df, output_suffix=''):
    """Export FTE-related results to a separate Excel file for fte_visualization.py"""
    scenarios = comparison_df.index.tolist()
    
    # Collect FTE-related columns
    fte_columns = [col for col in comparison_df.columns if 'fte' in col.lower()]
    
    if not fte_columns:
        print("No FTE data available for export.")
        return
    
    fte_path = os.path.join(RESULTS_DIR, f'fte_results{output_suffix}.xlsx')
    
    try:
        with pd.ExcelWriter(fte_path, engine='openpyxl') as writer:
            # Sheet 1: Summary - overall FTE metrics
            summary_data = {
                'Scenario': scenarios,
                'Total FTE Available': list(comparison_df.get('total_fte_available', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'Total FTE Used': list(comparison_df.get('total_fte_used', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'Total FTE Needed': list(comparison_df.get('total_fte_needed', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'Overall Utilization Rate (%)': [r * 100 for r in comparison_df.get('overall_fte_utilization_rate', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Sheet 2: FG Details
            fg_data = {
                'Scenario': scenarios,
                'FG Inbound Available': list(comparison_df.get('FG_inbound_fte_available', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'FG Inbound Used': list(comparison_df.get('FG_inbound_fte_used', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'FG Inbound Needed': list(comparison_df.get('FG_inbound_fte_needed', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'FG Inbound Utilization (%)': [r * 100 for r in comparison_df.get('FG_inbound_fte_utilization_rate', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)],
                'FG Outbound Available': list(comparison_df.get('FG_outbound_fte_available', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'FG Outbound Used': list(comparison_df.get('FG_outbound_fte_used', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'FG Outbound Needed': list(comparison_df.get('FG_outbound_fte_needed', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'FG Outbound Utilization (%)': [r * 100 for r in comparison_df.get('FG_outbound_fte_utilization_rate', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)],
            }
            fg_df = pd.DataFrame(fg_data)
            fg_df.to_excel(writer, sheet_name='FG Details', index=False)
            
            # Sheet 3: R&P Details
            rp_data = {
                'Scenario': scenarios,
                'R&P Inbound Available': list(comparison_df.get('R&P_inbound_fte_available', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'R&P Inbound Used': list(comparison_df.get('R&P_inbound_fte_used', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'R&P Inbound Needed': list(comparison_df.get('R&P_inbound_fte_needed', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'R&P Inbound Utilization (%)': [r * 100 for r in comparison_df.get('R&P_inbound_fte_utilization_rate', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)],
                'R&P Outbound Available': list(comparison_df.get('R&P_outbound_fte_available', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'R&P Outbound Used': list(comparison_df.get('R&P_outbound_fte_used', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'R&P Outbound Needed': list(comparison_df.get('R&P_outbound_fte_needed', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)),
                'R&P Outbound Utilization (%)': [r * 100 for r in comparison_df.get('R&P_outbound_fte_utilization_rate', pd.Series([0] * len(scenarios))).fillna(0).infer_objects(copy=False)],
            }
            rp_df = pd.DataFrame(rp_data)
            rp_df.to_excel(writer, sheet_name='R&P Details', index=False)
            
            # Sheet 4: Full Data - all FTE columns
            full_fte_df = comparison_df[fte_columns].copy()
            full_fte_df.index.name = 'Scenario'
            full_fte_df.to_excel(writer, sheet_name='Full Data')
        
        print(f"FTE results exported to: {fte_path}")
        
    except Exception as e:
        print(f"Error exporting FTE results: {e}")


def visualize_results(comparison_df, all_results=None):
    """生成可视化图表"""
    scenarios = comparison_df.index.tolist()

    def _clean_scenario_label(raw_name: str) -> str:
        if not raw_name:
            return ''
        # Extract time range in parentheses, if any.
        m = re.search(r'\((\d{2}:\d{2}\s*-\s*\d{2}:\d{2})\)', raw_name)
        time_range = m.group(1).replace(' ', '') if m else None
        if raw_name.lower().startswith('baseline'):
            return f'Baseline {time_range}' if time_range else 'Baseline'

        # Remove words like "Fixed Start" / "Shifted" from labels.
        if time_range:
            return time_range
        cleaned = raw_name
        cleaned = re.sub(r'(?i)\bfixed\s*start\b', '', cleaned)
        cleaned = re.sub(r'(?i)\bshifted\b', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -')
        return cleaned

    scenario_labels = [_clean_scenario_label(SIMULATION_CONFIG[s]['name']) for s in scenarios]
    
    print(f"\n{'='*70}\n生成基础可视化图表...\n{'='*70}")
    
    # 提取 hourly 数据用于时段分析
    hourly_data_all = {}
    if all_results:
        for scenario in scenarios:
            if scenario in all_results and 'hourly_dock_utilization' in all_results[scenario]:
                hourly_data_all[scenario] = all_results[scenario]['hourly_dock_utilization']
    
    # 图 1: 完成率 + 准时率（所有订单口径）
    fig_width = max(12, min(26, 1.6 * len(scenarios)))
    fig, ax = plt.subplots(figsize=(fig_width, 6))

    completion_rates = [all_results[s].get('order_statistics', {}).get('completion_rate', 0) for s in scenarios]
    on_time_rates_all = [
        all_results[s].get('order_statistics', {}).get('on_time_rate_all', all_results[s].get('order_statistics', {}).get('on_time_rate', 0))
        for s in scenarios
    ]

    x = np.arange(len(scenario_labels))
    width = 0.38

    bars1 = ax.bar(x - width/2, completion_rates, width, label='Completion Rate', color='#3498db')
    bars2 = ax.bar(x + width/2, on_time_rates_all, width, label='On Time Rate (All Orders)', color='#2ecc71')

    ax.set_ylabel('Rate (%)', fontsize=12)
    ax.set_title('Completion & On-Time Rate Comparison (All Orders)', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels, rotation=30, ha='right')
    ax.set_ylim([0, 105])
    ax.legend(fontsize=11, loc='upper right')
    ax.grid(axis='y', alpha=0.3)

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    path1 = os.path.join(FIGURES_DIR, '1_completion_on_time_rate.png')
    plt.savefig(path1, dpi=300, bbox_inches='tight')
    print(f"Completion & on-time rate chart saved: {path1}")
    plt.close()

    # 图 1 (split): Completion rate by flow (FG/R&P × Inbound/Outbound)
    fig, axes = plt.subplots(2, 2, figsize=(16, 9), sharey=True)
    axes = axes.flatten()
    flow_panels = [
        ('FG Inbound', 'FG_inbound_completion_rate', '#3498db'),
        ('FG Outbound', 'FG_outbound_completion_rate', '#5dade2'),
        ('R&P Inbound', 'RP_inbound_completion_rate', '#e74c3c'),
        ('R&P Outbound', 'RP_outbound_completion_rate', '#ec7063'),
    ]
    for ax, (title, key, color) in zip(axes, flow_panels):
        vals = [all_results[s].get('order_statistics', {}).get(key, 0.0) for s in scenarios]
        bars = ax.bar(np.arange(len(scenario_labels)), vals, color=color, alpha=0.9)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(len(scenario_labels)))
        ax.set_xticklabels(scenario_labels, rotation=15, ha='right', fontsize=9)
        ax.set_ylim([0, 105])
        ax.grid(axis='y', alpha=0.25)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    fig.suptitle('Completion Rate by Flow (Scoped Orders)', fontsize=15, fontweight='bold', y=0.98)
    fig.text(0.04, 0.5, 'Completion Rate (%)', va='center', rotation='vertical', fontsize=12)
    plt.tight_layout(rect=[0.05, 0.04, 1, 0.95])
    path1_split_c = os.path.join(FIGURES_DIR, '1_completion_rate_by_flow.png')
    plt.savefig(path1_split_c, dpi=300, bbox_inches='tight')
    print(f"Completion rate by flow chart saved: {path1_split_c}")
    plt.close()

    # 图 1 (split): On-time rate by flow (FG/R&P × Inbound/Outbound)
    # 注意：Inbound on-time 采用 24h processing deadline 口径（processing_end_time <= processing_deadline）。
    fig, axes = plt.subplots(2, 2, figsize=(16, 9), sharey=True)
    axes = axes.flatten()
    flow_panels_ot = [
        ('FG Inbound (<=24h)', 'FG_inbound_on_time_rate_all', '#3498db'),
        ('FG Outbound (Timeslot)', 'FG_outbound_on_time_rate_all', '#5dade2'),
        ('R&P Inbound (<=24h)', 'RP_inbound_on_time_rate_all', '#e74c3c'),
        ('R&P Outbound (Timeslot)', 'RP_outbound_on_time_rate_all', '#ec7063'),
    ]
    for ax, (title, key, color) in zip(axes, flow_panels_ot):
        vals = [all_results[s].get('order_statistics', {}).get(key, 0.0) for s in scenarios]
        bars = ax.bar(np.arange(len(scenario_labels)), vals, color=color, alpha=0.9)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(len(scenario_labels)))
        ax.set_xticklabels(scenario_labels, rotation=15, ha='right', fontsize=9)
        ax.set_ylim([0, 105])
        ax.grid(axis='y', alpha=0.25)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    fig.suptitle('On-Time Rate by Flow (Scoped Orders)', fontsize=15, fontweight='bold', y=0.98)
    fig.text(0.04, 0.5, 'On-Time Rate (%)', va='center', rotation='vertical', fontsize=12)
    plt.tight_layout(rect=[0.05, 0.04, 1, 0.95])
    path1_split_ot = os.path.join(FIGURES_DIR, '1_on_time_rate_by_flow.png')
    plt.savefig(path1_split_ot, dpi=300, bbox_inches='tight')
    print(f"On-time rate by flow chart saved: {path1_split_ot}")
    plt.close()

    # 图 1a: Day1 -> Day2 reschedule（原定第1天，实际第2天才完成）
    fig, ax1 = plt.subplots(figsize=(12, 6))

    day1_to_day2_counts = [
        all_results[s].get('order_statistics', {}).get('day1_to_day2_outbound_orders', 0)
        for s in scenarios
    ]
    day1_to_day2_rates = [
        all_results[s].get('order_statistics', {}).get('day1_to_day2_outbound_rate', 0.0)
        for s in scenarios
    ]

    x = np.arange(len(scenario_labels))
    width = 0.38

    bars_count = ax1.bar(
        x - width/2, day1_to_day2_counts, width,
        label='Orders (Day1 scheduled -> Day2 completed)',
        color='#9b59b6'
    )
    ax1.set_ylabel('Orders (#)', fontsize=12)
    ax1.grid(axis='y', alpha=0.3)

    ax2 = ax1.twinx()
    bars_rate = ax2.bar(
        x + width/2, day1_to_day2_rates, width,
        label='Rate (of Day1 scheduled)',
        color='#f39c12', alpha=0.9
    )
    ax2.set_ylabel('Rate (%)', fontsize=12)
    ax2.set_ylim([0, 105])

    ax1.set_title('Day1→Day2 Rescheduled Volume & Rate (Outbound)', fontsize=14, fontweight='bold', pad=20)
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenario_labels, rotation=15, ha='right')

    # Left axis range for counts
    max_count = max([float(c) for c in day1_to_day2_counts], default=0.0)
    ax1.set_ylim([0, max(1.0, max_count * 1.25)])

    # Combined legend
    ax1.legend([bars_count, bars_rate], ['Orders', 'Rate (%)'], fontsize=11, loc='upper right')

    for bar in bars_count:
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width()/2., height,
            f'{height:.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold'
        )
    for bar in bars_rate:
        height = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width()/2., height,
            f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold'
        )

    plt.tight_layout()
    path1a = os.path.join(FIGURES_DIR, '1a_day1_to_day2_rescheduled.png')
    plt.savefig(path1a, dpi=300, bbox_inches='tight')
    print(f"Day1->Day2 rescheduled chart saved: {path1a}")
    plt.close()
    
    # 图 1b: 准时率按地区分解
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    g2_rates = comparison_df['G2_on_time_rate'] * 100
    row_rates = comparison_df['ROW_on_time_rate'] * 100
    g2_stds = comparison_df.get('G2_on_time_rate_std', pd.Series([0]*len(scenarios))) * 100
    row_stds = comparison_df.get('ROW_on_time_rate_std', pd.Series([0]*len(scenarios))) * 100
    
    bars1 = ax.bar(x - width/2, g2_rates, width, label='G2 Region', 
                   color='#3498db', yerr=g2_stds, capsize=5)
    bars2 = ax.bar(x + width/2, row_rates, width, label='ROW Region', 
                   color='#e74c3c', yerr=row_stds, capsize=5)
    
    ax.set_ylabel('On Time Rate (%)', fontsize=12)
    ax.set_title('On Time Rate by Region (G2 vs ROW)', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax.set_ylim([0, 105])
    ax.legend(fontsize=11, loc='lower left')
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    for bar in bars2:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    path1b = os.path.join(FIGURES_DIR, '1b_sla_by_region.png')
    plt.savefig(path1b, dpi=300, bbox_inches='tight')
    print(f"SLA by region chart saved: {path1b}")
    plt.close()
    
    # Figure 2: Flow Statistics (Stacked Bars)
    fig, ax = plt.subplots(figsize=(12, 7))
    
    fg_inbound = comparison_df['FG_inbound_pallets']
    fg_outbound = comparison_df['FG_outbound_pallets']
    rp_inbound = comparison_df['R&P_inbound_pallets']
    rp_outbound = comparison_df['R&P_outbound_pallets']
    
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, fg_inbound, width, label='FG Inbound', color='#3498db')
    bars2 = ax.bar(x - width/2, fg_outbound, width, bottom=fg_inbound, label='FG Outbound', color='#5dade2')
    bars3 = ax.bar(x + width/2, rp_inbound, width, label='R&P Inbound', color='#e74c3c')
    bars4 = ax.bar(x + width/2, rp_outbound, width, bottom=rp_inbound, label='R&P Outbound', color='#ec7063')
    
    ax.set_ylabel('Number of Pallets', fontsize=12)
    ax.set_title('Flow Statistics Comparison (by Product Category)', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    
    for i in range(len(scenario_labels)):
        fg_in = fg_inbound.iloc[i]
        if fg_in > 0:
            ax.text(i - width/2, fg_in/2, f'{fg_in/1000:.1f}k', 
                    ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        fg_out = fg_outbound.iloc[i]
        if fg_out > 0:
            ax.text(i - width/2, fg_in + fg_out/2, f'{fg_out/1000:.1f}k', 
                    ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        rp_in = rp_inbound.iloc[i]
        if rp_in > 0:
            ax.text(i + width/2, rp_in/2, f'{rp_in/1000:.1f}k', 
                    ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        rp_out = rp_outbound.iloc[i]
        if rp_out > 0:
            ax.text(i + width/2, rp_in + rp_out/2, f'{rp_out/1000:.1f}k', 
                    ha='center', va='center', fontsize=8, color='white', fontweight='bold')
    
    plt.tight_layout()
    path4 = os.path.join(FIGURES_DIR, '2_flow_statistics.png')
    plt.savefig(path4, dpi=300, bbox_inches='tight')
    print(f"Flow statistics chart saved: {path4}")
    plt.close()
    
    # Figure 2b: FG Outbound by Region (Pallets)
    fig, ax = plt.subplots(figsize=(12, 7))
    
    fg_g2_outbound = comparison_df['FG_G2_outbound_pallets']
    fg_row_outbound = comparison_df['FG_ROW_outbound_pallets']
    
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, fg_g2_outbound, width, label='FG G2 Region Outbound', color='#3498db')
    bars2 = ax.bar(x + width/2, fg_row_outbound, width, label='FG ROW Region Outbound', color='#5dade2')
    
    ax.set_ylabel('Number of Pallets', fontsize=12)
    ax.set_title('FG Outbound Flow by Region', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax.legend(fontsize=11, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height/1000:.1f}k', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    for bar in bars2:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height/1000:.1f}k', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path4b = os.path.join(FIGURES_DIR, '2b_fg_outbound_by_region.png')
    plt.savefig(path4b, dpi=300, bbox_inches='tight')
    print(f"FG outbound flow by region chart saved: {path4b}")
    plt.close()
    
    # Figure 2c: Orders vs Pallets Flow Comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    fg_inbound_pallets = comparison_df['FG_inbound_pallets']
    fg_outbound_pallets = comparison_df['FG_outbound_pallets']
    rp_inbound_pallets = comparison_df['R&P_inbound_pallets']
    rp_outbound_pallets = comparison_df['R&P_outbound_pallets']
    
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, fg_inbound_pallets, width, label='FG Inbound', color='#3498db')
    bars2 = ax1.bar(x - width/2, fg_outbound_pallets, width, bottom=fg_inbound_pallets, label='FG Outbound', color='#5dade2')
    bars3 = ax1.bar(x + width/2, rp_inbound_pallets, width, label='R&P Inbound', color='#e74c3c')
    bars4 = ax1.bar(x + width/2, rp_outbound_pallets, width, bottom=rp_inbound_pallets, label='R&P Outbound', color='#ec7063')
    
    ax1.set_ylabel('Number of Pallets', fontsize=12)
    ax1.set_title('Flow Statistics Comparison - Pallets', fontsize=13, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax1.legend(fontsize=10, loc='upper right')
    ax1.grid(axis='y', alpha=0.3)
    
    for i in range(len(scenario_labels)):
        fg_in = fg_inbound_pallets.iloc[i]
        if fg_in > 0:
            ax1.text(i - width/2, fg_in/2, f'{fg_in/1000:.1f}k', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        fg_out = fg_outbound_pallets.iloc[i]
        if fg_out > 0:
            ax1.text(i - width/2, fg_in + fg_out/2, f'{fg_out/1000:.1f}k', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        rp_in = rp_inbound_pallets.iloc[i]
        if rp_in > 0:
            ax1.text(i + width/2, rp_in/2, f'{rp_in/1000:.1f}k', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        rp_out = rp_outbound_pallets.iloc[i]
        if rp_out > 0:
            ax1.text(i + width/2, rp_in + rp_out/2, f'{rp_out/1000:.1f}k', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
    
    fg_inbound_orders = comparison_df['FG_inbound_orders']
    fg_outbound_orders = comparison_df['FG_outbound_orders']
    rp_inbound_orders = comparison_df['R&P_inbound_orders']
    rp_outbound_orders = comparison_df['R&P_outbound_orders']
    
    bars5 = ax2.bar(x - width/2, fg_inbound_orders, width, label='FG Inbound', color='#3498db')
    bars6 = ax2.bar(x - width/2, fg_outbound_orders, width, bottom=fg_inbound_orders, label='FG Outbound', color='#5dade2')
    bars7 = ax2.bar(x + width/2, rp_inbound_orders, width, label='R&P Inbound', color='#e74c3c')
    bars8 = ax2.bar(x + width/2, rp_outbound_orders, width, bottom=rp_inbound_orders, label='R&P Outbound', color='#ec7063')
    
    ax2.set_ylabel('Number of Orders', fontsize=12)
    ax2.set_title('Flow Statistics Comparison - Orders', fontsize=13, fontweight='bold', pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax2.legend(fontsize=10, loc='upper right')
    ax2.grid(axis='y', alpha=0.3)
    
    for i in range(len(scenario_labels)):
        fg_in = fg_inbound_orders.iloc[i]
        if fg_in > 0:
            ax2.text(i - width/2, fg_in/2, f'{fg_in:.0f}', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        fg_out = fg_outbound_orders.iloc[i]
        if fg_out > 0:
            ax2.text(i - width/2, fg_in + fg_out/2, f'{fg_out:.0f}', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        rp_in = rp_inbound_orders.iloc[i]
        if rp_in > 0:
            ax2.text(i + width/2, rp_in/2, f'{rp_in:.0f}', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        rp_out = rp_outbound_orders.iloc[i]
        if rp_out > 0:
            ax2.text(i + width/2, rp_in + rp_out/2, f'{rp_out:.0f}', ha='center', va='center', fontsize=8, color='white', fontweight='bold')
    
    plt.tight_layout()
    path4c = os.path.join(FIGURES_DIR, '2c_flow_statistics_orders.png')
    plt.savefig(path4c, dpi=300, bbox_inches='tight')
    print(f"Orders flow statistics chart saved: {path4c}")
    plt.close()
    
    # Figure 2d: FG Outbound by Region (Orders)
    fig, ax = plt.subplots(figsize=(12, 7))
    
    fg_g2_orders = comparison_df['FG_G2_outbound_orders']
    fg_row_orders = comparison_df['FG_ROW_outbound_orders']
    
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, fg_g2_orders, width, label='FG G2 Region Outbound', color='#3498db')
    bars2 = ax.bar(x + width/2, fg_row_orders, width, label='FG ROW Region Outbound', color='#5dade2')
    
    ax.set_ylabel('Number of Orders', fontsize=12)
    ax.set_title('FG Outbound Orders by Region', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax.legend(fontsize=11, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    for bar in bars2:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path4d = os.path.join(FIGURES_DIR, '2d_fg_outbound_orders_by_region.png')
    plt.savefig(path4d, dpi=300, bbox_inches='tight')
    print(f"FG outbound orders by region chart saved: {path4d}")
    plt.close()
    
    # Figure 3: Timeslot Dock Utilization Rate (by Direction)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    fg_inbound_util = comparison_df['FG_inbound_utilization'] * 100
    fg_outbound_util = comparison_df['FG_outbound_utilization'] * 100
    
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, fg_inbound_util, width, label='FG Inbound (Reception)', color='#3498db')
    bars2 = ax1.bar(x + width/2, fg_outbound_util, width, label='FG Outbound (Loading)', color='#5dade2')
    
    ax1.set_ylabel('Utilization Rate (%)', fontsize=12)
    ax1.set_title('FG Dock Utilization (Inbound vs Outbound)', fontsize=13, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax1.legend(fontsize=10)
    ax1.grid(axis='y', alpha=0.3)
    
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    
    rp_inbound_util = comparison_df['R&P_inbound_utilization'] * 100
    rp_outbound_util = comparison_df['R&P_outbound_utilization'] * 100
    
    bars3 = ax2.bar(x - width/2, rp_inbound_util, width, label='R&P Inbound (Reception)', color='#e74c3c')
    bars4 = ax2.bar(x + width/2, rp_outbound_util, width, label='R&P Outbound (Loading)', color='#ec7063')
    
    ax2.set_ylabel('Utilization Rate (%)', fontsize=12)
    ax2.set_title('R&P Dock Utilization (Inbound vs Outbound)', fontsize=13, fontweight='bold', pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenario_labels, rotation=15, ha='right')
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3)
    
    for bars in [bars3, bars4]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    
    fig.suptitle('Timeslot Dock Utilization Comparison (by Direction)', fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout()
    path5 = os.path.join(FIGURES_DIR, '3_timeslot_utilization.png')
    plt.savefig(path5, dpi=300, bbox_inches='tight')
    print(f"Timeslot utilization chart saved: {path5}")
    plt.close()
    
    # Figure 3b: Dock Utilization by Time Slot (4 category charts, 2x2 bar subplots per scenario)
    if hourly_data_all:
        import math
        from matplotlib.gridspec import GridSpec

        # Each scenario is shown as a compact 2x2 panel (FG/R&P × In/Out).
        panels = [
            ('FG', 'inbound', 'FG In', '#4A90E2', '#E8F4FF'),
            ('FG', 'outbound', 'FG Out', '#50C878', '#E8F8F0'),
            ('R&P', 'inbound', 'RP In', '#E74C3C', '#FDECEA'),
            ('R&P', 'outbound', 'RP Out', '#F39C12', '#FEF5E7')
        ]

        scenarios_per_page = 6  # was 4; shrink panels to reduce number of pages/images
        scenario_chunks = [scenarios[i:i+scenarios_per_page] for i in range(0, len(scenarios), scenarios_per_page)]
        hours = list(range(24))
        xticks = [0, 6, 12, 18, 23]

        def _plot_one_panel(ax, hourly_dict, color_used, color_avail, title, show_legend=False):
            available_caps = []
            used_caps = []
            util_rates = []
            for h in hours:
                d = hourly_dict.get(h)
                if not d:
                    available_caps.append(0.0)
                    used_caps.append(0.0)
                    util_rates.append(np.nan)
                    continue
                avail = float(d.get('available', 0) or 0)
                used = float(d.get('used', 0) or 0)
                available_caps.append(avail)
                used_caps.append(used)
                if avail > 0:
                    util_rates.append(used / avail * 100)
                elif used > 0:
                    util_rates.append(0.0)
                else:
                    util_rates.append(np.nan)

            bars_avail = ax.bar(hours, available_caps, color=color_avail, alpha=1.0, edgecolor='white', linewidth=0.3)
            bars_used = ax.bar(hours, used_caps, color=color_used, alpha=0.7, edgecolor='white', linewidth=0.3)

            ax2 = ax.twinx()
            (line_util,) = ax2.plot(hours, util_rates, color='#2c3e50', linewidth=1.0)
            ax2.set_ylim([0, 105])
            ax2.set_yticks([0, 50, 100])
            ax2.tick_params(axis='y', labelsize=7)
            ax2.grid(False)

            ax.set_title(title, fontsize=9, fontweight='bold', pad=2)
            ax.set_xticks(xticks)
            ax.tick_params(axis='x', labelsize=7)
            ax.tick_params(axis='y', labelsize=7)
            ax.grid(axis='y', alpha=0.2, linestyle='--', linewidth=0.6)

            if show_legend:
                ax.legend([bars_avail, bars_used, line_util], ['Available', 'Used', 'Util%'], fontsize=8, loc='upper left')

        for page_idx, scenario_chunk in enumerate(scenario_chunks, start=1):
            n = len(scenario_chunk)
            ncols = 3
            nrows = int(math.ceil(n / ncols))

            # Each scenario consumes a 2x2 block in the overall GridSpec.
            fig = plt.figure(figsize=(18, 4.8 * nrows))
            gs = GridSpec(2 * nrows, 2 * ncols, figure=fig, wspace=0.15, hspace=0.35)

            has_any = False
            legend_done = False

            for idx, scenario in enumerate(scenario_chunk):
                block_r = (idx // ncols) * 2
                block_c = (idx % ncols) * 2
                scenario_label = _clean_scenario_label(SIMULATION_CONFIG[scenario]['name'])

                # Scenario title on the block (use the top-left axis)
                for p_idx, (category, direction, panel_title, color_used, color_avail) in enumerate(panels):
                    rr = block_r + (p_idx // 2)
                    cc = block_c + (p_idx % 2)
                    ax = fig.add_subplot(gs[rr, cc])

                    key = f'{category}_{direction}'
                    hourly_dict = hourly_data_all.get(scenario, {}).get(key)
                    if not hourly_dict:
                        ax.set_axis_off()
                        continue

                    title = panel_title
                    if p_idx == 0:
                        title = f'{scenario_label}\n{panel_title}'

                    _plot_one_panel(
                        ax,
                        hourly_dict,
                        color_used=color_used,
                        color_avail=color_avail,
                        title=title,
                        show_legend=(not legend_done)
                    )
                    legend_done = True
                    has_any = True

            if not has_any:
                plt.close(fig)
                continue

            fig.suptitle('Dock Slot Utilization (Used vs Available + Util%)', fontsize=14, fontweight='bold', y=0.995)
            fig.text(0.5, 0.01, 'Time Slot (Hour)', ha='center', fontsize=11)
            fig.text(0.01, 0.5, 'Capacity (slots/hour)', va='center', rotation='vertical', fontsize=11)
            fig.text(0.99, 0.5, 'Utilization (%)', va='center', rotation='vertical', fontsize=11)

            plt.tight_layout(rect=[0.03, 0.03, 0.97, 0.97])
            suffix = f'_p{page_idx}' if len(scenario_chunks) > 1 else ''
            path = os.path.join(FIGURES_DIR, f'3b_slot_utilization_grouped{suffix}.png')
            plt.savefig(path, dpi=300, bbox_inches='tight')
            print(f"Hourly utilization chart saved: {path}")
            plt.close(fig)
    
    print(f"{'='*70}")
    print(f"All visualization charts completed! Figures saved to: {FIGURES_DIR}")
    print(f"  - 1_completion_on_time_rate.png: Completion + On-time rate (all orders)")
    print(f"  - 1a_day1_to_day2_rescheduled.png: Day1->Day2 rescheduled outbound volume & rate")
    print(f"  - 1b_sla_by_region.png: On-time rate by region (G2 vs ROW, all orders)")
    print(f"  - 2*.png: Flow statistics (pallets & orders)")
    print(f"  - 3_timeslot_utilization.png: Average dock utilization")
    print(f"  - 3b_*.png: Hourly utilization by slot (grouped, up to 6 scenarios per page)")
    print(f"{'='*70}")


# ==================== Main Program Entry ====================

if __name__ == '__main__':
    # 设置随机种子以确保可重复性
    np.random.seed(42)

    # 选择仿真月份（generated_orders.json 按 M01..M12 分组）
    TARGET_MONTH = 1
    
    RUN_SINGLE_MONTH = False
    RUN_YEARLY_SUMMARY = False  # Case 1: 时间窗口变化影响的FTE分析
    RUN_FTE_POWER_OVERLAY = True  # Case 2: α=0.7,0.8,0.9的FTE弹性分析
    RUN_BIWEEKLY_FRIDAY_LATE_SHIFT_CANCEL_OVERLAY = False  # Scenario A: no timeslot compression
    RUN_FRIDAY_LATE_SHIFT_CANCEL_ON_SELECTED_WINDOWS = False  # Case 3: 班次灵活性策略的FTE分析
    FTE_POWER_ALPHAS = [0.7, 0.8, 0.9]  # FTE效率弹性参数  # 只测试0.1
    FTE_POWER_BASELINE_HOURS = 18

    # Always run the alpha-sweep overlay when enabled (independent from RUN_SINGLE_MONTH)
    if RUN_FTE_POWER_OVERLAY:
        # 1) Baseline
        results_base, comparison_df_base = run_scenario_comparison(
            scenarios_to_run=None,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
        )

        # 2) Multiple FTE power-law adjusted runs (same scenarios, different per-hour capacity)
        results_by_label = {}
        for alpha in FTE_POWER_ALPHAS:
            safe_alpha = str(alpha).replace('.', 'p')
            suffix = f'_ftepow_a{safe_alpha}'
            lbl = f'α={alpha}'
            print(f"\n{'='*50}")
            print(f"开始运行 Alpha = {alpha} 的FTE弹性测试")
            print(f"{'='*50}")
            res, _df = run_scenario_comparison(
                scenarios_to_run=None,
                num_replications=3,
                duration_days=30,
                target_month=TARGET_MONTH,
                scenario_config_transform=_scenario_transform_fte_power(
                    alpha=alpha,
                    baseline_hours=FTE_POWER_BASELINE_HOURS
                ),
                output_suffix=suffix,
                details_suffix=suffix
            )
            results_by_label[lbl] = res
            print(f"Alpha = {alpha} 的FTE弹性测试完成！")
            
            # FTE analysis results are now generated separately by fte_visualization.py

        # Visualize: full set for baseline + one overlay figure with 4 legend entries.
        visualize_results(comparison_df_base, results_base)
        
        # FTE analysis charts are now generated separately by fte_visualization.py

        visualize_fte_power_overlay_multi(
            results_base,
            results_by_label,
            label_base='Baseline',
            out_name='compare_fte_power_overlay.png'
        )
        
        # Alpha comparison charts are now generated separately by fte_visualization.py

    if RUN_SINGLE_MONTH and (not RUN_FTE_POWER_OVERLAY):
        # 运行单月场景对比
        results, comparison_df = run_scenario_comparison(
            scenarios_to_run=None,
            num_replications=3,  # 每个场景重复 3 次
            duration_days=30,    # 仿真 30 天
            target_month=TARGET_MONTH
        )

        # 可视化结果（传入all_results用于hourly数据）
        visualize_results(comparison_df, results)
        
        # FTE analysis charts are now generated separately by fte_visualization.py

    # Scenario A (requested): cancel Friday late shift every 2 weeks (day1=Mon, start from 2nd Friday)
    # No timeslot compression/reassignment: demand stays the same; supply windows change.
    if RUN_BIWEEKLY_FRIDAY_LATE_SHIFT_CANCEL_OVERLAY:
        scenarios_to_run = ['baseline']

        base_res, _base_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            output_suffix='_biwkfri_base',
            details_suffix='_biwkfri_base'
        )

        biweekly_res, _biweekly_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_biweekly_cancel_friday_late_shift(
                day1_weekday=0,
                start_week_index=1,
                cancel_start_hour=15,
                every_n_weeks=2
            ),
            output_suffix='_biwkfri_cancel',
            details_suffix='_biwkfri_cancel'
        )

        weekly_res, _weekly_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_weekly_cancel_friday_late_shift(
                day1_weekday=0,
                cancel_start_hour=15
            ),
            output_suffix='_wkfri_cancel',
            details_suffix='_wkfri_cancel'
        )

        weekly_full_off_res, _weekly_full_off_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_weekly_cancel_friday_full_day(
                day1_weekday=0
            ),
            output_suffix='_wkfri_fulloff',
            details_suffix='_wkfri_fulloff'
        )

        tue_thu_res, _tue_thu_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_weekly_cancel_tue_thu_late_shift(
                day1_weekday=0,
                cancel_start_hour=15
            ),
            output_suffix='_wktuth_cancel',
            details_suffix='_wktuth_cancel'
        )

        visualize_fte_power_overlay_multi(
            base_res,
            {
                'Biweekly Fri 15-24 off': biweekly_res,
                'Weekly Fri 15-24 off': weekly_res,
                'Weekly Fri FULL off': weekly_full_off_res,
                'Weekly Tue+Thu 15-24 off': tue_thu_res
            },
            label_base='Baseline',
            out_name='compare_friday_late_shift_cancel_5way.png',
            show_value_labels=True
        )

        visualize_flow_kpis_overlay_multi_runs(
            base_res,
            {
                'Biweekly Fri 15-24 off': biweekly_res,
                'Weekly Fri 15-24 off': weekly_res,
                'Weekly Fri FULL off': weekly_full_off_res,
                'Weekly Tue+Thu 15-24 off': tue_thu_res
            },
            label_base='Baseline',
            out_name='compare_friday_late_shift_cancel_by_flow_5way.png',
            show_value_labels=True
        )

    # Stacked comparison: select time-window scenarios, then overlay Friday late-shift cancellations.
    # Requested set: baseline (06-24), 06-22, 06-20.
    if RUN_FRIDAY_LATE_SHIFT_CANCEL_ON_SELECTED_WINDOWS:
        scenarios_to_run = ['baseline', 'fixed_06_22', 'fixed_06_20']

        base_res, _base_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            output_suffix='_fri_cancel_tw_base',
            details_suffix='_fri_cancel_tw_base'
        )

        biweekly_res, _biweekly_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_biweekly_cancel_friday_late_shift_with_fte_adjustment(
                day1_weekday=0,
                start_week_index=1,
                cancel_start_hour=15,
                every_n_weeks=2,
                baseline_hours=18
            ),
            output_suffix='_fri_cancel_tw_biwk',
            details_suffix='_fri_cancel_tw_biwk'
        )

        weekly_res, _weekly_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_weekly_cancel_friday_late_shift_with_fte_adjustment(
                day1_weekday=0,
                cancel_start_hour=15,
                baseline_hours=18
            ),
            output_suffix='_fri_cancel_tw_wk',
            details_suffix='_fri_cancel_tw_wk'
        )

        weekly_full_off_res, _weekly_full_off_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_weekly_cancel_friday_full_day_with_fte_adjustment(
                day1_weekday=0,
                baseline_hours=18
            ),
            output_suffix='_fri_cancel_tw_wkfulloff',
            details_suffix='_fri_cancel_tw_wkfulloff'
        )

        tue_thu_res, _tue_thu_df = run_scenario_comparison(
            scenarios_to_run=scenarios_to_run,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH,
            scenario_config_transform=_scenario_transform_weekly_cancel_tue_thu_late_shift_with_fte_adjustment(
                day1_weekday=0,
                cancel_start_hour=15,
                baseline_hours=18
            ),
            output_suffix='_fri_cancel_tw_wktuth',
            details_suffix='_fri_cancel_tw_wktuth'
        )

        visualize_fte_power_overlay_multi(
            base_res,
            {
                'Biweekly Fri 15-24 off': biweekly_res,
                'Weekly Fri 15-24 off': weekly_res,
                'Weekly Fri FULL off': weekly_full_off_res,
                'Weekly Tue+Thu 15-24 off': tue_thu_res
            },
            label_base='Baseline',
            out_name='compare_friday_late_shift_cancel_across_time_windows_5way.png',
            show_value_labels=True,
            suptitle='Time-Window Scenarios vs Shift-Cancel Strategies (5-way)'
        )

        # By-flow: split into two readable 2x2 figures (FG and R&P).
        visualize_flow_kpis_overlay_across_scenarios_2x2_by_category(
            base_res,
            {
                'Biweekly Fri 15-24 off': biweekly_res,
                'Weekly Fri 15-24 off': weekly_res,
                'Weekly Fri FULL off': weekly_full_off_res,
                'Weekly Tue+Thu 15-24 off': tue_thu_res
            },
            scenarios=scenarios_to_run,
            category='FG',
            label_base='Baseline',
            out_name='compare_friday_late_shift_cancel_across_time_windows_by_flow_big_5way_FG.png',
            show_value_labels=True
        )

        visualize_flow_kpis_overlay_across_scenarios_2x2_by_category(
            base_res,
            {
                'Biweekly Fri 15-24 off': biweekly_res,
                'Weekly Fri 15-24 off': weekly_res,
                'Weekly Fri FULL off': weekly_full_off_res,
                'Weekly Tue+Thu 15-24 off': tue_thu_res
            },
            scenarios=scenarios_to_run,
            category='RP',
            label_base='Baseline',
            out_name='compare_friday_late_shift_cancel_across_time_windows_by_flow_big_5way_RP.png',
            show_value_labels=True
        )
        
        # Generate FTE analysis charts for shift flexibility scenarios
        # Create comparison DataFrame for FTE analysis - use all tested scenarios
        shift_scenarios = {}
        for scenario in scenarios_to_run:
            shift_scenarios[f'Baseline ({scenario})'] = base_res[scenario]
            shift_scenarios[f'Biweekly Fri off ({scenario})'] = biweekly_res[scenario] 
            shift_scenarios[f'Weekly Fri off ({scenario})'] = weekly_res[scenario]
            shift_scenarios[f'Weekly Fri FULL off ({scenario})'] = weekly_full_off_res[scenario]
            shift_scenarios[f'Weekly Tue+Thu off ({scenario})'] = tue_thu_res[scenario]
        
        shift_comparison_df = pd.DataFrame(shift_scenarios).T
        
        # FTE analysis charts are now generated separately by fte_visualization.py

    if RUN_YEARLY_SUMMARY:
        # Case 1: 时间窗口变化影响的FTE分析
        print("\n" + "="*70)
        print("Case 1: 运行时间窗口变化的FTE分析")
        print("="*70)
        
        # 运行Case 1的基准仿真
        results_case1, comparison_df_case1 = run_scenario_comparison(
            scenarios_to_run=None,
            num_replications=3,
            duration_days=30,
            target_month=TARGET_MONTH
        )
        
        # 可视化结果
        visualize_results(comparison_df_case1, results_case1)
        
        # FTE analysis charts are now generated separately by scripts/fte_visualization.py
        
        # Export FTE results for Case 1
        # FTE results export is now handled separately by fte_visualization.py
        
        # 全年汇总：对所有可用月份的KPI取均值
        run_yearly_scenario_summary(
            scenarios_to_run=None,
            months=None,          # 自动识别 generated_orders.json 里有哪些月份
            num_replications=3,
            duration_days=30
        )
    
    print("\n" + "="*70)
    print("仿真分析完成！生成的文件：")
    print("  1. simulation_results_comparison.xlsx - 场景对比汇总表")
    print("  2. fte_results*.xlsx - FTE相关结果专用表（由独立脚本生成）")
    print("  4. 可视化图片（见 outputs/figures/）:")
    print("     - 1_completion_on_time_rate: 完成率 + 准时率（所有订单口径）")
    print("     - 1a_day1_to_day2_rescheduled: 第一天应完成但第二天才完成（量与比例，Outbound）")
    print("     - 1b_sla_by_region: 按地区分解准时率(G2 vs ROW，所有订单口径)")
    print("     - 2/2b/2c/2d: 流量统计（托盘与订单）")
    print("     - 3_timeslot_utilization: Timeslot平均利用率")
    print("     - 3b_*: 时段详细分析（grouped，每张图最多6个scenario，按页输出）")
    print("     注：FTE专项分析请运行 python scripts/fte_visualization.py")
    print("="*70)


# ==================== 主执行函数 ====================
