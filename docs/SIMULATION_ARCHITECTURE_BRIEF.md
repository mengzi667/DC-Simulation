# Simulation Architecture Overview | 仿真架构概览

## Executive Summary | 核心概要

This discrete event simulation models a distribution center's operations using a **two-phase design**: data preparation generates a full year's worth of pre-allocated orders, while simulation execution runs a 30-day operational window to evaluate different capacity scenarios.

本离散事件仿真采用**两阶段设计**来模拟配送中心运营：数据准备阶段生成全年预分配订单数据，仿真执行阶段运行30天运营窗口以评估不同产能场景。

---

## Two-Phase Design | 两阶段设计

### Phase 1: Data Preparation | 阶段一：数据准备
**File:** `data_preparation.py`

**Process | 流程：**
1. **Input:** Historical shipment data (Shipments 2025 Excel file)
   - **输入：** 历史发货数据（2025年发货记录Excel文件）

2. **Order Generation:** Generate 12 months of orders (35,145 total)
   - **订单生成：** 生成12个月订单数据（总计35,145个）
   - FG Inbound: 10,688 orders | FG入库：10,688个订单
   - FG Outbound: 11,178 orders | FG出库：11,178个订单
   - R&P Inbound: 5,797 orders | R&P入库：5,797个订单
   - R&P Outbound: 7,482 orders | R&P出库：7,482个订单

3. **Timeslot Pre-allocation:** Assign loading/reception timeslots at generation time
   - **时间槽预分配：** 在生成时即分配装卸时间槽

4. **Output:** `generated_orders.json` with pre-allocated timeslots
   - **输出：** 包含预分配时间槽的订单JSON文件

**Key Innovation | 关键创新：**
- Orders are **pre-generated** with assigned timeslots, eliminating runtime competition for slots
- 订单**预先生成**并分配时间槽，消除运行时对时间槽的竞争

---

### Phase 2: Simulation Execution | 阶段二：仿真执行
**File:** `dc_simulation.py`

**Simulation Window | 仿真窗口：**
- **Duration:** 30 days (720 hours)
- **持续时间：** 30天（720小时）
- **Orders Processed:** Only orders with `creation_time ≤ 720h` (~3,000 orders completed)
- **处理订单：** 仅处理`creation_time ≤ 720h`的订单（约完成3,000个）

**Scenarios Evaluated | 评估场景：**
1. **Baseline:** 18 operating hours/day
2. **Scenario 1:** 16 operating hours/day
3. **Scenario 2:** 14 operating hours/day
4. **Scenario 3:** 12 operating hours/day

每个场景运行3次重复实验。

---

## Process Flows | 流程架构

### Inbound Process | 入库流程
**Trigger:** Random truck arrivals (Poisson distribution)
**触发机制：** 随机卡车到达（泊松分布）

**Stages | 阶段：**
1. **Truck Arrival** → Queue for reception timeslot
   - **卡车到达** → 等待接收时间槽

2. **Timeslot Allocation** → Dock assignment (FIFO)
   - **时间槽分配** → 月台分配（先进先出）

3. **Unloading** (30 minutes fixed duration)
   - **卸货**（固定30分钟）

4. **FTE Processing** (24-hour deadline constraint)
   - **人力处理**（24小时期限约束）

5. **Completion** → KPI recording
   - **完成** → KPI记录

**Key Constraints | 关键约束：**
- Hourly timeslot limits: FG (2 slots/hour), R&P (1 slot/hour)
- 每小时时间槽限制：FG（2个/小时），R&P（1个/小时）
- 24-hour processing deadline from unloading completion
- 从卸货完成起24小时处理期限

---

### Outbound Process | 出库流程
**Trigger:** Pre-generated orders activated at `creation_time`
**触发机制：** 预生成订单在`creation_time`时激活

**Stages | 阶段：**
1. **Order Scheduler** → Triggers order at `creation_time`
   - **订单调度器** → 在`creation_time`触发订单

2. **FTE Processing** → Prepare goods for loading
   - **人力处理** → 准备装载货物

3. **Wait for Pre-allocated Timeslot** → No runtime competition
   - **等待预分配时间槽** → 无运行时竞争

4. **Loading** (30 minutes fixed duration)
   - **装载**（固定30分钟）

5. **SLA Check** → Departure deadline validation
   - **SLA检查** → 离开期限验证
   - G2 region: Same-day departure required
   - G2区域：要求当日离开
   - ROW region: Next-day departure allowed
   - ROW区域：允许次日离开

6. **Departure** → KPI recording (on-time vs. delayed)
   - **离开** → KPI记录（准时 vs. 延迟）

**Key Innovation | 关键创新：**
- **Two-stage processing:** Process BEFORE timeslot (reversed from typical flow)
- **两阶段处理：** 在时间槽之前处理（与典型流程相反）
- **Pre-allocated timeslots:** Eliminates runtime allocation conflicts
- **预分配时间槽：** 消除运行时分配冲突

---

## Core Components | 核心组件

### Entities | 实体类型
1. **Truck** (Inbound/Outbound)
   - Attributes: category, pallets, region
   - 属性：类别、托盘数、区域

2. **Order** (Pre-generated with timeslot)
   - Attributes: creation_time, timeslot_time, deadline
   - 属性：创建时间、时间槽时间、截止期限

---

### Resources | 资源管理
1. **FTE Manager** → Hourly capacity allocation
   - **人力管理器** → 每小时产能分配
   - Adjusted based on operating hours scenario
   - 根据运营时长场景调整

2. **Timeslot Tracker** → Pre-allocated slot enforcement
   - **时间槽跟踪器** → 预分配槽位强制执行
   - No runtime reallocation
   - 无运行时重新分配

3. **Dock Positions** → Physical dock capacity
   - **月台位置** → 物理月台产能
   - FG: 2 reception + 1 loading docks
   - FG：2个接收 + 1个装载月台
   - R&P: 1 reception + 4-6 loading docks
   - R&P：1个接收 + 4-6个装载月台

---

### Constraints | 约束机制
1. **Hourly Capacity Limits**
   - **每小时产能限制**
   - Reception: FG (2/h), R&P (1/h)
   - 接收：FG（2/小时），R&P（1/小时）
   - Loading: FG (1/h), R&P (4-6/h)
   - 装载：FG（1/小时），R&P（4-6/小时）

2. **Time Deadlines**
   - **时间期限**
   - Inbound: 24h processing deadline
   - 入库：24小时处理期限
   - Outbound: SLA-based departure deadlines (G2: same-day, ROW: next-day)
   - 出库：基于SLA的离开期限（G2：当日，ROW：次日）

3. **DC Operating Hours** (Scenario-dependent)
   - **配送中心运营时长**（场景相关）
   - Baseline: 18h/day | 基准：18小时/天
   - Reduced scenarios: 16h, 14h, 12h
   - 缩减场景：16、14、12小时

---

### Managers | 管理器
1. **Hourly Manager** → Updates resource availability every simulation hour
   - **小时管理器** → 每仿真小时更新资源可用性

2. **KPI Collector** → Tracks completion, flow statistics, on-time rates
   - **KPI收集器** → 跟踪完成量、流量统计、准时率

3. **Order Scheduler** → Activates pre-generated orders at `creation_time`
   - **订单调度器** → 在`creation_time`激活预生成订单

---

## Key Performance Indicators | 关键绩效指标

### Output Metrics | 输出指标
1. **Order Statistics | 订单统计**
   - Total orders completed | 总完成订单数
   - On-time rate (100% in all scenarios) | 准时率（所有场景均为100%）
   - Completion variance across scenarios (3,035 → 2,928) | 跨场景完成量差异（3,035 → 2,928）

2. **Flow Statistics | 流量统计**
   - Total pallets processed (from completed orders only) | 处理托盘总数（仅计算已完成订单）
   - Inbound: ~18,000 pallets | 入库：约18,000托盘
   - Outbound: ~24,000 pallets | 出库：约24,000托盘

3. **Scenario Comparison | 场景对比**
   - Operating hours impact on throughput | 运营时长对吞吐量的影响
   - FTE utilization rates | 人力利用率
   - Resource bottleneck identification | 资源瓶颈识别

---

## Simulation Characteristics | 仿真特性

### Strengths | 优势
1. **Pre-generation eliminates runtime variability** in timeslot allocation
   - **预生成消除运行时变异性**（时间槽分配）

2. **Realistic historical data-driven** order patterns
   - **真实历史数据驱动**的订单模式

3. **Flexible scenario evaluation** with adjustable operating hours
   - **灵活场景评估**（可调运营时长）

4. **Comprehensive KPI tracking** for operational insights
   - **全面KPI跟踪**以获得运营洞察

### Design Rationale | 设计理念
1. **12-month data pool with 30-day window:**
   - Provides realistic monthly variation patterns
   - Allows testing different months without regeneration
   - **12个月数据池配30天窗口：**
     - 提供真实的月度变化模式
     - 允许测试不同月份而无需重新生成

2. **Pre-allocated timeslots:**
   - Reflects real-world advance scheduling practices
   - Simplifies simulation logic (no runtime slot competition)
   - **预分配时间槽：**
     - 反映现实世界的提前调度实践
     - 简化仿真逻辑（无运行时槽位竞争）

3. **Two-stage outbound processing:**
   - Mirrors actual DC operations (prepare before loading)
   - Enables accurate FTE capacity modeling
   - **两阶段出库处理：**
     - 镜像实际配送中心操作（装载前准备）
     - 实现准确的人力产能建模

---

## Data Flow Summary | 数据流概要

```
[Historical Shipments 2025]
         ↓
[data_preparation.py: Generate 12 months, 35,145 orders]
         ↓
[Timeslot Pre-allocation]
         ↓
[generated_orders.json]
         ↓
[dc_simulation.py: Load orders, filter by creation_time ≤ 720h]
         ↓
[30-day Simulation Window: ~3,000 orders processed]
         ↓
[KPI Collection: Completion, Flow Statistics, On-time Rate]
         ↓
[Scenario Comparison: Operating Hours Impact Analysis]
```

---

## Technical Implementation | 技术实现

- **Simulation Engine:** SimPy (discrete event simulation)
- **仿真引擎：** SimPy（离散事件仿真）

- **Programming Language:** Python 3.12.2
- **编程语言：** Python 3.12.2

- **Data Format:** JSON for order storage, Excel for input data
- **数据格式：** JSON用于订单存储，Excel用于输入数据

- **Visualization:** Matplotlib for KPI charts (8 figures generated)
- **可视化：** Matplotlib生成KPI图表（8个图表）

- **Replications:** 3 per scenario (12 total runs)
- **重复实验：** 每场景3次（总计12次运行）

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-15  
**Related Files:** ARCHITECTURE_DIAGRAMS.tex, SIMULATION_MODEL_OVERVIEW.md
