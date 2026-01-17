# 2-Minute Presentation Script | 2分钟演讲稿
## Distribution Center Simulation Architecture

---

## English Version (2 minutes)

**[SLIDE 1: Introduction - 15 seconds]**

Good morning everyone. Today I'll present our distribution center simulation model designed to evaluate operational capacity under different working hour scenarios.

**[SLIDE 2: Challenge - 20 seconds]**

The challenge we faced was: How do we accurately model a complex DC with thousands of orders, constrained resources, and strict time deadlines? Traditional approaches struggle with the massive scale and realistic scheduling patterns.

**[SLIDE 3: Our Solution - Two-Phase Design - 30 seconds]**

We developed a two-phase architecture. 

In **Phase 1**, we pre-generate an entire year's worth of orders—35,145 orders total—using historical shipment data from 2025. Crucially, we pre-allocate timeslots at this stage, eliminating runtime competition for dock positions.

In **Phase 2**, we run a 30-day simulation window, processing only orders within that timeframe—about 3,000 orders. This approach gives us realistic monthly variation while keeping simulation runtime efficient.

**[SLIDE 4: Key Innovation - 25 seconds]**

Three key innovations make this work:

First, **pre-allocated timeslots**—orders arrive knowing exactly when they'll be loaded or unloaded. This mirrors real-world advance scheduling.

Second, our **outbound process reverses the typical flow**—we prepare goods BEFORE the timeslot, not after. This accurately models actual DC operations.

Third, we use a **creation-time scheduler** that activates orders dynamically, ensuring realistic arrival patterns throughout the 30-day window.

**[SLIDE 5: Results - 20 seconds]**

We evaluated four scenarios: 18, 16, 14, and 12 operating hours per day. The results show clear throughput reduction as hours decrease—from 3,035 completed orders at baseline to 2,928 at 12 hours. Importantly, all completed orders maintained 100% on-time delivery.

**[SLIDE 6: Impact - 10 seconds]**

This simulation provides decision-makers with quantitative evidence for capacity planning, helping optimize the balance between operational costs and service levels.

Thank you.

---

## 中文版本（2分钟）

**[幻灯片1：引言 - 15秒]**

大家早上好。今天我将介绍我们的配送中心仿真模型，该模型用于评估不同工作时长场景下的运营产能。

**[幻灯片2：挑战 - 20秒]**

我们面临的挑战是：如何准确建模一个拥有数千订单、资源受限、且有严格时间期限的复杂配送中心？传统方法难以应对大规模数据和真实的调度模式。

**[幻灯片3：解决方案 - 两阶段设计 - 30秒]**

我们开发了一个两阶段架构。

**第一阶段**，我们使用2025年历史发货数据，预生成整整一年的订单——总计35,145个订单。关键在于，我们在此阶段就预分配了时间槽，消除了运行时对月台位置的竞争。

**第二阶段**，我们运行30天的仿真窗口，只处理该时间范围内的订单——约3,000个。这种方法既保证了真实的月度变化模式，又保持了仿真运行效率。

**[幻灯片4：核心创新 - 25秒]**

三个核心创新点支撑了这个设计：

首先，**预分配时间槽**——订单到达时就知道确切的装卸时间。这反映了现实世界的提前调度实践。

其次，我们的**出库流程逆转了传统流程**——在时间槽之前准备货物，而非之后。这准确模拟了实际配送中心操作。

第三，我们使用**创建时间调度器**动态激活订单，确保整个30天窗口内的到达模式真实可信。

**[幻灯片5：结果 - 20秒]**

我们评估了四个场景：每天18、16、14和12个运营小时。结果显示随着时长减少，吞吐量明显下降——从基准的3,035个完成订单降至12小时场景的2,928个。重要的是，所有完成订单都保持了100%的准时交付率。

**[幻灯片6：影响 - 10秒]**

该仿真为决策者提供了产能规划的定量证据，帮助优化运营成本与服务水平之间的平衡。

谢谢大家。

---

## Speaking Notes | 演讲要点

### Timing Breakdown | 时间分配
- Introduction: 15s | 引言：15秒
- Problem statement: 20s | 问题陈述：20秒
- Solution (Two-phase): 30s | 解决方案（两阶段）：30秒
- Key innovations: 25s | 核心创新：25秒
- Results: 20s | 结果：20秒
- Impact/Conclusion: 10s | 影响/结论：10秒
- **Total: 120 seconds (2 minutes) | 总计：120秒（2分钟）**

### Key Points to Emphasize | 重点强调
1. **Scale:** 35,145 orders generated, 3,000 processed | **规模：** 生成35,145个订单，处理3,000个
2. **Innovation:** Pre-allocation eliminates runtime conflicts | **创新：** 预分配消除运行时冲突
3. **Realism:** Based on historical 2025 data | **真实性：** 基于2025年历史数据
4. **Results:** Clear correlation between hours and throughput | **结果：** 时长与吞吐量明确相关

### Slides to Prepare | 需准备的幻灯片
1. Title slide with DC image | 标题页配配送中心图片
2. Challenge statement with data scale | 挑战说明及数据规模
3. Two-phase architecture diagram | 两阶段架构图
4. Key innovations (3 bullet points) | 核心创新（3个要点）
5. Results chart (scenario comparison) | 结果图表（场景对比）
6. Impact statement | 影响说明

### Potential Questions to Anticipate | 可能的提问
- **Q: Why 12 months if you only simulate 30 days?**
  - A: Provides monthly variation patterns and allows testing different months without regeneration.
  - **问：为什么生成12个月但只模拟30天？**
  - **答：** 提供月度变化模式，允许测试不同月份而无需重新生成。

- **Q: What about randomness/variability?**
  - A: We run 3 replications per scenario (12 total runs) to capture stochastic variation.
  - **问：随机性/变异性如何处理？**
  - **答：** 每个场景运行3次重复实验（总计12次）以捕获随机变化。

- **Q: How accurate is the model?**
  - A: Uses actual 2025 shipment data and validated against real DC operational constraints.
  - **问：模型准确性如何？**
  - **答：** 使用真实2025年发货数据，并根据实际配送中心运营约束进行验证。

---

## Visual Aids Suggestions | 视觉辅助建议

### Slide 3: Two-Phase Diagram
```
Phase 1: Data Preparation          Phase 2: Simulation
┌─────────────────────┐           ┌──────────────────┐
│ Historical Data     │           │ 30-Day Window    │
│ ↓                   │           │                  │
│ 12 Months Generated │    →      │ ~3,000 Orders    │
│ 35,145 Orders       │           │ Processed        │
│ ↓                   │           │                  │
│ Timeslot Allocated  │           │ 4 Scenarios      │
└─────────────────────┘           └──────────────────┘
```

### Slide 5: Results Chart
Show bar chart:
- X-axis: Scenarios (18h, 16h, 14h, 12h)
- Y-axis: Completed Orders
- Bars: 3,035 → 3,035 → 2,963 → 2,928
- Note: "100% on-time rate maintained"

---

**Presentation Time:** 2 minutes  
**Target Audience:** Technical/Management  
**Objective:** Demonstrate simulation architecture and impact  
**演讲时长：** 2分钟  
**目标听众：** 技术/管理层  
**目标：** 展示仿真架构和影响
