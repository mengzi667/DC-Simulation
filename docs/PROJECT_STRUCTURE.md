# 项目结构说明

```
Design_Project/
│
├── 📁 data/                          # 原始数据 (不修改)
│   ├── KPI sheet 2025.xlsx           # 效率数据 (11个月)
│   ├── Total Shipments 2025.xlsx     # 到达率数据 (305天)
│   ├── Timeslot by week/             # 码头容量数据 (48周)
│   │   ├── W1.xlsx
│   │   ├── W2.xlsx
│   │   └── ... (W48.xlsx)
│   └── [其他历史分析文件]
│
├── 📁 src/                           # 核心代码
│   ├── dc_simulation.py              # 主仿真模型 (954行)
│   ├── data_preparation.py           # 数据提取脚本 (517行)
│   └── analyze_hourly_capacity.py    # 容量分析工具 (273行)
│
├── 📁 outputs/                       # 输出结果
│   ├── results/                      # Excel结果文件
│   │   ├── simulation_results_*.xlsx
│   │   └── simulation_details_*.xlsx
│   └── figures/                      # 可视化图表
│       ├── DC_Simulation_Architecture.jpg
│       └── [其他分析图表]
│
├── 📁 docs/                          # 项目文档
│   ├── DC_SIMULATION_SUMMARY.md      # 模型完整总结 ⭐
│   ├── SIMULATION_ANALYSIS.md        # 架构详细分析
│   ├── OUTBOUND_PARAMETER_ANALYSIS.md # 参数分析文档
│   └── PROJECT_STRUCTURE.md          # 本文档
│
├── 📁 .venv/                         # Python虚拟环境
│
├── README.md                         # 项目说明
├── requirements.txt                  # Python依赖
└── generate_flowchart.py             # 流程图生成脚本

```

---

## 📂 目录说明

### 1. data/ - 原始数据目录
**用途**: 存放所有原始业务数据，**只读不写**

**主要文件**:
- `KPI sheet 2025.xlsx`: 
  - 11个月的R&P和FG效率数据
  - 包含工时、托盘数等
  - 用于提取效率参数

- `Total Shipments 2025.xlsx`:
  - 2个sheet: Inbound/Outbound Shipments
  - 305天的全年卡车到达记录
  - 包含Category, Date, Hour, Total pal等字段
  - 用于计算到达率分布

- `Timeslot by week/`:
  - 48个Excel文件 (W1-W48)
  - 每周每小时的码头容量数据
  - 用于时变容量参数

**注意**: 此目录下还有一些历史分析文件（Nov_analysis, Timeslot_Yearly_Analysis等），为早期探索性分析产物，已不再使用。

---

### 2. src/ - 源代码目录
**用途**: 存放所有Python代码

#### 核心文件

**dc_simulation.py** (954行)
```python
功能: 主仿真模型
包含:
  - 5个实体类 (Truck, TrailerBuffer, FTEManager, KPICollector等)
  - DCSimulation主类
  - 7个并发进程
  - 4个场景配置
  - 结果输出和可视化
```

**data_preparation.py** (517行)
```python
功能: 数据提取和参数生成
包含:
  - extract_efficiency_parameters() - 从KPI sheet提取
  - extract_demand_distribution() - 从Total Shipments提取
  - calculate_factory_production_rate() - 计算生产速率
  - generate_simulation_config() - 生成配置文件
```

**analyze_hourly_capacity.py** (273行)
```python
功能: 分析48周码头容量数据
包含:
  - 读取W1-W48所有文件
  - 计算每小时平均容量
  - 生成时变容量参数
  - 可视化容量分布
```

---

### 3. outputs/ - 输出目录
**用途**: 存放所有仿真结果和图表

#### results/ - 结果文件
```
simulation_results_comparison.xlsx  # 场景对比汇总
simulation_details_baseline.xlsx   # Baseline详细数据
simulation_details_scenario_1.xlsx # Scenario 1详细数据
...
```

**Excel文件结构**:
- Sheet 1: Waiting_Times - 等待时间记录
- Sheet 2: Buffer_Occupancy - 缓冲区占用率
- Sheet 3: Outbound_Ops - 出库操作详情
- Sheet 4: Inbound_Ops - 入库操作详情
- Sheet 5: Summary - 汇总统计

#### figures/ - 图表文件
```
DC_Simulation_Architecture.jpg     # 仿真架构流程图 ⭐
hourly_arrival_pattern.png         # 到达分布图
scenario_comparison.png             # 场景对比图
...
```

---

### 4. docs/ - 文档目录
**用途**: 项目文档和分析报告

**DC_SIMULATION_SUMMARY.md** ⭐
- 模型完整总结
- 实体、进程、参数详细说明
- 数据来源和使用方法
- **推荐首先阅读此文档**

**SIMULATION_ANALYSIS.md**
- 仿真架构深入分析
- 9个进程详解
- 参数来源追溯
- 技术实现细节

**OUTBOUND_PARAMETER_ANALYSIS.md**
- 出库参数分析
- 历史问题记录 (FG双重建模)
- 修复方案说明

**PROJECT_STRUCTURE.md** (本文档)
- 项目结构说明
- 文件组织逻辑

---

## 🔄 工作流程

### 典型使用流程

```
1. 准备数据
   └── 确保data/目录下有3个数据文件

2. 提取参数 (可选，参数已内置)
   └── python src/data_preparation.py

3. 运行仿真
   └── python src/dc_simulation.py

4. 查看结果
   ├── outputs/results/*.xlsx - Excel数据
   └── outputs/figures/*.jpg - 图表

5. 阅读文档
   └── docs/DC_SIMULATION_SUMMARY.md
```

---

## 📊 数据流

```
原始数据 (data/)
    ↓
数据提取 (data_preparation.py)
    ↓
参数配置 (SYSTEM_PARAMETERS)
    ↓
仿真执行 (dc_simulation.py)
    ↓
结果输出 (outputs/)
    ↓
分析报告 (docs/)
```

---

## 🎯 关键文件速查

| 需求 | 文件位置 |
|------|---------|
| 了解模型架构 | `docs/DC_SIMULATION_SUMMARY.md` |
| 查看流程图 | `outputs/figures/DC_Simulation_Architecture.jpg` |
| 修改仿真参数 | `src/dc_simulation.py` (第55-135行) |
| 运行仿真 | `python src/dc_simulation.py` |
| 查看结果 | `outputs/results/simulation_results_comparison.xlsx` |
| 修改场景配置 | `src/dc_simulation.py` (第29-53行) |
| 重新提取数据 | `python src/data_preparation.py` |

---

## 🔧 维护指南

### 添加新场景
1. 编辑 `src/dc_simulation.py`
2. 在 `SIMULATION_CONFIG` 中添加新场景
3. 重新运行仿真

### 更新数据
1. 替换 `data/` 目录下的Excel文件
2. 运行 `python src/data_preparation.py`
3. 检查输出的参数是否合理
4. 重新运行仿真

### 修改参数
1. 编辑 `src/dc_simulation.py` 中的 `SYSTEM_PARAMETERS`
2. 查阅注释了解参数含义
3. 重新运行仿真并验证结果

---

## 📝 代码规范

### 命名约定
- 类名: CamelCase (如 `DCSimulation`)
- 函数名: snake_case (如 `truck_arrival_process`)
- 常量: UPPER_CASE (如 `SYSTEM_PARAMETERS`)

### 文档字符串
```python
def function_name(param):
    """
    简短描述
    
    Args:
        param: 参数说明
    
    Returns:
        返回值说明
    """
```

### 代码组织
- 按功能分组
- 相关代码放在一起
- 添加分隔注释 `# ========== 标题 ==========`

---

## 🐛 问题排查

### 常见问题

**Q: 找不到数据文件**
```
A: 检查data/目录是否完整
   确保运行路径正确
```

**Q: 仿真运行很慢**
```
A: 减少仿真天数 (duration_days)
   减少重复次数 (num_replications)
```

**Q: 结果异常**
```
A: 检查参数设置是否合理
   查看outputs/results/中的详细数据
   验证数据源是否正确
```

---

## 📞 联系方式

- 项目文档: `docs/`
- 技术问题: 查看 `SIMULATION_ANALYSIS.md`
- 参数问题: 查看 `DC_SIMULATION_SUMMARY.md`

---

**最后更新**: 2026年1月8日  
**版本**: v2.0
