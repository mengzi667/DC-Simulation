"""
DC 仿真数据准备脚本

从现有数据中提取仿真所需参数：
1. 效率参数（托盘/小时） - 来源: KPI sheet 2025.xlsx (11个月数据)
2. 卡车到达分布 - 来源: Total Shipments 2025.xlsx (全年305天数据)
3. 码头容量分布 - 来源: Timeslot W1-W48.xlsx (48周数据)

数据覆盖：2025年全年
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json

# 数据文件路径
DATA_DIR = Path('data')
KPI_FILE = DATA_DIR / 'KPI sheet 2025.xlsx'
SHIPMENTS_FILE = DATA_DIR / 'Total Shipments 2025.xlsx'

def extract_efficiency_parameters():
    """
    从 KPI sheet 提取效率参数
    
    Returns:
        dict: 包含 R&P 和 FG 的平均效率和标准差
    """
    print("=" * 60)
    print("1. 提取效率参数")
    print("=" * 60)
    
    df = pd.read_excel(KPI_FILE, sheet_name='Hours & volumes per subgroup', header=None)
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    def extract_category_efficiency(df, category):
        """提取特定类别的效率数据"""
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
        
        # 转换为数值
        hours_data = pd.to_numeric(hours_data, errors='coerce')
        inbound_data = pd.to_numeric(inbound_data, errors='coerce')
        outbound_data = pd.to_numeric(outbound_data, errors='coerce')
        
        # 计算总托盘和效率
        total_pallets = inbound_data + outbound_data
        efficiency = total_pallets / hours_data
        
        # 过滤掉 NaN 值
        valid_efficiency = efficiency[~np.isnan(efficiency)]
        
        result = {
            'mean': np.mean(valid_efficiency),
            'std': np.std(valid_efficiency),
            'median': np.median(valid_efficiency),
            'min': np.min(valid_efficiency),
            'max': np.max(valid_efficiency),
            'monthly_data': list(valid_efficiency)
        }
        
        return result
    
    # 提取 R&P 和 FG 数据
    rp_efficiency = extract_category_efficiency(df, 'R&P')
    fg_efficiency = extract_category_efficiency(df, 'FG')
    
    efficiency_params = {
        'R&P': rp_efficiency,
        'FG': fg_efficiency
    }
    
    print(f"\nR&P 效率参数:")
    print(f"  平均值: {rp_efficiency['mean']:.2f} 托盘/小时")
    print(f"  标准差: {rp_efficiency['std']:.3f}")
    print(f"  中位数: {rp_efficiency['median']:.2f}")
    print(f"  范围: [{rp_efficiency['min']:.2f}, {rp_efficiency['max']:.2f}]")
    
    print(f"\nFG 效率参数:")
    print(f"  平均值: {fg_efficiency['mean']:.2f} 托盘/小时")
    print(f"  标准差: {fg_efficiency['std']:.3f}")
    print(f"  中位数: {fg_efficiency['median']:.2f}")
    print(f"  范围: [{fg_efficiency['min']:.2f}, {fg_efficiency['max']:.2f}]")
    
    return efficiency_params


def extract_demand_distribution(target_year=2025):
    """
    从 Total Shipments 提取需求分布（全年数据）
    
    Args:
        target_year: 目标年份（默认 2025）
    
    Returns:
        dict: 包含每小时到达率和每日需求分布
    """
    print("\n" + "=" * 60)
    print("2. 提取需求分布参数（全年数据）")
    print("=" * 60)
    
    # 读取数据
    inbound_df = pd.read_excel(SHIPMENTS_FILE, sheet_name='Inbound Shipments 2025')
    outbound_df = pd.read_excel(SHIPMENTS_FILE, sheet_name='Outbound Shipments 2025')
    
    # 转换日期
    inbound_df['Date Hour appointement'] = pd.to_datetime(inbound_df['Date Hour appointement'])
    outbound_df['Date Hour appointement'] = pd.to_datetime(outbound_df['Date Hour appointement'])
    
    # 使用全年数据
    inbound_year = inbound_df[inbound_df['Date Hour appointement'].dt.year == target_year]
    outbound_year = outbound_df[outbound_df['Date Hour appointement'].dt.year == target_year]
    
    print(f"\n{target_year} 年全年数据统计:")
    print(f"  入库记录数: {len(inbound_year)}")
    print(f"  出库记录数: {len(outbound_year)}")
    
    # 计算数据覆盖的月份
    inbound_months = inbound_year['Date Hour appointement'].dt.month.unique()
    outbound_months = outbound_year['Date Hour appointement'].dt.month.unique()
    print(f"  入库数据覆盖月份: {sorted(inbound_months.tolist())}")
    print(f"  出库数据覆盖月份: {sorted(outbound_months.tolist())}")
    
    # 提取小时到达分布（Outbound，用于卡车到达率）
    outbound_year['Hour'] = outbound_year['Date Hour appointement'].dt.hour
    
    # 分类别统计
    hourly_arrivals = {}
    
    for category in ['FG', 'R&P']:
        category_data = outbound_year[outbound_year['Category'] == category]
        
        # 计算每小时平均到达卡车数（全年平均）
        hourly_counts = category_data.groupby('Hour').size()
        num_days = category_data['Date Hour appointement'].dt.date.nunique()
        
        hourly_rate = (hourly_counts / num_days).to_dict()
        hourly_arrivals[category] = hourly_rate
        
        total_trucks = hourly_counts.sum()
        avg_per_day = total_trucks / num_days
        print(f"\n{category} 出库统计（全年）:")
        print(f"  总卡车数: {total_trucks}")
        print(f"  统计天数: {num_days}")
        print(f"  平均每天: {avg_per_day:.2f} 辆")
        print(f"  每小时平均到达卡车数:")
        for hour in sorted(hourly_rate.keys()):
            print(f"    {hour:02d}:00 - {hourly_rate[hour]:.2f}")
    
    # 合并所有类别计算总到达率
    combined_hourly = outbound_year.groupby('Hour').size()
    num_days_total = outbound_year['Date Hour appointement'].dt.date.nunique()
    total_hourly_rate = (combined_hourly / num_days_total).to_dict()
    
    print(f"\n总体每小时平均到达卡车数:")
    for hour in sorted(total_hourly_rate.keys()):
        print(f"  {hour:02d}:00 - {total_hourly_rate[hour]:.2f}")
    
    # 计算每日需求（托盘）- 使用全年数据
    def daily_demand_stats(df, category):
        """计算每日需求统计（全年）"""
        cat_data = df[df['Category'] == category].copy()
        cat_data['Date'] = cat_data['Date Hour appointement'].dt.date
        
        daily_pallets = cat_data.groupby('Date')['Total pal'].sum()
        
        return {
            'mean': daily_pallets.mean(),
            'std': daily_pallets.std(),
            'median': daily_pallets.median(),
            'min': daily_pallets.min(),
            'max': daily_pallets.max(),
            'total_days': len(daily_pallets)
        }
    
    daily_demand = {
        'FG': {
            'inbound': daily_demand_stats(inbound_year, 'FG'),
            'outbound': daily_demand_stats(outbound_year, 'FG')
        },
        'R&P': {
            'inbound': daily_demand_stats(inbound_year, 'R&P'),
            'outbound': daily_demand_stats(outbound_year, 'R&P')
        }
    }
    
    print(f"\n每日需求统计（托盘 - 全年平均）:")
    for category in ['FG', 'R&P']:
        print(f"\n{category}:")
        inbound_days = daily_demand[category]['inbound']['total_days']
        outbound_days = daily_demand[category]['outbound']['total_days']
        print(f"  入库 - 平均: {daily_demand[category]['inbound']['mean']:.0f}, "
              f"标准差: {daily_demand[category]['inbound']['std']:.0f} (统计{inbound_days}天)")
        print(f"  出库 - 平均: {daily_demand[category]['outbound']['mean']:.0f}, "
              f"标准差: {daily_demand[category]['outbound']['std']:.0f} (统计{outbound_days}天)")
    
    demand_distribution = {
        'hourly_arrival_rate': total_hourly_rate,
        'hourly_arrival_by_category': hourly_arrivals,
        'daily_demand': daily_demand
    }
    
    return demand_distribution


def calculate_factory_production_rate(daily_demand):
    """
    基于每日需求反推工厂 24/7 生产速率
    
    Args:
        daily_demand: 每日需求字典
    
    Returns:
        dict: 每小时生产速率（托盘/小时）
    """
    print("\n" + "=" * 60)
    print("3. 计算工厂生产速率")
    print("=" * 60)
    
    production_rates = {}
    
    for category in ['FG', 'R&P']:
        # 使用入库平均值作为生产速率基准
        daily_production = daily_demand[category]['inbound']['mean']
        
        # 假设工厂 24/7 运作
        hourly_rate = daily_production / 24
        
        production_rates[category] = {
            'hourly_rate': hourly_rate,
            'daily_production': daily_production
        }
        
        print(f"\n{category} 工厂生产速率:")
        print(f"  每日生产: {daily_production:.0f} 托盘")
        print(f"  每小时: {hourly_rate:.1f} 托盘/小时（24/7 连续）")
    
    return production_rates


def estimate_buffer_capacity_requirement(production_rate, dc_closed_hours=6):
    """
    估算缓冲区容量需求
    
    Args:
        production_rate: 每小时生产速率字典
        dc_closed_hours: DC 关闭小时数（默认 6 小时，对应 00:00-06:00）
    
    Returns:
        dict: 缓冲区容量需求
    """
    print("\n" + "=" * 60)
    print("4. 估算缓冲区容量需求")
    print("=" * 60)
    
    pallets_per_trailer = 33
    buffer_requirements = {}
    
    for category in ['FG', 'R&P']:
        # DC 关闭期间累积的托盘数
        accumulated_pallets = production_rate[category]['hourly_rate'] * dc_closed_hours
        
        # 需要的挂车数（向上取整）
        required_trailers = np.ceil(accumulated_pallets / pallets_per_trailer)
        
        # 加上 20% 安全余量
        recommended_trailers = int(required_trailers * 1.2)
        
        buffer_requirements[category] = {
            'accumulated_pallets': accumulated_pallets,
            'required_trailers': int(required_trailers),
            'recommended_trailers': recommended_trailers
        }
        
        print(f"\n{category} 缓冲区需求 (DC 关闭 {dc_closed_hours} 小时):")
        print(f"  累积托盘: {accumulated_pallets:.0f}")
        print(f"  最低挂车数: {int(required_trailers)}")
        print(f"  推荐挂车数: {recommended_trailers} (含 20% 余量)")
    
    return buffer_requirements


def visualize_hourly_arrival_pattern(hourly_rates):
    """可视化每小时到达模式"""
    print("\n" + "=" * 60)
    print("5. 生成可视化图表")
    print("=" * 60)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    hours = sorted(hourly_rates.keys())
    rates = [hourly_rates[h] for h in hours]
    
    ax.bar(hours, rates, color='steelblue', alpha=0.7, edgecolor='navy')
    ax.plot(hours, rates, color='red', marker='o', linewidth=2, markersize=6, label='到达率趋势')
    
    ax.set_xlabel('小时', fontsize=12)
    ax.set_ylabel('平均卡车到达数', fontsize=12)
    ax.set_title('每小时卡车到达分布（基于 2025 年 11 月数据）', fontsize=14, fontweight='bold')
    ax.set_xticks(range(0, 24))
    ax.set_xticklabels([f'{h:02d}:00' for h in range(0, 24)], rotation=45, ha='right')
    ax.grid(axis='y', alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig('hourly_arrival_pattern.png', dpi=300, bbox_inches='tight')
    print("  已保存: hourly_arrival_pattern.png")
    plt.close()


def generate_simulation_config(efficiency_params, demand_distribution, 
                                production_rates, buffer_requirements):
    """
    生成仿真配置文件
    
    Args:
        efficiency_params: 效率参数
        demand_distribution: 需求分布
        production_rates: 生产速率
        buffer_requirements: 缓冲区需求
    
    Returns:
        dict: 完整的仿真配置
    """
    print("\n" + "=" * 60)
    print("6. 生成仿真配置文件")
    print("=" * 60)
    
    config = {
        'efficiency': {
            'rp_mean': efficiency_params['R&P']['mean'],
            'rp_std': efficiency_params['R&P']['std'],
            'fg_mean': efficiency_params['FG']['mean'],
            'fg_std': efficiency_params['FG']['std']
        },
        'factory_production': {
            'rp_rate': production_rates['R&P']['hourly_rate'],
            'fg_rate': production_rates['FG']['hourly_rate']
        },
        'buffer_capacity': {
            'rp_trailers': buffer_requirements['R&P']['recommended_trailers'],
            'fg_trailers': buffer_requirements['FG']['recommended_trailers'],
            'pallets_per_trailer': 33
        },
        'truck_arrival_rates': demand_distribution['hourly_arrival_rate'],
        'daily_demand': demand_distribution['daily_demand'],
        'data_source': {
            'month': 11,
            'year': 2025,
            'extraction_date': pd.Timestamp.now().strftime('%Y-%m-%d')
        }
    }
    
    # 保存为 JSON 文件
    with open('simulation_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print("  已保存: simulation_config.json")
    
    # 保存为 Excel 文件（便于查看）
    with pd.ExcelWriter('simulation_parameters.xlsx', engine='openpyxl') as writer:
        # 效率参数
        efficiency_df = pd.DataFrame({
            'Category': ['R&P', 'FG'],
            'Mean Efficiency (pal/hr)': [
                efficiency_params['R&P']['mean'],
                efficiency_params['FG']['mean']
            ],
            'Std Dev': [
                efficiency_params['R&P']['std'],
                efficiency_params['FG']['std']
            ],
            'Min': [
                efficiency_params['R&P']['min'],
                efficiency_params['FG']['min']
            ],
            'Max': [
                efficiency_params['R&P']['max'],
                efficiency_params['FG']['max']
            ]
        })
        efficiency_df.to_excel(writer, sheet_name='Efficiency', index=False)
        
        # 生产速率
        production_df = pd.DataFrame({
            'Category': ['R&P', 'FG'],
            'Hourly Rate (pal/hr)': [
                production_rates['R&P']['hourly_rate'],
                production_rates['FG']['hourly_rate']
            ],
            'Daily Production (pal)': [
                production_rates['R&P']['daily_production'],
                production_rates['FG']['daily_production']
            ]
        })
        production_df.to_excel(writer, sheet_name='Production_Rate', index=False)
        
        # 缓冲区需求
        buffer_df = pd.DataFrame({
            'Category': ['R&P', 'FG'],
            'Required Trailers': [
                buffer_requirements['R&P']['required_trailers'],
                buffer_requirements['FG']['required_trailers']
            ],
            'Recommended Trailers': [
                buffer_requirements['R&P']['recommended_trailers'],
                buffer_requirements['FG']['recommended_trailers']
            ],
            'Accumulated Pallets (6hr)': [
                buffer_requirements['R&P']['accumulated_pallets'],
                buffer_requirements['FG']['accumulated_pallets']
            ]
        })
        buffer_df.to_excel(writer, sheet_name='Buffer_Capacity', index=False)
        
        # 每小时到达率
        arrival_df = pd.DataFrame({
            'Hour': sorted(demand_distribution['hourly_arrival_rate'].keys()),
            'Arrival Rate (trucks/hr)': [
                demand_distribution['hourly_arrival_rate'][h] 
                for h in sorted(demand_distribution['hourly_arrival_rate'].keys())
            ]
        })
        arrival_df.to_excel(writer, sheet_name='Hourly_Arrivals', index=False)
    
    print("  已保存: simulation_parameters.xlsx")
    
    return config


def main():
    """主函数 - 执行所有数据提取步骤"""
    print("\n" + "="*70)
    print("DC 仿真数据准备脚本")
    print("从现有数据中提取仿真所需参数")
    print("="*70)
    
    try:
        # 1. 提取效率参数（基于11个月数据）
        efficiency_params = extract_efficiency_parameters()
        
        # 2. 提取需求分布（使用全年数据）
        demand_distribution = extract_demand_distribution(target_year=2025)
        
        # 3. 计算工厂生产速率
        production_rates = calculate_factory_production_rate(demand_distribution['daily_demand'])
        
        # 4. 估算缓冲区容量
        buffer_requirements = estimate_buffer_capacity_requirement(production_rates, dc_closed_hours=6)
        
        # 5. 可视化
        visualize_hourly_arrival_pattern(demand_distribution['hourly_arrival_rate'])
        
        # 6. 生成配置文件
        config = generate_simulation_config(
            efficiency_params, 
            demand_distribution, 
            production_rates, 
            buffer_requirements
        )
        
        # 打印汇总
        print("\n" + "="*70)
        print("数据准备完成！")
        print("="*70)
        print("\n生成的文件:")
        print("  1. simulation_config.json - 仿真配置（JSON 格式）")
        print("  2. simulation_parameters.xlsx - 参数汇总表（Excel）")
        print("  3. hourly_arrival_pattern.png - 到达分布可视化")
        print("\n下一步:")
        print("  运行 dc_simulation.py 进行仿真分析")
        print("="*70 + "\n")
        
        return config
        
    except FileNotFoundError as e:
        print(f"\n错误: 找不到数据文件 - {e}")
        print("请确保以下文件存在:")
        print(f"  - {KPI_FILE}")
        print(f"  - {SHIPMENTS_FILE}")
        return None
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    config = main()
