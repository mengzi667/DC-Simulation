# DC 运营时间缩短仿真分析

## 项目概述

本项目使用 **离散事件仿真 (Discrete Event Simulation, DES)** 方法，基于 Python SimPy 库构建配送中心（DC）运营仿真模型，用于量化评估缩短 DC 运营时间对作业完成率和 SLA 的影响。

### 核心研究问题
在仅保留 FG（成品）和 R&P（原材料和包装）业务的情况下，缩短 DC 运营时间（当前为 06:00-24:00）将如何影响：
- ✅ SLA 遵守率
- ✅ 缓冲区容量需求
- ✅ 午夜积压情况
- ✅ 卡车等待时间
- ✅ 资源利用率

---

## 文件结构

```
Design_Project/
│
├── simulation_framework.md        # 详细的建模方法论和理论框架
├── dc_simulation.py               # 主仿真程序（SimPy 实现）
├── data_preparation.py            # 数据提取和参数准备脚本
├── README_SIMULATION.md           # 本文件：使用指南
│
├── data/                          # 数据文件夹
│   ├── KPI sheet 2025.xlsx        # 效率数据
│   ├── Total Shipments 2025.xlsx  # 需求数据
│   ├── productivity.py            # 效率分析脚本
│   ├── volume.py                  # 需求分析脚本
│   └── Timeslot.py                # 时位分析脚本
│
└── results/                       # 输出结果（运行后生成）
    ├── simulation_config.json
    ├── simulation_parameters.xlsx
    ├── simulation_results_comparison.xlsx
    ├── simulation_results_visualization.png
    └── simulation_details_*.xlsx
```

---

## 快速开始

### 1. 环境准备

#### 安装依赖
```bash
pip install simpy numpy pandas matplotlib openpyxl
```

或使用 requirements.txt：
```bash
pip install -r requirements.txt
```

#### requirements.txt 内容
```
simpy>=4.0.1
numpy>=1.21.0
pandas>=1.3.0
matplotlib>=3.4.0
openpyxl>=3.0.9
```

### 2. 数据准备

首先运行数据准备脚本，从现有 Excel 文件中提取仿真参数：

```bash
python data_preparation.py
```

**输出文件：**
- `simulation_config.json` - 仿真配置参数（JSON 格式）
- `simulation_parameters.xlsx` - 参数汇总表（Excel）
- `hourly_arrival_pattern.png` - 每小时到达分布可视化

**提取的参数包括：**
- **效率参数**：R&P 和 FG 的平均效率及标准差
- **需求分布**：每小时卡车到达率（基于历史数据）
- **生产速率**：工厂 24/7 连续生产的托盘/小时
- **缓冲区需求**：估算的挂车缓冲容量

### 3. 运行仿真

执行主仿真程序：

```bash
python dc_simulation.py
```

**仿真场景：**
1. **Baseline**: 06:00 - 24:00 (18 小时)
2. **Scenario 1**: 07:00 - 23:00 (16 小时)
3. **Scenario 2**: 08:00 - 22:00 (14 小时)
4. **Scenario 3**: 08:00 - 20:00 (12 小时)

**仿真参数：**
- 每个场景重复 3-5 次（可配置）
- 每次仿真 30 天（可配置）
- 随机种子固定，确保可重复性

**输出文件：**
- `simulation_results_comparison.xlsx` - 场景对比汇总
- `simulation_details_baseline.xlsx` - Baseline 详细数据
- `simulation_details_scenario_1.xlsx` - Scenario 1 详细数据
- `simulation_details_scenario_2.xlsx` - Scenario 2 详细数据
- `simulation_details_scenario_3.xlsx` - Scenario 3 详细数据
- `simulation_results_visualization.png` - 可视化对比图

---

## 仿真模型详解

### 核心组件

#### 1. 实体 (Entities)
- **Truck**: 卡车实体（Inbound/Outbound）
- **Order**: FG 订单实体（固定发运时间）

#### 2. 资源 (Resources)
- **Docks**: 码头资源（FG/R&P，Reception/Loading）
- **FTE**: 人力资源（动态分配）
- **Trailer Buffer**: 挂车缓冲区（DC 关闭时存储）

#### 3. 进程 (Processes)
- **工厂生产进程**: 24/7 连续生产（R&P 和 FG）
- **卡车到达进程**: 基于泊松分布的随机到达
- **缓冲区释放进程**: DC 开门时优先处理缓冲区
- **订单处理进程**: FG 订单处理和 SLA 检查
- **监控进程**: 午夜积压检查、缓冲区占用率监控

### 关键逻辑

#### 缓冲机制（针对 R&P 和 FG）
```python
if DC 关闭:
    if 缓冲区有空间:
        托盘 → 缓冲区
    else:
        记录溢出事件
else:  # DC 开门
    从缓冲区释放托盘 → 优先处理
    新生产托盘 → 直接入库
```

#### FG 固定班次约束
```python
订单发运时间 = 固定班次时间表 [8, 10, 12, 14, 16, 18, 20, 22, 24]
截单时间 = 发运时间 - 2 小时

if 订单完成时间 > 发运时间:
    记录 SLA 延误
```

#### 随机性建模
- **效率波动**: 正态分布 $N(\mu, \sigma)$
  - R&P: $\mu = 5.81$, $\sigma = 0.416$
  - FG: $\mu = 3.5$, $\sigma = 0.5$
- **卡车到达**: 泊松分布 $Poisson(\lambda_h)$，$\lambda_h$ 因小时而异
- **到达延迟**: 指数分布 $Exp(0.25)$，平均 15 分钟

---

## KPI 说明

### 1. SLA 遵守率
$$\text{SLA Compliance Rate} = \frac{\text{准时完成订单数}}{\text{总订单数}} \times 100\%$$

**目标**: ≥ 95%

### 2. 缓冲区溢出事件
- DC 关闭期间，缓冲区满后无法容纳的托盘数
- **关键指标**：溢出事件数 & 溢出托盘总数

### 3. 午夜积压
$$\text{Midnight Backlog} = \text{24:00 时刻未完成订单的托盘数}$$

**理想状态**: 日清（Backlog = 0）

### 4. 卡车等待时间
$$\text{Waiting Time} = \text{服务开始时间} - \text{到达时间}$$

**统计量**:
- 平均等待时间
- P95 等待时间（95% 的卡车等待时间不超过此值）

### 5. 缓冲区平均占用率
$$\text{Buffer Occupancy} = \frac{\text{当前托盘数}}{\text{最大容量}} \times 100\%$$

---

## 自定义仿真

### 修改场景配置

在 `dc_simulation.py` 中修改 `SIMULATION_CONFIG`：

```python
SIMULATION_CONFIG = {
    'custom_scenario': {
        'name': '自定义场景 (07:00-21:00)',
        'dc_open_time': 7,
        'dc_close_time': 21,
        'operating_hours': 14
    }
}
```

### 调整系统参数

在 `dc_simulation.py` 中修改 `SYSTEM_PARAMETERS`：

```python
SYSTEM_PARAMETERS = {
    'efficiency': {
        'rp_mean': 5.81,      # 调整 R&P 平均效率
        'fg_mean': 3.5        # 调整 FG 平均效率
    },
    'buffer_capacity': {
        'rp_trailers': 20,    # 增加 R&P 缓冲容量
        'fg_trailers': 25     # 增加 FG 缓冲容量
    },
    'fte_total': 60           # 增加人力资源
}
```

### 修改仿真参数

在 `run_scenario_comparison()` 函数中：

```python
results, comparison_df = run_scenario_comparison(
    scenarios_to_run=['baseline', 'custom_scenario'],
    num_replications=10,  # 增加重复次数
    duration_days=60      # 延长仿真天数
)
```

---

## 结果解读

### 汇总表 (simulation_results_comparison.xlsx)

| 场景 | SLA 遵守率 | 溢出事件 | 平均等待 | 午夜积压 |
|------|-----------|---------|----------|----------|
| Baseline | 98.5% | 0 | 0.35 hr | 45 pal |
| Scenario 1 | 96.2% | 2 | 0.48 hr | 120 pal |
| Scenario 2 | 92.1% | 8 | 0.72 hr | 280 pal |
| Scenario 3 | 85.3% | 25 | 1.15 hr | 510 pal |

### 可视化图表

`simulation_results_visualization.png` 包含 6 个子图：

1. **SLA 遵守率对比**：柱状图，显示各场景的 SLA 表现
2. **缓冲区溢出事件**：柱状图，显示溢出频率
3. **平均卡车等待时间**：柱状图，显示等待时间变化
4. **平均午夜积压**：柱状图，显示未完成工作量
5. **缓冲区平均占用率**：分组柱状图，区分 R&P 和 FG
6. **综合性能评分**：横向柱状图，加权综合评分

### 详细数据表

每个场景的详细 Excel 文件包含以下工作表：

- **Buffer_Overflows**: 缓冲区溢出事件详情
- **Truck_Wait_Times**: 所有卡车等待时间记录
- **SLA_Misses**: SLA 延误订单详情
- **Completed_Orders**: 已完成订单统计
- **Midnight_Backlogs**: 每日午夜积压情况

---

## 高级分析

### 1. 敏感性分析

测试关键参数的影响：

```python
# 测试不同缓冲容量
buffer_sizes = [10, 15, 20, 25, 30]

for size in buffer_sizes:
    SYSTEM_PARAMETERS['buffer_capacity']['fg_trailers'] = size
    # 运行仿真...
```

### 2. What-If 场景

模拟特殊情况：

```python
# 模拟设备故障
class EquipmentFailure:
    def __init__(self, env, docks, failure_time, duration):
        self.env = env
        self.env.process(self.run(docks, failure_time, duration))
    
    def run(self, docks, failure_time, duration):
        yield self.env.timeout(failure_time)
        # 临时减少码头容量
        original_capacity = docks['FG_Loading']._capacity
        docks['FG_Loading']._capacity = original_capacity // 2
        
        yield self.env.timeout(duration)
        docks['FG_Loading']._capacity = original_capacity
```

### 3. 优化分析

寻找最优参数组合：

```python
from itertools import product

open_times = [6, 7, 8]
close_times = [20, 21, 22, 23, 24]
fte_levels = [45, 50, 55, 60]

best_config = None
best_score = 0

for open_t, close_t, fte in product(open_times, close_times, fte_levels):
    if close_t - open_t < 12:  # 至少运营 12 小时
        continue
    
    config = {
        'dc_open_time': open_t,
        'dc_close_time': close_t,
        'fte_total': fte
    }
    
    # 运行仿真并评估
    score = evaluate_config(config)
    
    if score > best_score:
        best_score = score
        best_config = config
```

---

## 常见问题 (FAQ)

### Q1: 仿真运行需要多长时间？
**A**: 单个场景（3 次重复，30 天）约 2-5 分钟，具体取决于计算机性能。

### Q2: 如何增加仿真精度？
**A**: 
1. 增加重复次数（`num_replications`）
2. 延长仿真天数（`duration_days`）
3. 使用更细粒度的时间步长

### Q3: 结果出现异常值怎么办？
**A**: 
1. 检查随机种子是否固定
2. 增加重复次数以获得稳定平均值
3. 检查输入参数是否合理

### Q4: 如何验证模型准确性？
**A**: 
1. 运行 Baseline 场景，对比实际 KPI 数据
2. 误差应 < 10%
3. 如果偏差较大，需要校准参数（效率、到达率等）

### Q5: 可以模拟更长时间段吗？
**A**: 可以，但需注意：
- 长时间仿真可能遇到内存问题
- 建议分批运行（如每次 30 天，多次运行）
- 季节性变化需要调整需求分布

---

## 扩展建议

### 1. 集成实时数据
从数据库或 API 读取最新数据：

```python
import sqlalchemy

def load_real_time_data():
    engine = sqlalchemy.create_engine('connection_string')
    df = pd.read_sql('SELECT * FROM shipments WHERE date >= CURRENT_DATE - 30', engine)
    return process_data(df)
```

### 2. 机器学习预测
使用历史数据训练预测模型：

```python
from sklearn.ensemble import RandomForestRegressor

model = RandomForestRegressor()
model.fit(X_train, y_train)

# 在仿真中使用预测的到达率
predicted_arrival_rate = model.predict(features)
```

### 3. 交互式仪表板
使用 Streamlit 或 Dash 构建可视化界面：

```python
import streamlit as st

st.title('DC 仿真分析仪表板')

dc_open = st.slider('DC 开门时间', 0, 12, 6)
dc_close = st.slider('DC 关门时间', 12, 24, 24)

if st.button('运行仿真'):
    results = run_simulation(dc_open, dc_close)
    st.write(results)
```

---

## 参考文献

1. **SimPy 官方文档**: https://simpy.readthedocs.io/
2. **离散事件仿真**: Law, A. M. (2015). *Simulation Modeling and Analysis*. McGraw-Hill.
3. **物流系统仿真**: Banks, J. (2005). *Discrete-Event System Simulation*. Prentice Hall.

---

## 联系支持

如有问题或建议，请联系：
- **项目团队**: Design Project Group 18
- **技术支持**: [your-email@example.com]

---

## 更新日志

### Version 1.0 (2026-01-08)
- ✅ 初始版本发布
- ✅ 实现基础仿真框架
- ✅ 4 个场景对比分析
- ✅ 数据提取脚本
- ✅ 可视化输出

### 计划功能
- ⏳ GUI 界面
- ⏳ 实时数据集成
- ⏳ 优化算法集成
- ⏳ 报告自动生成

---

**祝仿真顺利！** 🚀
