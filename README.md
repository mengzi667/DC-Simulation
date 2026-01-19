# DC Operation Simulation

离散事件仿真（DES）项目，模拟物流配送中心（DC）的出入库运营，支持多场景分析和性能对比。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备数据（生成订单）
python src/data_preparation.py

# 3. 运行仿真
python src/dc_simulation.py

# 4. 查看结果
# - 图表: outputs/figures/
# - 数据: outputs/results/simulation_results.xlsx
```

## 项目说明

### 核心功能
- **订单生成**: 从KPI和历史数据生成合成订单（FG/R&P × Inbound/Outbound）
- **动态调度**: 优先级队列调度，按最晚开始时间排序
- **时间槽管理**: 基于真实码头容量的Timeslot分配
- **SLA追踪**: 统计准时交付率和超期订单
- **多场景仿真**: 4个运营时间场景
- **可视化分析**: 完整的KPI仪表板 + Excel数据导出

### 运营模拟
- **FG出库**: 两步 → 处理货物 → 装车出库
- **R&P出库**: 两步 → 处理货物 → 装车出库  
- **入库**: 两步 → 卸货 → 处理货物
- **约束**: FTE有限，Timeslot容量有限

## 项目结构

```
src/
  ├─ data_preparation.py ........ 数据提取和订单生成
  ├─ dc_simulation.py ........... 主仿真引擎
  └─ dc_simulation_plot_update.py  结果分析和可视化
data/
  ├─ raw/ ....................... 原始数据
  ├─ Input FTE Data.txt ......... FTE配置
  └─ processed/ ................. 处理后的数据
outputs/
  ├─ simulation_configs/ ........ 配置文件（自动生成）
  ├─ figures/ ................... KPI可视化图表
  └─ results/ ................... Excel和JSON结果
docs/
  ├─ 机制.md ..................... 仿真逻辑说明
  └─ ARCHITECTURE_GUIDE.md ...... 架构说明
```

## 输出结果

### 配置文件 (outputs/simulation_configs/)
- `simulation_config.json`: 完整的仿真配置（KPI、FTE、容量等）
- `generated_orders.json`: 合成订单数据
- `simulation_parameters.xlsx`: 参数汇总表

### 图表 (outputs/figures/)
- SLA合规率对比
- 等待时间分布
- 码头容量利用率
- 类别和方向的详细分析
- 吞吐量趋势

### 数据 (outputs/results/)
- `report_data.json`: 详细的KPI数据
- 包含所有场景的SLA、等待时间、超期订单等

## 配置

### 数据范围
- **时间跟度**: 1-8月（数据有效期，9-12月数据已排除）
- **类别**: FG和R&P
- **方向**: Inbound和Outbound
- **订单总数**: 由KPI月度总量和shipments分布决定

### 仿真配置
运营时间可通过调整 `SIMULATION_CONFIG` 修改：
- Baseline: 06:00-24:00 (18小时)
- Scenario 1: 07:00-23:00 (16小时)
- Scenario 2: 08:00-22:00 (14小时)
- Scenario 3: 08:00-20:00 (12小时)

## 依赖

- Python 3.8+
- simpy (仿真框架)
- pandas (数据处理)
- matplotlib (可视化)
- openpyxl (Excel)

详见 `requirements.txt`

## 数据准备流程

`data_preparation.py` 执行以下步骤：
1. **提取效率参数**: 从KPI sheet获取人工作业效率
2. **提取需求分布**: 从Shipments文件计算卡车到达率（1-8月）
3. **提取容量配置**: 从码头Timeslot表提取实际容量
4. **生成订单**: 基于KPI月度总量和历史分布合成订单
5. **保存配置**: 导出配置文件供仿真使用

## 仿真机制

详细说明请查看 [docs/机制.md](docs/机制.md)

核心流程：
1. **订单到达**: 按creation_time序列到达
2. **优先级调度**: 按最晚开始时间排序
3. **处理**: 受FTE、Timeslot容量限制
4. **计算KPI**: SLA、等待时间、吞吐量等

## 使用示例

```python
# 查看一个场景的详细结果
import pandas as pd

df = pd.read_excel('outputs/results/simulation_results_comparison.xlsx')
print(df[['Scenario', 'SLA_Compliance_Rate', 'Avg_Truck_Wait_Time']])
```
