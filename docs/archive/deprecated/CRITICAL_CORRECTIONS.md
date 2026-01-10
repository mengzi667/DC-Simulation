# 🚨 仿真参数重大修正

## 发现的问题

### 1️⃣ **人力资源(FTE)有实际数据！**

#### ❌ 之前的错误
- 文档说：FTE总数 = 50 (估算值 ⭐⭐⭐)
- 实际情况：**KPI sheet 2025.xlsx** 中有每月的实际工时(Hours)数据！

#### ✅ 实际数据来源

**来自 productivity.py 运行结果：**

| 月份 | R&P Hours | FG Hours | 总Hours |
|------|-----------|----------|---------|
| Jan | 3,645 | 22,549 | 26,194 |
| Feb | 4,215 | 19,503 | 23,718 |
| Mar | 4,785 | 20,100 | 24,885 |
| Apr | 4,503 | 16,940 | 21,443 |
| May | 4,646 | 15,227 | 19,873 |
| Jun | 4,428 | 15,479 | 19,907 |
| Jul | 5,053 | 17,710 | 22,763 |
| Aug | 4,668 | 15,123 | 19,791 |
| Sep | 4,500 | 15,336 | 19,836 |
| Oct | 5,100 | 15,865 | 20,965 |
| Nov | 4,376 | 14,199 | 18,575 |

**11个月平均：**
- R&P平均: **4,538 小时/月**
- FG平均: **17,094 小时/月**
- **总计: 21,632 小时/月**

#### 📊 转换为FTE

假设：
- 每人每月工作: 160小时 (40小时/周 × 4周)
- 或使用实际工作日: 22天/月 × 8小时 = 176小时/月

**方法1 (160h/月):**
```
总FTE = 21,632 / 160 = 135.2 人
R&P FTE = 4,538 / 160 = 28.4 人
FG FTE = 17,094 / 160 = 106.9 人
```

**方法2 (176h/月):**
```
总FTE = 21,632 / 176 = 122.9 人
R&P FTE = 4,538 / 176 = 25.8 人
FG FTE = 17,094 / 176 = 97.1 人
```

**建议使用: ~120-135 FTE** (而不是之前的50!)

---

### 2️⃣ **Timeslot数据完全没用上！**

#### 问题分析

1. **Timeslot.py 寻找的文件**:
   ```python
   file_pattern = 'W*.xlsx'  # 寻找 W开头的Excel文件
   ```
   但在data/文件夹中找不到这些文件！

2. **实际存在的Timeslot相关文件**:
   ```
   drive-download-20251212T210746Z-3-001/
     ├─ Timeslot Capacity (1).xlsx  ← 这个！
     └─ Slot Capacity.xlsx           ← 这个！
   ```

3. **已生成的文件**:
   ```
   data/Nov_analysis/
     └─ Timeslot_Filtered_Data_November_2025.xlsx
   ```

#### Timeslot数据包含什么？

根据 Timeslot.py 代码分析：

```python
# 提取字段
- 'Loading' 或 'Reception' (出库/入库)
- Category (FG / R&P)
- 'Booking taken' (已预订时位)
- 'Available Capacity' (可用容量)
- 24个小时的时位数据 (7:00 - 30:00?)
```

**这能告诉我们什么：**
- ✅ 每小时各类型的实际码头容量
- ✅ 每小时的利用率
- ✅ 实际的Loading/Reception码头数

**目前仿真中的码头数都是估算的：**
```python
'docks': {
    'fg_reception': 10,   # 估算 ⭐⭐⭐
    'fg_loading': 12,     # 估算 ⭐⭐⭐
    'rp_reception': 8,    # 估算 ⭐⭐⭐
    'rp_loading': 6       # 估算 ⭐⭐⭐
}
```

---

### 3️⃣ **需求分布计算方法**

#### 当前实现 (data_preparation.py 第150-220行)

**步骤1: 提取小时到达率**
```python
# 从 Total Shipments 2025.xlsx 提取
outbound_nov['Hour'] = outbound_nov['Date Hour appointement'].dt.hour

# 计算每小时平均到达卡车数
hourly_counts = category_data.groupby('Hour').size()
num_days = category_data['Date Hour appointement'].dt.date.nunique()
hourly_rate = (hourly_counts / num_days).to_dict()
```

**结果：** 每小时平均到达λ (泊松分布参数)

**步骤2: 计算每日需求**
```python
cat_data['Date'] = cat_data['Date Hour appointement'].dt.date
daily_pallets = cat_data.groupby('Date')['Total pal'].sum()

return {
    'mean': daily_pallets.mean(),
    'std': daily_pallets.std(),
    ...
}
```

**结果：** 每日托盘需求的均值、标准差

#### 在仿真中的使用

```python
# dc_simulation.py 第 479-520行
def truck_arrival_process(self):
    arrival_rates = SYSTEM_PARAMETERS['truck_arrival_rates']
    
    hour = int(self.env.now) % 24
    
    if hour in arrival_rates:
        # 泊松到达
        num_arrivals = np.random.poisson(arrival_rates[hour])
        
        for _ in range(num_arrivals):
            truck = self._generate_truck()
            # 添加延迟
            delay = np.random.exponential(scale=0.25)
            ...
```

**问题：**
- ✅ 计算方法正确
- ❌ 但 `arrival_rates` 数据结构在代码中是硬编码的简化版本
- ❌ 没有从 data_preparation.py 自动提取

---

### 4️⃣ **人力资源在仿真中的作用**

#### 当前实现 (dc_simulation.py)

**FTEManager类 (第186-214行):**

```python
class FTEManager:
    def __init__(self, total_fte):
        self.total_fte = total_fte  # 总人数
        
    def get_efficiency(self, category):
        """获取实际效率（考虑随机波动）"""
        # 使用正态分布模拟效率波动
        efficiency = np.random.normal(mean, std)
        return max(efficiency, mean * 0.5)
    
    def allocate_fte(self, rp_workload, fg_workload):
        """根据工作负荷动态分配 FTE"""
        total_workload = rp_workload + fg_workload
        
        # 按比例分配
        fte_rp = (rp_workload / total_workload) * self.total_fte
        fte_fg = (fg_workload / total_workload) * self.total_fte
        
        return fte_rp, fte_fg
```

#### 实际使用场景

**1. 入库处理 (第546-565行):**
```python
def inbound_process(self, category, pallets, from_buffer=False):
    # 请求码头资源
    with self.docks[dock_key].request() as req:
        yield req
        
        # 获取效率并计算处理时间
        efficiency = self.fte_manager.get_efficiency(category)
        processing_time = pallets / efficiency  # ← FTE影响这里！
        
        yield self.env.timeout(processing_time)
```

**2. 出库处理 (第567-602行):**
```python
def outbound_process(self, truck):
    with self.docks[dock_key].request() as req:
        yield req
        
        # 获取效率并计算装车时间
        efficiency = self.fte_manager.get_efficiency(truck.category)
        loading_time = truck.pallets / efficiency  # ← FTE影响这里！
        
        yield self.env.timeout(loading_time)
```

#### 🔍 问题分析

**当前问题：**
1. ❌ FTE总数设为50，但实际应该是~120-135人
2. ❌ `allocate_fte()` 函数定义了但**从未被调用**！
3. ❌ 效率直接从KPI数据读取，没有考虑FTE数量的影响

**效率与FTE的关系：**
```
效率 = 托盘总数 / 工时总数

当前：
R&P效率 = 27,870托盘 / 4,376小时 = 6.37 托盘/小时
FG效率 = 55,270托盘 / 14,199小时 = 3.89 托盘/小时

这个效率是"每工时"效率，不是"每人"效率！
```

**正确理解：**
- **工时(Hours)** = FTE数量 × 工作时长
- **效率(Efficiency)** = 托盘 / 工时 = 单位时间单位人力的生产率
- **当前仿真**：效率已经隐含了人力因素

**因此：**
- ✅ 使用效率计算处理时间是正确的
- ⚠️ FTE总数在当前模型中**不直接影响**处理时间
- ⚠️ FTE的作用应该是：
  1. **资源约束**：总人力有限，需要在R&P和FG之间分配
  2. **疲劳效应**：人力不足时效率下降
  3. **班次管理**：不同时段可用人力不同

---

## 🔧 修正建议

### 优先级1: 立即修正FTE数据

```python
# dc_simulation.py 第95行
SYSTEM_PARAMETERS = {
    'fte_total': 125,  # 从50改为125 (基于实际工时数据)
    
    'fte_allocation': {  # 新增：各类别基准人力
        'rp_baseline': 28,   # R&P基准人力
        'fg_baseline': 97    # FG基准人力
    }
}
```

### 优先级2: 整合Timeslot数据

**创建新脚本提取码头容量：**

```python
# extract_timeslot_capacity.py
import pandas as pd

file_path = 'drive-download-20251212T210746Z-3-001/Timeslot Capacity (1).xlsx'
# 或 'drive-download-20251212T210746Z-3-001/Slot Capacity.xlsx'

# 提取各类别各时段的实际容量
# 更新 SYSTEM_PARAMETERS['docks']
```

### 优先级3: 自动化需求分布提取

**修改dc_simulation.py使其从data_preparation.py输出读取参数：**

```python
# 读取 data_preparation.py 生成的 simulation_config.json
import json

with open('simulation_config.json', 'r') as f:
    config = json.load(f)

SYSTEM_PARAMETERS['truck_arrival_rates'] = config['hourly_arrival_rate']
```

### 优先级4: 改进FTE建模

**选项A: 简单改进 (保持当前逻辑)**
- 更新FTE总数为125
- 文档说明效率已包含人力因素
- allocate_fte() 仅用于报告/分析

**选项B: 高级建模 (重构)**
```python
class FTEManager:
    def __init__(self, total_fte, allocation_dict):
        self.total_fte = total_fte
        self.current_allocation = allocation_dict
        
    def get_efficiency(self, category, current_workload):
        """效率受人力配置影响"""
        base_efficiency = EFFICIENCY_PARAMS[category]['mean']
        
        # 计算人力压力系数
        allocated_fte = self.current_allocation[category]
        required_fte = current_workload / (base_efficiency * 8)  # 8h工作日
        
        stress_factor = required_fte / allocated_fte if allocated_fte > 0 else 999
        
        # 压力过大时效率下降
        if stress_factor > 1.2:
            efficiency_penalty = 0.9 ** (stress_factor - 1)
            actual_efficiency = base_efficiency * efficiency_penalty
        else:
            actual_efficiency = base_efficiency
            
        # 加上随机波动
        return np.random.normal(actual_efficiency, std)
```

---

## 📋 行动清单

### 必须完成 (影响结果准确性)

- [ ] **修正FTE总数**: 50 → 125
- [ ] **提取Timeslot数据**确定实际码头数
- [ ] **连接data_preparation.py输出**到仿真输入
- [ ] **更新所有文档**中的参数可信度评级

### 可选改进 (提高模型真实性)

- [ ] 实现FTE动态分配逻辑
- [ ] 添加人力疲劳效应
- [ ] 建模班次轮换
- [ ] 考虑高峰时段临时人力

---

## 📝 数据质量重新评估

| 参数类别 | 之前 | 现在 | 改变 |
|---------|------|------|------|
| **FTE总数** | ⭐⭐⭐ (估算) | ⭐⭐⭐⭐⭐ (实际数据) | ✅ 提升 |
| **码头容量** | ⭐⭐⭐ (估算) | ⭐⭐⭐⭐ (Timeslot数据) | ✅ 可提升 |
| **到达分布** | ⭐⭐⭐⭐ (计算) | ⭐⭐⭐⭐⭐ (直接提取) | ✅ 可提升 |

---

**创建时间**: 2026-01-08  
**状态**: 🚨 需要立即修正
