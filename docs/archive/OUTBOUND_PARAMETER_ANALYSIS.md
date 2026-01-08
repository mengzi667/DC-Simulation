# Outbound装车流程参数使用分析

## 🚛 Outbound的两个来源

### 1️⃣ **truck_arrival_process（随机到达的卡车）**
```python
使用的参数：
✅ truck_arrival_rates: {6: 2.5, 7: 3.2, ...}  # 每小时到达率
✅ 指数延迟: scale=0.25（平均15分钟）
✅ FG/R&P比例: [0.67, 0.33]
✅ 托盘数: np.random.randint(20, 35)
✅ fg_departure_schedule: [8, 10, 12, ...]     # 分配发运时间
```

**流程**：
```
每小时 → 泊松到达 → 生成卡车 → outbound_process
  ↓
使用truck_arrival_rates[hour]
```

---

### 2️⃣ **fg_order_generator（FG订单驱动的卡车）**
```python
使用的参数：
✅ fg_departure_schedule: [8, 10, 12, ...]     # 发运时间表
✅ loading_lead_time: 2                        # 提前2小时截单
✅ 下单时间偏移: uniform(1, 4)小时
✅ 托盘数: np.random.randint(80, 200)
```

**流程**：
```
发运时间表 → 提前下单 → 创建订单 → 创建卡车 → outbound_process
  ↓
不使用truck_arrival_rates！
```

---

## ⚠️ **关键问题：参数冲突与重复建模**

### **问题1：两个进程都在生成FG outbound卡车**

```python
# 进程1：truck_arrival_process
if category == 'FG':  # 67%概率
    truck.departure_deadline = _assign_departure_time()
    → outbound_process(truck)

# 进程2：fg_order_generator
for departure_hour in schedule:
    order = Order(...)
    → process_fg_order(order)
        → outbound_process(truck)
```

**结果**：
- ❌ FG出库被**重复建模**了！
- ❌ 同一个业务流程有两套逻辑

---

### **问题2：truck_arrival_rates的实际含义不清**

从 `Total Shipments 2025.xlsx` 提取的 `truck_arrival_rates` 是：

```python
'truck_arrival_rates': {
    6: 2.5,   # 早上6点平均2.5辆卡车
    7: 3.2,
    ...
}
```

**这个数据包含了什么？**
- ✅ 包含FG outbound
- ✅ 包含R&P outbound
- ❓ 是所有outbound还是只有一部分？

**但代码中**：
- `truck_arrival_process` 使用这个数据生成随机卡车
- `fg_order_generator` 又独立生成FG卡车

**→ 如果数据已包含FG，为什么还要单独建模FG订单？**

---

## 🔍 **实际使用的参数清单**

### **Outbound Process使用的参数**

| 参数 | 来源 | 在outbound_process中的使用 |
|------|------|--------------------------|
| **hourly_dock_capacity['loading']** | 48周Timeslot | ✅ 码头容量检查 |
| **efficiency (FG/R&P)** | KPI sheet | ✅ 计算装车时间 |
| **truck.pallets** | 随机生成 | ✅ 计算装车时间 |
| **truck.category** | 随机/订单 | ✅ 选择码头、效率 |
| **truck.departure_deadline** | fg_departure_schedule | ✅ 检查SLA（仅FG） |

---

### **truck_arrival_process使用的参数**

| 参数 | 值 | 实际用途 |
|------|-----|---------|
| **truck_arrival_rates** | {6:2.5, 7:3.2, ...} | ✅ 泊松到达的λ参数 |
| **指数延迟** | scale=0.25 | ✅ 同一小时内卡车间隔 |
| **FG/R&P比例** | [0.67, 0.33] | ✅ 类别随机选择 |
| **托盘数范围** | 20-35 | ✅ 卡车载量 |
| **fg_departure_schedule** | [8,10,12,...] | ✅ FG分配发运时间 |

---

### **fg_order_generator使用的参数**

| 参数 | 值 | 实际用途 |
|------|-----|---------|
| **fg_departure_schedule** | [8,10,12,...] | ✅ 发运时间表 |
| **loading_lead_time** | 2小时 | ✅ 计算截单时间 |
| **下单时间偏移** | uniform(1,4) | ✅ 订单提前时间 |
| **订单托盘数** | 80-200 | ✅ 订单大小 |

---

## 🚨 **当前模型的逻辑问题**

### **矛盾1：FG被重复建模**

```
实际业务：
  FG订单 → 装车 → 发运

当前模型：
  [进程1] 随机到达卡车（67%是FG）→ 装车
  [进程2] FG订单 → 创建卡车 → 装车
  
  → 两个进程都在生成FG出库！
```

---

### **矛盾2：参数来源与使用不匹配**

```
truck_arrival_rates 提取自：
  Total Shipments 2025 - Outbound（所有出库记录）
  
但模型中：
  truck_arrival_process → 生成一部分outbound
  fg_order_generator → 又生成一部分FG outbound
  
  → 总到达率 > 实际数据？
```

---

## 💡 **建议的修正方案**

### **方案A：分离R&P和FG的到达建模**

```python
1. truck_arrival_process → 只生成R&P outbound
   - 使用R&P的到达率（从数据中分离）
   
2. fg_order_generator → 生成FG outbound
   - 基于发运时间表和订单
   
3. 删除_generate_truck中的FG逻辑
```

---

### **方案B：统一为订单驱动模型**

```python
1. 删除truck_arrival_process
   
2. 扩展为通用order_generator
   - FG订单：基于发运时间表
   - R&P订单：基于历史到达分布
   
3. 所有outbound统一通过订单处理
```

---

### **方案C：保留当前模型但明确区分**

```python
1. truck_arrival_process → 即时性小批量
   - "临时加单"、"紧急出库"
   
2. fg_order_generator → 计划性大批量
   - "固定发运窗口"的订单
   
3. 在文档中明确说明两种业务场景
```

---

## 📊 **参数实际使用率统计**

| 参数类别 | 参数数量 | 使用率 | 备注 |
|---------|---------|-------|------|
| **Outbound相关** | 5个 | 100% | 都有使用 |
| **码头容量** | 2个 | 100% | loading容量 |
| **效率参数** | 4个 | 100% | 装车时间计算 |
| **到达分布** | 1个 | ⚠️ 50% | 仅truck_arrival使用 |
| **FG时间表** | 2个 | ⚠️ 重复 | 两处都用 |

---

## ✅ **回答原问题：Outbound参数有用到吗？**

**简短回答**：
- ✅ **大部分参数都用到了**
- ⚠️ **但存在逻辑不一致**：
  - `truck_arrival_rates` 只在随机到达中使用
  - `fg_departure_schedule` 被两个进程同时使用
  - FG outbound 被重复建模

**详细说明**：

### **用到的参数**：
1. ✅ `hourly_dock_capacity['loading']` - 码头容量限制
2. ✅ `efficiency (FG/R&P)` - 装车时间计算
3. ✅ `truck_arrival_rates` - 随机卡车到达
4. ✅ `fg_departure_schedule` - FG发运窗口
5. ✅ `loading_lead_time` - 截单提前时间

### **没完全用到/有问题的**：
1. ⚠️ `truck_arrival_rates` 从Outbound数据提取，但只用于生成随机卡车，FG订单不走这个逻辑
2. ⚠️ 托盘数有两套：随机到达20-35，订单80-200

---

## 🎯 **核心发现**

当前模型中，**Outbound有两个并行的生成机制**：

```
机制1（基于统计到达率）:
  truck_arrival_rates → 泊松到达 → 随机卡车 → outbound

机制2（基于业务规则）:
  fg_departure_schedule → 订单生成 → 计划卡车 → outbound
```

**这可能是**：
- ✅ 有意设计：区分"计划发运"和"随机补单"
- ❌ 建模错误：FG被重复计算

**需要明确**：
1. 实际业务中，FG outbound是100%计划性还是有随机性？
2. `truck_arrival_rates`中的FG部分是否应该剔除？
3. 两个机制生成的卡车是否应该合并到一个统计中？
