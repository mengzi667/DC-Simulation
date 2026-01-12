import pandas as pd
import json

# Read Excel file
df = pd.read_excel('d:/TUD/Design_Project/outputs/results/simulation_results_comparison.xlsx')

scenarios = ['Baseline', 'Scenario 1', 'Scenario 2', 'Scenario 3']

# Extract all key metrics
data = {
    'scenarios': scenarios,
    'metrics': {}
}

# Define metrics to extract
metrics = {
    # SLA metrics
    'sla_compliance_rate': 'SLA Compliance Rate',
    'G2_sla_compliance_rate': 'G2 SLA',
    'ROW_sla_compliance_rate': 'ROW SLA',
    
    # Waiting time
    'avg_truck_wait_time': 'Avg Wait Time (hrs)',
    'max_truck_wait_time': 'Max Wait Time (hrs)',
    'p95_truck_wait_time': 'P95 Wait Time (hrs)',
    
    # Throughput - Pallets
    'total_inbound_pallets': 'Total Inbound Pallets',
    'total_outbound_pallets': 'Total Outbound Pallets',
    'FG_inbound_pallets': 'FG Inbound Pallets',
    'FG_outbound_pallets': 'FG Outbound Pallets',
    'R&P_inbound_pallets': 'R&P Inbound Pallets',
    'R&P_outbound_pallets': 'R&P Outbound Pallets',
    
    # Throughput - Orders
    'total_inbound_orders': 'Total Inbound Orders',
    'total_outbound_orders': 'Total Outbound Orders',
    'FG_inbound_orders': 'FG Inbound Orders',
    'FG_outbound_orders': 'FG Outbound Orders',
    'R&P_inbound_orders': 'R&P Inbound Orders',
    'R&P_outbound_orders': 'R&P Outbound Orders',
    
    # Regional throughput
    'FG_G2_outbound_pallets': 'FG G2 Outbound Pallets',
    'FG_ROW_outbound_pallets': 'FG ROW Outbound Pallets',
    'FG_G2_outbound_orders': 'FG G2 Outbound Orders',
    'FG_ROW_outbound_orders': 'FG ROW Outbound Orders',
    
    # Utilization
    'loading_avg_utilization': 'Loading Avg Utilization',
    'reception_avg_utilization': 'Reception Avg Utilization',
    'FG_dock_avg_utilization': 'FG Dock Avg Utilization',
    'R&P_dock_avg_utilization': 'R&P Dock Avg Utilization',
    
    # Inbound delays
    'total_inbound_delays': 'Total Inbound Delays',
    'avg_inbound_delay_hours': 'Avg Inbound Delay (hrs)',
    'max_inbound_delay_hours': 'Max Inbound Delay (hrs)',
}

for metric_col, metric_name in metrics.items():
    if metric_col in df.columns:
        mean_values = df[metric_col].tolist()
        std_values = df[metric_col + '_std'].tolist() if (metric_col + '_std') in df.columns else [0, 0, 0, 0]
        
        data['metrics'][metric_col] = {
            'name': metric_name,
            'mean': mean_values,
            'std': std_values
        }

# Print formatted output
print("="*80)
print("SIMULATION RESULTS - ALL METRICS")
print("="*80)
print(f"\nScenarios: {', '.join(scenarios)}\n")

for metric_col, metric_info in data['metrics'].items():
    print(f"{metric_info['name']}:")
    for i, scenario in enumerate(scenarios):
        mean_val = metric_info['mean'][i]
        std_val = metric_info['std'][i]
        if 'rate' in metric_col.lower() or 'utilization' in metric_col.lower():
            # Convert to percentage
            print(f"  {scenario:15s}: {mean_val*100:6.2f}% ± {std_val*100:5.2f}%")
        else:
            print(f"  {scenario:15s}: {mean_val:8.2f} ± {std_val:6.2f}")
    print()

# Save to JSON for later use
with open('d:/TUD/Design_Project/outputs/results/report_data.json', 'w') as f:
    json.dump(data, f, indent=2)

print("\n" + "="*80)
print("Data saved to: outputs/results/report_data.json")
print("="*80)
