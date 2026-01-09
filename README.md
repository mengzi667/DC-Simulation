# DC仿真项目 - Distribution Center Simulation

## 📋 项目概述

本项目使用**SimPy离散事件仿真**，基于2025年全年真实业务数据，评估配送中心(DC)运营时间缩短对业务的影响。

**核心问题**: DC运营时间从18小时缩减至12-16小时，会对以下方面造成什么影响？
- 缓冲区容量
- 等待时间
- 码头利用率
- 资源配置

---

## 🎯 快速开始

### 1. 查看流程图
📊 **[查看仿真架构流程图](outputs/figures/simulation_structure_diagram.png)** - 一图了解整个模型

### 2. 阅读文档
📖 **[仿真模型概述](docs/SIMULATION_MODEL_OVERVIEW.md)** - 自然语言描述的完整模型总览（实体、资源、进程、事件、分布）

📚 **[技术架构文档](docs/SIMULATION_MODEL_STRUCTURE.md)** - 详细的技术实现和参数说明

### 3. 运行仿真
```bash
# 安装依赖
pip install -r requirements.txt

# 运行仿真
python src/dc_simulation.py

# 查看结果
start outputs/results/simulation_results_comparison.xlsx
```

---

## 📊 数据基础

| 数据源 | 时间跨度 | 用途 |
|--------|---------|------|
| KPI sheet 2025.xlsx | 11个月 | 效率参数 (R&P: 5.81, FG: 3.5 托盘/h) |
| Total Shipments 2025.xlsx | 305天 | 到达率 (FG: 36.77辆/天, R&P: 16.27辆/天) |
| Timeslot W1-W48.xlsx | 48周 | 码头容量 (Loading: 3-8, Reception: 1-6) |

**实际业务比例**: FG占69.3%, R&P占30.7%

---

## 🏗️ 模型架构

### 核心实体 (5个)
- **Truck**: 卡车 (FG/R&P, Inbound/Outbound)
- **TrailerBuffer**: 缓冲区 (R&P: 50托盘, FG: 100托盘)
- **FTEManager**: 人力资源 (125 FTE)
- **Dock Resources**: 码头 (时变容量)
- **KPICollector**: KPI收集器

### 主要进程 (7个并发)
1. **工厂生产** (24/7连续) → 缓冲区
2. **缓冲区释放** (DC开门时) → 入库
3. **卡车到达** (泊松分布，FG/R&P独立)
4. **入库处理** (等待码头→卸货)
5. **出库处理** (等待码头→装车)
6. **缓冲区监控** (每小时记录)
7. **容量更新** (时变码头容量)

### 仿真场景 (4个)
- **Baseline**: 06:00-24:00 (18小时)
- **Scenario 1**: 07:00-23:00 (16小时)
- **Scenario 2**: 08:00-22:00 (14小时)
- **Scenario 3**: 08:00-20:00 (12小时)

---

## 📁 项目结构

```
Design_Project/
├── 📁 data/              # 原始数据 (只读)
│   ├── KPI sheet 2025.xlsx
│   ├── Total Shipments 2025.xlsx
│   └── Timeslot by week/ (W1-W48)
│
├── 📁 src/               # 源代码
│   ├── dc_simulation.py           # 主仿真模型 (999行) ⭐
│   └── data_preparation.py        # 数据提取工具
│
├── 📁 outputs/           # 结果输出
│   ├── results/          # Excel结果和验证报告
│   └── figures/          # 流程图和可视化图表 ⭐
│
├── 📁 docs/              # 核心文档
│   ├── SIMULATION_MODEL_OVERVIEW.md    # 自然语言模型总览 ⭐ NEW
│   ├── SIMULATION_MODEL_STRUCTURE.md   # 技术架构文档 ⭐
│   ├── SIMULATION_ANALYSIS.md          # 分析结果文档
│   └── archive/                        # 历史文档和验证报告
│
├── 📁 scripts/           # 辅助脚本
│
└── README.md             # 本文档
```

---

## 📈 输出结果

### KPI指标
- ✅ 等待时间 (平均/最大/P95)
- ✅ SLA遵守率 (成品出库时限)
- ✅ 缓冲区占用率 (R&P: 495托盘, FG: 660托盘)
- ✅ 溢出次数 (缓冲区超容)
- ✅ 吞吐量 (总托盘数/总卡车数)
- ✅ 码头利用率 (时变容量，按小时)
- ✅ 场景对比分析 (4个运营时间场景)

### 输出文件
```
outputs/
├── results/
│   ├── simulation_results_comparison.xlsx  # 场景对比 ⭐
│   ├── dock_capacity_validation.txt        # 码头容量验证
│   ├── pallet_distribution_validation.txt  # 托盘分布验证
│   └── arrival_distribution_validation.txt # 到达分布验证
└── figures/
    ├── simulation_structure_diagram.png    # 架构流程图 ⭐
    ├── dock_capacity_by_hour.png          # 时变码头容量
    ├── pallet_distribution_*.png          # 托盘分布图
    └── arrival_distribution_*.png         # 到达分布图
```

---

## 🔬 技术栈

- **Python**: 3.12
- **仿真引擎**: SimPy 4.0.1
- **数据处理**: Pandas, NumPy
- **可视化**: Matplotlib
- **存储**: Excel (openpyxl)

---

## 📖 文档导航

| 文档 | 说明 |
|------|------|
| [SIMULATION_MODEL_OVERVIEW.md](docs/SIMULATION_MODEL_OVERVIEW.md) | 📌 **推荐首读** - 自然语言模型总览 (实体、资源、进程、事件、分布) |
| [SIMULATION_MODEL_STRUCTURE.md](docs/SIMULATION_MODEL_STRUCTURE.md) | 📋 技术架构详解 (参数配置、代码结构、数据来源) |
| [SIMULATION_ANALYSIS.md](docs/SIMULATION_ANALYSIS.md) | 📊 分析结果和技术细节 |
| [架构流程图](outputs/figures/simulation_structure_diagram.png) | 🎨 可视化架构图 |
| [验证报告](outputs/results/) | ✅ 参数验证报告 (码头、托盘、到达分布) |

### 📂 历史文档 (archive/)
所有参数修正过程、验证报告、旧版总结文档均已归档在 `docs/archive/`，包含完整的参数验证历程。

---

## 🎓 模型特点

### ✓ 数据驱动
- 基于305天实际到达数据
- 48周码头容量变化
- 11个月效率统计

### ✓ 分类别建模  
- FG和R&P独立到达进程
- 各自的参数和逻辑
- 实际比例69.3% : 30.7%

### ✓ 时变特性
- 每小时码头容量动态调整
- 到达率按时段变化
- 效率随机波动

### ✓ 全流程仿真
- 24/7工厂生产
- 缓冲区管理
- DC开门释放
- 资源竞争

---

## 🔄 使用流程

```
1. 环境准备
   └── pip install -r requirements.txt

2. (可选) 重新提取数据
   └── python src/data_preparation.py

3. 运行仿真
   └── python src/dc_simulation.py

4. 查看结果
   ├── outputs/results/*.xlsx
   └── outputs/figures/*.jpg

5. 理解模型
   └── docs/DC_SIMULATION_SUMMARY.md
```

---

## 📊 关键参数

### 到达率 (全年305天)
- **FG**: 17个时段, 峰值3.21辆/h (11点)
- **R&P**: 20个时段, 峰值1.42辆/h (19点)

### 效率 (11个月)
- **R&P**: 5.81 ± 0.42 托盘/小时
- **FG**: 3.50 ± 0.50 托盘/小时

### 码头容量 (48周)
- **Loading**: 3-8个码头 (出库)
- **Reception**: 1-6个码头 (入库)

---

## 🐛 问题排查

**找不到数据文件？**
→ 检查 `data/` 目录是否完整

**仿真运行很慢？**
→ 减少 `duration_days` 或 `num_replications`

**结果异常？**
→ 查看 `outputs/results/` 中的详细数据

---

## 📅 版本历史

**v2.0** (2026-01-08) - 全年数据版
- ✅ 使用305天全年到达数据
- ✅ FG/R&P分类别独立建模
- ✅ 删除订单生成，统一到达率驱动
- ✅ 实际比例69.3%:30.7%

**v1.0** (初始版本)
- 基于11月20天数据
- 固定比例67%:33%

---

## 📞 支持

- 📖 查看 [完整文档](docs/DC_SIMULATION_SUMMARY.md)
- 📊 查看 [流程图](outputs/figures/DC_Simulation_Architecture.jpg)
- 🔍 查看 [项目结构](docs/PROJECT_STRUCTURE.md)

---

**最后更新**: 2026年1月8日  
**项目版本**: v2.0
