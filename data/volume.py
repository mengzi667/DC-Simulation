import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

file_path = 'data\Total Shipments 2025.xlsx'
inbound_df = pd.read_excel(file_path, sheet_name='Inbound Shipments 2025')
outbound_df = pd.read_excel(file_path, sheet_name='Outbound Shipments 2025')

inbound_df['Date Hour appointement'] = pd.to_datetime(inbound_df['Date Hour appointement'])
outbound_df['Date Hour appointement'] = pd.to_datetime(outbound_df['Date Hour appointement'])

inbound_nov = inbound_df[(inbound_df['Date Hour appointement'].dt.year == 2025) & 
                         (inbound_df['Date Hour appointement'].dt.month == 11)]
outbound_nov = outbound_df[(outbound_df['Date Hour appointement'].dt.year == 2025) & 
                           (outbound_df['Date Hour appointement'].dt.month == 11)]

def daily_statistics(df, category):
    df_filtered = df[df['Category'] == category].copy()
    
    df_filtered['Date'] = df_filtered['Date Hour appointement'].dt.date
    
    daily_stats = df_filtered.groupby('Date').agg({
        'Date Hour appointement': 'count',
        'Total pal': 'sum'
    }).reset_index()
    
    daily_stats.columns = ['Date', 'Order Amount', 'Total Pallet']
    
    return daily_stats

def plot_dual_axis(data, title, category, shipment_type):
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    x = range(len(data))
    x_labels = [str(date) for date in data['Date']]
    
    color1 = 'steelblue'
    ax1.bar(x, data['Total Pallet'], color=color1, alpha=0.7, label='Total Pallet')
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Total Pallet', color=color1, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(x_labels, rotation=45, ha='right')
    ax1.grid(True, alpha=0.3)
    
    ax2 = ax1.twinx()
    color2 = 'orangered'
    ax2.plot(x, data['Order Amount'], color=color2, marker='o', linewidth=2, 
             markersize=6, label='Order Amount')
    ax2.set_ylabel('Order Amount', color=color2, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color2)
    
    plt.title(f'{category} - {shipment_type} - November 2025 Daily Statistics', 
              fontsize=14, fontweight='bold')
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(f'{category}_{shipment_type}_November_2025.png', dpi=300, bbox_inches='tight')
    plt.show()

print("Generating statistics for FG Inbound...")
fg_inbound_stats = daily_statistics(inbound_nov, 'FG')
print(f"Total records: {fg_inbound_stats['Order Amount'].sum()}")
print(f"Total pallets: {fg_inbound_stats['Total Pallet'].sum()}")
print()

print("Generating statistics for FG Outbound...")
fg_outbound_stats = daily_statistics(outbound_nov, 'FG')
print(f"Total records: {fg_outbound_stats['Order Amount'].sum()}")
print(f"Total pallets: {fg_outbound_stats['Total Pallet'].sum()}")
print()

print("Generating statistics for R&P Inbound...")
rp_inbound_stats = daily_statistics(inbound_nov, 'R&P')
print(f"Total records: {rp_inbound_stats['Order Amount'].sum()}")
print(f"Total pallets: {rp_inbound_stats['Total Pallet'].sum()}")
print()

print("Generating statistics for R&P Outbound...")
rp_outbound_stats = daily_statistics(outbound_nov, 'R&P')
print(f"Total records: {rp_outbound_stats['Order Amount'].sum()}")
print(f"Total pallets: {rp_outbound_stats['Total Pallet'].sum()}")
print()

print("Plotting charts...")
plot_dual_axis(fg_inbound_stats, 'FG Inbound November 2025', 'FG', 'Inbound')
plot_dual_axis(fg_outbound_stats, 'FG Outbound November 2025', 'FG', 'Outbound')
plot_dual_axis(rp_inbound_stats, 'R&P Inbound November 2025', 'R&P', 'Inbound')
plot_dual_axis(rp_outbound_stats, 'R&P Outbound November 2025', 'R&P', 'Outbound')

print("Saving data to Excel...")
with pd.ExcelWriter('Volume_Analysis_Data_November_2025.xlsx', engine='openpyxl') as writer:
    fg_inbound_stats.to_excel(writer, sheet_name='FG_Inbound', index=False)
    fg_outbound_stats.to_excel(writer, sheet_name='FG_Outbound', index=False)
    rp_inbound_stats.to_excel(writer, sheet_name='R&P_Inbound', index=False)
    rp_outbound_stats.to_excel(writer, sheet_name='R&P_Outbound', index=False)

print("All charts have been generated and saved!")
print("Data has been saved to Volume_Analysis_Data_November_2025.xlsx")
