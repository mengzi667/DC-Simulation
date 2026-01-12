# 🎯 新增架构图使用指南

## 📌 文件位置
`docs/ARCHITECTURE_DIAGRAMS.tex` - 包含3个详细TikZ架构图

---

## 📊 三个架构图对比

| 图名 | 适用章节 | 层次 | 主要内容 | 优先级 |
|------|---------|------|---------|--------|
| **总体设计架构** | 4.3 模型架构总览 | 高层抽象 | Entity/Process/Resource/Constraint分类 | ⭐⭐⭐ |
| **Inbound流程架构** | 4.3.4 入库流程 | 详细流程 | 到达→Buffer→Timeslot→处理 | ⭐⭐⭐ |
| **Outbound流程架构** | 4.3.3 出库流程 | 详细流程 | 到达→处理→Loading→SLA检查 | ⭐⭐⭐ |

---

## 🔧 LaTeX配置要求

在你的LaTeX文件preamble中添加：

```latex
\usepackage{tikz}
\usetikzlibrary{shapes,arrows,positioning,fit,backgrounds}
```

---

## 📍 插入位置建议

### 方案A: 三图全插入（推荐，篇幅允许时）

```latex
% ========== Section 4.3 - Model Architecture Overview ==========
\section{Model Architecture}

% 1. 总体设计架构图 (给出全局视角)
\input{ARCHITECTURE_DIAGRAMS}  % 第190-290行的内容

% ========== Section 4.3.3 - Outbound Process ==========
\subsection{Outbound Process Model}

% 2. Outbound流程架构图
\input{ARCHITECTURE_DIAGRAMS}  % 第75-140行的内容

% ========== Section 4.3.4 - Inbound Process ==========
\subsection{Inbound Process Model}

% 3. Inbound流程架构图
\input{ARCHITECTURE_DIAGRAMS}  % 第15-65行的内容
```

### 方案B: 仅插入总体架构图（篇幅紧张时）

```latex
% 只在4.3开头插入总体设计架构图
\section{Model Architecture}

% 替换原有的简化架构图 (PART1 line 50-95)
\input{ARCHITECTURE_DIAGRAMS}  % 第190-290行
```

---

## 📖 各图详细说明

### 图1: 总体仿真设计架构 (Overall Architecture)

**标签**: `\label{fig:simulation_architecture_overview}`  
**代码行**: ARCHITECTURE_DIAGRAMS.tex, line 190-290  

**展示内容**:
- **Entity层**: Truck (Inbound/Outbound), Order (FG only), Buffer (Trailers)
- **Process层**: Arrival Process, Inbound Processing, Outbound Processing
- **Resource层**: FTE Manager, Timeslot Capacity, Dock Positions
- **Constraint层**: Hourly Capacity Limits, Time Deadlines, DC Operating Hours
- **Manager层**: Hourly Manager, KPI Collector, Buffer Release Process

**适用场景**: 
- 在4.3开头给读者整体概念
- 解释仿真系统的组成要素和交互关系
- 作为后续详细流程图的引导

**特点**:
- 图例清晰：实线=流程，虚线=约束，点线=监控
- 包含底部说明框：Entity属性、Process特征
- 全景视角：所有组件一览无遗

---

### 图2: Inbound流程架构 (Inbound Process)

**标签**: `\label{fig:inbound_architecture}`  
**代码行**: ARCHITECTURE_DIAGRAMS.tex, line 15-65  

**流程阶段** (从左到右):
1. **Truck Arrival** (Poisson分布)
2. **Queue for Timeslot** (等待Reception位置)
3. **Unloading at Dock** (固定30分钟)
4. **FTE Processing** (24小时deadline)
5. **Processing Complete**

**关键机制**:
- **Buffer机制**: DC关闭时到达的货物进入Buffer，开门后释放
- **Timeslot约束**: FG Reception 2个位置，R&P Reception 1个位置
- **24小时deadline**: 从到达到处理完成必须在24小时内
- **FTE容量约束**: 每小时处理能力有限

**适用场景**:
- 详细讲解入库操作流程
- 说明Buffer的作用（DC关闭时的缓冲）
- 强调24小时处理时限

---

### 图3: Outbound流程架构 (Outbound Process)

**标签**: `\label{fig:outbound_architecture}`  
**代码行**: ARCHITECTURE_DIAGRAMS.tex, line 75-140  

**流程阶段** (从左到右):
1. **Truck Arrival** (混合模式: 75% Scheduled + 25% Poisson)
2. **FTE Processing** (准备货物)
3. **Queue for Timeslot** (等待Loading位置)
4. **Loading at Dock** (固定30分钟)
5. **SLA Check** (检查是否按时发运)
6. **Truck Departure** (正常) 或 **Delayed** (延误)

**关键差异** (vs Inbound):
- **两阶段流程**: 先处理货物（FTE），后装车（Timeslot）
  - Inbound相反: 先卸货（Timeslot），后处理（FTE）
- **到达模式混合**: 75%预约 + 25%临时到达
- **SLA检查**: 仅FG有发运时限
  - G2: same-day deadline (当天发运)
  - ROW: next-day deadline (次日发运)
- **Timeslot容量不同**: FG Loading 1个位置，R&P Loading 4-6个位置

**适用场景**:
- 详细讲解出库操作流程
- 说明两阶段处理逻辑（为什么先处理后装车）
- 解释SLA检查机制和区域差异

---

## 🔍 三图之间的关系

```
总体架构图 (Overview)
    ↓ 提供全局视角
    ├─→ Inbound流程架构 (详细展开Inbound部分)
    └─→ Outbound流程架构 (详细展开Outbound部分)
```

**推荐文字说明顺序**:
1. 先插入总体架构图，写一段话："The simulation model consists of three entity types (Truck, Order, Buffer), three main process flows (Arrival, Inbound, Outbound), and multiple resource/constraint mechanisms as shown in Figure X."
   
2. 在Outbound章节插入Outbound架构图，写："Figure X details the outbound process flow. Unlike inbound operations, outbound processing follows a two-stage approach..."

3. 在Inbound章节插入Inbound架构图，写："Figure X illustrates the inbound process. When DC is closed, arriving trucks are buffered and released when operations resume..."

---

## 📋 快速检查清单

插入前确认：
- [ ] LaTeX preamble已添加tikz相关包
- [ ] `\usetikzlibrary{fit,backgrounds}` 已加载
- [ ] 确定插入位置（4.3总览 或 4.3.3/4.3.4详细章节）
- [ ] 准备好配套文字说明（每图2-3句话）

插入后验证：
- [ ] 编译无错误
- [ ] 图片显示完整（无超出页边距）
- [ ] 标签引用正确（`\ref{fig:...}` 有效）
- [ ] 图例清晰可读

---

## 💡 与原有简化架构图的对比

| 特性 | 简化版 (PART1) | 详细版 (ARCHITECTURE_DIAGRAMS) |
|-----|---------------|-------------------------------|
| 图数量 | 1个 | 3个 |
| 总代码行数 | ~50行 | ~320行 |
| Entity展示 | 抽象提及 | 详细分类+属性 |
| Process细节 | 高度简化 | 分Inbound/Outbound详述 |
| Constraint机制 | 简单箭头 | 专门Constraint层 |
| Buffer机制 | 无 | Inbound图中详细展示 |
| SLA检查 | 无 | Outbound图中详细展示 |
| 适用读者 | 快速理解 | 深入学习 |

**选择建议**:
- 如果读者需要快速了解→ 用简化版
- 如果报告篇幅充足→ 用详细版（更专业）
- 如果要体现工作量→ 用详细版（展示建模深度）

---

## 📞 文件位置总结

```
docs/
├── ARCHITECTURE_DIAGRAMS.tex          ← 3个新架构图 (⭐⭐⭐)
│   ├── Inbound Architecture (line 15-65)
│   ├── Outbound Architecture (line 75-140)
│   └── Overall Architecture (line 190-290)
│
├── PART1_Chapter4_Tables_Figures.tex  ← 简化架构图 (可选替代)
│   └── Simple Architecture (line 50-95)
│
└── MASTER_INDEX.tex                   ← 总索引 (已更新)
```

---

**更新日期**: 2026-01-12  
**版本**: v2.0 (新增架构图集)
