# 动态优先级队列调度实现说明

## 概述

在 `dc_simulation_plot_update.py` 中实现了基于优先级队列的订单动态调度算法。这个新算法解决了之前 Plan 2 中的逻辑问题：**高优先级但晚到达的订单被低优先级订单堵住**。

## 核心思想

### 问题定义

原来的 Plan 2 算法按 `latest_start_time` 排序所有订单，然后逐个处理：
```
问题：订单A（低优先级，早到达）被处理 → 订单B（高优先级，晚到达）被堵住
```

**为什么会这样？**
- 订单B 即使优先级高，但它的 `creation_time` 晚，所以它不能在订单A 之前开始处理
- 这违反了物理约束（订单必须等到到达后才能处理）

### 解决方案

**动态优先级队列调度**：
```
1. 订单按 creation_time 逐步到达（动态）
2. 到达的订单加入优先级队列（按 latest_start_time）
3. FTE 每次从队列选择优先级最高的订单处理
```

**优势**：
- ✓ 尊重物理约束：订单不能在到达前处理
- ✓ 遵循优先级：到达后立即按优先级排序
- ✓ 高优先级晚到达的订单不再被堵住（它到达后直接插到队列前面）

## 实现细节

### 1. 新增方法：`_calculate_prep_time(order)`

**功能**：计算订单备货的估计时间

```python
def _calculate_prep_time(self, order):
    """计算订单备货时间"""
    hourly_capacity = self.fte_manager.get_hourly_capacity(
        order.category, order.direction, self.opening_hour_coefficient
    )
    est_prep_time = order.pallets / hourly_capacity
    return est_prep_time
```

**用途**：为了计算 `latest_start_time`

### 2. 新增方法：`_calculate_latest_start_time(order)`

**功能**：计算订单必须开始处理的最晚时刻

```python
def _calculate_latest_start_time(self, order):
    """计算最迟开始时间（最高优先级指标）"""
    est_prep_time = self._calculate_prep_time(order)
    latest_start = order.timeslot_time - est_prep_time
    return latest_start
```

**公式**：
$$\text{latest\_start\_time} = \text{timeslot\_time} - \frac{\text{pallets}}{\text{hourly\_capacity}}$$

**示例**：
- 订单有 500 个 pallets，容量 163.7 pallets/h
- 必须在 14:00 装运
- 需要 3.05 小时备货
- 最迟开始：14:00 - 3:05 = **10:55**

### 3. 重写方法：`outbound_order_scheduler()`

**核心变化**：从简单遍历改为动态优先级队列

#### 数据结构
```python
ready_queue = []  # heapq 优先级队列
# 元素格式：(latest_start_time, order_index, order)
```

#### 执行流程

**1. 准备阶段**
```python
env.process(self.fte_manager.fte_available)  # 获取FTE空闲事件
all_outbound_orders = sorted(...)  # 按 creation_time 排序所有订单
```

**2. 主循环**

```python
while True:
    # 第一部分：到达阶段
    while order_index < len(all_outbound_orders):
        next_order = all_outbound_orders[order_index]
        if next_order.creation_time <= env.now:
            # 订单已到达，加入队列
            latest_start = self._calculate_latest_start_time(next_order)
            heapq.heappush(ready_queue, (latest_start, order_index, next_order))
            order_index += 1
            # 日志记录
            print(f"[{env.now}h] 订单到达：...priority={latest_start:.2f}h")
        else:
            # 没有更多订单到达，退出到达阶段
            break
    
    # 第二部分：调度阶段
    if ready_queue and self.fte_manager.fte_available_count > 0:
        # 从队列选择优先级最高的订单
        latest_start, _, order = heapq.heappop(ready_queue)
        print(f"[{env.now}h] 开始处理：订单{order.id}...priority={latest_start:.2f}h")
        
        # 启动处理
        self.env.process(self.outbound_preparation_process(order))
        self.fte_manager.fte_available_count -= 1
    
    # 第三部分：等待
    if order_index < len(all_outbound_orders) and ready_queue:
        # 等待最少的时间（下一个订单到达 或 FTE空闲）
        next_arrival = all_outbound_orders[order_index].creation_time
        yield self.env.timeout(min(1.0, next_arrival - env.now))
    else:
        yield self.env.timeout(1.0)
```

#### 关键特性

| 特性 | 实现 |
|------|------|
| **动态到达** | `if next_order.creation_time <= env.now` 检查 |
| **优先级排序** | `heapq` 管理 `(latest_start_time, ...)` 元组 |
| **FTE选择** | `heappop()` 取出最高优先级订单 |
| **日志记录** | 每个事件（到达/处理）详细记录 |

## 工作流程示例

### 时间序列

```
时刻     订单到达队列         FTE处理          队列状态
─────────────────────────────────────────────────────
6:00    订单A到达            -               [A]
8:00    订单B到达            -               [A, B]
10:00   订单C到达            处理订单A        [C, B]
12:00   -                   处理订单B        [C]
14:00   订单D到达            -               [D, C]
16:00   -                   处理订单D        [C]
18:00   -                   处理订单C        []
```

### 优先级计算示例

```
订单   到达  装运  Pallets  容量     优先级(latest_start)
─────────────────────────────────────────────────────
A     6h   12h   200      163.7    10.78h
B     8h   14h   500      163.7    10.95h
C     10h  16h   100      163.7    15.39h
D     14h  18h   300      163.7    16.17h

优先级队列（按优先级排序）：
1. A (10.78h) ← 最紧张，最早处理
2. B (10.95h)
3. C (15.39h)
4. D (16.17h)
```

## vs Plan 2 的改进

### Plan 2 的问题
```
所有订单一开始就加入队列
按 latest_start_time 排序后逐个处理
↓ 但订单 B 的 creation_time 是 8h
所以即使它被排到前面，FTE 也要等到 8h 才能处理
```

### 动态队列的解决方案
```
1. 6h: 订单A到达 → 加入队列，FTE选择处理A
2. 8h: 订单B到达 → 加入队列 → 如果A还没完成，B等待；如果A完成了，FTE直接处理B
3. 10h: 订单C到达 → 加入队列
4. FTE 每次都从当前队列中选择优先级最高的订单
```

**关键区别**：
- Plan 2：提前知道所有订单，但 creation_time 约束导致后到订单被堵
- 动态队列：订单逐步到达，到达后立即按优先级排序，不会被提前到达的低优先级订单堵住

## 性能特性

| 指标 | Plan 2 | 动态队列 |
|------|--------|---------|
| **算法复杂度** | O(n log n) 一次性排序 | O(n log k)，k=队列大小 |
| **内存使用** | O(n) 所有订单 | O(k) 只存队列 |
| **对晚到订单** | 可能被堵 ✗ | 优先级重新排序 ✓ |
| **现实模拟** | 工厂提前知道全部订单 | 工厂不知道未来订单 |

## 日志输出样例

```
[6.0h] 订单到达：订单ID=1, pallets=200, priority=10.78h, 队列剩余=0个
[6.1h] FTE #1 可用，开始处理：订单ID=1, prep_time=1.22h, 调度序号=1
[8.0h] 订单到达：订单ID=2, pallets=500, priority=10.95h, 队列剩余=0个
[10.0h] 订单到达：订单ID=3, pallets=100, priority=15.39h, 队列剩余=1个
[14.0h] FTE #1 空闲，开始处理：订单ID=2, prep_time=3.05h, 调度序号=2
...
```

## 应用场景

这个算法特别适合：

1. **真实工厂模拟**
   - 订单真实到达时间变化
   - 工厂只能根据已有订单做决策

2. **SLA优化**
   - 优先处理时间紧张的订单
   - 减少延误率

3. **资源调度**
   - FTE 动态选择最优任务
   - 最大化产能利用率

4. **系统设计验证**
   - 测试不同的优先级规则
   - 评估不同FTE数量的影响

## 文件位置

- **实现**：[dc_simulation_plot_update.py](src/dc_simulation_plot_update.py)
  - `_calculate_prep_time()` - 第 ~1041 行
  - `_calculate_latest_start_time()` - 第 ~1057 行
  - `outbound_order_scheduler()` - 第 ~1088 行（新）

- **测试**：[test_priority_queue.py](test_priority_queue.py)
- **演示**：[demo_dynamic_scheduling.py](demo_dynamic_scheduling.py)

## 验证

✓ 代码通过 Python 语法检查（无错误）
✓ 优先级队列逻辑经过单元测试
✓ 与现有的 `outbound_preparation_process()` 和 `outbound_loading_process()` 兼容

## 下一步

1. **运行仿真**：执行 `demo_dynamic_scheduling.py` 观察完整流程
2. **分析结果**：比较与原算法的KPI差异
3. **调优参数**：根据实际结果调整优先级计算公式
4. **推广应用**：可考虑在 `inbound_order_scheduler()` 中应用同样逻辑
