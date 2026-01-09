# DC仿真模型完整文档

## 📊 模型概览

**项目名称**: Distribution Center Operating Hours Reduction Simulation  
**仿真引擎**: SimPy 4.0.1 (离散事件仿真)  
**数据基础**: 2025年全年实际运营数据  
**建模目的**: 评估DC运营时间缩短对业务的影响

---

## 🎯 仿真目标

1. **主要目标**: 量化分析DC运营时间从18小时缩减至12-16小时的影响
2. **关键问题**: 
   - 缓冲区是否溢出？
   - 等待时间是否增加？
   - 码头利用率如何变化？
   - 人力资源如何调配？

---

## 📦 核心实体 (5个)

### 1. **Truck (卡车)**
```python
属性:
  - category: 'FG' | 'R&P'
  - direction: 'Inbound' | 'Outbound'
  - pallets: 20-35托盘
  - scheduled_time: 计划到达时间
  - actual_arrival_time: 实际到达时间
  - service_start/end_time: 服务开始/结束时间
```

### 2. **TrailerBuffer (挂车缓冲区)**
```python
容量:
  - R&P: 50托盘 (15挂车 × 33托盘/挂车)
  - FG: 100托盘 (20挂车 × 33托盘/挂车)
  
功能:
  - 存储工厂生产的货物
  - DC关门期间累积
  - DC开门后释放入库
```

### 3. **FTEManager (人力资源管理器)**
```python
总人数: 125 FTE
  - R&P基准: 28人
  - FG基准: 97人
  
动态分配:
  - 根据工作负荷实时调整
  - 效率受人员数量影响
```

### 4. **Dock Resources (码头资源)**
```python
类型:
  - Loading (装车): 3-8个码头/小时
  - Reception (卸货): 1-6个码头/小时
  
特点:
  - 时变容量 (基于48周实际数据)
  - FG/R&P按70:30比例分配
```

### 5. **KPICollector (KPI收集器)**
```python
收集指标:
  - 等待时间 (waiting_times)
  - 缓冲区占用率 (buffer_occupancy)
  - 出入库操作 (inbound/outbound_ops)
  - SLA遵守情况 (sla_misses)
```

---

## ⚙️ 主要进程 (7个并发)

### 1. **factory_production_process** (工厂生产)
- **频率**: 24/7连续生产
- **速率**: R&P 23托盘/h, FG 46托盘/h
- **输出**: 货物进入缓冲区

### 2. **buffer_release_process** (缓冲区释放)
- **触发**: DC开门时刻
- **逻辑**: 每30分钟检查，释放货物入库
- **限制**: 每次最多150托盘

### 3. **truck_arrival_process** (卡车到达) ⭐
- **分布**: 泊松分布 (λ按小时变化)
- **类别**: FG和R&P分别独立到达
- **全年数据**: 
  - FG: 17个时段, 36.77辆/天
  - R&P: 20个时段, 16.27辆/天

### 4. **inbound_process** (入库处理)
- **流程**: 等待码头 → 卸货 → 释放资源
- **时间**: pallets / efficiency (效率随机)
- **码头**: Reception码头

### 5. **outbound_process** (出库处理) ⭐
- **流程**: 等待码头 → 装车 → 离开
- **时间**: pallets / efficiency
- **码头**: Loading码头

### 6. **buffer_monitor** (缓冲区监控)
- **频率**: 每小时记录
- **数据**: R&P和FG的占用率

### 7. **码头容量更新** (隐式)
- **频率**: 每小时动态更新
- **数据**: 基于48周Timeslot实际容量

---

## 📊 关键参数 (20个)

### 数据来源汇总

| 参数类别 | 数据源 | 时间跨度 | 数据点数 |
|---------|--------|---------|---------|
| 效率参数 | KPI sheet 2025.xlsx | 11个月 | 11 |
| 到达率 | Total Shipments 2025.xlsx | 305天 | 16,176 |
| 码头容量 | Timeslot W1-W48.xlsx | 48周 | 48×7×24 |

### 1. 效率参数 (基于11个月KPI数据)
```python
R&P: 5.81 ± 0.42 托盘/小时
FG:  3.50 ± 0.50 托盘/小时
```

### 2. 到达率参数 (基于305天全年数据)
```python
FG到达率 (17个时段):
  6h: 1.62, 7h: 2.80, 8h: 2.47, 9h: 2.61, 10h: 3.15,
  11h: 3.21, 12h: 3.16, 13h: 3.01, 14h: 2.90, 15h: 2.60,
  16h: 2.65, 17h: 2.11, 18h: 1.82, 19h: 1.59, 20h: 0.70,
  21h: 0.23, 22h: 0.15

R&P到达率 (20个时段):
  6h: 0.77, 7h: 1.13, 8h: 1.13, 9h: 1.14, 10h: 0.96,
  11h: 1.08, 12h: 0.78, 13h: 0.83, 14h: 0.95, 15h: 0.99,
  16h: 0.87, 17h: 0.87, 18h: 0.94, 19h: 1.42, 20h: 0.77,
  21h: 0.75, 22h: 0.52, 23h: 0.36

实际比例: FG 69.3%, R&P 30.7%
```

### 3. 码头容量参数 (基于48周数据)
```python
Loading (出库码头):
  高峰: 7-15点, 7-8个码头
  低峰: 20-23点, 4-5个码头
  关闭: 0-5点

Reception (入库码头):
  稳定: 6-18点, 5个码头
  降低: 19-23点, 1-4个码头
  关闭: 0-5点

分配比例: FG 70%, R&P 30%
```

### 4. 其他参数
```python
工厂生产速率:
  R&P: 23 托盘/小时 (24/7连续)
  FG:  46 托盘/小时 (24/7连续)

缓冲区容量:
  R&P: 50 托盘
  FG:  100 托盘

人力资源:
  总FTE: 125人
  R&P基准: 28人
  FG基准: 97人

托盘分布:
  范围: 20-35托盘/车
  平均: 27.5托盘
```

---

## 🔄 仿真流程

```
1. 初始化
   ├── 创建SimPy环境
   ├── 加载参数配置
   ├── 初始化实体和资源
   └── 设置随机种子

2. 并发进程启动
   ├── factory_production_process (R&P)
   ├── factory_production_process (FG)
   ├── buffer_release_process
   ├── truck_arrival_process (FG + R&P)
   └── buffer_monitor

3. 事件循环 (SimPy引擎)
   ├── 按时间推进仿真
   ├── 处理资源竞争
   ├── 更新状态
   └── 记录KPI

4. 结果输出
   ├── 生成汇总统计
   ├── 导出Excel详细数据
   └── 可视化图表
```

---

## 📈 输出KPI

### 1. 等待时间指标
- 平均等待时间 (avg_waiting_time)
- 最大等待时间 (max_waiting_time)
- P95等待时间

### 2. 缓冲区指标
- 平均占用率 (R&P / FG)
- 最大占用率
- 溢出次数和托盘数

### 3. 吞吐量指标
- 总出库操作数 (total_outbound_ops)
- 总入库操作数 (total_inbound_ops)
- 总托盘数 (inbound/outbound)

### 4. 资源利用率
- 码头利用率 (按小时)
- FTE分配情况

### 5. 场景对比
- Baseline vs Scenario 1/2/3
- 运营时间影响分析

---

## 🎨 模型特点

### ✓ 数据驱动
- **305天**实际到达数据
- **48周**码头容量变化
- **11个月**效率统计

### ✓ 分类别建模
- FG和R&P独立到达进程
- 各自的到达率和效率参数
- 分别的缓冲区管理

### ✓ 时变特性
- 每小时码头容量动态变化
- 效率随机波动
- 到达率按时段变化

### ✓ 24/7工厂生产
- 连续生产模拟
- 缓冲区累积机制
- DC开门释放逻辑

### ✓ 动态资源管理
- FTE根据负荷分配
- 码头资源竞争
- 效率受人员影响

---

## 🔧 技术栈

- **仿真引擎**: SimPy 4.0.1
- **数据处理**: Pandas 2.x
- **数值计算**: NumPy 1.x
- **可视化**: Matplotlib 3.x
- **数据存储**: Excel (openpyxl)
- **语言**: Python 3.12

---

## 📁 项目文件

### 核心代码
- `src/dc_simulation.py` - 主仿真模型 (954行)
- `src/data_preparation.py` - 数据提取 (517行)
- `src/analyze_hourly_capacity.py` - 容量分析 (273行)

### 数据文件
- `data/KPI sheet 2025.xlsx` - 效率数据
- `data/Total Shipments 2025.xlsx` - 到达数据
- `data/Timeslot by week/W*.xlsx` - 容量数据 (48个文件)

### 输出
- `outputs/results/*.xlsx` - 仿真结果
- `outputs/figures/*.jpg` - 可视化图表

### 文档
- `README.md` - 项目说明
- `PROJECT_STRUCTURE.md` - 结构文档
- `SIMULATION_ANALYSIS.md` - 架构分析
- `DC_SIMULATION_SUMMARY.md` - 本文档

---

## 🚀 使用方法

### 1. 数据准备
```bash
python src/data_preparation.py
```

### 2. 运行仿真
```bash
python src/dc_simulation.py
```

### 3. 查看结果
- 打开 `outputs/results/simulation_results_comparison.xlsx`
- 查看 `outputs/figures/` 中的图表

---

## 📊 验证与校准

### 数据一致性检查
- ✓ 到达率总和 = 实际记录卡车数
- ✓ 效率分布 = KPI sheet统计
- ✓ 码头容量 = Timeslot平均值

### 模型验证
- ✓ Baseline场景 ≈ 实际运营情况
- ✓ 缓冲区逻辑符合业务规则
- ✓ 资源竞争机制合理

---

## 📅 更新日志

**2026-01-08**
- ✅ 修改为使用全年305天到达数据
- ✅ FG和R&P分类别独立建模
- ✅ 移除固定比例，使用实际到达率
- ✅ 删除订单生成逻辑，统一为到达率驱动
- ✅ 更新所有参数注释说明数据来源

**关键改进**
- 从11月20天数据 → 全年305天数据
- 从固定比例67:33 → 实际比例69.3:30.7
- 从订单+随机双重建模 → 统一到达率建模
- FG从16时段 → 17时段，R&P从8时段 → 20时段

---

**文档生成时间**: 2026年1月8日  
**模型版本**: v2.0 (全年数据版)  
**作者**: DC Simulation Team
