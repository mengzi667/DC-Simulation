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

def load_simulation_config(config_path='simulation_config.json'):
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
    },
    'scenario_4': {
        'name': 'Scenario 4: Arrival Optimized (07:00-23:00)',
        'dc_open_time': 7,
        'dc_close_time': 23,
        'operating_hours': 16,
        'arrival_smoothing': True
    }
}

if LOADED_CONFIG:
    SYSTEM_PARAMETERS = {
        'efficiency': LOADED_CONFIG['efficiency'],
        'factory_production': LOADED_CONFIG['factory_production'],
        'buffer_capacity': LOADED_CONFIG['buffer_capacity'],
        'truck_arrival_rates': LOADED_CONFIG['truck_arrival_rates'],
    }
    
    # 加载码头容量（如果配置文件中有，否则使用默认值）
    if 'hourly_dock_capacity' in LOADED_CONFIG:
        SYSTEM_PARAMETERS['hourly_dock_capacity'] = LOADED_CONFIG['hourly_dock_capacity']
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
        
        'truck_arrival_rates': {
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
    """卡车实体"""
    _id_counter = 0
    
    def __init__(self, category, direction, pallets, scheduled_time):
        Truck._id_counter += 1
        self.id = Truck._id_counter
        self.category = category  # 'FG' or 'R&P'
        self.direction = direction  # 'Inbound' or 'Outbound'
        self.pallets = pallets
        self.scheduled_time = scheduled_time
        self.actual_arrival_time = None
        self.service_start_time = None
        self.service_end_time = None
        self.departure_deadline = None  # 仅 FG Outbound 使用
        
    def __repr__(self):
        return f"Truck-{self.id}({self.category}-{self.direction}, {self.pallets}p)"


class Order:
    """订单实体"""
    _id_counter = 0
    
    def __init__(self, pallets, order_time, departure_time):
        Order._id_counter += 1
        self.id = Order._id_counter
        self.pallets = pallets
        self.order_time = order_time  # 下单/到达时间
        self.departure_time = departure_time  # 要求发运时间
        self.completion_time = None  # 实际完成时间
        
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
    """人力资源管理器"""
    def __init__(self, total_fte):
        self.total_fte = total_fte
        self.efficiency_params = SYSTEM_PARAMETERS['efficiency']
        
    def get_efficiency(self, category):
        """获取团队实际效率（考虑随机波动）
        
        返回: 团队总效率（托盘/小时）
        计算: 单人效率 × 分配人数
        
        注意: 团队规模基于总人数和码头数量的合理分配
        - 考虑轮班制度（不是所有人同时工作）
        - 考虑多个并发码头分摊人力
        """
        if category == 'R&P':
            mean = self.efficiency_params['rp_mean']
            std = self.efficiency_params['rp_std']
            # R&P: 28人 ÷ (入库1+出库6最多) ≈ 4人/码头
            # 考虑轮班，每班约6-8人服务一个码头
            team_size = 8
        else:  # FG
            mean = self.efficiency_params['fg_mean']
            std = self.efficiency_params['fg_std']
            # FG: 97人 ÷ (入库2+出库1) ≈ 32人/码头
            # 但FG出库只有1个码头，可能分配更多人
            # 考虑轮班和其他活动，假设每班约15人服务出库码头
            team_size = 15
        
        # 使用截断正态分布（避免负值或异常值）
        efficiency_per_person = np.random.normal(mean, std)
        efficiency_per_person = max(efficiency_per_person, mean * 0.5)  # 最低效率为平均值的 50%
        
        # 返回团队总效率
        return efficiency_per_person * team_size
    
    def allocate_fte(self, rp_workload, fg_workload):
        """根据工作负荷动态分配 FTE"""
        total_workload = rp_workload + fg_workload
        if total_workload == 0:
            return 0, 0
        
        # 按比例分配
        fte_rp = (rp_workload / total_workload) * self.total_fte
        fte_fg = (fg_workload / total_workload) * self.total_fte
        
        return fte_rp, fte_fg


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
            'on_time': order.completion_time <= order.departure_time
        })
    
    def record_inbound_operation(self, category, pallets, start_time, end_time, from_buffer):
        self.inbound_operations.append({
            'category': category,
            'pallets': pallets,
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'from_buffer': from_buffer
        })
    
    def record_outbound_operation(self, truck):
        self.outbound_operations.append({
            'category': truck.category,
            'pallets': truck.pallets,
            'scheduled_time': truck.scheduled_time,
            'start_time': truck.service_start_time,
            'end_time': truck.service_end_time
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
        
        # 缓冲区溢出
        summary['buffer_overflow_events'] = len(self.buffer_overflows)
        summary['total_overflow_pallets'] = sum(e['pallets'] for e in self.buffer_overflows)
        
        # 等待时间
        if self.truck_wait_times:
            wait_times = [w['wait_time'] for w in self.truck_wait_times]
            summary['avg_truck_wait_time'] = np.mean(wait_times)
            summary['max_truck_wait_time'] = np.max(wait_times)
            summary['p95_truck_wait_time'] = np.percentile(wait_times, 95)
        else:
            summary['avg_truck_wait_time'] = 0
            summary['max_truck_wait_time'] = 0
            summary['p95_truck_wait_time'] = 0
        
        # SLA 遵守率
        total_orders = len(self.completed_orders)
        if total_orders > 0:
            on_time_orders = sum(1 for o in self.completed_orders if o['on_time'])
            summary['sla_compliance_rate'] = on_time_orders / total_orders
            summary['sla_miss_rate'] = 1 - summary['sla_compliance_rate']
            summary['total_sla_misses'] = len(self.sla_misses)
        else:
            summary['sla_compliance_rate'] = 1.0
            summary['sla_miss_rate'] = 0.0
            summary['total_sla_misses'] = 0
        
        # 午夜积压
        if self.midnight_backlogs:
            summary['avg_midnight_backlog_orders'] = np.mean([b['pending_orders'] for b in self.midnight_backlogs])
            summary['avg_midnight_backlog_pallets'] = np.mean([b['pending_pallets'] for b in self.midnight_backlogs])
            summary['max_midnight_backlog_pallets'] = max([b['pending_pallets'] for b in self.midnight_backlogs])
        else:
            summary['avg_midnight_backlog_orders'] = 0
            summary['avg_midnight_backlog_pallets'] = 0
            summary['max_midnight_backlog_pallets'] = 0
        
        # 作业统计
        summary['total_inbound_pallets'] = sum(o['pallets'] for o in self.inbound_operations)
        summary['total_outbound_pallets'] = sum(o['pallets'] for o in self.outbound_operations)
        
        # 缓冲区平均占用率
        for category in ['R&P', 'FG']:
            if category in self.hourly_buffer_occupancy:
                occupancy_rates = [o['occupancy_rate'] for o in self.hourly_buffer_occupancy[category]]
                summary[f'{category.lower()}_avg_buffer_occupancy'] = np.mean(occupancy_rates)
            else:
                summary[f'{category.lower()}_avg_buffer_occupancy'] = 0
        
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
        
        # 如果启用到达平滑化，计算优化后的到达率
        if self.config.get('arrival_smoothing', False):
            self.arrival_rates = self._smooth_arrival_rates(self.config)
        else:
            self.arrival_rates = SYSTEM_PARAMETERS['truck_arrival_rates']
        
        print(f"初始化仿真: {scenario_config['name']}")
        print(f"  运营时间: {scenario_config['dc_open_time']:02d}:00 - {scenario_config['dc_close_time']:02d}:00")
        print(f"  运营小时数: {scenario_config['operating_hours']} 小时/天")
        if self.config.get('arrival_smoothing', False):
            print(f"  到达优化: 已启用（平滑高峰流量）")
    
    def _init_resources(self):
        """初始化仿真资源（时变码头容量）"""
        # 时变码头资源 - 使用实际FG/R&P分类数据（来自48周Timeslot）
        hourly_config = SYSTEM_PARAMETERS['hourly_dock_capacity']
        
        # 获取FG和R&P的最大容量（不再使用70:30比例）
        max_fg_loading = max(hourly_config['FG']['loading'].values())
        max_fg_reception = max(hourly_config['FG']['reception'].values())
        max_rp_loading = max(hourly_config['R&P']['loading'].values())
        max_rp_reception = max(hourly_config['R&P']['reception'].values())
        
        # 创建最大容量的码头资源（稍后通过request数量控制实际可用数）
        self.max_docks = {
            'fg_reception': max_fg_reception,
            'fg_loading': max_fg_loading,
            'rp_reception': max_rp_reception,
            'rp_loading': max_rp_loading
        }
        
        self.docks = {
            'FG_Reception': simpy.Resource(self.env, capacity=self.max_docks['fg_reception']),
            'FG_Loading': simpy.Resource(self.env, capacity=self.max_docks['fg_loading']),
            'RP_Reception': simpy.Resource(self.env, capacity=self.max_docks['rp_reception']),
            'RP_Loading': simpy.Resource(self.env, capacity=self.max_docks['rp_loading'])
        }
        
        # 当前小时的实际可用码头数（动态更新）
        self.current_dock_capacity = {
            'fg_reception': 0,
            'fg_loading': 0,
            'rp_reception': 0,
            'rp_loading': 0
        }
        
        # 启动码头容量更新进程
        self.env.process(self.update_dock_capacity_process())
        
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
        
        # 人力资源管理器
        self.fte_manager = FTEManager(SYSTEM_PARAMETERS['fte_total'])
    
    def _smooth_arrival_rates(self, dc_config):
        """
        根据DC运营时间动态平滑到达率：限制高峰流量，分散到非高峰时段
        
        策略：
        - FG高峰（10-13点）：从3.15降至1.75（服务能力）
        - 超出部分**仅分配到DC开放时段内的低谷时段**
        - R&P保持不变（无明显瓶颈）
        """
        original_rates = SYSTEM_PARAMETERS['truck_arrival_rates']
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
    
    def update_dock_capacity_process(self):
        """动态更新码头容量（按小时）"""
        hourly_config = SYSTEM_PARAMETERS['hourly_dock_capacity']
        
        while True:
            current_hour = int(self.env.now) % 24
            
            # 直接使用FG和R&P的实际容量（不再计算比例）
            self.current_dock_capacity['fg_loading'] = hourly_config['FG']['loading'].get(current_hour, 0)
            self.current_dock_capacity['rp_loading'] = hourly_config['R&P']['loading'].get(current_hour, 0)
            self.current_dock_capacity['fg_reception'] = hourly_config['FG']['reception'].get(current_hour, 0)
            self.current_dock_capacity['rp_reception'] = hourly_config['R&P']['reception'].get(current_hour, 0)
            
            # 等待到下一个小时
            next_hour = (int(self.env.now) // 1 + 1) * 1
            yield self.env.timeout(next_hour - self.env.now)
    
    def get_available_docks(self, dock_type, category):
        """获取当前可用的码头数量"""
        key = f'{category.lower()}_{dock_type.lower()}'
        return self.current_dock_capacity.get(key, 1)
    
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
        self.env.process(self.update_dock_capacity_process())  # 启动码头容量更新（重要！）
        self.env.process(self.factory_production_process('R&P'))
        self.env.process(self.factory_production_process('FG'))
        self.env.process(self.buffer_release_process())
        self.env.process(self.truck_arrival_process())  # 统一的卡车到达进程（包含FG和R&P）
        self.env.process(self.buffer_monitor())
        self.env.process(self.midnight_backlog_monitor())  # 启动午夜积压监控
        
        # 运行仿真
        self.env.run(until=duration_days * 24)
        
        print(f"仿真运行完成！")
        
        # 生成汇总报告
        summary = self.kpi.generate_summary()
        return summary
    
    def factory_production_process(self, category):
        """工厂 24/7 连续生产进程"""
        production_params = SYSTEM_PARAMETERS['factory_production']
        # 使用正确的参数名（小写，使用下划线）
        param_key = 'rp_rate' if category == 'R&P' else 'fg_rate'
        rate = production_params[param_key]
        
        while True:
            # 每小时生成托盘（泊松分布）
            pallets = np.random.poisson(rate)
            
            if not self.is_dc_open():
                # DC 关闭，进入缓冲区
                buffer = self.buffer_rp if category == 'R&P' else self.buffer_fg
                success = buffer.add(pallets, self.env.now)
                
                if not success:
                    # 缓冲区溢出
                    self.kpi.record_buffer_overflow(category, self.env.now, pallets)
            else:
                # DC 开启，直接处理入库
                self.env.process(self.inbound_process(category, pallets, from_buffer=False))
            
            yield self.env.timeout(1)  # 等待 1 小时
    
    def buffer_release_process(self):
        """缓冲区释放进程（DC 开门时优先处理）"""
        while True:
            if self.is_dc_open():
                # 释放 R&P 缓冲
                if self.buffer_rp.current_pallets > 0:
                    release_amount = min(100, self.buffer_rp.current_pallets)
                    pallets = self.buffer_rp.release(release_amount)
                    if pallets > 0:
                        self.env.process(self.inbound_process('R&P', pallets, from_buffer=True))
                
                # 释放 FG 缓冲
                if self.buffer_fg.current_pallets > 0:
                    release_amount = min(150, self.buffer_fg.current_pallets)
                    pallets = self.buffer_fg.release(release_amount)
                    if pallets > 0:
                        self.env.process(self.inbound_process('FG', pallets, from_buffer=True))
            
            yield self.env.timeout(0.5)  # 每 30 分钟检查一次
    
    def truck_arrival_process(self):
        """
        卡车到达进程（基于统计到达率）
        
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
                    if hour in arrival_rates[category]:
                        # 混合到达模型（预约+临时）
                        # 基于实际数据验证：FG Var/Mean=0.48, R&P Var/Mean=0.30
                        # 到达比泊松分布更规律，使用75%预约+25%临时模型
                        lambda_hour = arrival_rates[category][hour]
                        scheduled_ratio = 0.75  # 75%为预约到达
                        
                        # 预约到达（近似确定性）
                        num_scheduled = int(lambda_hour * scheduled_ratio + 0.5)  # 四舍五入
                        
                        # 临时到达（泊松分布）
                        num_random = np.random.poisson(lambda_hour * (1 - scheduled_ratio))
                        
                        num_arrivals = num_scheduled + num_random
                        
                        for _ in range(num_arrivals):
                            # 生成指定类别的卡车
                            truck = self._generate_truck(category)
                            
                            # 添加到达延迟（指数分布，平均 15 分钟）
                            # 避免同一小时内所有卡车同时到达
                            delay = np.random.exponential(scale=0.25)
                            yield self.env.timeout(delay)
                            
                            truck.actual_arrival_time = self.env.now
                            
                            # 启动出库处理（所有卡车都是Outbound）
                            self.env.process(self.outbound_process(truck))
            
            yield self.env.timeout(1)  # 每小时检查一次
    
    def inbound_process(self, category, pallets, from_buffer=False):
        """入库处理进程（考虑时变码头容量）"""
        # 根据类别确定码头键名（使用大写，与资源字典匹配）
        if category == 'R&P':
            dock_key = 'RP_Reception'
            capacity_key = 'rp_reception'
        else:
            dock_key = 'FG_Reception'
            capacity_key = 'fg_reception'
        
        # 等待直到有可用码头
        while True:
            available_docks = self.current_dock_capacity[capacity_key]
            current_usage = len(self.docks[dock_key].queue) + self.docks[dock_key].count
            
            if available_docks > 0 and current_usage < available_docks:
                break  # 有可用码头，跳出等待循环
            else:
                # 没有可用码头，等待15分钟后重新检查
                yield self.env.timeout(0.25)
        
        # 请求码头资源
        with self.docks[dock_key].request() as req:
            yield req
            
            start_time = self.env.now
            
            # 获取团队效率并计算处理时间
            # efficiency: 团队总效率（托盘/小时）
            efficiency = self.fte_manager.get_efficiency(category)
            processing_time = pallets / efficiency
            
            # 处理
            yield self.env.timeout(processing_time)
            
            # 记录 KPI
            self.kpi.record_inbound_operation(
                category, pallets, start_time, self.env.now, from_buffer
            )

    
    def outbound_process(self, truck):
        """出库处理进程（考虑时变码头容量）"""
        # 根据类别确定码头键名
        if truck.category == 'R&P':
            dock_key = 'RP_Loading'
            capacity_key = 'rp_loading'
        else:
            dock_key = 'FG_Loading'
            capacity_key = 'fg_loading'
        
        # 等待直到有可用码头
        while True:
            available_docks = self.current_dock_capacity[capacity_key]
            current_usage = len(self.docks[dock_key].queue) + self.docks[dock_key].count
            
            if available_docks > 0 and current_usage < available_docks:
                break  # 有可用码头，跳出等待循环
            else:
                # 没有可用码头，等待15分钟后重新检查
                yield self.env.timeout(0.25)
        
        # 请求装车码头
        with self.docks[dock_key].request() as req:
            yield req
            
            truck.service_start_time = self.env.now
            
            # 记录等待时间（传入DC配置以排除关闭时间）
            self.kpi.record_truck_wait(truck, self.config)
            
            # 获取团队效率并计算装车时间
            # efficiency: 团队总效率（托盘/小时）
            # 例如：FG团队10人 × 3.5托盘/小时/人 = 35托盘/小时
            #       30托盘 / 35托盘/小时 = 0.86小时 ≈ 51分钟
            efficiency = self.fte_manager.get_efficiency(truck.category)
            loading_time = truck.pallets / efficiency
            
            # 执行装车
            yield self.env.timeout(loading_time)
            
            truck.service_end_time = self.env.now
            
            # 检查是否错过发运时间（仅 FG）
            if truck.category == 'FG' and truck.departure_deadline:
                if self.env.now > truck.departure_deadline:
                    # 创建虚拟订单记录 SLA miss
                    dummy_order = Order(truck.pallets, truck.scheduled_time, truck.departure_deadline)
                    self.kpi.record_sla_miss(dummy_order, self.env.now)
            
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
        生成指定类别的随机到达卡车
        
        Args:
            category: 'FG' 或 'R&P'
        
        Returns:
            Truck: 新生成的卡车实体
            
        生成规则:
            - 类别: 由调用者指定（基于实际到达率）
            - 托盘数: 基于实际数据的三角分布（FG: 1-33-276, R&P: 1-22-560）
            - 方向: Outbound（出库装车）
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
        
        # 创建卡车实体
        truck = Truck(category, 'Outbound', pallets, self.env.now)
        
        # 为成品出库设置发运时限（到达后8小时内必须完成）
        if category == 'FG':
            truck.departure_deadline = self.env.now + 8  # 8小时SLA
        
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
            print(f"  SLA 遵守率: {result['sla_compliance_rate']:.2%}")
            print(f"  SLA 延误次数: {result['total_sla_misses']}")
            print(f"  缓冲区溢出事件: {result['buffer_overflow_events']}")
            print(f"  缓冲区溢出托盘: {result['total_overflow_pallets']}")
            print(f"  平均卡车等待时间: {result['avg_truck_wait_time']:.2f} 小时")
            print(f"  平均午夜积压: {result['avg_midnight_backlog_pallets']:.1f} 托盘")
            
            # 导出详细数据（仅第一次重复）
            if rep == 0:
                output_path = os.path.join(RESULTS_DIR, f'simulation_details_{scenario_name}.xlsx')
                sim.kpi.export_to_excel(output_path)
        
        # 计算平均结果
        avg_result = {}
        for key in scenario_results[0].keys():
            values = [r[key] for r in scenario_results]
            avg_result[key] = np.mean(values)
            avg_result[f'{key}_std'] = np.std(values)
        
        all_results[scenario_name] = avg_result
        
        print(f"\n{scenario_config['name']} - 平均结果 ({num_replications} 次重复):")
        print(f"  SLA 遵守率: {avg_result['sla_compliance_rate']:.2%} ± {avg_result['sla_compliance_rate_std']:.2%}")
        print(f"  缓冲区溢出事件: {avg_result['buffer_overflow_events']:.1f} ± {avg_result['buffer_overflow_events_std']:.1f}")
        print(f"  平均卡车等待时间: {avg_result['avg_truck_wait_time']:.2f} ± {avg_result['avg_truck_wait_time_std']:.2f} 小时")
        print(f"  平均午夜积压: {avg_result['avg_midnight_backlog_pallets']:.1f} ± {avg_result['avg_midnight_backlog_pallets_std']:.1f} 托盘")
    
    # 生成对比表格
    comparison_df = pd.DataFrame(all_results).T
    comparison_path = os.path.join(RESULTS_DIR, 'simulation_results_comparison.xlsx')
    comparison_df.to_excel(comparison_path)
    
    print(f"\n{'='*70}")
    print("所有场景仿真完成！")
    print(f"对比结果已保存到: {comparison_path}")
    print(f"{'='*70}")
    
    return all_results, comparison_df


# ==================== 可视化 ====================

def visualize_results(comparison_df):
    """可视化场景对比结果 - 分开保存为多张图"""
    
    scenarios = comparison_df.index.tolist()
    scenario_labels = [SIMULATION_CONFIG[s]['name'] for s in scenarios]
    
    print(f"\n{'='*70}")
    print("生成可视化图表...")
    print(f"{'='*70}")
    
    # ========== 图1: SLA 遵守率 ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    compliance_rates = comparison_df['sla_compliance_rate'] * 100
    errors = comparison_df['sla_compliance_rate_std'] * 100
    bars = ax.bar(scenario_labels, compliance_rates, yerr=errors, capsize=5, 
                   color=['#2ecc71', '#f39c12', '#e74c3c', '#c0392b'][:len(scenarios)])
    ax.set_ylabel('SLA 遵守率 (%)', fontsize=12)
    ax.set_title('SLA 遵守率对比', fontsize=14, fontweight='bold', pad=20)
    ax.set_ylim([0, 105])
    ax.axhline(y=95, color='red', linestyle='--', linewidth=2, label='目标 95%')
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path1 = os.path.join(FIGURES_DIR, '1_sla_compliance_rate.png')
    plt.savefig(path1, dpi=300, bbox_inches='tight')
    print(f"SLA遵守率图已保存: {path1}")
    plt.close()
    
    # ========== 图2: 缓冲区溢出事件 ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    overflow_events = comparison_df['buffer_overflow_events']
    errors = comparison_df['buffer_overflow_events_std']
    bars = ax.bar(scenario_labels, overflow_events, yerr=errors, capsize=5,
                   color=['#3498db', '#9b59b6', '#e67e22', '#e74c3c'][:len(scenarios)])
    ax.set_ylabel('溢出事件数', fontsize=12)
    ax.set_title('缓冲区溢出事件对比', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path2 = os.path.join(FIGURES_DIR, '2_buffer_overflow_events.png')
    plt.savefig(path2, dpi=300, bbox_inches='tight')
    print(f"缓冲区溢出图已保存: {path2}")
    plt.close()
    
    # ========== 图3: 平均卡车等待时间 ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    wait_times = comparison_df['avg_truck_wait_time']
    errors = comparison_df['avg_truck_wait_time_std']
    bars = ax.bar(scenario_labels, wait_times, yerr=errors, capsize=5,
                   color=['#1abc9c', '#16a085', '#27ae60', '#2980b9'][:len(scenarios)])
    ax.set_ylabel('等待时间 (小时)', fontsize=12)
    ax.set_title('平均卡车等待时间对比', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}h', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path3 = os.path.join(FIGURES_DIR, '3_avg_truck_wait_time.png')
    plt.savefig(path3, dpi=300, bbox_inches='tight')
    print(f"等待时间图已保存: {path3}")
    plt.close()
    
    # ========== 图4: 午夜积压 ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    backlogs = comparison_df['avg_midnight_backlog_pallets']
    errors = comparison_df['avg_midnight_backlog_pallets_std']
    bars = ax.bar(scenario_labels, backlogs, yerr=errors, capsize=5,
                   color=['#95a5a6', '#7f8c8d', '#34495e', '#2c3e50'][:len(scenarios)])
    ax.set_ylabel('积压托盘数', fontsize=12)
    ax.set_title('平均午夜积压对比', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path4 = os.path.join(FIGURES_DIR, '4_midnight_backlog.png')
    plt.savefig(path4, dpi=300, bbox_inches='tight')
    print(f"午夜积压图已保存: {path4}")
    plt.close()
    
    # ========== 图5: 缓冲区平均占用率 ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    rp_occupancy = comparison_df['r&p_avg_buffer_occupancy'] * 100
    fg_occupancy = comparison_df['fg_avg_buffer_occupancy'] * 100
    
    x = np.arange(len(scenario_labels))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, rp_occupancy, width, label='R&P', color='#3498db')
    bars2 = ax.bar(x + width/2, fg_occupancy, width, label='FG', color='#e74c3c')
    
    ax.set_ylabel('占用率 (%)', fontsize=12)
    ax.set_title('缓冲区平均占用率对比', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    path5 = os.path.join(FIGURES_DIR, '5_buffer_occupancy.png')
    plt.savefig(path5, dpi=300, bbox_inches='tight')
    print(f"缓冲区占用率图已保存: {path5}")
    plt.close()
    
    # ========== 图6: 综合评分 ==========
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 归一化并计算综合得分（越高越好）
    # 权重：SLA 40%, 缓冲溢出 20%, 等待时间 20%, 积压 20%
    normalized_scores = pd.DataFrame()
    normalized_scores['sla'] = comparison_df['sla_compliance_rate'] * 100
    
    # 缓冲溢出：如果所有场景都是0，则都得满分100
    buffer_max = comparison_df['buffer_overflow_events'].max()
    if buffer_max > 0:
        normalized_scores['buffer'] = 100 - (comparison_df['buffer_overflow_events'] / buffer_max * 100)
    else:
        normalized_scores['buffer'] = 100  # 所有场景都无溢出，都得满分
    
    # 等待时间：反向归一化（等待越短得分越高）
    wait_max = comparison_df['avg_truck_wait_time'].max()
    if wait_max > 0:
        normalized_scores['wait'] = 100 - (comparison_df['avg_truck_wait_time'] / wait_max * 100)
    else:
        normalized_scores['wait'] = 100
    
    # 积压：反向归一化（积压越少得分越高）
    backlog_max = comparison_df['avg_midnight_backlog_pallets'].max()
    if backlog_max > 0:
        normalized_scores['backlog'] = 100 - (comparison_df['avg_midnight_backlog_pallets'] / backlog_max * 100)
    else:
        normalized_scores['backlog'] = 100  # 所有场景都无积压，都得满分
    
    composite_score = (normalized_scores['sla'] * 0.4 + 
                       normalized_scores['buffer'] * 0.2 +
                       normalized_scores['wait'] * 0.2 +
                       normalized_scores['backlog'] * 0.2)
    
    bars = ax.barh(scenario_labels, composite_score, 
                   color=['#27ae60', '#f39c12', '#e67e22', '#c0392b', '#9b59b6'][:len(scenarios)])
    ax.set_xlabel('综合得分', fontsize=12)
    ax.set_title('综合性能评分\n(SLA 40%, 缓冲 20%, 等待 20%, 积压 20%)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xlim([0, 105])
    ax.grid(axis='x', alpha=0.3)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2.,
                f' {width:.1f}', ha='left', va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    path6 = os.path.join(FIGURES_DIR, '6_composite_score.png')
    plt.savefig(path6, dpi=300, bbox_inches='tight')
    print(f"综合评分图已保存: {path6}")
    plt.close()
    
    print(f"{'='*70}")
    print(f"所有可视化图表已生成完成！共6张图片保存在: {FIGURES_DIR}")
    print(f"{'='*70}")


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    # 设置随机种子以确保可重复性
    np.random.seed(42)
    
    # 运行场景对比
    results, comparison_df = run_scenario_comparison(
        scenarios_to_run=['baseline', 'scenario_1', 'scenario_2', 'scenario_3', 'scenario_4'],
        num_replications=3,  # 每个场景重复 3 次
        duration_days=30     # 仿真 30 天
    )
    
    # 可视化结果
    visualize_results(comparison_df)
    
    print("\n" + "="*70)
    print("仿真分析完成！生成的文件：")
    print("  1. simulation_results_comparison.xlsx - 场景对比汇总表")
    print("  2. simulation_details_*.xlsx - 各场景详细数据")
    print("  3. simulation_results_visualization.png - 可视化对比图")
    print("="*70)
