# Architecture Descriptions | 架构描述
## Three Independent Sections for Presentation

---

## Section 1: Overall Architecture | 总体架构

### English Version

Our simulation uses a **two-phase design architecture**. 

**Phase 1—Data Preparation**: We generate one year's worth of orders (35,145 total) from historical 2025 data, with timeslots pre-allocated during generation. This eliminates runtime resource competition.

**Phase 2—Simulation Execution**: We run a 30-day window, processing only orders within 720 hours (approximately 3,000 orders). This captures realistic patterns while maintaining efficiency.

The architecture has four component types: **Entities** (Trucks, Orders), **Processes** (Arrival, Processing), **Resources** (FTE, Timeslots, Docks), and **Constraints** (Hourly limits, Deadlines, Operating hours). Two managers monitor system state and collect KPIs. This modular design enables testing scenarios from 18 to 12 operating hours per day.

### 中文版本

我们的仿真采用**两阶段设计架构**。

**阶段1——数据准备**：使用2025年历史数据生成一年订单（总计35,145个），在生成时预分配时间槽。这消除了运行时资源竞争。

**阶段2——仿真执行**：运行30天窗口，仅处理720小时内的订单（约3,000个）。这既捕获真实模式又保持效率。

架构包含四种组件：**实体**（卡车、订单）、**流程**（到达、处理）、**资源**（人力、时间槽、月台）和**约束**（每小时限制、期限、运营时长）。两个管理器监控系统状态并收集KPI。这种模块化设计可测试每天18至12小时的不同场景。

---

## Section 2: Outbound Process | 出库流程

### English Version

The **outbound process** uses a reversed two-stage flow that mirrors real DC operations.

An **Order Scheduler** activates pre-generated orders at their creation time. Each order has a pre-allocated loading timeslot assigned during data preparation, eliminating runtime dock competition.

Activated orders enter **FTE Processing** where goods are prepared for loading. This is our key innovation: we process BEFORE the timeslot, not after. This reflects real operations where picking occurs before truck arrival.

Orders then **wait for their pre-allocated timeslot**, proceed to **Loading** (30 minutes), and undergo **SLA checks**. FG orders must meet region-specific deadlines: G2 (same-day), ROW (next-day). 

Results show 100% on-time delivery across all scenarios, proving reduced hours affect throughput but not delivery reliability.

### 中文版本

**出库流程**采用逆向两阶段流程，反映真实配送中心运营。

**订单调度器**在创建时间激活预生成订单。每个订单在数据准备时已分配装载时间槽，消除运行时月台竞争。

激活后订单进入**人力处理**阶段准备货物。这是关键创新：我们在时间槽之前处理，而非之后。这反映了卡车到达前拣货的真实操作。

订单随后**等待预分配时间槽**，进入**装载**（30分钟），并经历**SLA检查**。FG订单必须满足区域期限：G2（当日），ROW（次日）。

结果显示所有场景100%准时交付，证明缩减时长影响吞吐量而非交付可靠性。

---

## Section 3: Inbound Process | 入库流程

### English Version

The **inbound process** follows a traditional sequential flow for receiving shipments.

**Random truck arrivals** follow a Poisson distribution from historical data. Trucks queue for available reception timeslots on a first-in-first-out basis, competing for slots unlike pre-allocated outbound orders.

Once allocated, trucks proceed to **unloading** (30 minutes fixed). Hourly capacity is a key bottleneck: FG allows 2 slots/hour, R&P allows 1 slot/hour.

After unloading, goods enter **FTE processing** with a strict **24-hour deadline**. This represents the requirement to clear docks and update inventory within one day.

Completed orders are recorded in KPIs. Testing shows reduced hours primarily impact dock wait times, not processing times, as FTE capacity adjusts proportionally.

### 中文版本

**入库流程**遵循传统顺序流程接收货物。

**随机卡车到达**遵循历史数据的泊松分布。卡车按先进先出排队等待接收时间槽，与预分配的出库订单不同，需竞争槽位。

分配后，卡车进入**卸货**（固定30分钟）。每小时容量是关键瓶颈：FG允许2个槽位/小时，R&P允许1个槽位/小时。

卸货后，货物进入**人力处理**，有严格的**24小时期限**。这代表在一天内清空月台并更新库存的要求。

完成的订单记录在KPI中。测试显示缩减时长主要影响月台等待时间而非处理时间，因为人力产能按比例调整。

---

## Usage Guidelines | 使用指南

### For Presentations | 演讲使用
- **Overall Architecture**: Use as introduction slide to establish context
  - **总体架构**：用作引言幻灯片建立背景
- **Outbound Process**: Present when discussing innovation and design decisions
  - **出库流程**：讨论创新和设计决策时展示
- **Inbound Process**: Present when discussing constraints and operational realism
  - **入库流程**：讨论约束和运营真实性时展示

### Reading Time | 阅读时长
- Each section: ~30-40 seconds at normal speaking pace
- 每段：正常语速约30-40秒

### Customization Tips | 定制建议
- Add specific numbers from your simulation results
- 添加仿真结果中的具体数字
- Include visual references to architecture diagrams
- 包含对架构图的视觉引用
- Adjust technical depth based on audience background
- 根据听众背景调整技术深度

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-15  
**Companion Files:** ARCHITECTURE_DIAGRAMS.tex, PRESENTATION_SCRIPT_2MIN.md
