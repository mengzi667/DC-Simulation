# DC 运营时间缩短仿真建模方案

## 一、建模方法论选择

### 1.1 推荐使用离散事件仿真 (Discrete Event Simulation, DES)

**为什么选择 DES：**
- 能够模拟物流系统中的离散事件（卡车到达、装卸作业、时位预约）
- 支持随机性建模（生产率波动、到达时间不确定性）
- 可以跟踪个体实体（托盘、订单、卡车）的完整生命周期
- 便于计算时间依赖的 KPI（等待时间、完成率、SLA）

**推荐工具：**
1. **SimPy（Python）** - 首选，与您现有 Python 代码无缝集成
2. AnyLogic - 可视化强，但需要学习新平台
3. Arena/FlexSim - 商业软件，功能强大但成本高

### 1.2 模型层次结构

```
主控制器 (Simulation Controller)
│
├── 时间管理模块 (Time Management)
│   ├── DC 运营时间窗口控制
│   ├── 时位预约系统
│   └── 班次调度
│
├── 业务流模块 (Business Processes)
│   ├── R&P 流程
│   │   ├── 入库流程（Reception）
│   │   ├── 存储/拣选
│   │   └── 出库流程（Loading to Factory）
│   │
│   └── FG 流程
│       ├── 入库流程（From Factory）
│       ├── 存储/拣选
│       └── 出库流程（Loading to Customers）
│
├── 资源管理模块 (Resource Management)
│   ├── 码头资源（Docks）
│   ├── 人力资源（FTE）
│   ├── 存储空间
│   └── 挂车缓冲（Trailer Buffer）
│
└── 数据收集模块 (Data Collection)
    ├── KPI 监控
    ├── 瓶颈分析
    └── 日志记录
```

## 二、详细建模方案

### 2.1 核心实体定义 (Entities)

```python
# 伪代码示例
class Truck:
    def __init__(self):
        self.id = unique_id
        self.category = 'FG' or 'R&P'
        self.direction = 'Inbound' or 'Outbound'
        self.pallets = number
        self.scheduled_time = datetime
        self.actual_arrival_time = datetime  # 加随机延迟
        self.service_start_time = None
        self.service_end_time = None
        
class Order:
    def __init__(self):
        self.id = unique_id
        self.category = 'FG' or 'R&P'
        self.pallets = number
        self.deadline = datetime  # FG 固定班次时间
        self.status = 'Pending', 'Processing', 'Completed'
        
class Buffer:
    def __init__(self):
        self.capacity = max_trailers
        self.current_load = []  # List of pallets waiting
        self.category = 'R&P' or 'FG'
```

### 2.2 资源建模

#### 2.2.1 码头资源 (Dock Resources)
```python
# 基于您的 Timeslot 数据
class DockSystem:
    def __init__(self):
        # 从 Timeslot 数据中提取
        self.reception_rp_docks = n1  # 需要从数据确定
        self.reception_fg_docks = n2
        self.loading_rp_docks = n3
        self.loading_fg_docks = n4
        
    def is_available(self, category, direction, time_slot):
        # 检查时位预约可用性
        # 使用您的 Timeslot.py 数据
        return available_capacity > 0
```

#### 2.2.2 人力资源动态调配
```python
class FTEManager:
    def __init__(self):
        self.total_fte = total_workers
        self.efficiency_rp = 5.81  # 从 productivity.py
        self.efficiency_fg = 3.5  # 平均值
        self.efficiency_std_rp = 0.416
        
    def allocate_fte(self, current_time):
        # 基于当前负荷动态分配
        rp_demand = get_rp_workload(current_time)
        fg_demand = get_fg_workload(current_time)
        
        total_demand = rp_demand + fg_demand
        
        # 按比例分配
        fte_rp = (rp_demand / total_demand) * self.total_fte
        fte_fg = (fg_demand / total_demand) * self.total_fte
        
        return fte_rp, fte_fg
    
    def get_actual_efficiency(self, base_efficiency, std):
        # 加入随机波动
        return np.random.normal(base_efficiency, std)
```

### 2.3 缓冲机制建模（关键）

#### 2.3.1 挂车缓冲容量模拟
```python
class TrailerBuffer:
    def __init__(self, max_trailers=20, pallets_per_trailer=33):
        self.max_capacity = max_trailers * pallets_per_trailer
        self.current_pallets = 0
        self.overflow_count = 0
        
    def receive_from_factory(self, pallets, timestamp):
        """工厂 24/7 生产的成品进入缓冲"""
        if self.current_pallets + pallets <= self.max_capacity:
            self.current_pallets += pallets
            return True
        else:
            self.overflow_count += 1
            # 记录缓冲溢出事件
            log_overflow(timestamp, pallets)
            return False
    
    def release_to_dc(self, pallets):
        """DC 开门时从缓冲区释放"""
        if self.current_pallets >= pallets:
            self.current_pallets -= pallets
            return True
        return False
```

#### 2.3.2 工厂生产模拟（针对 R&P 和 FG）
```python
def factory_production_process(env, buffer, production_rate_per_hour):
    """模拟工厂 24/7 连续生产"""
    while True:
        # 每小时产生一定数量的托盘
        pallets = production_rate_per_hour
        
        # 如果 DC 关闭，进入缓冲
        current_hour = env.now % 24
        if not is_dc_open(current_hour):
            buffer.receive_from_factory(pallets, env.now)
        else:
            # 直接送入 DC 处理
            process_inbound(pallets, env.now)
        
        yield env.timeout(1)  # 等待 1 小时
```

### 2.4 FG 固定班次约束建模

```python
class FixedScheduleManager:
    def __init__(self):
        # 基于实际数据定义固定发运时间
        self.departure_times = [8, 10, 12, 14, 16, 18, 20, 22, 24]
        
    def get_cutoff_time(self, departure_time, loading_hours=2):
        """计算截单时间"""
        return departure_time - loading_hours
    
    def check_deadline_miss(self, order, current_time):
        """检查是否会错过固定班次"""
        required_departure = order.scheduled_departure
        cutoff = self.get_cutoff_time(required_departure)
        
        # 估算剩余处理时间
        remaining_pallets = order.pallets - order.processed_pallets
        estimated_time = remaining_pallets / current_efficiency
        
        if current_time + estimated_time > cutoff:
            return True  # 会延误
        return False
```

### 2.5 时间窗口场景对比

#### 场景定义
```python
scenarios = {
    'baseline': {
        'dc_open_time': 6,   # 06:00
        'dc_close_time': 24,  # 24:00
        'total_hours': 18
    },
    'scenario_1': {
        'dc_open_time': 7,   # 07:00
        'dc_close_time': 23,  # 23:00
        'total_hours': 16
    },
    'scenario_2': {
        'dc_open_time': 8,   # 08:00
        'dc_close_time': 22,  # 22:00
        'total_hours': 14
    },
    'scenario_3': {
        'dc_open_time': 8,   # 08:00
        'dc_close_time': 20,  # 20:00
        'total_hours': 12
    }
}
```

## 三、数据输入准备

### 3.1 基于现有数据的参数提取

#### 从 productivity.py 提取效率参数
```python
# 计算月度平均和标准差
rp_efficiency_mean = 5.81  # 托盘/小时
rp_efficiency_std = 0.416
fg_efficiency_mean = 3.5
fg_efficiency_std = 0.5  # 需要从数据计算
```

#### 从 volume.py 提取需求分布
```python
# 使用历史数据构建每日、每小时需求分布
def build_demand_distribution():
    # 读取 Total Shipments 2025.xlsx
    # 分析 11 月数据的时序模式
    
    # 输出：每小时到达率（泊松分布参数λ）
    arrival_rate_by_hour = {
        6: 2.5,  # 06:00-07:00 平均 2.5 辆卡车
        7: 3.2,
        # ... 其他时段
    }
    return arrival_rate_by_hour
```

#### 从 Timeslot.py 提取时位容量约束
```python
# 提取每小时的码头容量
def extract_dock_capacity():
    # 读取 Timeslot 数据
    # 返回：{hour: {category: {direction: capacity}}}
    
    capacity_matrix = {
        6: {'FG': {'Inbound': 10, 'Outbound': 8},
            'R&P': {'Inbound': 6, 'Outbound': 4}},
        # ... 其他时段
    }
    return capacity_matrix
```

### 3.2 缺失数据估算

#### 需要估算的参数
1. **挂车缓冲容量**
   - 估算方法：查看场地规划或假设合理值（如 15-20 辆挂车）
   - 每辆挂车容量：33 托盘（标准）

2. **工厂生产速率**
   - 从月度 Inbound 总量反推
   - R&P：16,500 托盘/月 ≈ 23 托盘/小时（24/7）
   - FG：33,000 托盘/月 ≈ 46 托盘/小时（24/7）

3. **装卸作业时间分布**
   - 可以假设为三角分布或对数正态分布
   - 需要收集部分实际数据或行业标准

## 四、SimPy 实现框架

### 4.1 完整仿真流程结构

```python
import simpy
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

class DCSimulation:
    def __init__(self, env, config):
        self.env = env
        self.config = config
        
        # 初始化资源
        self.docks = self._init_docks()
        self.fte_manager = FTEManager(config['total_fte'])
        self.trailer_buffer_rp = TrailerBuffer(max_trailers=15)
        self.trailer_buffer_fg = TrailerBuffer(max_trailers=20)
        
        # KPI 收集器
        self.kpis = KPICollector()
        
    def _init_docks(self):
        """根据时位数据初始化码头资源"""
        return {
            'FG_Reception': simpy.Resource(self.env, capacity=10),
            'FG_Loading': simpy.Resource(self.env, capacity=12),
            'RP_Reception': simpy.Resource(self.env, capacity=8),
            'RP_Loading': simpy.Resource(self.env, capacity=6)
        }
    
    def is_dc_open(self, hour):
        """检查 DC 是否在运营时间内"""
        return (self.config['dc_open_time'] <= hour < 
                self.config['dc_close_time'])
    
    def run_simulation(self, duration_days=30):
        """运行仿真"""
        # 启动工厂生产进程（24/7）
        self.env.process(self.factory_production_rp())
        self.env.process(self.factory_production_fg())
        
        # 启动卡车到达进程
        self.env.process(self.truck_arrivals())
        
        # 启动缓冲区释放进程
        self.env.process(self.buffer_release_process())
        
        # 运行仿真
        self.env.run(until=duration_days * 24)
        
        # 返回 KPI 结果
        return self.kpis.generate_report()
    
    def factory_production_rp(self):
        """R&P 工厂生产进程（24/7）"""
        production_rate = 23  # 托盘/小时
        
        while True:
            current_hour = int(self.env.now) % 24
            
            # 生成托盘
            pallets = np.random.poisson(production_rate)
            
            if not self.is_dc_open(current_hour):
                # DC 关闭，进入缓冲
                overflow = not self.trailer_buffer_rp.receive_from_factory(
                    pallets, self.env.now)
                if overflow:
                    self.kpis.record_buffer_overflow('R&P', self.env.now, pallets)
            else:
                # DC 开启，直接处理
                self.env.process(self.process_inbound_rp(pallets))
            
            yield self.env.timeout(1)  # 1 小时后继续
    
    def factory_production_fg(self):
        """FG 工厂生产进程（24/7）"""
        production_rate = 46  # 托盘/小时
        
        while True:
            current_hour = int(self.env.now) % 24
            pallets = np.random.poisson(production_rate)
            
            if not self.is_dc_open(current_hour):
                overflow = not self.trailer_buffer_fg.receive_from_factory(
                    pallets, self.env.now)
                if overflow:
                    self.kpis.record_buffer_overflow('FG', self.env.now, pallets)
            else:
                self.env.process(self.process_inbound_fg(pallets))
            
            yield self.env.timeout(1)
    
    def truck_arrivals(self):
        """卡车到达进程（基于历史数据分布）"""
        arrival_rates = self._load_arrival_distribution()
        
        while True:
            current_hour = int(self.env.now) % 24
            
            if self.is_dc_open(current_hour):
                # 获取该时段的到达率
                lambda_rate = arrival_rates.get(current_hour, 0)
                
                # 泊松到达
                num_arrivals = np.random.poisson(lambda_rate)
                
                for _ in range(num_arrivals):
                    # 生成卡车属性
                    truck = self._generate_truck()
                    
                    if truck.direction == 'Outbound':
                        self.env.process(self.outbound_process(truck))
            
            yield self.env.timeout(1)
    
    def buffer_release_process(self):
        """缓冲区释放进程（DC 开门时优先处理）"""
        while True:
            current_hour = int(self.env.now) % 24
            
            if self.is_dc_open(current_hour):
                # 从缓冲区释放托盘进行处理
                if self.trailer_buffer_rp.current_pallets > 0:
                    pallets = min(50, self.trailer_buffer_rp.current_pallets)
                    self.trailer_buffer_rp.release_to_dc(pallets)
                    self.env.process(self.process_inbound_rp(pallets, from_buffer=True))
                
                if self.trailer_buffer_fg.current_pallets > 0:
                    pallets = min(80, self.trailer_buffer_fg.current_pallets)
                    self.trailer_buffer_fg.release_to_dc(pallets)
                    self.env.process(self.process_inbound_fg(pallets, from_buffer=True))
            
            yield self.env.timeout(0.5)  # 每半小时检查一次
    
    def process_inbound_rp(self, pallets, from_buffer=False):
        """R&P 入库处理"""
        # 请求码头资源
        with self.docks['RP_Reception'].request() as req:
            yield req
            
            # 获取当前效率（加入随机波动）
            efficiency = self.fte_manager.get_actual_efficiency(5.81, 0.416)
            
            # 计算处理时间
            processing_time = pallets / efficiency
            
            # 记录开始时间
            start_time = self.env.now
            
            # 处理
            yield self.env.timeout(processing_time)
            
            # 记录 KPI
            self.kpis.record_inbound_completion(
                'R&P', pallets, start_time, self.env.now, from_buffer)
    
    def process_inbound_fg(self, pallets, from_buffer=False):
        """FG 入库处理"""
        with self.docks['FG_Reception'].request() as req:
            yield req
            
            efficiency = self.fte_manager.get_actual_efficiency(3.5, 0.5)
            processing_time = pallets / efficiency
            
            start_time = self.env.now
            yield self.env.timeout(processing_time)
            
            self.kpis.record_inbound_completion(
                'FG', pallets, start_time, self.env.now, from_buffer)
    
    def outbound_process(self, truck):
        """出库处理（关键：检查固定班次约束）"""
        category = truck.category
        dock_key = f'{category}_Loading'
        
        # 请求装车码头
        with self.docks[dock_key].request() as req:
            # 等待码头可用
            yield req
            
            # 记录等待时间
            wait_time = self.env.now - truck.scheduled_time
            self.kpis.record_truck_wait_time(category, wait_time)
            
            # 获取效率并计算装车时间
            if category == 'FG':
                efficiency = self.fte_manager.get_actual_efficiency(3.5, 0.5)
                # 检查是否会错过固定班次
                deadline = truck.departure_deadline
                loading_time = truck.pallets / efficiency
                
                if self.env.now + loading_time > deadline:
                    self.kpis.record_sla_miss('FG', truck, self.env.now)
            else:
                efficiency = self.fte_manager.get_actual_efficiency(5.81, 0.416)
                loading_time = truck.pallets / efficiency
            
            # 执行装车
            yield self.env.timeout(loading_time)
            
            # 记录完成
            self.kpis.record_outbound_completion(
                category, truck, self.env.now)
    
    def _generate_truck(self):
        """根据历史分布生成卡车"""
        # 基于实际数据分布随机生成
        truck = Truck()
        truck.category = np.random.choice(['FG', 'R&P'], p=[0.67, 0.33])
        truck.pallets = np.random.randint(20, 35)
        
        if truck.category == 'FG':
            # FG 有固定发运时间
            truck.departure_deadline = self._assign_departure_time()
        
        return truck
    
    def _assign_departure_time(self):
        """为 FG 分配固定发运时间"""
        possible_times = [8, 10, 12, 14, 16, 18, 20, 22, 24]
        current_hour = int(self.env.now) % 24
        
        # 选择最近的未来时间
        future_times = [t for t in possible_times if t > current_hour]
        if future_times:
            return min(future_times)
        else:
            return possible_times[0] + 24  # 次日第一个班次
    
    def _load_arrival_distribution(self):
        """从历史数据加载到达分布"""
        # 这里应该从 volume.py 的分析结果中读取
        # 简化示例
        return {
            6: 2.5, 7: 3.2, 8: 4.1, 9: 3.8, 10: 4.5,
            11: 4.2, 12: 3.5, 13: 3.8, 14: 4.3, 15: 4.6,
            16: 5.1, 17: 4.8, 18: 3.9, 19: 3.2, 20: 2.5,
            21: 1.8, 22: 1.2, 23: 0.5
        }


class KPICollector:
    """KPI 数据收集和分析"""
    def __init__(self):
        self.buffer_overflows = []
        self.truck_wait_times = []
        self.sla_misses = []
        self.inbound_completions = []
        self.outbound_completions = []
        self.midnight_backlogs = []
    
    def record_buffer_overflow(self, category, timestamp, pallets):
        self.buffer_overflows.append({
            'category': category,
            'timestamp': timestamp,
            'pallets': pallets
        })
    
    def record_truck_wait_time(self, category, wait_time):
        self.truck_wait_times.append({
            'category': category,
            'wait_time': wait_time
        })
    
    def record_sla_miss(self, category, truck, timestamp):
        self.sla_misses.append({
            'category': category,
            'truck_id': truck.id,
            'scheduled': truck.departure_deadline,
            'actual': timestamp,
            'delay': timestamp - truck.departure_deadline
        })
    
    def record_inbound_completion(self, category, pallets, start_time, end_time, from_buffer):
        self.inbound_completions.append({
            'category': category,
            'pallets': pallets,
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'from_buffer': from_buffer
        })
    
    def record_outbound_completion(self, category, truck, completion_time):
        self.outbound_completions.append({
            'category': category,
            'truck_id': truck.id,
            'pallets': truck.pallets,
            'completion_time': completion_time
        })
    
    def check_midnight_backlog(self, pending_orders):
        """记录午夜未完成订单"""
        self.midnight_backlogs.append({
            'timestamp': 24,  # 午夜
            'pending_count': len(pending_orders),
            'pending_pallets': sum(o.pallets for o in pending_orders)
        })
    
    def generate_report(self):
        """生成仿真结果报告"""
        report = {
            'buffer_overflow_events': len(self.buffer_overflows),
            'total_overflow_pallets': sum(e['pallets'] for e in self.buffer_overflows),
            
            'average_truck_wait_time': np.mean([w['wait_time'] for w in self.truck_wait_times]),
            'max_truck_wait_time': max([w['wait_time'] for w in self.truck_wait_times]) if self.truck_wait_times else 0,
            
            'sla_miss_count': len(self.sla_misses),
            'sla_miss_rate': len(self.sla_misses) / len(self.outbound_completions) if self.outbound_completions else 0,
            
            'average_midnight_backlog': np.mean([b['pending_pallets'] for b in self.midnight_backlogs]),
            
            'total_processed_pallets': sum(c['pallets'] for c in self.inbound_completions),
            'buffer_processed_ratio': sum(c['pallets'] for c in self.inbound_completions if c['from_buffer']) / 
                                      sum(c['pallets'] for c in self.inbound_completions)
        }
        
        return report


# 运行多场景对比
def run_scenario_comparison():
    scenarios = {
        'baseline': {'dc_open_time': 6, 'dc_close_time': 24, 'total_fte': 50},
        'scenario_1': {'dc_open_time': 7, 'dc_close_time': 23, 'total_fte': 50},
        'scenario_2': {'dc_open_time': 8, 'dc_close_time': 22, 'total_fte': 50},
        'scenario_3': {'dc_open_time': 8, 'dc_close_time': 20, 'total_fte': 50}
    }
    
    results = {}
    
    for scenario_name, config in scenarios.items():
        print(f"Running scenario: {scenario_name}")
        
        # 创建仿真环境
        env = simpy.Environment()
        sim = DCSimulation(env, config)
        
        # 运行仿真（30 天）
        result = sim.run_simulation(duration_days=30)
        
        results[scenario_name] = result
        
        print(f"  - SLA Miss Rate: {result['sla_miss_rate']:.2%}")
        print(f"  - Buffer Overflow Events: {result['buffer_overflow_events']}")
        print(f"  - Avg Midnight Backlog: {result['average_midnight_backlog']:.1f} pallets")
        print()
    
    # 生成对比报告
    comparison_df = pd.DataFrame(results).T
    comparison_df.to_excel('Simulation_Results_Comparison.xlsx')
    
    return comparison_df


if __name__ == '__main__':
    results = run_scenario_comparison()
    print("\n=== Scenario Comparison Summary ===")
    print(results)
```

## 五、仿真实施步骤

### 步骤 1：数据准备（1-2 天）
1. 从现有 Excel 文件提取参数
   - 运行 `productivity.py` 获取效率统计
   - 运行 `volume.py` 获取需求分布
   - 运行 `Timeslot.py` 获取时位容量

2. 构建输入数据集
   ```python
   # 创建统一的参数配置文件
   simulation_params = {
       'efficiency': {
           'rp_mean': 5.81,
           'rp_std': 0.416,
           'fg_mean': 3.5,
           'fg_std': 0.5
       },
       'demand': {
           'rp_inbound_daily': 550,
           'rp_outbound_daily': 550,
           'fg_inbound_daily': 1100,
           'fg_outbound_daily': 1100
       },
       'capacity': {
           'trailer_buffer_rp': 15,
           'trailer_buffer_fg': 20,
           'pallets_per_trailer': 33
       }
   }
   ```

### 步骤 2：模型构建（3-5 天）
1. 安装 SimPy：`pip install simpy`
2. 实现基础框架
   - 实体类定义
   - 资源管理
   - 进程逻辑
3. 集成实际数据
4. 添加 KPI 收集

### 步骤 3：验证与校准（2-3 天）
1. 使用历史数据验证模型
   - 运行 baseline 场景（06:00-24:00）
   - 对比仿真输出与实际 KPI
   - 调整参数直到误差 < 10%

2. 敏感性分析
   - 测试关键参数的影响
   - 确保模型鲁棒性

### 步骤 4：场景实验（2-3 天）
1. 运行所有缩时场景
2. 收集 KPI 数据
3. 统计分析（置信区间、显著性检验）

### 步骤 5：结果分析与报告（2-3 天）
1. 可视化对比
2. 瓶颈识别
3. 优化建议

## 六、关键建模细节

### 6.1 随机性建模

#### 效率波动
```python
def generate_efficiency(base_efficiency, std_dev):
    """生成考虑波动的实际效率"""
    # 使用截断正态分布（避免负值）
    efficiency = np.random.normal(base_efficiency, std_dev)
    return max(efficiency, base_efficiency * 0.5)  # 最低 50%
```

#### 卡车到达延迟
```python
def generate_arrival_time(scheduled_time):
    """生成实际到达时间（考虑延迟）"""
    # 假设延迟服从指数分布，平均 15 分钟
    delay = np.random.exponential(scale=0.25)  # 小时
    return scheduled_time + delay
```

### 6.2 缓冲区逻辑细化

```python
class AdvancedTrailerBuffer:
    def __init__(self, max_trailers, pallets_per_trailer):
        self.max_capacity = max_trailers * pallets_per_trailer
        self.current_pallets = 0
        self.queue = []  # FIFO 队列
        
    def add_pallets(self, pallets, timestamp, priority='normal'):
        """添加托盘到缓冲区"""
        if self.current_pallets + pallets <= self.max_capacity:
            self.queue.append({
                'pallets': pallets,
                'timestamp': timestamp,
                'priority': priority
            })
            self.current_pallets += pallets
            return True
        else:
            # 尝试为高优先级腾出空间
            if priority == 'high':
                self._make_space(pallets)
                return self.add_pallets(pallets, timestamp, priority)
            return False
    
    def release_batch(self, max_pallets):
        """批量释放（FIFO）"""
        released = []
        total_released = 0
        
        while self.queue and total_released < max_pallets:
            batch = self.queue[0]
            if total_released + batch['pallets'] <= max_pallets:
                released.append(self.queue.pop(0))
                total_released += batch['pallets']
                self.current_pallets -= batch['pallets']
            else:
                break
        
        return released, total_released
```

### 6.3 FG 固定班次精细化

```python
class DepartureScheduleManager:
    def __init__(self):
        # 定义每日固定发运时间和容量
        self.schedules = {
            8: {'capacity': 200, 'cutoff_hour': 6},
            10: {'capacity': 150, 'cutoff_hour': 8},
            12: {'capacity': 180, 'cutoff_hour': 10},
            # ... 更多班次
        }
    
    def assign_order_to_schedule(self, order_time, pallets):
        """为订单分配最优班次"""
        current_hour = int(order_time)
        
        # 找到最近的可用班次
        for departure_time in sorted(self.schedules.keys()):
            if departure_time > current_hour:
                schedule = self.schedules[departure_time]
                
                # 检查是否在截单时间之前
                if current_hour <= schedule['cutoff_hour']:
                    # 检查容量
                    if schedule['capacity'] >= pallets:
                        schedule['capacity'] -= pallets
                        return departure_time
        
        # 无可用班次，分配到次日
        return min(self.schedules.keys()) + 24
```

## 七、预期输出和KPI

### 7.1 核心输出指标

#### 运营完成率
- **午夜积压率**：$\text{Backlog Rate} = \frac{\text{Pending Pallets at 24:00}}{\text{Daily Total Pallets}} \times 100\%$
- **日清率**：$\text{Daily Completion Rate} = 1 - \text{Backlog Rate}$

#### SLA 遵守率
- **FG 准时发运率**：$\text{On-Time Departure Rate} = \frac{\text{Orders Departed on Time}}{\text{Total Orders}} \times 100\%$
- **平均延误时间**：对于延误订单的平均延迟（小时）

#### 资源利用率
- **码头利用率**：$\text{Dock Utilization} = \frac{\text{Occupied Time}}{\text{Total Available Time}} \times 100\%$
- **FTE 利用率**：$\text{FTE Utilization} = \frac{\text{Actual Working Hours}}{\text{Total FTE Hours}} \times 100\%$
- **峰值 FTE 需求**：识别是否出现人力短缺

#### 缓冲区性能
- **溢出事件数**：DC 关闭期间缓冲区满的次数
- **平均缓冲区占用率**：$\text{Avg Buffer Occupancy} = \frac{\text{Sum of Hourly Pallets}}{\text{Max Capacity} \times \text{Hours}}$

#### 等待时间
- **平均卡车等待时间**：从到达到服务开始的平均时间
- **P95 等待时间**：95% 的卡车等待时间不超过的值

### 7.2 可视化输出

```python
def visualize_results(results_dict):
    """生成对比可视化"""
    import matplotlib.pyplot as plt
    
    # 1. SLA 遵守率对比
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    scenarios = list(results_dict.keys())
    sla_rates = [results_dict[s]['sla_miss_rate'] for s in scenarios]
    
    axes[0, 0].bar(scenarios, sla_rates)
    axes[0, 0].set_title('SLA Miss Rate by Scenario')
    axes[0, 0].set_ylabel('Miss Rate (%)')
    
    # 2. 缓冲区溢出对比
    overflow_counts = [results_dict[s]['buffer_overflow_events'] for s in scenarios]
    axes[0, 1].bar(scenarios, overflow_counts)
    axes[0, 1].set_title('Buffer Overflow Events')
    
    # 3. 午夜积压对比
    backlogs = [results_dict[s]['average_midnight_backlog'] for s in scenarios]
    axes[1, 0].bar(scenarios, backlogs)
    axes[1, 0].set_title('Average Midnight Backlog (Pallets)')
    
    # 4. 等待时间对比
    wait_times = [results_dict[s]['average_truck_wait_time'] for s in scenarios]
    axes[1, 1].bar(scenarios, wait_times)
    axes[1, 1].set_title('Average Truck Wait Time (Hours)')
    
    plt.tight_layout()
    plt.savefig('Simulation_Results_Comparison.png', dpi=300)
    plt.show()
```

## 八、模型扩展建议

### 8.1 高级功能（可选）
1. **人力排班优化**
   - 集成优化算法动态调整 FTE 分配
   - 考虑加班成本

2. **时位预约策略模拟**
   - 测试不同的预约规则（如优先级、动态定价）

3. **多目标优化**
   - 同时优化成本、SLA、资源利用率

### 8.2 风险场景测试
1. **极端需求波动**
   - 测试峰值日（如月初、促销期）
   
2. **设备故障**
   - 模拟码头临时关闭的影响

3. **承运商延迟**
   - 大规模卡车延迟到达

## 九、实施时间表

| 阶段 | 任务 | 预计天数 |
|------|------|----------|
| 1 | 数据提取和预处理 | 2 |
| 2 | SimPy 模型框架搭建 | 3 |
| 3 | 集成实际数据和参数 | 2 |
| 4 | 模型验证和校准 | 3 |
| 5 | 多场景仿真实验 | 2 |
| 6 | 结果分析和报告撰写 | 3 |
| **总计** | | **15 天** |

## 十、成功标准

模型被认为成功，当：
1. Baseline 场景输出与历史数据误差 < 10%
2. 能够清晰量化缩时对关键 KPI 的影响
3. 识别出具体的瓶颈环节（码头、缓冲区、人力）
4. 提供可操作的优化建议

---

**下一步行动：**
1. 确认是否需要我帮助实现完整的 SimPy 代码
2. 确定是否有额外的数据需要收集
3. 讨论仿真参数的具体数值设定
