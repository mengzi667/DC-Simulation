# Distribution Center Simulation

> TU Delft Design Project - Danone DC运营优化仿真分析

基于2025年全年真实业务数据的配送中心（Distribution Center）离散事件仿真模型，用于评估运营时间缩短对业务性能的影响。

## 核心问题

**研究目标**: DC运营时间从18小时缩减至12-16小时，对以下指标的影响：
- 缓冲区容量需求
- 卡车等待时间
- 码头利用率
- 人力资源配置

## 特性

- **数据驱动**: 7类参数全部从真实Excel数据精确提取（效率、到达率、码头容量、托盘分布、人力等）
- **高保真仿真**: 完整模拟卡车到达、码头装卸、缓冲区管理、资源调度全流程
- **场景对比**: 支持Baseline + 4个优化场景的对比分析
- **可视化输出**: 自动生成KPI对比表、时序数据、图表

## 快速开始

### 1. 环境配置

```bash
# 克隆项目
git clone https://github.com/mengzi667/DC-Simulation.git
cd DC-Simulation

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows

# 安装依赖
pip install -r requirements.txt
``` 
### 2. 数据准备

提取仿真参数（从Excel数据中提取7类参数）：

```bash
cd src
python data_preparation.py
```

**输出**:
- `outputs/simulation_configs/simulation_config.json` - 仿真配置
- `outputs/simulation_configs/simulation_parameters.xlsx` - 参数汇总表
- `outputs/figures/hourly_arrival_pattern.png` - 到达分布图

**提取的参数**（基于2025年全年数据）:

| 参数类别 | 数据来源 | 样本量 | 说明 |
|---------|---------|-------|------|
| 效率参数 | KPI sheet | 11个月 | R&P 5.80, FG 3.54 pal/hr |
| 到达率 | Total Shipments | 全年 | 24小时分类别到达分布 |
| 码头容量 | Timeslot W1-W48 | 48周 | 按小时/类型的精确容量 |
| 托盘分布 | Total Shipments | 33,280批次 | 实际托盘数统计分布 |
| 人力资源 | KPI Hours | 11个月 | R&P 26人, FG 97人 |
| 缓冲区容量 | KPI sheet | 设计参数 | R&P 4辆, FG 9辆挂车 |
| 生产速率 | 业务规则 | 连续生产 | 24/7工厂供应 |

### 3. 运行仿真

```bash
python dc_simulation.py
```

**输出**:
- `outputs/results/simulation_results_comparison.xlsx` - 场景对比汇总
- `outputs/results/simulation_details_[scenario].xlsx` - 各场景详细数据
- `outputs/figures/*.png` - 6个KPI对比图表

**仿真场景**:
1. **Baseline** - 当前配置（18小时运营）
2. **Scenario 1** - 优化到达时间分布
3. **Scenario 2** - 增加码头容量
4. **Scenario 3** - 提升装卸效率
5. **Scenario 4** - 综合优化

## 项目结构

```
DC-Simulation/
├── src/
│   ├── data_preparation.py      # 数据提取模块
│   └── dc_simulation.py          # 仿真引擎（SimPy）
│
├── data/
│   ├── raw/                      # 原始Excel数据
│   │   ├── KPI sheet 2025.xlsx
│   │   └── Total Shipments 2025.xlsx
│   └── Timeslot by week/         # 48周码头容量数据
│
├── outputs/
│   ├── simulation_configs/       # 提取的参数配置
│   ├── results/                  # 仿真结果
│   └── figures/                  # 可视化图表
│
├── scripts/
│   ├── analysis/                 # 数据分析工具
│   └── debug/                    # 调试工具
│
└── docs/                         # 详细文档
```

详见 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## 核心方法

### 码头容量提取（创新点）

完全复现 `scripts/analysis/Timeslot.py` 的精确逻辑：

1. 读取48周Timeslot数据（W1-W48.xlsx）
2. 使用openpyxl标准化列数（31/32列处理）
3. 过滤2025年有效数据（Booking taken + Available）
4. 按 **FG/R&P × Loading/Reception × 24小时** 分组
5. 计算平均容量（总容量 ÷ 天数）

**提取结果**:
- FG Loading: 1.8 个码头/小时
- FG Reception: 1.8 个码头/小时
- R&P Loading: 3.3 个码头/小时
- R&P Reception: 1.2 个码头/小时

### 仿真性能目标

| KPI | 目标值 | 说明 |
|-----|--------|------|
| SLA达成率 | >95% | 卡车按时完成装卸 |
| 平均等待时间 | <30分钟 | 到达后等待开始服务 |
| 缓冲区溢出 | 0次 | 缓冲区满导致拒绝 |
| 午夜积压 | <5辆 | 每日结束时未处理卡车 |

## 技术栈

- **Python 3.11+**
- **SimPy** - 离散事件仿真框架
- **Pandas** - 数据处理
- **Matplotlib** - 可视化
- **OpenPyXL** - Excel读写

## 文档

| 文档 | 内容 |
|------|------|
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | 完整目录结构 |
| [docs/SIMULATION_MODEL_OVERVIEW.md](docs/SIMULATION_MODEL_OVERVIEW.md) | 模型设计思路 |
| [docs/SIMULATION_MODEL_STRUCTURE.md](docs/SIMULATION_MODEL_STRUCTURE.md) | 技术实现细节 |
| [docs/SIMULATION_ANALYSIS.md](docs/SIMULATION_ANALYSIS.md) | 结果分析报告 |

 