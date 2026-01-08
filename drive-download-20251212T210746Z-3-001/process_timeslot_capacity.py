import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Read Excel file
file_path = 'Timeslot Capacity (1).xlsx'
df = pd.read_excel(file_path)

print("="*60)
print("Step 1: Read Raw Data")
print("="*60)
print(f"Original data shape: {df.shape}")

# Step 2: Data Cleaning
print("\n" + "="*60)
print("Step 2: Data Cleaning")
print("="*60)

rows_before = len(df)
af_col_index = 31

# Identify completely empty columns
empty_cols = [i for i in range(af_col_index) if df.iloc[:, i].isna().all()]
print(f"Completely empty columns: {empty_cols}")

# Check columns for null values (exclude empty columns and D column index 3)
cols_to_check = [i for i in range(af_col_index) if i not in empty_cols and i != 3]
print(f"Number of columns to check: {len(cols_to_check)}")

# Remove rows with null values
mask = df.iloc[:, cols_to_check].isna().any(axis=1)
df = df[~mask]
print(f"Rows removed: {rows_before - len(df)}")
print(f"Remaining rows: {len(df)}")

# Step 3: Rename Columns
print("\n" + "="*60)
print("Step 3: Rename Columns")
print("="*60)

new_columns = df.columns.tolist()
new_columns[3] = 'type'
new_columns[4] = 'Event'
new_columns[5] = 'slot_type'

# Rename H to AD columns as 1h to 23h
for i in range(7, 30):
    new_columns[i] = f'{i - 6}h'

# Rename AE column to total
new_columns[30] = 'total'

df.columns = new_columns
print(f"Renaming completed")

# Save intermediate results
df.to_excel('processed_data_step1.xlsx', index=False)
print("Intermediate results saved: processed_data_step1.xlsx")

# Get hour columns
hour_columns = [col for col in df.columns if col.endswith('h') and col[:-1].isdigit()]
hour_columns.sort(key=lambda x: int(x[:-1]))
calc_columns = hour_columns + ['total']

# Process dates
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df['Date'] = df['Date'].apply(lambda x: x.replace(month=x.day, day=x.month) if pd.notna(x) and x.day <= 12 else x)
min_date = df['Date'].min()
max_date = df['Date'].max()
date_diff = (max_date - min_date).days if pd.notna(min_date) and pd.notna(max_date) else 1

print("\n" + "="*60)
print("Date Information")
print("="*60)
print(f"Earliest date: {min_date}")
print(f"Latest date: {max_date}")
print(f"Date difference: {date_diff} days")

# Results storage
results = {}

# Basic calculation (without type filter)
print("\n" + "="*60)
print("Basic Calculation (without type filter)")
print("="*60)

# Booking taken sum
print("\n1. Booking taken grouped by Condition")
print("-" * 60)
booking_taken = df[df['slot_type'] == 'Booking taken']

for group_name in ['Loading', 'Reception']:
    group_data = booking_taken[booking_taken['Condition'] == group_name]
    if len(group_data) > 0:
        sum_result = group_data[calc_columns].sum()
        results[f'Booking_taken_{group_name}_sum'] = sum_result
        print(f"\n{group_name}:")
        print(sum_result)
    else:
        print(f"\n{group_name}: No data")

# Available Capacity sum
print("\n\n2. Available Capacity grouped by Condition")
print("-" * 60)
available_capacity = df[df['slot_type'] == 'Available Capacity']

for group_name in ['Loading', 'Reception']:
    group_data = available_capacity[available_capacity['Condition'] == group_name]
    if len(group_data) > 0:
        sum_result = group_data[calc_columns].sum()
        results[f'Available_Capacity_{group_name}_sum'] = sum_result
        print(f"\n{group_name}:")
        print(sum_result)
    else:
        print(f"\n{group_name}: No data")

# Calculate utilization
print("\n\n3. Calculate Utilization (Booking / (Booking + Available))")
print("-" * 60)

for group_name in ['Loading', 'Reception']:
    booking_key = f'Booking_taken_{group_name}_sum'
    capacity_key = f'Available_Capacity_{group_name}_sum'
    
    if booking_key in results and capacity_key in results:
        booking = results[booking_key]
        capacity = results[capacity_key]
        total = booking + capacity
        
        # 计算每个时间段的利用率
        utilization = booking.astype(float) / total.replace(0, np.nan)
        utilization_pct = utilization * 100
        
        # 计算total的真实利用率（不是加和）
        total_booking = booking['total']
        total_capacity = capacity['total']
        if total_booking + total_capacity > 0:
            utilization_pct.loc['total'] = (total_booking / (total_booking + total_capacity)) * 100
        
        results[f'{group_name}_utilization'] = utilization
        results[f'{group_name}_utilization_pct'] = utilization_pct
        
        print(f"\n{group_name} (%):")
        print(utilization_pct)

# Add type filter (FG and R&P)
print("\n\n" + "="*60)
print("Add type filter (FG and R&P)")
print("="*60)

for type_value in ['FG', 'R&P']:
    print(f"\n{'='*60}")
    print(f"Type = {type_value}")
    print(f"{'='*60}")
    
    type_filtered = df[df['type'] == type_value]
    
    if len(type_filtered) == 0:
        print(f"Warning: No data")
        continue
    
    print(f"Data rows: {len(type_filtered)}")
    
    # Booking taken
    print(f"\n1. Booking taken grouped by Condition")
    print("-" * 60)
    booking_taken_type = type_filtered[type_filtered['slot_type'] == 'Booking taken']
    
    for group_name in ['Loading', 'Reception']:
        group_data = booking_taken_type[booking_taken_type['Condition'] == group_name]
        if len(group_data) > 0:
            sum_result = group_data[calc_columns].sum()
            results[f'{type_value}_Booking_taken_{group_name}_sum'] = sum_result
            print(f"\n{group_name}:")
            print(sum_result)
        else:
            print(f"\n{group_name}: No data")
    
    # Available Capacity
    print(f"\n\n2. Available Capacity grouped by Condition")
    print("-" * 60)
    available_capacity_type = type_filtered[type_filtered['slot_type'] == 'Available Capacity']
    
    for group_name in ['Loading', 'Reception']:
        group_data = available_capacity_type[available_capacity_type['Condition'] == group_name]
        if len(group_data) > 0:
            sum_result = group_data[calc_columns].sum()
            results[f'{type_value}_Available_Capacity_{group_name}_sum'] = sum_result
            print(f"\n{group_name}:")
            print(sum_result)
        else:
            print(f"\n{group_name}: No data")
    
    # Utilization
    print(f"\n\n3. Calculate Utilization (Booking / (Booking + Available))")
    print("-" * 60)
    
    for group_name in ['Loading', 'Reception']:
        booking_key = f'{type_value}_Booking_taken_{group_name}_sum'
        capacity_key = f'{type_value}_Available_Capacity_{group_name}_sum'
        
        if booking_key in results and capacity_key in results:
            booking = results[booking_key]
            capacity = results[capacity_key]
            total = booking + capacity
            
            # 计算每个时间段的利用率
            utilization = booking.astype(float) / total.replace(0, np.nan)
            utilization_pct = utilization * 100
            
            # 计算total的真实利用率（不是加和）
            total_booking = booking['total']
            total_capacity = capacity['total']
            if total_booking + total_capacity > 0:
                utilization_pct.loc['total'] = (total_booking / (total_booking + total_capacity)) * 100
            
            results[f'{type_value}_{group_name}_utilization'] = utilization
            results[f'{type_value}_{group_name}_utilization_pct'] = utilization_pct
            
            print(f"\n{group_name} (%):")
            print(utilization_pct)

# Save results
print("\n\n" + "="*60)
print("Save Results")
print("="*60)

if results:
    results_df = pd.DataFrame(results)
    results_df.to_excel('analysis_results.xlsx', index=True)
    print(f"✓ Analysis results saved: analysis_results.xlsx")
    print(f"  Number of statistics: {len(results)}")
else:
    print("Warning: No results")

print("\n✓ Cleaned data saved: processed_data_step1.xlsx")

# Visualization
print("\n" + "="*60)
print("Generate Visualizations")
print("="*60)

# 1. Basic utilization comparison chart (Loading vs Reception)
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Timeslot Capacity Analysis', fontsize=16, fontweight='bold')

# 1.1 Booking taken comparison
ax1 = axes[0, 0]
if 'Booking_taken_Loading_sum' in results and 'Booking_taken_Reception_sum' in results:
    loading_booking = results['Booking_taken_Loading_sum'][:-1]  # 排除total
    reception_booking = results['Booking_taken_Reception_sum'][:-1]
    x = range(len(loading_booking))
    width = 0.35
    ax1.bar([i - width/2 for i in x], loading_booking, width, label='Loading', alpha=0.8)
    ax1.bar([i + width/2 for i in x], reception_booking, width, label='Reception', alpha=0.8)
    ax1.set_xlabel('Time Slot', fontsize=12)
    ax1.set_ylabel('Booking Count', fontsize=12)
    ax1.set_title('Booking Taken Distribution Comparison', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(loading_booking.index, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)

# 1.2 Available Capacity comparison
ax2 = axes[0, 1]
if 'Available_Capacity_Loading_sum' in results and 'Available_Capacity_Reception_sum' in results:
    loading_capacity = results['Available_Capacity_Loading_sum'][:-1]
    reception_capacity = results['Available_Capacity_Reception_sum'][:-1]
    x = range(len(loading_capacity))
    ax2.bar([i - width/2 for i in x], loading_capacity, width, label='Loading', alpha=0.8)
    ax2.bar([i + width/2 for i in x], reception_capacity, width, label='Reception', alpha=0.8)
    ax2.set_xlabel('Time Slot', fontsize=12)
    ax2.set_ylabel('Available Count', fontsize=12)
    ax2.set_title('Available Capacity Distribution Comparison', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(loading_capacity.index, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

# 1.3 Utilization comparison (line chart)
ax3 = axes[1, 0]
if 'Loading_utilization_pct' in results and 'Reception_utilization_pct' in results:
    loading_util = results['Loading_utilization_pct'][:-1]
    reception_util = results['Reception_utilization_pct'][:-1]
    x = range(len(loading_util))
    ax3.plot(x, loading_util, marker='o', linewidth=2, markersize=6, label='Loading', alpha=0.8)
    ax3.plot(x, reception_util, marker='s', linewidth=2, markersize=6, label='Reception', alpha=0.8)
    ax3.set_xlabel('Time Slot', fontsize=12)
    ax3.set_ylabel('Utilization (%)', fontsize=12)
    ax3.set_title('Capacity Utilization Trend', fontsize=14, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(loading_util.index, rotation=45, ha='right')
    ax3.legend()
    ax3.grid(alpha=0.3)
    ax3.set_ylim(0, 100)

# 1.4 Overall utilization comparison (bar chart)
ax4 = axes[1, 1]
categories = []
values = []
if 'Loading_utilization_pct' in results:
    categories.append('Loading\nOverall')
    values.append(results['Loading_utilization_pct']['total'])
if 'Reception_utilization_pct' in results:
    categories.append('Reception\nOverall')
    values.append(results['Reception_utilization_pct']['total'])
if 'FG_Loading_utilization_pct' in results:
    categories.append('FG\nLoading')
    values.append(results['FG_Loading_utilization_pct']['total'])
if 'R&P_Loading_utilization_pct' in results:
    categories.append('R&P\nLoading')
    values.append(results['R&P_Loading_utilization_pct']['total'])

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
bars = ax4.bar(categories, values, color=colors[:len(categories)], alpha=0.8, edgecolor='black')
ax4.set_ylabel('Utilization (%)', fontsize=12)
ax4.set_title('Overall Utilization Comparison', fontsize=14, fontweight='bold')
ax4.set_ylim(0, 100)
ax4.grid(axis='y', alpha=0.3)
# 在柱子上标注数值
for bar, val in zip(bars, values):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height,
             f'{val:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

plt.tight_layout()
plt.savefig('capacity_analysis.png', dpi=300, bbox_inches='tight')
print("✓ Chart saved: capacity_analysis.png")

# 2. FG vs R&P comparison chart
if 'FG_Loading_utilization_pct' in results or 'R&P_Loading_utilization_pct' in results:
    fig2, axes2 = plt.subplots(1, 2, figsize=(16, 6))
    fig2.suptitle('FG vs R&P Capacity Comparison (Loading)', fontsize=16, fontweight='bold')
    
    # 2.1 Booking comparison
    ax_left = axes2[0]
    if 'FG_Booking_taken_Loading_sum' in results and 'R&P_Booking_taken_Loading_sum' in results:
        fg_booking = results['FG_Booking_taken_Loading_sum'][:-1]
        rp_booking = results['R&P_Booking_taken_Loading_sum'][:-1]
        x = range(len(fg_booking))
        width = 0.35
        ax_left.bar([i - width/2 for i in x], fg_booking, width, label='FG', alpha=0.8, color='#2ca02c')
        ax_left.bar([i + width/2 for i in x], rp_booking, width, label='R&P', alpha=0.8, color='#d62728')
        ax_left.set_xlabel('Time Slot', fontsize=12)
        ax_left.set_ylabel('Booking Count', fontsize=12)
        ax_left.set_title('Booking Taken Comparison', fontsize=14, fontweight='bold')
        ax_left.set_xticks(x)
        ax_left.set_xticklabels(fg_booking.index, rotation=45, ha='right')
        ax_left.legend()
        ax_left.grid(axis='y', alpha=0.3)
    
    # 2.2 Utilization comparison
    ax_right = axes2[1]
    if 'FG_Loading_utilization_pct' in results and 'R&P_Loading_utilization_pct' in results:
        fg_util = results['FG_Loading_utilization_pct'][:-1]
        rp_util = results['R&P_Loading_utilization_pct'][:-1]
        x = range(len(fg_util))
        ax_right.plot(x, fg_util, marker='o', linewidth=2, markersize=6, label='FG', alpha=0.8, color='#2ca02c')
        ax_right.plot(x, rp_util, marker='s', linewidth=2, markersize=6, label='R&P', alpha=0.8, color='#d62728')
        ax_right.set_xlabel('Time Slot', fontsize=12)
        ax_right.set_ylabel('Utilization (%)', fontsize=12)
        ax_right.set_title('Utilization Trend Comparison', fontsize=14, fontweight='bold')
        ax_right.set_xticks(x)
        ax_right.set_xticklabels(fg_util.index, rotation=45, ha='right')
        ax_right.legend()
        ax_right.grid(alpha=0.3)
        ax_right.set_ylim(0, 105)
    
    plt.tight_layout()
    plt.savefig('fg_vs_rp_analysis.png', dpi=300, bbox_inches='tight')
    print("✓ Chart saved: fg_vs_rp_analysis.png")

plt.close('all')

print("\n" + "="*60)
print("Processing Complete")
print("="*60)
