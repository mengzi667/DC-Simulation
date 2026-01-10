import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

file_path = 'data\KPI sheet 2025.xlsx'

df = pd.read_excel(file_path, sheet_name='Hours & volumes per subgroup', header=None)

months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def extract_monthly_data(df, category):
    hours_data = None
    inbound_data = None
    outbound_data = None
    
    if category == 'R&P':
        for idx, row in df.iterrows():
            if row[0] == 'R&P' and row[1] == 'Actual':
                hours_data = row[2:14].values
                break
        
        for idx, row in df.iterrows():
            if row[0] == 'R&P - pallets - inbound' and row[1] == 'Actual':
                inbound_data = row[2:14].values
            elif row[0] == 'R&P - pallets - outbound' and row[1] == 'Actual':
                outbound_data = row[2:14].values
                
    elif category == 'FG':
        for idx, row in df.iterrows():
            if row[0] == 'FG' and row[1] == 'Actual':
                hours_data = row[2:14].values
                break
        
        for idx, row in df.iterrows():
            if row[0] == 'FG - pallets - inbound' and row[1] == 'Actual':
                inbound_data = row[2:14].values
            elif row[0] == 'FG - pallets - outbound' and row[1] == 'Actual':
                outbound_data = row[2:14].values
    
    hours_data = pd.to_numeric(hours_data, errors='coerce')
    inbound_data = pd.to_numeric(inbound_data, errors='coerce')
    outbound_data = pd.to_numeric(outbound_data, errors='coerce')
    pallets_data = inbound_data + outbound_data
    
    efficiency = pallets_data / hours_data
    
    result_df = pd.DataFrame({
        'Month': months,
        'Hours': hours_data,
        'Pallets': pallets_data,
        'Efficiency': efficiency
    })
    
    return result_df

def plot_productivity(data, category):
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    x = range(len(data))
    x_labels = data['Month'].tolist()
    
    color1 = 'steelblue'
    ax1.bar(x, data['Pallets'], color=color1, alpha=0.7, label='Total Pallet')
    ax1.set_xlabel('Month', fontsize=12)
    ax1.set_ylabel('Total Pallet', color=color1, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(x_labels, rotation=45, ha='right')
    ax1.grid(True, alpha=0.3)
    
    ax2 = ax1.twinx()
    color2 = 'orangered'
    ax2.plot(x, data['Efficiency'], color=color2, marker='o', linewidth=2, 
             markersize=6, label='Efficiency (Pallets/Hour)')
    ax2.set_ylabel('Efficiency (Pallets/Hour)', color=color2, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color2)
    
    plt.title(f'{category} - Monthly Productivity Analysis 2025', 
              fontsize=14, fontweight='bold')
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(f'{category}_Monthly_Productivity_2025.png', dpi=300, bbox_inches='tight')
    plt.show()

print("Extracting R&P data...")
rp_data = extract_monthly_data(df, 'R&P')
print(rp_data)
print()

print("Extracting FG data...")
fg_data = extract_monthly_data(df, 'FG')
print(fg_data)
print()

print("Plotting R&P productivity chart...")
plot_productivity(rp_data, 'R&P')

print("Plotting FG productivity chart...")
plot_productivity(fg_data, 'FG')

print("Saving data to Excel...")
with pd.ExcelWriter('Productivity_Analysis_Data.xlsx', engine='openpyxl') as writer:
    rp_data.to_excel(writer, sheet_name='R&P', index=False)
    fg_data.to_excel(writer, sheet_name='FG', index=False)

print("All charts have been generated and saved!")
print("Data has been saved to Productivity_Analysis_Data.xlsx")
