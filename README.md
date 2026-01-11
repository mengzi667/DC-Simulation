# DC Operation Simulation

离散事件仿真（DES）项目，模拟物流配送中心（DC）的出入库运营，支持多场景分析和性能对比。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行仿真
python src/dc_simulation.py

# 3. 查看结果
# - 图表: outputs/figures/ (13个PNG)
# - 数据: outputs/results/simulation_results_comparison.xlsx
```

## 项目说明

### 核心功能
- **区域追踪**: G2（80%）和 ROW（其他地区，20%）
- **双指标**: 同时追踪 Pallet（体积）和 Order（订单数）
- **SLA分析**: 区分两个地区的准时率
- **多场景**: 4个场景 × 3个副本 = 12个仿真运行
- **可视化**: 13个完整图表 + Excel数据导出

### 运营模拟
- **FG出库**: 两步 → 处理货物 → 装车出库
- **R&P出库**: 两步 → 处理货物 → 装车出库  
- **入库**: 两步 → 卸货 → 处理货物
- **约束**: FTE有限，Timeslot容量有限

## 项目结构

```
src/
  └─ dc_simulation.py ........... 主仿真脚本
data/
  ├─ raw/ ....................... 原始数据
  ├─ Input FTE Data.txt ......... FTE配置
  └─ ...
outputs/
  ├─ figures/ ................... 13个可视化图表
  └─ results/ ................... Excel和文本结果
docs/
  └─ 机制.md ..................... 仿真逻辑说明
```

## 输出结果

### 图表 (outputs/figures/)
- **1-3**: SLA、等待时间、库存备份
- **1b**: SLA对比（G2 vs ROW）
- **4**: 流量统计（托盘）
- **4b-4d**: 区域和订单分析
- **5**: 时间槽利用率
- **5b**: 按时间的详细分析

### 数据 (outputs/results/)
- `simulation_results_comparison.xlsx`: 完整指标 (100+列)
- 包含所有场景的 SLA、等待时间、吞吐量等

## 配置

### FTE配置 (data/Input FTE Data.txt)
```
FG: Inbound/Outbound 44.75 FTE
R&P: Inbound/Outbound 10.025 FTE
FG效率: 665.43 pallet/FTE
R&P效率: 1308.83 pallet/FTE
```

### 仿真参数
编辑 `config/simulation_config.json` 修改：
- 时间槽（Timeslot）
- 托盘容量
- 仿真天数
- FTE分配

## 依赖

- Python 3.8+
- simpy (仿真框架)
- pandas (数据处理)
- matplotlib (可视化)
- openpyxl (Excel)

详见 `requirements.txt`

## 仿真机制

详细说明请查看 [docs/机制.md](docs/机制.md)

核心流程：
1. **创建订单**: 按时间序列生成入库/出库订单
2. **处理**: 受FTE和容量限制
3. **装车**: 占用Timeslot，统计KPI
4. **计算**: SLA、等待时间、吞吐量等

## 使用示例

```python
# 查看一个场景的详细结果
import pandas as pd

df = pd.read_excel('outputs/results/simulation_results_comparison.xlsx')
print(df[['Scenario', 'SLA_Compliance_Rate', 'Avg_Truck_Wait_Time']])
```
