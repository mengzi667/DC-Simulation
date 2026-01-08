# 项目结构说明

## 优化后的文件组织

```
Design_Project/
├── README.md                           # 📖 主文档（快速开始指南）
├── requirements.txt                    # 📦 Python依赖包列表
│
├── src/                                # 💻 核心代码
│   ├── dc_simulation.py                    # 主仿真模型（时变容量）
│   ├── data_preparation.py                 # 数据预处理脚本
│   └── analyze_hourly_capacity.py          # 码头容量小时分析
│
├── data/                               # 📊 原始数据（保持不变）
│   ├── KPI sheet 2025.xlsx                 # 效率和工时数据
│   ├── Total Shipments 2025.xlsx           # 需求数据
│   ├── Timeslot by week/W*.xlsx            # 48周码头时位数据
│   ├── productivity.py                     # 效率分析脚本
│   ├── volume.py                           # 需求分析脚本
│   └── Timeslot.py                         # 时位分析脚本
│
├── outputs/                            # 📁 仿真输出
│   ├── results/                            # Excel结果文件
│   │   ├── simulation_results_comparison.xlsx
│   │   ├── simulation_details_baseline.xlsx
│   │   ├── simulation_details_scenario_1.xlsx
│   │   ├── simulation_details_scenario_2.xlsx
│   │   ├── simulation_details_scenario_3.xlsx
│   │   ├── dock_capacity_hourly_analysis.txt
│   │   └── ...
│   └── figures/                            # 可视化图表
│       ├── simulation_results_visualization.png
│       ├── dock_capacity_by_hour.png
│       └── ...
│
├── docs/                               # 📚 详细文档
│   ├── README_SIMULATION.md                # 完整使用指南
│   ├── PARAMETERS_QUICK_REF.md             # 参数速查表
│   ├── simulation_framework.md             # 建模方法论
│   ├── TIMESLOT_ANALYSIS_SUMMARY.md        # 码头容量分析报告
│   └── ...
│
└── doc/                                # 📝 项目文档（原有）
    └── Danone Design Project.txt
```

## 清理说明

### 已删除的冗余文件
- ❌ analyze_all_48weeks.py（已合并到analyze_hourly_capacity.py）
- ❌ analyze_timeslot_detail.py（临时分析脚本）
- ❌ check_efficiency.py（测试文件）
- ❌ extract_dock_capacity.py（已集成到主程序）
- ❌ extract_timeslot_capacity.py（已集成到主程序）
- ❌ find_fixed_capacity.py（旧版本）
- ❌ quick_check_timeslot.py（临时检查）
- ❌ simple_simulation_demo.py（演示文件）
- ❌ test_setup.py（测试文件）
- ❌ visualize_parameters.py（已集成到主程序）

### 保留的核心文件

#### 代码 (src/)
1. **dc_simulation.py** - 主仿真模型（1028行）
   - 时变码头容量模型
   - 4场景对比分析
   - 完整KPI追踪

2. **data_preparation.py** - 数据预处理
   - Excel数据提取
   - 参数验证

3. **analyze_hourly_capacity.py** - 容量分析
   - 48周时位数据分析
   - 小时级统计

#### 文档 (docs/)
1. **README_SIMULATION.md** - 详细使用指南
2. **PARAMETERS_QUICK_REF.md** - 参数快速参考
3. **simulation_framework.md** - 理论框架
4. **TIMESLOT_ANALYSIS_SUMMARY.md** - 分析报告

## 使用流程

### 快速开始
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行仿真
cd src
python dc_simulation.py

# 3. 查看结果
# 结果在 outputs/results/ 和 outputs/figures/
```

### 输出文件说明

**Excel结果**
- `simulation_results_comparison.xlsx` - 4场景对比汇总
- `simulation_details_*.xlsx` - 各场景详细数据

**可视化图表**
- `simulation_results_visualization.png` - 综合对比图
- `dock_capacity_by_hour.png` - 时变容量分布

## 版本信息

- **版本**: 2.0
- **更新日期**: 2026-01-08
- **主要改进**: 
  - ✅ 时变码头容量模型
  - ✅ 项目结构优化
  - ✅ 输出路径规范化
  - ✅ 文档整合
