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

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'results')
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'figures')

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
    'scenario_1': {
        'name': 'Scenario 1 (07:00-23:00)',
        'dc_open_time': 7,
        'dc_close_time': 23,
        'operating_hours': 16,
        'arrival_smoothing': False
    },
    'scenario_2': {
        'name': 'Scenario 2 (08:00-22:00)',
        'dc_open_time': 8,
        'dc_close_time': 22,
        'operating_hours': 14,
        'arrival_smoothing': False
    },
    'scenario_3': {
        'name': 'Scenario 3 (08:00-20:00)',
        'dc_open_time': 8,
        'dc_close_time': 20,
        'operating_hours': 12,
        'arrival_smoothing': False
    }
}

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
    
    # 加载码头容量（如果配置文件中有，否则使用默认值）
    if 'hourly_dock_capacity' in LOADED_CONFIG:
        loaded_capacity = LOADED_CONFIG['hourly_dock_capacity']
        # 标准化键名：RP → R&P
        SYSTEM_PARAMETERS['hourly_dock_capacity'] = {
            'FG': loaded_capacity['FG'],
            'R&P': loaded_capacity.get('R&P', loaded_capacity.get('RP', {}))
        }
        print("使用配置文件中的码头容量数据")
    else:
        print("警告: 配置文件缺少码头容量，使用硬编码默认值")
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
    
    # 加载托盘数分布（如果配置文件中有，否则使用默认值）
    if 'pallets_distribution' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['pallets_distribution'] = LOADED_CONFIG['pallets_distribution']
        print("使用配置文件中的托盘数分布数据")
    else:
        print("警告: 配置文件缺少托盘数分布，使用硬编码默认值")
        SYSTEM_PARAMETERS['pallets_distribution'] = {
            'FG': {'type': 'triangular', 'min': 1, 'mode': 33, 'max': 276, 'mean': 30.0, 'std': 12.3},
            'R&P': {'type': 'triangular', 'min': 1, 'mode': 22, 'max': 560, 'mean': 22.7, 'std': 9.7}
        }
    
    # 加载人力资源数据（如果配置文件中有，否则使用默认值）
    if 'fte_total' in LOADED_CONFIG and 'fte_allocation' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['fte_total'] = LOADED_CONFIG['fte_total']
        SYSTEM_PARAMETERS['fte_allocation'] = LOADED_CONFIG['fte_allocation']
        print("使用配置文件中的人力资源数据")
    else:
        print("警告: 配置文件缺少人力资源数据，使用硬编码默认值")
        SYSTEM_PARAMETERS['fte_total'] = 125
        SYSTEM_PARAMETERS['fte_allocation'] = {'rp_baseline': 28, 'fg_baseline': 97}

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
        
        # 时变码头容量（基于48周Timeslot实际FG/R&P分类数据）
        # 数据来源：Timeslot W1-W48.xlsx - 48周中位数
        # 关键发现：R&P Loading需求远超业务量占比（装车复杂度更高）
        'hourly_dock_capacity': {
            # FG码头容量（实际数据）
            'FG': {
                'loading': {  # FG Loading（出库）
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
            # R&P码头容量（实际数据）
            'R&P': {
                'loading': {  # R&P Loading（出库）
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

class Truck:
    """卡车实体（代表一个订单）"""
    _id_counter = 0
    
    def __init__(self, category, direction, pallets, scheduled_time, region=None):
        Truck._id_counter += 1
        self.id = Truck._id_counter
        self.category = category  # FG or R&P
        self.direction = direction  # Inbound or Outbound
        self.pallets = pallets
        self.scheduled_time = scheduled_time
        self.actual_arrival_time = None
        self.region = region  # G2 or ROW (FG Outbound only)
        self.departure_deadline = None
        self.has_time_constraint = False  # For SLA calculation
        self.processing_start_time = None
        self.processing_end_time = None
        self.service_start_time = None  # Timeslot start
        self.service_end_time = None    # Timeslot end
        self.processing_deadline = None  # 24h inbound deadline
        self.is_delayed = False
        self.delay_hours = 0
        
    def __repr__(self):
        if self.region:
            return f"Truck-{self.id}({self.category}-{self.direction}, {self.pallets}p, {self.region})"
        return f"Truck-{self.id}({self.category}-{self.direction}, {self.pallets}p)"


class Order:
    """订单实体"""
    _id_counter = 0
    
    def __init__(self, pallets, order_time, departure_time, has_time_constraint=False, region=None):
        Order._id_counter += 1
        self.id = Order._id_counter
        self.pallets = pallets
        self.order_time = order_time
        self.departure_time = departure_time
        self.completion_time = None
        self.has_time_constraint = has_time_constraint
        self.region = region  # G2 or ROW
        
    def __repr__(self):
        return f"Order-{self.id}({self.pallets}p, deadline:{self.departure_time})"


# ==================== 资源管理器 ====================

class TrailerBuffer:
    """挂车缓冲区管理"""
    def __init__(self, env, category, max_trailers, pallets_per_trailer):
        self.env = env
        self.category = category
        self.max_capacity = max_trailers * pallets_per_trailer
        self.current_pallets = 0
        self.queue = []  # FIFO 队列
        self.overflow_count = 0
        self.total_overflow_pallets = 0
        
    def add(self, pallets, timestamp):
        """添加托盘到缓冲区"""
        if self.current_pallets + pallets <= self.max_capacity:
            self.queue.append({'pallets': pallets, 'timestamp': timestamp})
            self.current_pallets += pallets
            return True
        else:
            # 缓冲区满，记录溢出
            self.overflow_count += 1
            self.total_overflow_pallets += pallets
            return False
    
    def release(self, max_pallets):
        """从缓冲区释放托盘（FIFO）"""
        released_pallets = 0
        while self.queue and released_pallets < max_pallets:
            batch = self.queue[0]
            if released_pallets + batch['pallets'] <= max_pallets:
                released = self.queue.pop(0)
                released_pallets += released['pallets']
                self.current_pallets -= released['pallets']
            else:
                # 部分释放
                remaining = max_pallets - released_pallets
                self.queue[0]['pallets'] -= remaining
                self.current_pallets -= remaining
                released_pallets += remaining
                break
        
        return released_pallets
    
    def get_occupancy_rate(self):
        """获取当前占用率"""
        return self.current_pallets / self.max_capacity if self.max_capacity > 0 else 0


class FTEManager:
    """人力资源管理器（成本节约型：FTE按运营时长比例调整）
    
    基于Input FTE Data.txt的固定配置：
    - FG: Inbound 44.75 FTE, Outbound 44.75 FTE, 效率 665.43 pallet/FTE
    - R&P: Inbound 10.025 FTE, Outbound 10.025 FTE, 效率 1308.83 pallet/FTE
    - 1 FTE = 1人 × 8小时/天 × 22天/月 = 176小时/月
    """
    def __init__(self, operating_hours=18):
        """
        Args:
            operating_hours: 每天运营小时数（默认18小时，即Baseline）
        """
        # 尝试从配置文件加载FTE配置
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
            print("  使用配置文件中的FTE数据")
        else:
            # 使用硬编码默认值（从Input FTE Data.txt）
            self.baseline_fte = {
                'FG': {'Inbound': 44.75, 'Outbound': 44.75},
                'R&P': {'Inbound': 10.025, 'Outbound': 10.025}
            }
            self.efficiency_per_fte = {
                'FG': 665.43,
                'R&P': 1308.83
            }
            print("  使用硬编码FTE默认值")
        
        # 月度工时（22天 × 8小时）
        self.hours_per_month = 176
        
        # 基准运营时长
        self.baseline_hours = 18
        
        # 实际运营时长
        self.operating_hours = operating_hours
        
        # 计算调整后的FTE（按比例减少）
        self.operating_ratio = operating_hours / self.baseline_hours
        self.adjusted_fte = self._calculate_adjusted_fte()
        
    def _calculate_adjusted_fte(self):
        """根据运营时长调整FTE（成本节约型）"""
        adjusted = {}
        for category in ['FG', 'R&P']:
            adjusted[category] = {}
            for direction in ['Inbound', 'Outbound']:
                base = self.baseline_fte[category][direction]
                adjusted[category][direction] = base * self.operating_ratio
        return adjusted
    
    def get_hourly_capacity(self, category, direction):
        """获取每小时处理能力（托盘/小时）
        
        计算公式：(调整后FTE × 效率) / 月度工时
        注意：人员密度保持不变，因此每小时处理能力与baseline相同
        
        Returns:
            float: 托盘/小时
        """
        # 使用调整后的FTE
        fte = self.adjusted_fte[category][direction]
        efficiency = self.efficiency_per_fte[category]
        
        # 基础每小时容量
        base_capacity = (fte * efficiency) / self.hours_per_month
        
        # 考虑随机波动（±5%，模拟日常效率变化）
        actual_capacity = base_capacity * np.random.uniform(0.95, 1.05)
        
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
    def __init__(self):
        self.buffer_overflows = []
        self.truck_wait_times = []
        self.sla_misses = []
        self.completed_orders = []
        self.inbound_operations = []
        self.outbound_operations = []
        self.hourly_buffer_occupancy = defaultdict(list)
        self.midnight_backlogs = []
        self.inbound_delays = []  # 新增：记录Inbound 24小时超时
        self.dock_usage = []  # 新增：记录码头使用情况（用于计算利用率）
    
    def record_dock_usage(self, hour, dock_type, category, used, available):
        """记录码头使用情况"""
        # 计算利用率，确保不超过100%（如果used>available说明超容量运行）
        if available > 0:
            utilization = min(used / available, 1.0)  # 限制最大为100%
        else:
            utilization = 0
            
        self.dock_usage.append({
            'hour': hour,
            'dock_type': dock_type,  # 'loading' or 'reception'
            'category': category,  # 'FG' or 'R&P'
            'used': used,
            'available': available,
            'utilization': utilization,
            'over_capacity': max(0, used - available)  # 记录超容量部分
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
        """
        记录卡车等待时间（仅统计DC开放时间内的等待）
        
        排除DC关闭时间，例如：
        - 卡车23:00到达，第二天6:00开始服务
        - 总等待7小时，但DC关闭时间6小时不应计入业务等待
        - 实际业务等待 = 1小时（23:00-24:00）
        """
        total_wait = truck.service_start_time - truck.actual_arrival_time
        
        # 计算跨越了多少个完整的DC关闭周期
        arrival_time = truck.actual_arrival_time
        service_start = truck.service_start_time
        
        # 计算实际业务等待时间（排除DC关闭时间）
        dc_open = dc_config['dc_open_time']
        dc_close = dc_config['dc_close_time']
        daily_closure_hours = 24 - dc_close + dc_open
        
        business_wait = 0
        current_time = arrival_time
        
        while current_time < service_start:
            current_hour = int(current_time) % 24
            
            # 如果当前在DC开放时间内
            if dc_open <= current_hour < dc_close:
                # 计算到关门或服务开始的时间（取较小值）
                hours_until_close = dc_close - current_hour - (current_time % 1)
                hours_until_service = service_start - current_time
                hours_to_add = min(hours_until_close, hours_until_service)
                business_wait += hours_to_add
                current_time += hours_to_add
            else:
                # 当前在DC关闭时间内，跳到下一个开门时间
                next_day_start = (int(current_time) // 24 + 1) * 24 + dc_open
                current_time = next_day_start
        
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
    
    def generate_summary(self):
        """生成汇总报告"""
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
        
        # SLA 统计（仅时间受限订单）
        constrained_orders = [o for o in self.completed_orders if o.get('has_time_constraint', False)]
        total_constrained = len(constrained_orders)
        if total_constrained > 0:
            on_time_orders = sum(1 for o in constrained_orders if o['on_time'])
            summary['sla_compliance_rate'] = on_time_orders / total_constrained
            summary['sla_miss_rate'] = 1 - summary['sla_compliance_rate']
            summary['total_sla_misses'] = len(self.sla_misses)
            summary['total_constrained_orders'] = total_constrained
        else:
            summary['sla_compliance_rate'] = 1.0
            summary['sla_miss_rate'] = 0.0
            summary['total_sla_misses'] = 0
            summary['total_constrained_orders'] = 0
        
        # 按地区统计 SLA
        for region in ['G2', 'ROW']:
            region_constrained = [o for o in constrained_orders if o.get('region') == region]
            if region_constrained:
                region_on_time = sum(1 for o in region_constrained if o['on_time'])
                summary[f'{region}_sla_compliance_rate'] = region_on_time / len(region_constrained)
                summary[f'{region}_total_constrained_orders'] = len(region_constrained)
            else:
                summary[f'{region}_sla_compliance_rate'] = 1.0
                summary[f'{region}_total_constrained_orders'] = 0
        
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
            fg_region = [o for o in fg_outbound if o.get('region') == region]
            summary[f'FG_{region}_outbound_pallets'] = sum(o['pallets'] for o in fg_region)
            summary[f'FG_{region}_outbound_orders'] = sum(o.get('order_count', 1) for o in fg_region)
        
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
            
            # 总体平均利用率
            summary['avg_dock_utilization'] = df_usage['utilization'].mean()
            
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
                    summary[f'{dock_type}_avg_utilization'] = type_data['utilization'].mean()
                    summary[f'{dock_type}_peak_utilization'] = type_data['utilization'].max()
                else:
                    summary[f'{dock_type}_avg_utilization'] = 0
                    summary[f'{dock_type}_peak_utilization'] = 0
            
            # 按类别统计
            for category in ['FG', 'R&P']:
                cat_data = df_usage[df_usage['category'] == category]
                if len(cat_data) > 0:
                    summary[f'{category}_dock_avg_utilization'] = cat_data['utilization'].mean()
                else:
                    summary[f'{category}_dock_avg_utilization'] = 0
            
            # 按类别和方向统计（FG/R&P × Inbound/Outbound）
            for category in ['FG', 'R&P']:
                # Inbound = Reception码头
                inbound_data = df_usage[(df_usage['category'] == category) & (df_usage['dock_type'] == 'reception')]
                if len(inbound_data) > 0:
                    summary[f'{category}_inbound_utilization'] = inbound_data['utilization'].mean()
                else:
                    summary[f'{category}_inbound_utilization'] = 0
                
                # Outbound = Loading码头
                outbound_data = df_usage[(df_usage['category'] == category) & (df_usage['dock_type'] == 'loading')]
                if len(outbound_data) > 0:
                    summary[f'{category}_outbound_utilization'] = outbound_data['utilization'].mean()
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


# ==================== 主仿真类 ====================

class DCSimulation:
    """配送中心仿真主控制器"""
    
    def __init__(self, env, scenario_config, run_id=1):
        self.env = env
        self.config = scenario_config
        self.run_id = run_id
        
        # 初始化资源
        self._init_resources()
        
        # KPI 收集器
        self.kpi = KPICollector()
        
        # 订单队列（FG Outbound）
        self.pending_orders = []
        
        # 如果启用到达平滑化，计算优化后的到达率（仅针对Outbound）
        if self.config.get('arrival_smoothing', False):
            self.arrival_rates = self._smooth_arrival_rates(self.config)
        else:
            self.arrival_rates = SYSTEM_PARAMETERS.get('truck_arrival_rates_outbound', 
                                                       SYSTEM_PARAMETERS.get('truck_arrival_rates', {}))
        
        print(f"初始化仿真: {scenario_config['name']}")
        print(f"  运营时间: {scenario_config['dc_open_time']:02d}:00 - {scenario_config['dc_close_time']:02d}:00")
        print(f"  运营小时数: {scenario_config['operating_hours']} 小时/天")
        
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
        
        # 缓冲区
        buffer_config = SYSTEM_PARAMETERS['buffer_capacity']
        self.buffer_rp = TrailerBuffer(
            self.env, 'R&P', 
            buffer_config['rp_trailers'], 
            buffer_config['pallets_per_trailer']
        )
        self.buffer_fg = TrailerBuffer(
            self.env, 'FG', 
            buffer_config['fg_trailers'], 
            buffer_config['pallets_per_trailer']
        )
        
        # 人力资源管理器（传入operating_hours以调整FTE）
        operating_hours = self.config['operating_hours']
        self.fte_manager = FTEManager(operating_hours=operating_hours)
    
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
        hour = int(time) % 24
        return self.config['dc_open_time'] <= hour < self.config['dc_close_time']
    
    def run(self, duration_days=30):
        """运行仿真"""
        print(f"\n开始仿真运行，持续 {duration_days} 天...")
        
        # 启动各个进程
        self.env.process(self.timeslot_capacity_manager())  # 启动timeslot容量管理器（包含KPI记录）
        self.env.process(self.inbound_truck_arrival_process())  # Inbound卡车到达
        self.env.process(self.buffer_release_process())
        self.env.process(self.outbound_truck_arrival_process())  # Outbound卡车到达
        self.env.process(self.buffer_monitor())
        self.env.process(self.midnight_backlog_monitor())  # 启动午夜积压监控
        
        # 运行仿真
        self.env.run(until=duration_days * 24)
        
        print(f"仿真运行完成！")
        
        # 生成汇总报告
        summary = self.kpi.generate_summary()
        return summary
    
    def inbound_truck_arrival_process(self):
        """
        Inbound卡车到达进程（基于真实数据的hourly到达率）
        从Total Shipments 2025的Inbound sheet提取
        """
        arrival_rates = SYSTEM_PARAMETERS.get('truck_arrival_rates_inbound', {})
        
        if not arrival_rates:
            print("警告：没有Inbound卡车到达率数据，跳过Inbound流程")
            return
        
        while True:
            hour = int(self.env.now) % 24
            
            # 遍历每个类别
            for category in ['FG', 'R&P']:
                if category in arrival_rates:
                    hourly_rates = arrival_rates[category]
                    
                    # 获取当前小时的到达率（支持string和int key）
                    lambda_hour = hourly_rates.get(hour, hourly_rates.get(str(hour), 0))
                    
                    if lambda_hour > 0:
                        # 泊松分布生成到达卡车数
                        num_arrivals = np.random.poisson(lambda_hour)
                        
                        for i in range(num_arrivals):
                            # 生成Inbound卡车
                            truck = self._generate_inbound_truck(category)
                            
                            # 添加到达延迟（指数分布，平均 15 分钟）
                            delay = np.random.exponential(scale=0.25)
                            yield self.env.timeout(delay)
                            
                            truck.actual_arrival_time = self.env.now
                            
                            # 启动入库处理
                            self.env.process(self.inbound_truck_process(truck))
            
            yield self.env.timeout(1)  # 每小时检查一次
    
    def _generate_inbound_truck(self, category):
        """生成Inbound卡车（用于入库流程）"""
        # 从托盘分布中采样
        pallet_config = SYSTEM_PARAMETERS['pallets_distribution'][category]
        
        if pallet_config['type'] == 'triangular':
            pallets = int(np.random.triangular(
                pallet_config['min'],
                pallet_config['mode'],
                pallet_config['max']
            ))
        else:  # lognormal
            pallets = int(np.random.lognormal(
                pallet_config['mean'],
                pallet_config['std']
            ))
        
        # 创建Inbound卡车
        truck = Truck(category, 'Inbound', pallets, self.env.now, region=None)
        truck.departure_deadline = None  # Inbound没有departure deadline
        
        return truck
    
    def inbound_truck_process(self, truck):
        """处理 Inbound 卡车（Timeslot 预约制）"""
        category = truck.category
        pallets = truck.pallets
        arrival_time = self.env.now
        processing_deadline = arrival_time + 24
        
        slot_key = f'{category.lower()}_reception' if category == 'FG' else 'rp_reception'
        
        # 等待并预约 timeslot
        while True:
            current_hour = int(self.env.now) % 24
            available_slots = self.hourly_timeslot_capacity[slot_key]
            used_slots = self.hourly_timeslot_used[slot_key]
            
            if available_slots > 0 and used_slots < available_slots:
                self.hourly_timeslot_used[slot_key] += 1
                break
            else:
                yield self.env.timeout(0.25)
        
        truck.service_start_time = self.env.now
        self.kpi.record_truck_wait(truck, self.config)
        
        # 卸货操作
        unloading_time = self._calculate_unloading_time(category, pallets)
        yield self.env.timeout(unloading_time)
        unload_end_time = self.env.now
        
        self.kpi.record_inbound_operation(
            category=category,
            pallets=pallets,
            start_time=truck.service_start_time,
            end_time=unload_end_time,
            from_buffer=False
        )
        
        # 处理完成（24h deadline）
        hourly_capacity = self.fte_manager.get_hourly_capacity(category, 'Inbound')
        processing_time = pallets / hourly_capacity
        
        processing_start = self.env.now
        yield self.env.timeout(processing_time)
        processing_end = self.env.now
        
        if processing_end > processing_deadline:
            delay_hours = processing_end - processing_deadline
            self.kpi.record_inbound_delay(category, pallets, arrival_time, processing_end, delay_hours)
    
    def _calculate_unloading_time(self, category, pallets):
        """计算卸货时间"""
        efficiency_params = SYSTEM_PARAMETERS['efficiency']
        
        if category == 'R&P':
            efficiency = np.random.normal(
                efficiency_params['rp_mean'],
                efficiency_params['rp_std']
            )
        else:  # FG
            efficiency = np.random.normal(
                efficiency_params['fg_mean'],
                efficiency_params['fg_std']
            )
        
        # 确保效率为正
        efficiency = max(efficiency, 0.5)
        
        # 卸货时间 = 托盘数 / 效率（小时）
        unloading_time = pallets / efficiency
        return unloading_time
    
    def buffer_release_process(self):
        """缓冲区释放进程（DC 开门时优先处理）"""
        while True:
            if self.is_dc_open():
                # 释放 R&P 缓冲
                if self.buffer_rp.current_pallets > 0:
                    release_amount = min(100, self.buffer_rp.current_pallets)
                    pallets = self.buffer_rp.release(release_amount)
                    if pallets > 0:
                        # 创建虚拟truck对象处理从缓冲区来的货物
                        truck = Truck(category='R&P', direction='Inbound', pallets=pallets, 
                                    scheduled_time=self.env.now, region=None)
                        self.env.process(self.inbound_truck_process(truck))
                
                # 释放 FG 缓冲
                if self.buffer_fg.current_pallets > 0:
                    release_amount = min(150, self.buffer_fg.current_pallets)
                    pallets = self.buffer_fg.release(release_amount)
                    if pallets > 0:
                        # 创建虚拟truck对象处理从缓冲区来的货物
                        truck = Truck(category='FG', direction='Inbound', pallets=pallets, 
                                    scheduled_time=self.env.now, region=None)
                        self.env.process(self.inbound_truck_process(truck))
            
            yield self.env.timeout(0.5)  # 每 30 分钟检查一次
    
    def outbound_truck_arrival_process(self):
        """
        Outbound卡车到达进程（基于统计到达率）
        
        来源：Total Shipments 2025.xlsx - Outbound Shipments
        统计方法：分类别统计每小时实际到达卡车数的平均值
        全年实际数据（305天）：FG占69.3%（36.77辆/天），R&P占30.7%（16.27辆/天）
        """
        # 使用优化后的到达率（如果启用）
        arrival_rates = self.arrival_rates
        
        while True:
            hour = int(self.env.now) % 24
            
            if self.is_dc_open():
                # 分别生成FG和R&P的到达卡车（使用各自的到达率）
                for category in ['FG', 'R&P']:
                    # 支持字符串和整数键
                    hourly_rates = arrival_rates[category]
                    lambda_hour = hourly_rates.get(hour, hourly_rates.get(str(hour), 0))
                    
                    if lambda_hour > 0:
                        # 基于实际数据验证：FG Var/Mean=0.48, R&P Var/Mean=0.30
                        # 到达比泊松分布更规律，使用75%预约+25%临时模型
                        scheduled_ratio = 0.75  # 75%为预约到达
                        
                        # 预约到达（近似确定性）
                        num_scheduled = int(lambda_hour * scheduled_ratio + 0.5)  # 四舍五入
                        
                        # 临时到达（泊松分布）
                        num_random = np.random.poisson(lambda_hour * (1 - scheduled_ratio))
                        
                        num_arrivals = num_scheduled + num_random
                        
                        for i in range(num_arrivals):
                            # 生成指定类别的卡车（Outbound）
                            truck = self._generate_truck(category)
                            
                            # 添加到达延迟（指数分布，平均 15 分钟）
                            # 避免同一小时内所有卡车同时到达
                            delay = np.random.exponential(scale=0.25)
                            yield self.env.timeout(delay)
                            
                            truck.actual_arrival_time = self.env.now
                            
                            # 启动出库处理
                            self.env.process(self.outbound_process(truck))
            
            yield self.env.timeout(1)  # 每小时检查一次
    
    def outbound_process(self, truck):
        """
        出库处理进程（两阶段：先处理货物，后占用timeslot装车）
        
        阶段1: 处理货物（Before ready to load）
        阶段2: 占用timeslot装车
        """
        # ========== 阶段1: 处理货物 ==========
        # 使用FTE处理能力
        hourly_capacity = self.fte_manager.get_hourly_capacity(truck.category, 'Outbound')
        processing_time = truck.pallets / hourly_capacity
        
        truck.processing_start_time = self.env.now
        yield self.env.timeout(processing_time)
        truck.processing_end_time = self.env.now
        
        # ========== 阶段2: 等待并预约timeslot装车 ==========
        # 确定使用哪个timeslot类型
        slot_key = 'rp_loading' if truck.category == 'R&P' else 'fg_loading'
        
        # 等待直到本小时有可用的timeslot
        while True:
            current_hour = int(self.env.now) % 24
            available_slots = self.hourly_timeslot_capacity[slot_key]
            used_slots = self.hourly_timeslot_used[slot_key]
            
            if available_slots > 0 and used_slots < available_slots:
                # 有可用slot，占用1个
                self.hourly_timeslot_used[slot_key] += 1
                break
            else:
                # 没有可用slot或DC关闭，等待15分钟后重新检查
                yield self.env.timeout(0.25)
        
        # 记录获得timeslot的时间
        truck.service_start_time = self.env.now
        
        # 记录等待时间（传入DC配置以排除关闭时间）
        self.kpi.record_truck_wait(truck, self.config)
        
        # ========== 阶段3: 装车操作 ==========
        # 装车时间（假设固定30分钟）
        loading_time = 0.5  # 30分钟
        yield self.env.timeout(loading_time)
        
        truck.service_end_time = self.env.now
        
        # ========== 检查是否错过发运时间（仅FG） ==========
        if truck.category == 'FG' and truck.departure_deadline:
            if truck.service_end_time > truck.departure_deadline:
                # 标记延期
                truck.is_delayed = True
                truck.delay_hours = truck.service_end_time - truck.departure_deadline
                
                # 记录SLA miss
                dummy_order = Order(truck.pallets, truck.scheduled_time, truck.departure_deadline, 
                                   has_time_constraint=truck.has_time_constraint, region=truck.region)
                dummy_order.completion_time = truck.service_end_time
                self.kpi.record_sla_miss(dummy_order, truck.service_end_time)
        
        # 记录订单完成（用于SLA统计）
        if truck.departure_deadline:
            dummy_order = Order(truck.pallets, truck.scheduled_time, truck.departure_deadline,
                               has_time_constraint=truck.has_time_constraint, region=truck.region)
            dummy_order.completion_time = truck.service_end_time
            self.kpi.record_order_completion(dummy_order)
        
        # 记录完成
        self.kpi.record_outbound_operation(truck)
    
    def buffer_monitor(self):
        """缓冲区监控器"""
        while True:
            hour = int(self.env.now) % 24
            
            # 记录缓冲区占用率
            self.kpi.record_buffer_occupancy(hour, 'R&P', self.buffer_rp.get_occupancy_rate())
            self.kpi.record_buffer_occupancy(hour, 'FG', self.buffer_fg.get_occupancy_rate())
            
            yield self.env.timeout(1)  # 每小时记录
    
    def midnight_backlog_monitor(self):
        """午夜积压监控器 - 每天24:00记录待处理订单"""
        while True:
            # 等到下一个午夜（24小时）
            current_hour = self.env.now % 24
            time_to_midnight = 24 - current_hour if current_hour > 0 else 24
            yield self.env.timeout(time_to_midnight)
            
            # 记录缓冲区积压（作为待处理托盘数）
            day = int(self.env.now / 24)
            pending_pallets = self.buffer_rp.current_pallets + self.buffer_fg.current_pallets
            pending_orders = 0  # 暂时使用0，实际应该统计等待队列中的卡车数
            
            self.kpi.record_midnight_backlog(day, pending_orders, pending_pallets)
    
    def _generate_truck(self, category):
        """
        生成指定类别的随机到达卡车（按规则分配region和departure_time）
        
        Args:
            category: 'FG' 或 'R&P'
        
        Returns:
            Truck: 新生成的卡车实体
            
        生成规则:
            - 类别: 由调用者指定（基于实际到达率）
            - 托盘数: 基于实际数据的三角分布（FG: 1-33-276, R&P: 1-22-560）
            - 方向: Outbound（出库装车）
            - Region (仅FG): G2 (80%) / ROW (20%)
            - Departure time: 根据region计算
        """
        pallets_dist = SYSTEM_PARAMETERS['pallets_distribution'][category]
        
        # 使用三角分布生成托盘数（更符合实际数据）
        pallets = int(np.random.triangular(
            pallets_dist['min'], 
            pallets_dist['mode'],
            pallets_dist['max']
        ))
        
        # 确保至少1个托盘
        pallets = max(1, pallets)
        
        # ======== FG Outbound: 按规则分配region和departure_time ========
        if category == 'FG':
            # 按8:2比例分配region
            region = 'G2' if np.random.random() < 0.8 else 'ROW'
            
            # 创建卡车实体（带region）
            truck = Truck(category, 'Outbound', pallets, self.env.now, region=region)
            
            # 根据region计算departure_time
            current_hour = int(self.env.now) % 24
            current_day = int(self.env.now / 24)
            
            if region == 'G2':
                # G2: 50%当天，50%次日
                if np.random.random() < 0.5:
                    # 当天发运：假设18:00前送走
                    hours_until_18 = (18 - current_hour) if current_hour < 18 else 0
                    truck.departure_deadline = self.env.now + hours_until_18
                    truck.has_time_constraint = True  # G2有时间约束
                else:
                    # 次日上午发运：第二天10:00
                    hours_until_tomorrow_10 = (24 - current_hour) + 10
                    truck.departure_deadline = self.env.now + hours_until_tomorrow_10
                    truck.has_time_constraint = True  # G2有时间约束
            else:  # ROW
                # ROW: 100%次日上午10:00发运
                hours_until_tomorrow_10 = (24 - current_hour) + 10
                truck.departure_deadline = self.env.now + hours_until_tomorrow_10
                truck.has_time_constraint = True  # ROW有时间约束
        
        else:  # R&P
            # R&P无region和严格departure要求
            truck = Truck(category, 'Outbound', pallets, self.env.now, region=None)
            truck.departure_deadline = None
            truck.has_time_constraint = False  # R&P无时间约束，不计入SLA
        
        return truck


# ==================== 多场景对比运行 ====================

def run_scenario_comparison(scenarios_to_run=None, num_replications=5, duration_days=30):
    """运行多场景对比分析"""
    
    if scenarios_to_run is None:
        scenarios_to_run = list(SIMULATION_CONFIG.keys())
    
    print("=" * 70)
    print("DC 运营时间缩短仿真分析")
    print("=" * 70)
    print(f"场景数量: {len(scenarios_to_run)}")
    print(f"每场景重复次数: {num_replications}")
    print(f"仿真天数: {duration_days}")
    print("=" * 70)
    
    all_results = {}
    
    for scenario_name in scenarios_to_run:
        scenario_config = SIMULATION_CONFIG[scenario_name]
        print(f"\n{'='*70}")
        print(f"运行场景: {scenario_config['name']}")
        print(f"{'='*70}")
        
        scenario_results = []
        
        for rep in range(num_replications):
            print(f"\n--- 重复 {rep + 1}/{num_replications} ---")
            
            # 创建新的仿真环境
            env = simpy.Environment()
            sim = DCSimulation(env, scenario_config, run_id=rep+1)
            
            # 运行仿真
            result = sim.run(duration_days=duration_days)
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
            print(f"  Outbound SLA miss: {result['total_sla_misses']} 次")
            print(f"  SLA 遵守率: {result['sla_compliance_rate']:.2%}")
            
            print(f"\n  === 资源利用 ===")
            print(f"  平均卡车等待时间: {result['avg_truck_wait_time']:.2f} 小时")
            print(f"  平均午夜积压: {result['avg_midnight_backlog_pallets']:.1f} 托盘")
            
            # 显示码头利用率
            if result.get('avg_dock_utilization', 0) > 0:
                print(f"\n  === Timeslot利用率 ===")
                print(f"  整体平均利用率: {result['avg_dock_utilization']:.1%}")
                print(f"  Loading码头: 平均 {result['loading_avg_utilization']:.1%}, 峰值 {result['loading_peak_utilization']:.1%}")
                print(f"  Reception码头: 平均 {result['reception_avg_utilization']:.1%}, 峰值 {result['reception_peak_utilization']:.1%}")
                print(f"    - FG码头: {result['FG_dock_avg_utilization']:.1%}")
                print(f"    - R&P码头: {result['R&P_dock_avg_utilization']:.1%}")
            
            # 导出详细数据（仅第一次重复）
            if rep == 0:
                output_path = os.path.join(RESULTS_DIR, f'simulation_details_{scenario_name}.xlsx')
                sim.kpi.export_to_excel(output_path)
        
        # 计算平均结果
        avg_result = {}
        for key in scenario_results[0].keys():
            # 跳过字典类型的数据（如hourly_dock_utilization）
            if key == 'hourly_dock_utilization':
                # 直接使用第一次重复的hourly数据（因为是平均后的结果）
                avg_result[key] = scenario_results[0][key]
                continue
            
            values = [r[key] for r in scenario_results]
            avg_result[key] = np.mean(values)
            avg_result[f'{key}_std'] = np.std(values)
        
        all_results[scenario_name] = avg_result
        
        print(f"\n{scenario_config['name']} - 平均结果 ({num_replications} 次重复):")
        print(f"  SLA 遵守率: {avg_result['sla_compliance_rate']:.2%} ± {avg_result['sla_compliance_rate_std']:.2%}")
        print(f"  平均卡车等待时间: {avg_result['avg_truck_wait_time']:.2f} ± {avg_result['avg_truck_wait_time_std']:.2f} 小时")
        print(f"  平均午夜积压: {avg_result['avg_midnight_backlog_pallets']:.1f} ± {avg_result['avg_midnight_backlog_pallets_std']:.1f} 托盘")
    
    # 生成对比表格
    comparison_df = pd.DataFrame(all_results).T
    comparison_path = os.path.join(RESULTS_DIR, 'simulation_results_comparison.xlsx')
    comparison_df.to_excel(comparison_path)
    
    print(f"\n{'='*70}")
    print("所有场景仿真完成！")
    print(f"Comparison results saved to: {comparison_path}")
    print(f"{'='*70}")
    
    return all_results, comparison_df


# ==================== 可视化 ====================

def visualize_results(comparison_df, all_results=None):
    """生成可视化图表"""
    scenarios = comparison_df.index.tolist()
    scenario_labels = [SIMULATION_CONFIG[s]['name'] for s in scenarios]
    
    print(f"\n{'='*70}\n生成可视化图表...\n{'='*70}")
    
    # 提取 hourly 数据用于时段分析
    hourly_data_all = {}
    if all_results:
        for scenario in scenarios:
            if scenario in all_results and 'hourly_dock_utilization' in all_results[scenario]:
                hourly_data_all[scenario] = all_results[scenario]['hourly_dock_utilization']
    
    # 图 1: SLA 遵守率
    fig, ax = plt.subplots(figsize=(10, 6))
    compliance_rates = comparison_df['sla_compliance_rate'] * 100
    errors = comparison_df['sla_compliance_rate_std'] * 100
    bars = ax.bar(scenario_labels, compliance_rates, yerr=errors, capsize=5, 
                   color=['#2ecc71', '#f39c12', '#e74c3c', '#c0392b'][:len(scenarios)])
    ax.set_ylabel('SLA Compliance Rate (%)', fontsize=12)
    ax.set_title('SLA Compliance Rate Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.set_ylim([0, 105])
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path1 = os.path.join(FIGURES_DIR, '1_sla_compliance_rate.png')
    plt.savefig(path1, dpi=300, bbox_inches='tight')
    print(f"SLA compliance rate chart saved: {path1}")
    plt.close()
    
    # 图 1b: SLA 按地区分解
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    g2_rates = comparison_df['G2_sla_compliance_rate'] * 100
    row_rates = comparison_df['ROW_sla_compliance_rate'] * 100
    g2_stds = comparison_df['G2_sla_compliance_rate_std'] * 100
    row_stds = comparison_df['ROW_sla_compliance_rate_std'] * 100
    
    bars1 = ax.bar(x - width/2, g2_rates, width, label='G2 Region', 
                   color='#3498db', yerr=g2_stds, capsize=5)
    bars2 = ax.bar(x + width/2, row_rates, width, label='ROW Region', 
                   color='#e74c3c', yerr=row_stds, capsize=5)
    
    ax.set_ylabel('SLA Compliance Rate (%)', fontsize=12)
    ax.set_title('SLA Compliance Rate by Region (G2 vs ROW)', fontsize=14, fontweight='bold', pad=20)
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
    
    # 图 2: 平均卡车等待时间
    fig, ax = plt.subplots(figsize=(10, 6))
    wait_times = comparison_df['avg_truck_wait_time']
    errors = comparison_df['avg_truck_wait_time_std']
    bars = ax.bar(scenario_labels, wait_times, yerr=errors, capsize=5,
                   color=['#1abc9c', '#16a085', '#27ae60', '#2980b9'][:len(scenarios)])
    ax.set_ylabel('Wait Time (Hours)', fontsize=12)
    ax.set_title('Average Truck Wait Time Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}h', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path2 = os.path.join(FIGURES_DIR, '2_avg_truck_wait_time.png')
    plt.savefig(path2, dpi=300, bbox_inches='tight')
    print(f"Wait time chart saved: {path2}")
    plt.close()
    
    # 图 3: 午夜积压
    fig, ax = plt.subplots(figsize=(10, 6))
    backlogs = comparison_df['avg_midnight_backlog_pallets']
    errors = comparison_df['avg_midnight_backlog_pallets_std']
    bars = ax.bar(scenario_labels, backlogs, yerr=errors, capsize=5,
                   color=['#95a5a6', '#7f8c8d', '#34495e', '#2c3e50'][:len(scenarios)])
    ax.set_ylabel('Number of Pallets', fontsize=12)
    ax.set_title('Average Midnight Backlog Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path3 = os.path.join(FIGURES_DIR, '3_midnight_backlog.png')
    plt.savefig(path3, dpi=300, bbox_inches='tight')
    print(f"Midnight backlog chart saved: {path3}")
    plt.close()
    
    # Figure 4: Flow Statistics (Stacked Bars)
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
    path4 = os.path.join(FIGURES_DIR, '4_flow_statistics.png')
    plt.savefig(path4, dpi=300, bbox_inches='tight')
    print(f"Flow statistics chart saved: {path4}")
    plt.close()
    
    # Figure 4b: FG Outbound by Region (Pallets)
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
    path4b = os.path.join(FIGURES_DIR, '4b_fg_outbound_by_region.png')
    plt.savefig(path4b, dpi=300, bbox_inches='tight')
    print(f"FG outbound flow by region chart saved: {path4b}")
    plt.close()
    
    # Figure 4c: Orders vs Pallets Flow Comparison
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
    path4c = os.path.join(FIGURES_DIR, '4c_flow_statistics_orders.png')
    plt.savefig(path4c, dpi=300, bbox_inches='tight')
    print(f"Orders flow statistics chart saved: {path4c}")
    plt.close()
    
    # Figure 4d: FG Outbound by Region (Orders)
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
    path4d = os.path.join(FIGURES_DIR, '4d_fg_outbound_orders_by_region.png')
    plt.savefig(path4d, dpi=300, bbox_inches='tight')
    print(f"FG outbound orders by region chart saved: {path4d}")
    plt.close()
    
    # Figure 5: Timeslot Dock Utilization Rate (by Direction)
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
    path5 = os.path.join(FIGURES_DIR, '5_timeslot_utilization.png')
    plt.savefig(path5, dpi=300, bbox_inches='tight')
    print(f"Timeslot utilization chart saved: {path5}")
    plt.close()
    
    # Figure 5b: Dock Utilization by Time Slot (4 category charts)
    if hourly_data_all:
        categories_directions = [
            ('FG', 'inbound', 'FG - Inbound - Slot Utilization', '#4A90E2', '#E8F4FF'),
            ('FG', 'outbound', 'FG - Outbound - Slot Utilization', '#50C878', '#E8F8F0'),
            ('R&P', 'inbound', 'R&P - Inbound - Slot Utilization', '#E74C3C', '#FDECEA'),
            ('R&P', 'outbound', 'R&P - Outbound - Slot Utilization', '#F39C12', '#FEF5E7')
        ]
        
        for category, direction, title, color_used, color_avail in categories_directions:
            scenario = 'baseline'
            if scenario not in hourly_data_all:
                continue
                
            key = f'{category}_{direction}'
            if key not in hourly_data_all[scenario]:
                continue
                
            hourly_dict = hourly_data_all[scenario][key]
            if not hourly_dict:
                continue
            
            # 准备数据 - 使用实际slot数量
            hours = sorted(hourly_dict.keys())
            used_slots = [hourly_dict[h]['used'] for h in hours]
            available_slots = [hourly_dict[h]['available'] - hourly_dict[h]['used'] for h in hours]
            total_capacity = [hourly_dict[h]['available'] for h in hours]
            
            fig, ax = plt.subplots(figsize=(14, 6))
            
            bar_width = 0.8
            x_pos = range(len(hours))
            
            bars_used = ax.bar(x_pos, used_slots, bar_width, 
                              label='Booking Taken', color=color_used, edgecolor='white', linewidth=0.5)
            bars_avail = ax.bar(x_pos, available_slots, bar_width, 
                               bottom=used_slots, label='Available Capacity', 
                               color=color_avail, edgecolor='white', linewidth=0.5)
            
            for i, (hour, used, total) in enumerate(zip(hours, used_slots, total_capacity)):
                if used >= 0.5 and total > 0:
                    utilization_pct = (used / total) * 100
                    ax.text(i, used/2, f'{utilization_pct:.0f}%', 
                           ha='center', va='center', fontsize=9, fontweight='bold', color='white')
            
            ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
            ax.set_xlabel('Time Slot (Hour)', fontsize=11)
            ax.set_ylabel('Number of Timeslots', fontsize=11)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(hours, fontsize=9)
            
            max_capacity = max(total_capacity) if total_capacity else 10
            ax.set_ylim([0, max_capacity * 1.1])
            
            ax.legend(loc='upper right', fontsize=10)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            
            plt.tight_layout()
            safe_title = title.replace(' ', '_').replace('-', '').lower()
            path = os.path.join(FIGURES_DIR, f'5b_{safe_title}.png')
            plt.savefig(path, dpi=300, bbox_inches='tight')
            print(f"Hourly utilization chart saved: {path}")
            plt.close()
    
    print(f"{'='*70}")
    print(f"All visualization charts completed! Total 13 figures saved to: {FIGURES_DIR}")
    print(f"  - Key metrics: 1-3.png (SLA, Wait Time, Congestion)")
    print(f"  - Regional SLA breakdown: 1b.png (G2 vs ROW regions)")
    print(f"  - Flow analysis: 4.png (Pallets), 4b-4d.png (Flow and Order stats)")
    print(f"  - Timeslot: 5.png (Average utilization)")
    print(f"  - Hourly analysis: 5b_*.png (4 charts: FG/R&P × Inbound/Outbound)")
    print(f"{'='*70}")


# ==================== Main Program Entry ====================

if __name__ == '__main__':
    # 设置随机种子以确保可重复性
    np.random.seed(42)
    
    # 运行场景对比
    results, comparison_df = run_scenario_comparison(
        scenarios_to_run=['baseline', 'scenario_1', 'scenario_2', 'scenario_3'],
        num_replications=3,  # 每个场景重复 3 次
        duration_days=30     # 仿真 30 天
    )
    
    # 可视化结果（传入all_results用于hourly数据）
    visualize_results(comparison_df, results)
    
    print("\n" + "="*70)
    print("仿真分析完成！生成的文件：")
    print("  1. simulation_results_comparison.xlsx - 场景对比汇总表")
    print("  2. simulation_details_*.xlsx - 各场景详细数据")
    print("  3. 共15张可视化图片：")
    print("     - 1: SLA遵守率")
    print("     - 1b: 按地区分解的SLA(G2 vs ROW)")
    print("     - 2: 平均卡车等待时间")
    print("     - 3: 平均午夜积压")
    print("     - 4: 流量统计（托盘）")
    print("     - 4b: FG按地区分解的出库流量（托盘）")
    print("     - 4c: 托盘流量与订单流量并列对比")
    print("     - 4d: FG按地区分解的出库订单数")
    print("     - 5: Timeslot平均利用率")
    print("     - 5b_*: 4张时段详细分析（FG/R&P × Inbound/Outbound）")
    print("="*70)
