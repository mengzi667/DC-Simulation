import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os
import warnings
warnings.filterwarnings('ignore')

# Set default font
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False

# File path
file_path = 'data\\Total Shipments 2025.xlsx'
inbound_df = pd.read_excel(file_path, sheet_name='Inbound Shipments 2025')
outbound_df = pd.read_excel(file_path, sheet_name='Outbound Shipments 2025')

# Parse dates
inbound_df['Date Hour appointement'] = pd.to_datetime(inbound_df['Date Hour appointement'])
outbound_df['Date Hour appointement'] = pd.to_datetime(outbound_df['Date Hour appointement'])

# Filter 2025 data
inbound_year = inbound_df[inbound_df['Date Hour appointement'].dt.year == 2025]
outbound_year = outbound_df[outbound_df['Date Hour appointement'].dt.year == 2025]

print(f"Inbound records: {len(inbound_year)}")
print(f"Outbound records: {len(outbound_year)}")

# Create output directory structure
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, 'Volume_Yearly_Analysis')
monthly_dir = os.path.join(output_dir, 'Monthly_Details')
trends_dir = os.path.join(output_dir, 'Yearly_Trends')
boxplot_dir = os.path.join(output_dir, 'Yearly_Boxplots')

os.makedirs(monthly_dir, exist_ok=True)
os.makedirs(trends_dir, exist_ok=True)
os.makedirs(boxplot_dir, exist_ok=True)

# Month names
month_names = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December'
}

def daily_statistics(df, category):
    """Calculate daily statistics for a category"""
    df_filtered = df[df['Category'] == category].copy()
    
    df_filtered['Date'] = df_filtered['Date Hour appointement'].dt.date
    
    daily_stats = df_filtered.groupby('Date').agg({
        'Date Hour appointement': 'count',
        'Total pal': 'sum'
    }).reset_index()
    
    daily_stats.columns = ['Date', 'Order Amount', 'Total Pallet']
    daily_stats['Avg Pallet per Order'] = daily_stats['Total Pallet'] / daily_stats['Order Amount']
    
    return daily_stats

def plot_monthly_detail(data, category, shipment_type, month_name):
    """Plot monthly detail chart with dual axis"""
    fig, ax1 = plt.subplots(figsize=(14, 6))
    
    x = range(len(data))
    x_labels = [str(date.day) for date in data['Date']]
    
    color1 = 'steelblue'
    ax1.bar(x, data['Total Pallet'], color=color1, alpha=0.7, label='Total Pallet')
    ax1.set_xlabel('Day of Month', fontsize=12)
    ax1.set_ylabel('Total Pallet', color=color1, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(x_labels, rotation=0)
    ax1.grid(True, alpha=0.3, axis='y')
    
    ax2 = ax1.twinx()
    color2 = 'orangered'
    ax2.plot(x, data['Order Amount'], color=color2, marker='o', linewidth=2, 
             markersize=5, label='Order Amount')
    ax2.set_ylabel('Order Amount', color=color2, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color2)
    
    plt.title(f'{category} - {shipment_type} - {month_name} 2025 Daily Statistics', 
              fontsize=14, fontweight='bold')
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    filename = f'{category}_{shipment_type}_{month_name}_2025.png'
    plt.savefig(os.path.join(monthly_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()

def plot_yearly_trend(monthly_data, category, shipment_type):
    """Plot yearly monthly trend chart"""
    fig, ax1 = plt.subplots(figsize=(14, 6))
    
    x = range(len(monthly_data))
    x_labels = [month[:3] for month in monthly_data['Month']]
    
    color1 = 'steelblue'
    ax1.bar(x, monthly_data['Total Pallet'], color=color1, alpha=0.7, label='Total Pallet')
    ax1.set_xlabel('Month', fontsize=12)
    ax1.set_ylabel('Total Pallet', color=color1, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(x_labels, rotation=0)
    ax1.grid(True, alpha=0.3, axis='y')
    
    ax2 = ax1.twinx()
    color2 = 'orangered'
    ax2.plot(x, monthly_data['Total Orders'], color=color2, marker='o', linewidth=2, 
             markersize=7, label='Total Orders')
    ax2.set_ylabel('Total Orders', color=color2, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color2)
    
    plt.title(f'{category} - {shipment_type} - 2025 Monthly Trend', 
              fontsize=14, fontweight='bold')
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    filename = f'{category}_{shipment_type}_Yearly_Trend_2025.png'
    plt.savefig(os.path.join(trends_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()

def plot_boxplot(data_dict, metric_name, ylabel, color='lightblue'):
    """Plot boxplot for a specific metric"""
    categories = ['FG_Inbound', 'FG_Outbound', 'R&P_Inbound', 'R&P_Outbound']
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for idx, cat in enumerate(categories):
        ax = axes[idx]
        data_to_plot = []
        labels = []
        
        for month_data in data_dict[cat]:
            if len(month_data['values']) > 0:
                data_to_plot.append(month_data['values'])
                labels.append(month_data['month'][:3])
        
        if len(data_to_plot) == 0:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', fontsize=14)
            ax.set_title(cat.replace('_', ' '), fontsize=12, fontweight='bold')
            continue
        
        bp = ax.boxplot(data_to_plot, labels=labels, patch_artist=True,
                        showmeans=True, meanline=True)
        
        for patch in bp['boxes']:
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        for whisker in bp['whiskers']:
            whisker.set(color='gray', linewidth=1.5, linestyle=':')
        
        for cap in bp['caps']:
            cap.set(color='gray', linewidth=1.5)
        
        for median in bp['medians']:
            median.set(color='red', linewidth=2)
        
        for mean in bp['means']:
            mean.set(color='blue', linewidth=2)
        
        ax.set_xlabel('Month', fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(cat.replace('_', ' '), fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        ax.tick_params(axis='x', rotation=45)
    
    # Add overall legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='red', linewidth=2, label='Median'),
        Line2D([0], [0], color='blue', linewidth=2, label='Mean')
    ]
    fig.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    plt.suptitle(f'2025 Yearly {metric_name} Distribution by Month', 
                 fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    filename = f'Yearly_{metric_name.replace(" ", "_")}_Boxplot_2025.png'
    plt.savefig(os.path.join(boxplot_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()

# Storage for yearly data
yearly_data = {
    'FG_Inbound': {'months': [], 'daily_data': []},
    'FG_Outbound': {'months': [], 'daily_data': []},
    'R&P_Inbound': {'months': [], 'daily_data': []},
    'R&P_Outbound': {'months': [], 'daily_data': []}
}

boxplot_data = {
    'total_pallet': {'FG_Inbound': [], 'FG_Outbound': [], 'R&P_Inbound': [], 'R&P_Outbound': []},
    'order_amount': {'FG_Inbound': [], 'FG_Outbound': [], 'R&P_Inbound': [], 'R&P_Outbound': []},
    'avg_pallet_per_order': {'FG_Inbound': [], 'FG_Outbound': [], 'R&P_Inbound': [], 'R&P_Outbound': []}
}

all_monthly_details = []

print("\n=== Processing monthly data ===")

# Process each month
for month_num in range(1, 13):
    month_name = month_names[month_num]
    print(f"\nProcessing {month_name}...")
    
    # Filter month data
    inbound_month = inbound_year[inbound_year['Date Hour appointement'].dt.month == month_num]
    outbound_month = outbound_year[outbound_year['Date Hour appointement'].dt.month == month_num]
    
    if len(inbound_month) == 0 and len(outbound_month) == 0:
        print(f"  No data for {month_name}, skipping...")
        continue
    
    # Calculate statistics for each category
    categories = [
        ('FG', 'Inbound', inbound_month, 'FG_Inbound'),
        ('FG', 'Outbound', outbound_month, 'FG_Outbound'),
        ('R&P', 'Inbound', inbound_month, 'R&P_Inbound'),
        ('R&P', 'Outbound', outbound_month, 'R&P_Outbound')
    ]
    
    for cat_name, ship_type, month_df, key in categories:
        stats = daily_statistics(month_df, cat_name)
        
        if len(stats) > 0:
            # Generate monthly detail chart
            plot_monthly_detail(stats, cat_name, ship_type, month_name)
            
            # Store for yearly trend
            yearly_data[key]['daily_data'].append(stats)
            
            # Calculate monthly summary
            monthly_summary = {
                'Month': month_name,
                'Total Orders': stats['Order Amount'].sum(),
                'Total Pallet': stats['Total Pallet'].sum(),
                'Avg Daily Orders': stats['Order Amount'].mean(),
                'Avg Daily Pallet': stats['Total Pallet'].mean(),
                'Avg Pallet per Order': stats['Total Pallet'].sum() / stats['Order Amount'].sum() if stats['Order Amount'].sum() > 0 else 0,
                'Max Daily Orders': stats['Order Amount'].max(),
                'Max Daily Pallet': stats['Total Pallet'].max(),
                'Working Days': len(stats)
            }
            yearly_data[key]['months'].append(monthly_summary)
            
            # Store for boxplots
            boxplot_data['total_pallet'][key].append({
                'month': month_name,
                'values': stats['Total Pallet'].values
            })
            boxplot_data['order_amount'][key].append({
                'month': month_name,
                'values': stats['Order Amount'].values
            })
            boxplot_data['avg_pallet_per_order'][key].append({
                'month': month_name,
                'values': stats['Avg Pallet per Order'].values
            })
            
            # Store for overall summary
            all_monthly_details.append({
                'Category': cat_name,
                'Type': ship_type,
                **monthly_summary
            })
    
    print(f"  Generated charts for {month_name}")

print("\n=== Generating yearly trend charts ===")

# Generate yearly trend charts
for key in ['FG_Inbound', 'FG_Outbound', 'R&P_Inbound', 'R&P_Outbound']:
    if len(yearly_data[key]['months']) > 0:
        monthly_df = pd.DataFrame(yearly_data[key]['months'])
        cat, ship = key.split('_')
        plot_yearly_trend(monthly_df, cat, ship)
        print(f"  Generated trend chart for {key}")

print("\n=== Generating yearly boxplots ===")

# Generate boxplots
plot_boxplot(boxplot_data['total_pallet'], 'Total Pallet', 'Total Pallet', color='lightblue')
print("  Generated Total Pallet boxplot")

plot_boxplot(boxplot_data['order_amount'], 'Order Amount', 'Order Amount', color='lightgreen')
print("  Generated Order Amount boxplot")

plot_boxplot(boxplot_data['avg_pallet_per_order'], 'Avg Pallet per Order', 'Avg Pallet per Order', color='lightyellow')
print("  Generated Avg Pallet per Order boxplot")

print("\n=== Saving data to Excel ===")

# Create Excel summary
with pd.ExcelWriter(os.path.join(output_dir, 'Yearly_Summary_2025.xlsx'), engine='openpyxl') as writer:
    # Sheet 1: Overall monthly summary
    if len(all_monthly_details) > 0:
        summary_df = pd.DataFrame(all_monthly_details)
        summary_df.to_excel(writer, sheet_name='Monthly_Summary', index=False)
    
    # Sheet 2-13: Monthly details for each month
    for month_num in range(1, 13):
        month_name = month_names[month_num]
        month_details = []
        
        for key in ['FG_Inbound', 'FG_Outbound', 'R&P_Inbound', 'R&P_Outbound']:
            for daily_data in yearly_data[key]['daily_data']:
                if len(daily_data) > 0 and daily_data['Date'].iloc[0].month == month_num:
                    cat, ship = key.split('_')
                    daily_data_copy = daily_data.copy()
                    daily_data_copy.insert(0, 'Type', ship)
                    daily_data_copy.insert(0, 'Category', cat)
                    month_details.append(daily_data_copy)
        
        if len(month_details) > 0:
            month_df = pd.concat(month_details, ignore_index=True)
            sheet_name = f'{month_num:02d}_{month_name[:3]}'
            month_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    # Sheet: Yearly statistics
    yearly_stats = []
    for key in ['FG_Inbound', 'FG_Outbound', 'R&P_Inbound', 'R&P_Outbound']:
        if len(yearly_data[key]['months']) > 0:
            monthly_df = pd.DataFrame(yearly_data[key]['months'])
            cat, ship = key.split('_')
            yearly_stats.append({
                'Category': cat,
                'Type': ship,
                'Total_Orders_Year': monthly_df['Total Orders'].sum(),
                'Total_Pallet_Year': monthly_df['Total Pallet'].sum(),
                'Avg_Monthly_Orders': monthly_df['Total Orders'].mean(),
                'Avg_Monthly_Pallet': monthly_df['Total Pallet'].mean(),
                'Max_Monthly_Orders': monthly_df['Total Orders'].max(),
                'Max_Monthly_Pallet': monthly_df['Total Pallet'].max(),
                'Total_Working_Days': monthly_df['Working Days'].sum(),
                'Avg_Pallet_per_Order_Year': monthly_df['Total Pallet'].sum() / monthly_df['Total Orders'].sum() if monthly_df['Total Orders'].sum() > 0 else 0
            })
    
    if len(yearly_stats) > 0:
        yearly_stats_df = pd.DataFrame(yearly_stats)
        yearly_stats_df.to_excel(writer, sheet_name='Yearly_Statistics', index=False)

print(f"Summary data saved to Yearly_Summary_2025.xlsx")

print("\n" + "="*60)
print("All analysis complete!")
print(f"Monthly detail charts: {len([f for f in os.listdir(monthly_dir) if f.endswith('.png')])}")
print(f"Yearly trend charts: {len([f for f in os.listdir(trends_dir) if f.endswith('.png')])}")
print(f"Boxplot charts: {len([f for f in os.listdir(boxplot_dir) if f.endswith('.png')])}")
print(f"Output directory: {output_dir}")
print("="*60)
