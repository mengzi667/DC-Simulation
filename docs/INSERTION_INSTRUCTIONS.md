# 📋 报告插入完整指导手册

**生成日期**: 2026-01-12  
**项目**: DC Operation Simulation  
**文件位置**: 
- `PART1-4_*.tex` (LaTeX代码分模块)
- `ARCHITECTURE_DIAGRAMS.tex` ⭐⭐⭐ 新增完整架构图集

---

## 📌 快速概览

**总计插入内容**:
- ✅ **4个表格** (全部包含真实数据)
- ✅ **13张图片** (所有PNG都使用)
- ✅ **4个架构图** (3个新增详细架构 + 1个简化版)
- ✅ **4个文字段落** (分析+建议)

**新增亮点** 🆕:
- **Inbound流程架构图** - 详细展示入库流程、Buffer机制、24h deadline
- **Outbound流程架构图** - 详细展示两阶段出库、SLA检查、区域分类
- **总体仿真设计架构** - 高层次展示Entity/Process/Resource/Constraint关系

---

## 🎯 第4章插入点 (Simulation Model)

### 插入1: FTE配置表
**文件**: `docs/doc/4.txt`  
**位置**: 第380行附近，`\subsection{Workforce (FTE) Configuration...}` 之后  
**代码文件**: `PART1_Chapter4_Tables_Figures.tex`, line 10-25
**标签**: `\label{tab:ch4_fte_config}`

---

### 插入2: 到达随机性表
**文件**: `docs/doc/4.txt`  
**位置**: 第200行附近，替换 `\label{tab:arrival_stochasticity}` 占位符  
**代码文件**: `PART1_Chapter4_Tables_Figures.tex`, line 30-45

---

### 插入3A: 总体仿真设计架构图 (TikZ) ⭐⭐⭐ 新增
**文件**: `docs/doc/4.txt`  
**位置**: Section 4.3 开头 (模型架构总览)  
**代码文件**: `ARCHITECTURE_DIAGRAMS.tex`, line 190-290
**标签**: `\label{fig:simulation_architecture_overview}`

**内容**: 展示整个仿真系统的组成要素
- **Entity类型**: Truck, Order, Buffer
- **Process类型**: Arrival, Inbound, Outbound
- **Resource类型**: FTE Manager, Timeslot Capacity, Dock Positions
- **Constraint类型**: Hourly Limits, Time Deadlines, Operating Hours
- **Manager进程**: Hourly Manager, KPI Collector, Buffer Release

**必需包**:
```latex
\usepackage{tikz}
\usetikzlibrary{shapes,arrows,positioning,fit,backgrounds}
```

---

### 插入3B: Inbound流程架构图 (TikZ) ⭐⭐⭐ 新增
**文件**: `docs/doc/4.txt`  
**位置**: Section 4.3.4 (Inbound Process Model)  
**代码文件**: `ARCHITECTURE_DIAGRAMS.tex`, line 15-65
**标签**: `\label{fig:inbound_architecture}`

**内容**: Inbound详细流程
- Truck Arrival (Poisson) → Queue for Timeslot → Unloading → FTE Processing
- Buffer机制处理DC关闭时的到达
- 24小时处理deadline约束
- Reception Timeslot容量限制 (FG: 2, R&P: 1)

---

### 插入3C: Outbound流程架构图 (TikZ) ⭐⭐⭐ 新增
**文件**: `docs/doc/4.txt`  
**位置**: Section 4.3.3 (Outbound Process Model)  
**代码文件**: `ARCHITECTURE_DIAGRAMS.tex`, line 75-140
**标签**: `\label{fig:outbound_architecture}`

**内容**: Outbound详细流程
- Truck Arrival (75% Scheduled + 25% Random) → FTE Processing → Queue for Loading → Loading → SLA Check
- 两阶段流程：先处理货物，后装车
- SLA检查：G2 same-day deadline, ROW next-day
- Loading Timeslot容量限制 (FG: 1, R&P: 4-6)

---

### 插入3D: 简化架构图 (可选替代)
**文件**: `docs/doc/4.txt`  
**位置**: 第150行附近，替换 `\label{fig:ch4_architecture_overview}` 占位符  
**代码文件**: `PART1_Chapter4_Tables_Figures.tex`, line 50-95

**说明**: 如果篇幅有限，可用此简化版替代上述3个详细架构图

---

### 插入4: 验证细节列表
**文件**: `docs/doc/4.txt`  
**位置**: 第620行附近，替换 `/* Lines 379-381 omitted */` 注释  
**代码文件**: `PART1_Chapter4_Tables_Figures.tex`, line 100-110

---

## 🎯 第5章插入点 (Scenario Analysis)

### 插入5: 主对比表 ⭐⭐⭐ (最重要)
**文件**: `docs/doc/5.txt`  
**位置**: Table 5.1 (scenario definitions) 之后，新建一个subsection  
**代码文件**: `PART2_Chapter5_Tables.tex`, line 10-70
**标签**: `\label{tab:ch5_comparison_summary}`

**数据亮点**:
- **SLA**: Baseline 91.96%, Scenario 2最低89.97%
- **G2 vs ROW**: ROW 100%, G2 87-90%
- **等待时间**: Baseline 0.71hr → Scenario 3 0.86hr (+21%)
- **吞吐量**: Outbound从131k降至106k (-19%)

**完整表格**: 见 `latex_insertions_guide.tex` 第115-160行

---

### 插入6: 区域分解表
**文件**: `docs/doc/5.txt`  
**位置**: 主对比表之后或结果小节  
**标签**: `\label{tab:ch5_regional_breakdown}`

**数据亮点**:
- G2 占80% (578订单, 58k pallets in Baseline)
- ROW 占20% (144订单, 15k pallets in Baseline)

**完整表格**: 见guide第165-185行

---

## 📊 图片插入详细指导

### 图1: SLA Overall (必插⭐⭐⭐)
**文件**: `1_sla_compliance_rate.png`  
**位置**: Section 5.5.2 (Service Level Results)  
**替换**: `\label{fig:ch5_sla_overall}` 占位符

**关键数据**:
- Baseline: 91.96% ± 0.35%
- Scenario 2: 89.97% ± 0.84% (最低)

**配套分析段落**: 见guide第195-200行

---

### 图1b: SLA by Region (必插⭐⭐⭐)
**文件**: `1b_sla_by_region.png`  
**位置**: 紧跟图1之后  
**替换**: `\label{fig:ch5_sla_region}` 占位符

**关键发现**:
- ROW: 100% (所有场景)
- G2: 87.62-89.97%
- 差距: 10-12个百分点

**配套分析段落**: 见guide第210-220行

---

### 图2: 平均等待时间 (必插⭐⭐)
**文件**: `2_avg_truck_wait_time.png`  
**位置**: Section 5.5.3 (Congestion Results)  
**替换**: `\label{fig:ch5_wait_mean}` 占位符

**关键数据**:
- Baseline: 0.71hr ± 0.02
- Scenario 3: 0.86hr ± 0.03 (+21%)

**配套分析**: 见guide第230-240行

---

### 图3: Midnight Backlog (可选)
**文件**: `3_midnight_backlog.png`  
**位置**: 结果章节或附录  
**注意**: 报告中需说明buffer逻辑未完全实现

---

### 图4: 吞吐量-托盘 (必插⭐⭐)
**文件**: `4_flow_statistics.png`  
**位置**: Section 5.5.5 (Throughput Results)  
**替换**: `\label{fig:ch5_throughput_pallets}` 占位符

**关键发现**:
- Inbound稳定: 113k-120k
- Outbound下降: 131k → 106k (-19%)

---

### 图4b: FG区域分解-托盘 (必插⭐)
**文件**: `4b_fg_outbound_by_region.png`  
**位置**: 图4之后  
**替换**: `\label{fig:ch5_throughput_region}` 占位符

**关键数据**: G2/ROW = 80/20 (所有场景)

---

### 图4c: 订单vs托盘对比 (主体插入⭐⭐)
**文件**: `4c_flow_statistics_orders.png`  
**位置**: Section 5.5.5 - 新建 `\subsubsection{Order Count versus Pallet Volume}`  
**标签**: `\label{fig:ch5_orders_pallets}`

**关键比率**:
- FG: ~100 pallets/order
- R&P: ~190 pallets/order

**完整内容**: 见guide第290-310行

---

### 图4d: FG订单区域分解 (主体插入⭐)
**文件**: `4d_fg_outbound_orders_by_region.png`  
**位置**: 图4c之后  
**标签**: `\label{fig:ch5_outbound_orders_region}`

**关键数据**:
- G2: 483-578 orders
- ROW: 119-144 orders

---

### 图5: 码头利用率总体 (必插⭐⭐)
**文件**: `5_timeslot_utilization.png`  
**位置**: Section 5.5.4 (Dock Utilization)  
**替换**: `\label{fig:ch5_util_avg}` 占位符

**反直觉发现**: 利用率随开放时间缩短而**下降**!
- FG dock: 34.4% → 27.9%
- 原因: 吞吐量下降 > 容量压缩

**配套分析**: 见guide第330-345行

---

### 图5b: 小时利用率剖析 (必插⭐⭐⭐)
**文件**: 4个PNG (FG/R&P × Inbound/Outbound)
- `5b_fg__inbound__slot_utilization.png`
- `5b_fg__outbound__slot_utilization.png`
- `5b_r&p__inbound__slot_utilization.png`
- `5b_r&p__outbound__slot_utilization.png`

**位置**: 图5之后  
**替换**: `\label{fig:ch5_util_hourly}` 占位符

**布局**: 2x2 subfigure网格

**必需包**:
```latex
\usepackage{subcaption}
```

**关键模式**:
- 高峰: 08:00-12:00
- 下午递减: 14:00后
- 硬关闭: 营业时间外为0

**完整代码**: 见guide第360-395行

---

## 📝 文字段落插入

### 文字块1: 结果概览
**位置**: Section 5.5 开头或新建 `\section{Results Overview and Key Findings}`  

**包含4个段落**:
1. Service Level Robustness
2. Moderate Congestion Increase
3. Throughput Reduction
4. Underutilized Capacity

**完整内容**: 见guide第410-430行

---

### 文字块2: 局限性讨论
**位置**: Section 5.6 或 5.7 `\subsection{Limitations and Scope Boundaries}`

**包含5个段落**:
1. Buffer Logic Incomplete
2. Small Replication Count (n=3)
3. No Arrival Smoothing
4. Proportional FTE Scaling Assumption
5. Fixed Demand Profiles

**完整内容**: 见guide第440-470行

---

### 文字块3: 运营建议
**位置**: Section 5.7 或 Chapter 6 `\subsection{Operational Recommendations}`

**包含5个建议**:
1. Prioritize G2 Morning Timeslots
2. Shift Inbound Arrivals Earlier
3. Implement Arrival Smoothing
4. Increase Morning-Shift FTE
5. Monitor G2 SLA Contractual Thresholds

**完整内容**: 见guide第480-510行

---

## 🔧 LaTeX配置要求

### Preamble必需包:
```latex
\usepackage{tikz}
\usepackage{subcaption}
\usetikzlibrary{shapes,arrows,positioning}
```

### 图片路径配置 (可选):
```latex
\graphicspath{{../outputs/figures/}}
```

如果使用相对路径，确保编译时路径正确。

---

## ✅ 操作清单

### 第4章 (4个插入点):
- [ ] 插入FTE配置表 (表4.1)
- [ ] 插入到达随机性表 (表4.2)
- [ ] 插入TikZ架构图 (图4.X)
- [ ] 补充验证列表

### 第5章主表格 (2个):
- [ ] 插入主对比表 (表5.1) ⭐⭐⭐
- [ ] 插入区域分解表 (表5.2)

### 第5章图片 (13个):
- [ ] 图1: SLA Overall ⭐⭐⭐
- [ ] 图1b: SLA by Region ⭐⭐⭐
- [ ] 图2: Avg Wait Time ⭐⭐
- [ ] 图3: Midnight Backlog (可选)
- [ ] 图4: Throughput Pallets ⭐⭐
- [ ] 图4b: FG Region Pallets ⭐
- [ ] 图4c: Orders vs Pallets ⭐⭐ (新section)
- [ ] 图4d: FG Region Orders ⭐
- [ ] 图5: Dock Utilization ⭐⭐
- [ ] 图5b: Hourly Profiles (4张) ⭐⭐⭐

### 文字段落 (4块):
- [ ] 结果概览段落
- [ ] 局限性讨论段落
- [ ] 运营建议段落
- [ ] (可选) 每张图的分析段落

---

## 📂 文件清单

### 核心文件:
1. **LaTeX插入代码**: `docs/latex_insertions_guide.tex` (完整版)
2. **操作指导**: `docs/INSERTION_INSTRUCTIONS.md` (本文件)
3. **数据JSON**: `outputs/results/report_data.json` (备用)

### 图片文件 (outputs/figures/):
- `1_sla_compliance_rate.png`
- `1b_sla_by_region.png`
- `2_avg_truck_wait_time.png`
- `3_midnight_backlog.png`
- `4_flow_statistics.png`
- `4b_fg_outbound_by_region.png`
- `4c_flow_statistics_orders.png`
- `4d_fg_outbound_orders_by_region.png`
- `5_timeslot_utilization.png`
- `5b_fg__inbound__slot_utilization.png`
- `5b_fg__outbound__slot_utilization.png`
- `5b_r&p__inbound__slot_utilization.png`
- `5b_r&p__outbound__slot_utilization.png`

### Excel数据文件:
- `simulation_results_comparison.xlsx` (已提取)

---

## 🎨 关键数据速查

### SLA表现:
| Scenario   | Overall | G2    | ROW   |
|------------|---------|-------|-------|
| Baseline   | 91.96%  | 89.97%| 100%  |
| Scenario 1 | 91.39%  | 89.27%| 100%  |
| Scenario 2 | 89.97%  | 87.62%| 100%  |
| Scenario 3 | 91.06%  | 88.81%| 100%  |

### 等待时间:
| Scenario   | Avg (hrs) | Max (hrs) | P95 (hrs) |
|------------|-----------|-----------|-----------|
| Baseline   | 0.71      | 7.02      | 3.40      |
| Scenario 3 | 0.86      | 9.58      | 3.58      |
| 变化       | +21%      | +36%      | +5%       |

### 吞吐量对比:
| Flow Type     | Baseline | Scenario 3 | Change |
|---------------|----------|------------|--------|
| Inbound       | 116,360  | 113,743    | -2%    |
| Outbound      | 131,015  | 105,950    | -19%   |
| FG Outbound   | 73,227   | 62,175     | -15%   |
| R&P Outbound  | 57,787   | 43,775     | -24%   |

---

## 🚀 下一步行动

1. **复制LaTeX代码**: 打开 `docs/latex_insertions_guide.tex`
2. **按章节插入**: 第4章 → 第5章
3. **编译测试**: 确保TikZ和subfigure包已安装
4. **调整图片路径**: 根据你的LaTeX项目结构
5. **校对数值**: 确保与Excel数据一致

---

## 💡 提示

- **优先级**: 标⭐⭐⭐的必插 (7个图表 + 2个表格)
- **图片质量**: 所有PNG都是300 DPI
- **数据注释**: 图4c和其他堆叠图已有数据标签
- **一致性**: 所有文字已转英文
- **完整性**: 13张图全部使用，无遗漏

---

**问题联系**: 查看 `latex_insertions_guide.tex` 获取完整LaTeX代码  
**最后更新**: 2026-01-12
