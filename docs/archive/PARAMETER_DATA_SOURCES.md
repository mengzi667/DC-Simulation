# 仿真参数数据来源说明

**日期**: 2026年1月8日  
**状态**: 待完善

---

## ⚠️ 当前问题与改进计划

### 1️⃣ **码头容量分配（需要修正）**

**当前状态**: ❌ **使用假设比例**
```python
# dc_simulation.py 第81行
'fg_ratio': 0.70,  # FG占70% - 假设！
'rp_ratio': 0.30   # R&P占30% - 假设！
```

**问题**:
- Timeslot数据中**有FG和R&P的实际分类数据**
- `analyze_hourly_capacity.py` 代码已经提取了分类数据（第46-63行）
- 但最终只使用了**总容量**，然后按假设比例70:30分配

**实际数据位置**:
- 文件: `data/Timeslot by week/W*.xlsx`
- 数据包含:
  - FG Loading Capacity（按小时）
  - FG Reception Capacity（按小时）
  - R&P Loading Capacity（按小时）
  - R&P Reception Capacity（按小时）

**改进方案**:
```python
# 应该直接使用实际的FG和R&P码头容量，而不是按比例分配
'hourly_dock_capacity': {
    'loading': {
        'FG': {6: X, 7: Y, ...},    # 从Timeslot实际提取
        'R&P': {6: A, 7: B, ...}     # 从Timeslot实际提取
    },
    'reception': {
        'FG': {6: X, 7: Y, ...},
        'R&P': {6: A, 7: B, ...}
    }
}
```

---

### 2️⃣ **缓冲区容量（需要验证）**

**当前状态**: ⚠️ **基于计算假设**
```python
'buffer_capacity': {
    'rp': 50,   # 基于6小时关闭期间累积量估算
    'fg': 100   # 基于6小时关闭期间累积量估算
}
```

**计算逻辑** (data_preparation.py line 268-313):
```python
# 工厂24/7生产速率 × DC关闭小时数
accumulated_pallets = production_rate × 6小时
required_trailers = accumulated_pallets / 33托盘每挂车
recommended = required_trailers × 1.2  # 加20%安全余量
```

**数据来源**:
- ✅ 工厂生产速率：从KPI sheet计算（实际数据）
- ❌ DC关闭时长：假设6小时（00:00-06:00）
- ❌ 安全余量：假设20%
- ❌ 托盘/挂车：假设33托盘

**建议**:
1. 确认实际缓冲区物理容量限制
2. 如果有实际的挂车数量限制，应使用实际值
3. 当前计算方法合理，但需要验证假设参数

---

### 3️⃣ **托盘分布（需要实际数据）**

**当前状态**: ❌ **完全假设**
```python
'pallets_distribution': {
    'min': 20,
    'max': 35,
    'mean': 27.5
}
```

**问题**:
- 代码注释说"基于实际数据"但实际是假设值
- 没有从任何Excel文件提取

**实际数据位置**:
可能在以下文件中：
- ✅ `Total Shipments 2025.xlsx` - 有订单数和托盘数
- ✅ `KPI sheet 2025.xlsx` - 可能有平均托盘/订单

**改进方案**:
```python
# 从Total Shipments提取实际托盘分布
def extract_pallet_distribution(file_path):
    df = pd.read_excel(file_path)
    # 分析Pallets列的分布
    pallets = df['Pallets'].dropna()
    return {
        'min': pallets.min(),
        'max': pallets.max(),
        'mean': pallets.mean(),
        'std': pallets.std(),
        'distribution': 'triangular' or 'normal'  # 拟合分布类型
    }
```

---

### 4️⃣ **人力资源分配（待更新）**

**当前状态**: ⚠️ **部分实际，部分假设**
```python
'fte_total': 125,           # ✅ 从KPI sheet实际工时计算
'fte_allocation': {
    'rp_baseline': 28,      # ✅ 从KPI sheet计算
    'fg_baseline': 97       # ✅ 从KPI sheet计算
}
```

**FTE动态分配逻辑** (dc_simulation.py line 651-674):
```python
# ❌ 假设的动态分配比例
if buffer_level > threshold:
    # 提高缓冲区处理人员比例
    rp_ratio = 0.35  # 假设！
    fg_ratio = 0.65  # 假设！
```

**你提到的改进**:
> "后续我有一个不同活动的比例统计来分配"

**建议**:
1. 保留当前的baseline分配（基于工时实际数据）
2. 准备好活动比例数据后，更新动态分配逻辑
3. 新的分配应基于：
   - 实际的入库/出库/缓冲区处理时间比例
   - 不同时段的人员需求变化

---

## ✅ 已使用实际数据的参数

### 1. 卡车到达率
**来源**: `Total Shipments 2025.xlsx` - 305天全年数据
```python
'truck_arrival_rates': {
    'FG': {6: 1.62, 7: 2.8, ...},   # ✅ 实际统计
    'R&P': {6: 0.77, 7: 1.13, ...}  # ✅ 实际统计
}
```

### 2. 效率参数
**来源**: `KPI sheet 2025.xlsx` - 11个月数据
```python
'efficiency': {
    'rp': {
        'mean': 5.81,     # ✅ 11个月平均
        'std': 0.42       # ✅ 实际标准差
    },
    'fg': {
        'mean': 3.5,      # ✅ 11个月平均
        'std': 0.5        # ✅ 实际标准差
    }
}
```

### 3. 工厂生产速率
**来源**: `KPI sheet 2025.xlsx` - 从效率反推
```python
'factory_production': {
    'rp': 23,  # ✅ 托盘/小时
    'fg': 46   # ✅ 托盘/小时
}
```

### 4. FTE总数
**来源**: `KPI sheet 2025.xlsx` - 实际工时统计
```python
'fte_total': 125  # ✅ 21,632h/月 ÷ 176h/人/月
```

### 5. 码头总容量（按小时）
**来源**: `Timeslot W1-W48.xlsx` - 48周实际数据
```python
'hourly_dock_capacity': {
    'loading': {6: 6, 7: 8, ...},   # ✅ 48周中位数
    'reception': {6: 5, 7: 5, ...}  # ✅ 48周中位数
}
```

---

## 🔧 需要立即修复的优先级

### 🔴 高优先级
1. **修正码头容量分配** - 应使用Timeslot中FG/R&P的实际分配，而非70:30假设
2. **提取实际托盘分布** - 从Total Shipments数据中提取

### 🟡 中优先级
3. **验证缓冲区容量** - 确认实际物理限制
4. **更新FTE动态分配** - 等待实际活动比例数据

---

## 📝 修改清单

- [ ] 修改 `analyze_hourly_capacity.py` - 分别输出FG和R&P码头容量
- [ ] 修改 `dc_simulation.py` - 更新码头容量数据结构
- [ ] 创建 `extract_pallet_distribution.py` - 从Total Shipments提取托盘分布
- [ ] 更新文档注释 - 明确标注实际数据vs假设
- [ ] 验证缓冲区容量参数
- [ ] 等待活动比例数据 - 更新FTE分配逻辑

---

## 💡 下一步行动

1. **立即执行**:
   ```bash
   # 修改码头容量提取脚本
   python src/analyze_hourly_capacity.py
   ```
   输出应该包含：
   - FG Loading by hour
   - FG Reception by hour
   - R&P Loading by hour
   - R&P Reception by hour

2. **创建托盘分布提取脚本**

3. **更新仿真参数配置**

4. **重新运行仿真验证**

---

**更新时间**: 2026-01-08  
**待办事项**: 3个高优先级修正
