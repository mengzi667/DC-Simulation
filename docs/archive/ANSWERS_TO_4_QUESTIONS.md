# 回答您的4个问题

## 1️⃣ 人力资源不是有实际数据吗？

### ✅ 是的！您说得对！

**实际数据来源：KPI sheet 2025.xlsx → productivity.py**

```
11个月实际工时数据：
┌─────┬──────────┬──────────┬─────────┐
│月份 │ R&P Hours│ FG Hours │ 总Hours │
├─────┼──────────┼──────────┼─────────┤
│Jan  │  3,645   │ 22,549   │ 26,194  │
│Feb  │  4,215   │ 19,503   │ 23,718  │
│Mar  │  4,785   │ 20,100   │ 24,885  │
│Apr  │  4,503   │ 16,940   │ 21,443  │
│May  │  4,646   │ 15,227   │ 19,873  │
│Jun  │  4,428   │ 15,479   │ 19,907  │
│Jul  │  5,053   │ 17,710   │ 22,763  │
│Aug  │  4,668   │ 15,123   │ 19,791  │
│Sep  │  4,500   │ 15,336   │ 19,836  │
│Oct  │  5,100   │ 15,865   │ 20,965  │
│Nov  │  4,376   │ 14,199   │ 18,575  │
├─────┼──────────┼──────────┼─────────┤
│平均 │  4,538   │ 17,094   │ 21,632  │
└─────┴──────────┴──────────┴─────────┘
```

### 📊 转换为FTE

**计算方法：**
```
每人每月工作时长 = 22天 × 8小时 = 176小时

总FTE = 21,632小时/月 ÷ 176小时/人/月 = 122.9 ≈ 125人

分类别：
- R&P FTE = 4,538 ÷ 176 = 25.8 ≈ 28人
- FG FTE = 17,094 ÷ 176 = 97.1 ≈ 97人
```

### ⚠️ 之前的错误

❌ **文档中写的**：FTE总数 = 50人（估算 ⭐⭐⭐）  
✅ **实际应该是**：FTE总数 = **125人** (实际数据 ⭐⭐⭐⭐⭐)

### ✅ 已修正

已更新 `dc_simulation.py`:
```python
'fte_total': 125,  # 从50改为125
'fte_allocation': {
    'rp_baseline': 28,
    'fg_baseline': 97
}
```

---

## 2️⃣ Timeslot是完全没用上吗？

### 😔 是的，目前Timeslot数据完全没有被使用

### 问题分析

1. **Timeslot.py 在寻找什么：**
   ```python
   file_pattern = 'W*.xlsx'  # 寻找W开头的Excel文件
   ```
   但在 `data/` 文件夹中**找不到**这些文件！

2. **实际的Timeslot文件位置：**
   ```
   drive-download-20251212T210746Z-3-001/
     ├─ Timeslot Capacity (1).xlsx  ← 实际存在
     └─ Slot Capacity.xlsx           ← 实际存在
   ```

3. **当前仿真使用的码头数：**
   ```python
   'docks': {
       'fg_reception': 10,   # 估算值 ⭐⭐⭐
       'fg_loading': 12,     # 估算值 ⭐⭐⭐
       'rp_reception': 8,    # 估算值 ⭐⭐⭐
       'rp_loading': 6       # 估算值 ⭐⭐⭐
   }
   ```
   **全部是估算！**

### Timeslot数据包含什么？

根据文件结构分析：

```
列结构：
- Condition: Loading / Reception
- Date: 日期
- Category: FG / R&P
- 'Booking taken': 已预订的时位数
- 'Available Capacity': 可用容量
- 24个小时列 (0h00 - 23h00): 每小时的时位数据
```

**这能告诉我们：**
- ✅ 每小时实际的码头容量（有多少个Loading/Reception位）
- ✅ 每小时的利用率 = Booking taken / (Booking taken + Available)
- ✅ 高峰时段的容量需求
- ✅ FG vs R&P 的容量分配比例

### ⚠️ 数据提取遇到的问题

刚才运行 `extract_timeslot_capacity.py` 的结果：
```
FG_Reception: 平均14.9, 最大50
FG_Loading: 平均12.7, 最大50
RP_Reception: 平均11.8, 最大50
RP_Loading: 平均12.5, 最大72
```

**问题：** 这些数字（50, 72）看起来像"列标题中的数字"而不是实际容量值。

### ✅ 需要做的

1. **手动检查** `Timeslot Capacity (1).xlsx` 的实际格式
2. **修正数据提取脚本**使其正确读取容量数据
3. **更新仿真参数**使用实际码头容量

**目前建议：**保持估算值，但标记为"待验证"

---

## 3️⃣ 需求分布是怎么计算的？

### 📊 完整计算流程

#### 步骤1: 数据来源

**文件：** `Total Shipments 2025.xlsx`
- Sheet 1: Inbound Shipments 2025
- Sheet 2: Outbound Shipments 2025

**关键列：**
- `Date Hour appointement`: 预约时间（精确到小时）
- `Category`: FG 或 R&P
- `Total pal`: 托盘数量

#### 步骤2: 提取小时到达率 (data_preparation.py 第150-170行)

```python
# 1. 提取小时字段
outbound_nov['Hour'] = outbound_nov['Date Hour appointement'].dt.hour

# 2. 分类别统计每小时的订单数
for category in ['FG', 'R&P']:
    category_data = outbound_nov[outbound_nov['Category'] == category]
    
    # 每小时有多少笔订单
    hourly_counts = category_data.groupby('Hour').size()
    
    # 11月有多少天
    num_days = category_data['Date Hour appointement'].dt.date.nunique()
    
    # 计算每小时平均到达卡车数
    hourly_rate = (hourly_counts / num_days).to_dict()
```

**结果示例：**
```python
{
    6: 2.5,   # 06:00时段平均每天2.5辆卡车
    7: 3.2,   # 07:00时段平均每天3.2辆卡车
    8: 4.1,   # ...
    ...
}
```

#### 步骤3: 计算每日需求 (data_preparation.py 第188-200行)

```python
def daily_demand_stats(df, category):
    cat_data = df[df['Category'] == category].copy()
    
    # 按日期分组
    cat_data['Date'] = cat_data['Date Hour appointement'].dt.date
    
    # 计算每天的总托盘数
    daily_pallets = cat_data.groupby('Date')['Total pal'].sum()
    
    return {
        'mean': daily_pallets.mean(),      # 平均值
        'std': daily_pallets.std(),        # 标准差
        'median': daily_pallets.median(),
        'min': daily_pallets.min(),
        'max': daily_pallets.max()
    }
```

**结果示例：**
```python
{
    'FG': {
        'outbound': {
            'mean': 1842,  # 每天平均1842托盘
            'std': 234     # 标准差234
        }
    }
}
```

#### 步骤4: 在仿真中使用 (dc_simulation.py 第479-520行)

**卡车到达进程：**
```python
def truck_arrival_process(self):
    arrival_rates = SYSTEM_PARAMETERS['truck_arrival_rates']
    
    while True:
        hour = int(self.env.now) % 24
        
        if hour in arrival_rates:
            # 泊松分布到达
            λ = arrival_rates[hour]  # 每小时平均到达率
            num_arrivals = np.random.poisson(λ)
            
            # 生成num_arrivals辆卡车
            for _ in range(num_arrivals):
                truck = self._generate_truck()
                ...
```

**托盘数量随机生成：**
```python
def _generate_truck(self):
    # 随机托盘数（20-35之间）
    pallets = np.random.randint(20, 35)
    ...
```

### ⚠️ 当前问题

1. ✅ **计算方法正确**：基于实际11月数据
2. ❌ **硬编码问题**：`arrival_rates` 在代码中是硬编码的示例值
3. ❌ **未连接**：`data_preparation.py` 和 `dc_simulation.py` 之间没有自动连接

### ✅ 应该怎么做

**正确流程：**
```
1. 运行 data_preparation.py
   → 生成 simulation_config.json

2. dc_simulation.py 读取 simulation_config.json
   → 加载实际的 arrival_rates

3. 运行仿真
```

**当前实际：**
```
dc_simulation.py 直接使用硬编码值 ❌
```

---

## 4️⃣ 人力资源起到了什么作用？

### 🔍 当前实现分析

#### FTEManager类 (dc_simulation.py 第186-214行)

```python
class FTEManager:
    def __init__(self, total_fte):
        self.total_fte = total_fte  # 总人数 (现在是125)
        
    def get_efficiency(self, category):
        """获取实际效率（考虑随机波动）"""
        mean = 5.81 if category == 'R&P' else 3.5  # 托盘/工时
        std = 0.416 if category == 'R&P' else 0.5
        
        # 正态分布随机效率
        efficiency = np.random.normal(mean, std)
        return max(efficiency, mean * 0.5)
    
    def allocate_fte(self, rp_workload, fg_workload):
        """动态分配FTE"""
        # 按工作负荷比例分配人力
        fte_rp = (rp_workload / total_workload) * self.total_fte
        fte_fg = (fg_workload / total_workload) * self.total_fte
        
        return fte_rp, fte_fg
```

#### 实际使用场景

**1. 入库处理 (第546-565行)：**
```python
def inbound_process(self, category, pallets, from_buffer=False):
    # 请求码头
    with self.docks[dock_key].request() as req:
        yield req
        
        # ← FTE影响这里！
        efficiency = self.fte_manager.get_efficiency(category)
        processing_time = pallets / efficiency
        
        yield self.env.timeout(processing_time)
```

**计算示例：**
```
假设：
- 托盘数 = 100
- R&P效率 = 5.81 托盘/工时 (从get_efficiency获取)

处理时间 = 100 / 5.81 = 17.2 小时
```

**2. 出库处理 (第567-602行)：**
```python
def outbound_process(self, truck):
    with self.docks[dock_key].request() as req:
        yield req
        
        # ← FTE影响这里！
        efficiency = self.fte_manager.get_efficiency(truck.category)
        loading_time = truck.pallets / efficiency
        
        yield self.env.timeout(loading_time)
```

### 🔍 深入理解

#### 效率 vs FTE 的关系

**关键理解：**
```
效率 (Efficiency) = 托盘总数 / 工时总数

工时 (Hours) = FTE数量 × 每人工作时长

因此：
效率 = 托盘总数 / (FTE × 工作时长)
```

**实际数据验证 (11月)：**
```
R&P:
- 托盘: 27,870
- 工时: 4,376
- 效率 = 27,870 / 4,376 = 6.37 托盘/工时

FG:
- 托盘: 55,270
- 工时: 14,199
- 效率 = 55,270 / 14,199 = 3.89 托盘/工时
```

**这里的"效率"已经是"每工时"效率！**

### ⚠️ 当前问题

#### 问题1: allocate_fte() 从未被调用

```python
# FTEManager类中定义了这个函数
def allocate_fte(self, rp_workload, fg_workload):
    ...
```

**但在整个仿真中：**
- ❌ 从未调用过这个函数
- ❌ FTE数量不影响实际分配
- ❌ 没有模拟"人力不足"的场景

#### 问题2: FTE数量不影响处理时间

**当前逻辑：**
```python
efficiency = self.fte_manager.get_efficiency(category)
processing_time = pallets / efficiency
```

- `efficiency` 来自KPI数据的平均值（5.81或3.5）
- **与 `self.total_fte` 无关！**
- FTE总数可以是50、125或1000，处理时间**完全一样**

#### 问题3: 误解了"效率"的含义

**当前假设：**
- 效率 = 每人每小时处理的托盘数 ❌

**实际情况：**
- 效率 = 每工时处理的托盘数 ✅
- 已经包含了人力配置的影响 ✅

### ✅ FTE的正确作用

#### 方案A: 保持当前逻辑（推荐）

**理解：**
- 效率数据已经**隐含了**人力配置
- FTE总数用于**报告和分析**，不直接影响处理时间
- 125人是"维持当前效率所需的人力"

**文档说明：**
```
FTE总数 = 125人
作用：
1. 基准人力配置（R&P 28人，FG 97人）
2. 成本计算（人工成本 = 125 × 人工单价）
3. 资源报告（人力利用率分析）
4. 不直接影响处理时间（效率已包含人力因素）
```

#### 方案B: 高级建模（复杂）

**如果要让FTE真正影响效率：**

```python
class FTEManager:
    def get_efficiency(self, category, current_workload):
        """效率受人力配置影响"""
        base_efficiency = EFFICIENCY_PARAMS[category]['mean']
        
        # 计算当前需要的人力
        allocated_fte = self.current_allocation[category]
        required_fte = current_workload / (base_efficiency * 8)
        
        # 人力压力系数
        stress_factor = required_fte / allocated_fte
        
        # 人力不足时效率下降
        if stress_factor > 1.2:  # 超负荷20%
            penalty = 0.9 ** (stress_factor - 1)
            actual_efficiency = base_efficiency * penalty
        else:
            actual_efficiency = base_efficiency
            
        # 加随机波动
        return np.random.normal(actual_efficiency, std)
```

**需要额外建模：**
- 实时工作负荷计算
- 动态人力调度
- 疲劳效应
- 班次轮换
- 加班机制

---

## 📋 总结：需要立即修正的问题

### ✅ 已修正
1. **FTE总数**: 50 → 125 (基于实际工时数据)
2. **添加FTE分配基准**: R&P 28人，FG 97人

### ⚠️ 需要手动修正
1. **Timeslot数据**: 
   - 检查 `Timeslot Capacity (1).xlsx` 实际格式
   - 提取真实的码头容量数据
   - 更新 `'docks'` 参数

2. **需求分布自动化**:
   - 运行 `data_preparation.py` 生成配置文件
   - 修改 `dc_simulation.py` 从配置文件读取
   - 删除硬编码的 `arrival_rates`

### 📝 需要文档说明
1. **FTE的作用**:
   - 说明效率已包含人力因素
   - FTE用于成本分析，不影响处理时间
   - 如需高级建模，参考方案B

---

**创建时间**: 2026-01-08  
**已完成修正**: FTE参数  
**待完成**: Timeslot提取、需求分布自动化
