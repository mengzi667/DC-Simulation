"""
按时间段分析Timeslot码头容量
"""

import pandas as pd
import numpy as np
import glob
import matplotlib.pyplot as plt
from collections import Counter

print("=" * 70)
print("按时间段分析48周Timeslot数据")
print("=" * 70)

files = glob.glob('data/Timeslot by week/W*.xlsx')
print(f"\n找到 {len(files)} 个文件")

# 为每个小时收集数据
hourly_loading = {hour: [] for hour in range(24)}    # 总Loading
hourly_reception = {hour: [] for hour in range(24)}  # 总Reception

fg_hourly_loading = {hour: [] for hour in range(24)}
fg_hourly_reception = {hour: [] for hour in range(24)}
rp_hourly_loading = {hour: [] for hour in range(24)}
rp_hourly_reception = {hour: [] for hour in range(24)}

print("\n正在处理...")
for idx, file in enumerate(files, 1):
    if idx % 10 == 0:
        print(f"  进度: {idx}/{len(files)}")
    
    df = pd.read_excel(file, header=None)
    
    for row_idx in range(len(df)):
        row = df.iloc[row_idx]
        category = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ''
        capacity_type = str(row.iloc[5]) if pd.notna(row.iloc[5]) else ''
        
        is_loading_capacity = 'loading capacity' in capacity_type.lower()
        is_reception_capacity = 'reception' in capacity_type.lower() and 'capacity' in capacity_type.lower()
        
        if is_loading_capacity or is_reception_capacity:
            # 提取24小时数据（列7-30）
            for hour in range(24):
                col_idx = 7 + hour
                try:
                    value = float(row.iloc[col_idx])
                    if value > 0:  # 只记录非零值
                        is_total = category == 'nan' or category == ''
                        
                        if is_loading_capacity:
                            if is_total:
                                hourly_loading[hour].append(value)
                            elif 'FG' in category:
                                fg_hourly_loading[hour].append(value)
                            elif 'R&P' in category:
                                rp_hourly_loading[hour].append(value)
                        
                        elif is_reception_capacity:
                            if is_total:
                                hourly_reception[hour].append(value)
                            elif 'FG' in category:
                                fg_hourly_reception[hour].append(value)
                            elif 'R&P' in category:
                                rp_hourly_reception[hour].append(value)
                except:
                    pass

print("\n✓ 处理完成！")

# 分析每个时段的容量
print("\n" + "=" * 70)
print("每小时Loading码头容量统计")
print("=" * 70)

loading_stats = []
for hour in range(24):
    data = hourly_loading[hour]
    if data:
        stats = {
            '小时': f'{hour:02d}:00',
            '数据点': len(data),
            '中位数': np.median(data),
            '平均值': np.mean(data),
            '众数': Counter(data).most_common(1)[0][0] if data else 0,
            '最小值': min(data),
            '最大值': max(data)
        }
        loading_stats.append(stats)
        
        # 只打印工作时段（6-24点）
        if 6 <= hour < 24:
            print(f"{hour:02d}:00-{hour+1:02d}:00 | "
                  f"中位数: {stats['中位数']:.0f} | "
                  f"平均: {stats['平均值']:.1f} | "
                  f"众数: {stats['众数']:.0f} | "
                  f"范围: {stats['最小值']:.0f}-{stats['最大值']:.0f} | "
                  f"数据点: {stats['数据点']}")

print("\n" + "=" * 70)
print("每小时Reception码头容量统计")
print("=" * 70)

reception_stats = []
for hour in range(24):
    data = hourly_reception[hour]
    if data:
        stats = {
            '小时': f'{hour:02d}:00',
            '数据点': len(data),
            '中位数': np.median(data),
            '平均值': np.mean(data),
            '众数': Counter(data).most_common(1)[0][0] if data else 0,
            '最小值': min(data),
            '最大值': max(data)
        }
        reception_stats.append(stats)
        
        if 6 <= hour < 24:
            print(f"{hour:02d}:00-{hour+1:02d}:00 | "
                  f"中位数: {stats['中位数']:.0f} | "
                  f"平均: {stats['平均值']:.1f} | "
                  f"众数: {stats['众数']:.0f} | "
                  f"范围: {stats['最小值']:.0f}-{stats['最大值']:.0f} | "
                  f"数据点: {stats['数据点']}")

# 分析容量是否随时间变化
print("\n" + "=" * 70)
print("容量时变特性分析")
print("=" * 70)

# 工作时段（6:00-23:00）
work_hours = range(6, 24)
loading_medians = [np.median(hourly_loading[h]) if hourly_loading[h] else 0 for h in work_hours]
reception_medians = [np.median(hourly_reception[h]) if hourly_reception[h] else 0 for h in work_hours]

loading_min = min(loading_medians)
loading_max = max(loading_medians)
loading_range = loading_max - loading_min

reception_min = min(reception_medians)
reception_max = max(reception_medians)
reception_range = reception_max - reception_min

print(f"\nLoading码头容量:")
print(f"  最小值: {loading_min:.0f} 个码头（{[h for h in work_hours if np.median(hourly_loading[h]) == loading_min]}点）")
print(f"  最大值: {loading_max:.0f} 个码头（{[h for h in work_hours if np.median(hourly_loading[h]) == loading_max]}点）")
print(f"  变化幅度: {loading_range:.0f} 个码头 ({loading_range/loading_max*100:.1f}%)")

print(f"\nReception码头容量:")
print(f"  最小值: {reception_min:.0f} 个码头（{[h for h in work_hours if np.median(hourly_reception[h]) == reception_min]}点）")
print(f"  最大值: {reception_max:.0f} 个码头（{[h for h in work_hours if np.median(hourly_reception[h]) == reception_max]}点）")
print(f"  变化幅度: {reception_range:.0f} 个码头 ({reception_range/reception_max*100:.1f}%)")

# 判断是否需要时变建模
if loading_range > 2 or reception_range > 2:
    print("\n⚠️  容量存在明显的时变特性（变化>2个码头）")
    print("建议：在仿真中建模时变码头容量")
else:
    print("\n✓ 容量相对稳定，可以使用固定值")

# 推荐配置
print("\n" + "=" * 70)
print("推荐码头配置")
print("=" * 70)

# 方案1: 使用工作时段的中位数
loading_work_all = []
reception_work_all = []
for h in work_hours:
    loading_work_all.extend(hourly_loading[h])
    reception_work_all.extend(hourly_reception[h])

loading_overall_median = np.median(loading_work_all)
reception_overall_median = np.median(reception_work_all)

print("\n方案1: 使用工作时段整体中位数（简化模型）")
print(f"  总Loading: {loading_overall_median:.0f} 个码头")
print(f"  总Reception: {reception_overall_median:.0f} 个码头")
print(f"  按业务量分配（FG 70%, R&P 30%）:")
print(f"    - FG Loading: {int(loading_overall_median * 0.7)} 个")
print(f"    - R&P Loading: {int(loading_overall_median * 0.3)} 个")
print(f"    - FG Reception: {int(reception_overall_median * 0.7)} 个")
print(f"    - R&P Reception: {int(reception_overall_median * 0.3)} 个")

# 方案2: 使用峰值容量（保守）
print("\n方案2: 使用峰值容量（保守，能应对高峰）")
print(f"  总Loading峰值: {int(loading_max)} 个码头")
print(f"  总Reception峰值: {int(reception_max)} 个码头")
print(f"  按业务量分配:")
print(f"    - FG Loading: {int(loading_max * 0.7)} 个")
print(f"    - R&P Loading: {int(loading_max * 0.3)} 个")
print(f"    - FG Reception: {int(reception_max * 0.7)} 个")
print(f"    - R&P Reception: {int(reception_max * 0.3)} 个")

# 方案3: 时变配置
print("\n方案3: 时变码头配置（高级，最真实）")
print("  在仿真中根据小时动态调整码头数量")
print("  示例代码:")
print("  ```python")
print("  hourly_docks = {")
for h in [6, 9, 12, 15, 18, 21]:
    if hourly_loading[h]:
        print(f"      {h}: {int(np.median(hourly_loading[h]))},  # {h}:00点")
print("  }")
print("  ```")

# 可视化
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# Loading容量
hours_label = [f'{h:02d}:00' for h in work_hours]
ax1.plot(hours_label, loading_medians, 'o-', linewidth=2, markersize=8, label='中位数', color='#2E86AB')
ax1.fill_between(range(len(work_hours)), 
                  [min(hourly_loading[h]) if hourly_loading[h] else 0 for h in work_hours],
                  [max(hourly_loading[h]) if hourly_loading[h] else 0 for h in work_hours],
                  alpha=0.2, color='#2E86AB', label='范围')
ax1.axhline(y=loading_overall_median, color='red', linestyle='--', linewidth=2, label=f'整体中位数 ({loading_overall_median:.0f})')
ax1.set_xlabel('时间段', fontsize=12, fontweight='bold')
ax1.set_ylabel('Loading码头数量', fontsize=12, fontweight='bold')
ax1.set_title('Loading码头容量 - 按小时分布（48周数据）', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10)
ax1.set_xticks(range(len(hours_label)))
ax1.set_xticklabels(hours_label, rotation=45)

# Reception容量
ax2.plot(hours_label, reception_medians, 'o-', linewidth=2, markersize=8, label='中位数', color='#A23B72')
ax2.fill_between(range(len(work_hours)), 
                  [min(hourly_reception[h]) if hourly_reception[h] else 0 for h in work_hours],
                  [max(hourly_reception[h]) if hourly_reception[h] else 0 for h in work_hours],
                  alpha=0.2, color='#A23B72', label='范围')
ax2.axhline(y=reception_overall_median, color='red', linestyle='--', linewidth=2, label=f'整体中位数 ({reception_overall_median:.0f})')
ax2.set_xlabel('时间段', fontsize=12, fontweight='bold')
ax2.set_ylabel('Reception码头数量', fontsize=12, fontweight='bold')
ax2.set_title('Reception码头容量 - 按小时分布（48周数据）', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=10)
ax2.set_xticks(range(len(hours_label)))
ax2.set_xticklabels(hours_label, rotation=45)

plt.tight_layout()
plt.savefig('dock_capacity_by_hour.png', dpi=300, bbox_inches='tight')
print(f"\n✓ 可视化图表已保存: dock_capacity_by_hour.png")

# 保存详细数据
with open('dock_capacity_hourly_analysis.txt', 'w', encoding='utf-8') as f:
    f.write("按时间段的码头容量分析（48周数据）\n")
    f.write("=" * 70 + "\n\n")
    
    f.write("Loading码头容量（按小时）:\n")
    for h in work_hours:
        if hourly_loading[h]:
            f.write(f"  {h:02d}:00 - 中位数: {np.median(hourly_loading[h]):.0f}, ")
            f.write(f"众数: {Counter(hourly_loading[h]).most_common(1)[0][0]:.0f}\n")
    
    f.write("\nReception码头容量（按小时）:\n")
    for h in work_hours:
        if hourly_reception[h]:
            f.write(f"  {h:02d}:00 - 中位数: {np.median(hourly_reception[h]):.0f}, ")
            f.write(f"众数: {Counter(hourly_reception[h]).most_common(1)[0][0]:.0f}\n")
    
    f.write(f"\n建议配置:\n")
    f.write(f"  - 简化模型: Loading={loading_overall_median:.0f}, Reception={reception_overall_median:.0f}\n")
    f.write(f"  - 保守配置: Loading={loading_max:.0f}, Reception={reception_max:.0f}\n")
    f.write(f"  - 时变特性: 变化幅度 Loading={loading_range:.0f}, Reception={reception_range:.0f}\n")

print(f"✓ 详细数据已保存: dock_capacity_hourly_analysis.txt")

print("\n" + "=" * 70)
print("✓ 完成")
print("=" * 70)
