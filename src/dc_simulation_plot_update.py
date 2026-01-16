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
            self.creation_time = None  # 绝对仿真时间，后续计算
            self.preparation_started = False
            self.preparation_completed = False
            self.preparation_pallets_done = 0
        
        # Inbound/Outbound通用
        self.timeslot_hour = order_data.get('timeslot_hour')
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
    def __init__(self, operating_hours=18):
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
    
    def get_hourly_capacity(self, category, direction, coefficient=1.0):
        """每小时处理能力（托盘/小时）
        
        公式: (调整FTE × 效率) / 月度工时 × coefficient
        """
        fte = self.adjusted_fte[category][direction]
        efficiency = self.efficiency_per_fte[category]
        base_capacity = (fte * efficiency) / self.hours_per_month
        adjusted_capacity = base_capacity * coefficient
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


# ==================== 主仿真类 ====================

class DCSimulation:
    """配送中心仿真主控制器"""
    
    def __init__(self, env, scenario_config, run_id=1):
        self.env = env
        self.config = scenario_config
        # backward-compat alias (older code paths may reference dc_config)
        self.dc_config = self.config
        self.run_id = run_id
        
        # 初始化资源
        self._init_resources()
        
        # KPI 收集器
        self.kpi = KPICollector()
        
        # ===== 新逻辑：加载预生成订单 =====
        self.orders = self._load_orders()
        
        # 订单队列（FG Outbound） - 保留兼容性
        self.pending_orders = []
        
        # Opening hour coefficient（可手动调节）
        self.opening_hour_coefficient = scenario_config.get('opening_hour_coefficient', 
                                                             SYSTEM_PARAMETERS.get('opening_hour_coefficient', 1.0))
        
        # 如果启用到达平滑化，计算优化后的到达率（仅针对Outbound）
        if self.config.get('arrival_smoothing', False):
            self.arrival_rates = self._smooth_arrival_rates(self.config)
        else:
            self.arrival_rates = SYSTEM_PARAMETERS.get('truck_arrival_rates_outbound', 
                                                       SYSTEM_PARAMETERS.get('truck_arrival_rates', {}))
        
        print(f"初始化仿真: {scenario_config['name']}")
        print(f"  运营时间: {scenario_config['dc_open_time']:02d}:00 - {scenario_config['dc_close_time']:02d}:00")
        print(f"  运营小时数: {scenario_config['operating_hours']} 小时/天")
        print(f"  Opening Hour Coefficient: {self.opening_hour_coefficient}")
        
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
                    # 假设仿真从第1天0点开始
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
    
    # ==================== 新逻辑：订单驱动流程 ====================
    
    def outbound_order_scheduler(self, target_month=1):
        """Outbound订单调度器（新逻辑）
        
        Args:
            target_month: 仿真的目标月份
        """
        if not self.orders:
            print("警告: 无订单数据，跳过Outbound订单调度")
            return
        
        # 收集该月的所有Outbound订单
        outbound_orders = []
        for key, orders_list in self.orders.items():
            if f'M{target_month:02d}' in key and 'Outbound' in key:
                outbound_orders.extend(orders_list)
        
        if not outbound_orders:
            print(f"警告: 月份{target_month}无Outbound订单")
            return
        
        print(f"调度{len(outbound_orders)}个Outbound订单")
        
        # 按creation_time排序
        outbound_orders.sort(key=lambda o: o.creation_time)
        
        for order in outbound_orders:
            # 等待到creation_time启动备货
            if order.creation_time > self.env.now:
                yield self.env.timeout(order.creation_time - self.env.now)
            
            # 启动备货流程
            self.env.process(self.outbound_preparation_process(order))
            
            # 调度装货流程（在timeslot时刻）
            self.env.process(self.outbound_loading_process(order))
    
    def outbound_preparation_process(self, order):
        """Outbound备货流程（从creation_time开始）"""
        order.preparation_started = True
        order.processing_start_time = self.env.now
        
        # 获取每小时FTE处理能力
        hourly_capacity = self.fte_manager.get_hourly_capacity(
            order.category, 
            'Outbound',
            coefficient=self.opening_hour_coefficient
        )
        
        total_pallets = order.pallets
        processed_pallets = 0
        
        # 逐小时处理直到完成或到达timeslot
        while processed_pallets < total_pallets:
            # 检查是否已到timeslot时刻
            if order.timeslot_time and self.env.now >= order.timeslot_time:
                break
            
            # 本小时能处理的数量（取剩余和容量的最小值）
            pallets_this_hour = min(hourly_capacity, total_pallets - processed_pallets)
            
            # 计算需要的时间（小时）
            time_needed = pallets_this_hour / hourly_capacity if hourly_capacity > 0 else 1
            
            # 等待处理完成（但不超过timeslot时刻）
            if order.timeslot_time:
                time_until_slot = max(0, order.timeslot_time - self.env.now)
                actual_time = min(time_needed, time_until_slot)
            else:
                actual_time = time_needed
            
            if actual_time > 0:
                yield self.env.timeout(actual_time)
                processed_pallets += pallets_this_hour
                order.preparation_pallets_done = processed_pallets
        
        # 检查是否完成
        if processed_pallets >= total_pallets:
            order.preparation_completed = True
            order.processing_end_time = self.env.now
    
    def outbound_loading_process(self, order):
        """Outbound装货流程（在timeslot时刻）"""
        # 等待到timeslot时刻
        if order.timeslot_time and order.timeslot_time > self.env.now:
            yield self.env.timeout(order.timeslot_time - self.env.now)
        
        # 检查备货是否完成
        if not order.preparation_completed:
            # 备货未完成：该订单不可能按原timeslot完成
            order.on_time = False

            # 继续等待备货完成
            while not order.preparation_completed:
                yield self.env.timeout(0.1)  # 每6分钟检查一次

            # 重新分配到下一个可用的整点timeslot（并尽量避开DC关闭时段/零容量时段）
            new_slot = self.reschedule_delayed_order(order)

            # 等待到新timeslot（new_slot 保证不早于当前时间，且为整点）
            if new_slot > self.env.now:
                yield self.env.timeout(new_slot - self.env.now)
        else:
            # 备货完成：按原timeslot执行（如果容量满，后续仍可能顺延）
            if order.timeslot_time is not None:
                # timeslot_time是整点，但为了稳妥仍做一次对齐
                slot = int(order.timeslot_time)
                if slot > self.env.now:
                    yield self.env.timeout(slot - self.env.now)
        
        # 检查timeslot容量
        slot_key = f'{order.category.lower()}_loading' if order.category == 'FG' else 'rp_loading'
        
        # 等待可用slot（如果当前小时已满）
        while True:
            available = self.hourly_timeslot_capacity.get(slot_key, 0)
            used = self.hourly_timeslot_used.get(slot_key, 0)
            
            if used < available:
                break
            
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
        
        # 装货（1小时）
        loading_start = self.env.now
        yield self.env.timeout(1)
        
        order.completed = True
        
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
        # 检查timeslot容量
        slot_key = f'{order.category.lower()}_reception' if order.category == 'FG' else 'rp_reception'
        
        # 等待可用slot
        while True:
            available = self.hourly_timeslot_capacity.get(slot_key, 0)
            used = self.hourly_timeslot_used.get(slot_key, 0)
            
            if used < available:
                break
            
            yield self.env.timeout(1)
        
        # 占用timeslot
        self.hourly_timeslot_used[slot_key] = self.hourly_timeslot_used.get(slot_key, 0) + 1
        
        # 卸货（1小时）
        unloading_start = self.env.now
        yield self.env.timeout(1)
        
        # 记录24小时处理deadline
        order.processing_deadline = self.env.now + 24
        order.processing_start_time = self.env.now
        
        # FTE处理（24小时内完成）
        hourly_capacity = self.fte_manager.get_hourly_capacity(
            order.category,
            'Inbound',
            coefficient=self.opening_hour_coefficient
        )
        
        total_pallets = order.pallets
        processed_pallets = 0
        
        while processed_pallets < total_pallets:
            # 检查是否超过deadline
            if self.env.now >= order.processing_deadline:
                print(f"警告: 订单{order.order_id}超过24h处理deadline")
                break
            
            # 本小时能处理的数量
            pallets_this_hour = min(hourly_capacity, total_pallets - processed_pallets)
            time_needed = pallets_this_hour / hourly_capacity if hourly_capacity > 0 else 1
            
            yield self.env.timeout(time_needed)
            processed_pallets += pallets_this_hour
        
        order.processing_end_time = self.env.now
        order.completed = True
        
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

        dc_open = self.config['dc_open_time']
        dc_close = self.config['dc_close_time']

        def _hourly_capacity(hour_of_day: int) -> int:
            if order.category == 'FG':
                cap_map = hourly_config['FG']['loading']
            else:
                cap_map = hourly_config['R&P']['loading']
            return cap_map.get(hour_of_day, cap_map.get(str(hour_of_day), 0))

        def _is_open(hour_of_day: int) -> bool:
            # 当前模型所有场景均为同日开关门（dc_open < dc_close）
            return dc_open <= hour_of_day < dc_close

        # 从下一整点开始查找（避免返回小数时间导致非整点装货）
        search_start = int(np.ceil(self.env.now))

        # 扫描更长窗口，避免尾部时段“无解”
        for abs_hour in range(search_start, search_start + 24 * 30):  # 最多搜索30天
            hour_of_day = abs_hour % 24
            if not _is_open(hour_of_day):
                continue
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
        
        # 生成汇总报告
        summary = self.kpi.generate_summary()
        
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

        # Outbound on-time（按 timeslot）
        outbound = [o for o in scoped_orders if o.direction == 'Outbound']
        stats['total_outbound_orders'] = len(outbound)
        stats['completed_outbound_orders'] = sum(1 for o in outbound if o.completed)
        stats['on_time_outbound_orders'] = sum(1 for o in outbound if o.completed and o.on_time)
        stats['delayed_outbound_orders'] = sum(1 for o in outbound if o.completed and not o.on_time)

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
            os_ = result.get('order_statistics', {})
            print(f"  完成率: {os_.get('completion_rate', 0):.1f}%")
            print(f"  准时率(所有订单): {os_.get('on_time_rate_all', os_.get('on_time_rate', 0)):.1f}%")
            print(f"  准时率(仅已完成订单): {os_.get('on_time_rate_completed', 0):.1f}%")
            
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
            # 跳过字典类型的数据（如hourly_dock_utilization, order_statistics）
            if key in ['hourly_dock_utilization', 'order_statistics']:
                if key == 'order_statistics':
                    # 对常用KPI做跨重复平均，避免“只看第一次重复”的偏差
                    dicts = [r.get('order_statistics', {}) for r in scenario_results]
                    numeric_keys = [
                        'total_orders', 'completed_orders', 'incomplete_orders',
                        'on_time_orders', 'delayed_orders', 'total_delay_hours',
                        'completion_rate', 'on_time_rate', 'on_time_rate_all', 'on_time_rate_completed',
                        'avg_delay_hours'
                    ]
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
    
    # 图 1: 完成率 + 准时率（所有订单口径）
    fig, ax = plt.subplots(figsize=(12, 6))

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
    ax.set_xticklabels(scenario_labels, rotation=15, ha='right')
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
        categories_directions = [
            ('FG', 'inbound', 'FG - Inbound - Slot Utilization', '#4A90E2', '#E8F4FF'),
            ('FG', 'outbound', 'FG - Outbound - Slot Utilization', '#50C878', '#E8F8F0'),
            ('R&P', 'inbound', 'R&P - Inbound - Slot Utilization', '#E74C3C', '#FDECEA'),
            ('R&P', 'outbound', 'R&P - Outbound - Slot Utilization', '#F39C12', '#FEF5E7')
        ]
        
        for category, direction, title, color_used, color_avail in categories_directions:
            key = f'{category}_{direction}'
            hours = list(range(24))

            fig, axes = plt.subplots(2, 2, figsize=(18, 10), sharey=True)
            axes = axes.flatten()

            has_any = False
            for i, scenario in enumerate(scenarios[:4]):
                ax = axes[i]
                if scenario not in hourly_data_all or key not in hourly_data_all[scenario]:
                    ax.set_axis_off()
                    continue

                hourly_dict = hourly_data_all[scenario][key]
                if not hourly_dict:
                    ax.set_axis_off()
                    continue

                util_rates = []
                for h in hours:
                    d = hourly_dict.get(h)
                    if not d:
                        util_rates.append(0.0)
                        continue
                    avail = d.get('available', 0)
                    used = d.get('used', 0)
                    util_rates.append((used / avail * 100) if avail else 0.0)

                ax.bar(hours, util_rates, color='#4A90E2', alpha=0.85, edgecolor='white', linewidth=0.5)
                ax.set_title(SIMULATION_CONFIG[scenario]['name'], fontsize=12, fontweight='bold')
                ax.set_xticks(hours)
                ax.set_xticklabels(hours, fontsize=8)
                ax.set_ylim([0, 105])
                ax.grid(axis='y', alpha=0.25, linestyle='--')
                has_any = True

            if not has_any:
                plt.close(fig)
                continue

            fig.suptitle(title + ' (Bars per Scenario)', fontsize=15, fontweight='bold', y=0.98)
            fig.text(0.5, 0.04, 'Time Slot (Hour)', ha='center', fontsize=11)
            fig.text(0.04, 0.5, 'Utilization Rate (%)', va='center', rotation='vertical', fontsize=11)

            plt.tight_layout(rect=[0.05, 0.06, 1, 0.94])
            safe_title = (
                title.replace(' ', '_')
                .replace('-', '')
                .replace('&', 'and')
                .lower()
            )
            path = os.path.join(FIGURES_DIR, f'3b_{safe_title}.png')
            plt.savefig(path, dpi=300, bbox_inches='tight')
            print(f"Hourly utilization chart saved: {path}")
            plt.close()
    
    print(f"{'='*70}")
    print(f"All visualization charts completed! Figures saved to: {FIGURES_DIR}")
    print(f"  - 1_completion_on_time_rate.png: Completion + On-time rate (all orders)")
    print(f"  - 1b_sla_by_region.png: On-time rate by region (G2 vs ROW, all orders)")
    print(f"  - 2*.png: Flow statistics (pallets & orders)")
    print(f"  - 3_timeslot_utilization.png: Average dock utilization")
    print(f"  - 3b_*.png: Hourly utilization by slot (all scenarios on same chart)")
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
    print("  3. 可视化图片（见 outputs/figures/）:")
    print("     - 1_completion_on_time_rate: 完成率 + 准时率（所有订单口径）")
    print("     - 1b_sla_by_region: 按地区分解准时率(G2 vs ROW，所有订单口径)")
    print("     - 2/2b/2c/2d: 流量统计（托盘与订单）")
    print("     - 3_timeslot_utilization: Timeslot平均利用率")
    print("     - 3b_*: 4张时段详细分析（每张图同时包含4个scenario）")
    print("="*70)
