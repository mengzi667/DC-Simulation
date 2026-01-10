"""
DC 仿真数据准备脚本
从KPI、Shipments、Timeslot数据提取仿真参数
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
import os

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'raw'
TIMESLOT_DIR = PROJECT_ROOT / 'data' / 'Timeslot by week'
OUTPUT_DIR = PROJECT_ROOT / 'outputs' / 'simulation_configs'
FIGURES_DIR = PROJECT_ROOT / 'outputs' / 'figures'

KPI_FILE = DATA_DIR / 'KPI sheet 2025.xlsx'
SHIPMENTS_FILE = DATA_DIR / 'Total Shipments 2025.xlsx'

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

def extract_efficiency_parameters():
    """提取效率参数（托盘/小时）"""
    print("=" * 60)
    print("1. 提取效率参数")
    print("=" * 60)
    
    df = pd.read_excel(KPI_FILE, sheet_name='Hours & volumes per subgroup', header=None)
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    def extract_category_efficiency(df, category):
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
        
        total_pallets = inbound_data + outbound_data
        efficiency = total_pallets / hours_data
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
    
    def daily_demand_stats(df, category):
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
        'hourly_arrival_by_category': hourly_arrivals,  # 保留分类别数据
        'daily_demand': daily_demand
    }
    
    return demand_distribution


def calculate_factory_production_rate(daily_demand):
    """基于每日需求计算工厂24/7生产速率"""
    print("\n" + "=" * 60)
    print("3. 计算工厂生产速率")
    print("=" * 60)
    
    production_rates = {}
    
    for category in ['FG', 'R&P']:
        daily_production = daily_demand[category]['inbound']['mean']
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
    """估算缓冲区容量需求（基于DC关闭时段累积量）"""
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
    fig_path = FIGURES_DIR / 'hourly_arrival_pattern.png'
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    print(f"  已保存: {fig_path.name}")
    plt.close()


def extract_dock_capacity_from_timeslot():
    """
    从Timeslot数据提取码头容量（每小时）
    完全参照Timeslot.py和Timeslot_yearly.py的处理逻辑
    """
    print("\n" + "=" * 60)
    print("6. 提取码头容量数据（48周数据）")
    print("=" * 60)
    
    from openpyxl import load_workbook
    
    # 查找所有Timeslot文件（修正路径：直接在data目录下）
    timeslot_files = list(TIMESLOT_DIR.glob('W*.xlsx'))
    
    if not timeslot_files:
        print(f"警告: 未找到Timeslot文件，路径: {TIMESLOT_DIR / 'W*.xlsx'}")
        return None
    
    print(f"  找到 {len(timeslot_files)} 个周数据文件")
    
    try:
        # 读取并合并所有文件（参照Timeslot.py的逻辑）
        dfs = []
        for file in timeslot_files:
            wb = load_workbook(file, data_only=True)
            ws = wb.active
            
            data = []
            for row in ws.iter_rows(values_only=True):
                data.append(list(row))
            
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 标准化列数
            if len(df.columns) == 31:
                df.insert(7, '0h00', 0)
            if len(df.columns) == 32:
                df = df.iloc[:, :-1]
            
            # 统一列名
            df.columns = [f'col_{i}' for i in range(len(df.columns))]
            dfs.append(df)
        
        merged_df = pd.concat(dfs, ignore_index=True)
        print(f"  合并后总行数: {len(merged_df)}")
        
        # 解析日期
        merged_df['Date_parsed'] = pd.to_datetime(merged_df.iloc[:, 1], errors='coerce', dayfirst=True)
        
        # 修正日期错误（YYYY-M-11 → YYYY-11-M）
        mask = (merged_df['Date_parsed'].dt.year == 2025) & \
               (merged_df['Date_parsed'].dt.day == 11) & \
               (merged_df['Date_parsed'].dt.month <= 10)
        
        if mask.sum() > 0:
            corrected_dates = merged_df.loc[mask, 'Date_parsed'].apply(
                lambda x: pd.Timestamp(year=x.year, month=11, day=x.month)
            )
            merged_df.loc[mask, 'Date_parsed'] = corrected_dates
        
        # 过滤2025年数据
        year_data = merged_df[merged_df['Date_parsed'].dt.year == 2025]
        
        # 过滤有效数据
        year_data = year_data[year_data.iloc[:, 3].notna()]  # col_3: Category不为空
        year_data = year_data[year_data.iloc[:, 5].isin(['Booking taken', 'Available Capacity'])]
        
        print(f"  有效数据行数: {len(year_data)}")
        
        # 时间列索引（col_7到col_30，共24列）
        time_columns = list(range(7, 31))
        
        # 提取码头容量的函数（参照Timeslot.py的extract_timeslot_data）
        def extract_capacity(df, condition_type, category):
            """提取特定条件和类别的容量数据"""
            if condition_type == 'outbound':
                condition_filter = df.iloc[:, 0] == 'Loading'
            else:
                condition_filter = df.iloc[:, 0] == 'Reception'
            
            category_filter = df.iloc[:, 3] == category
            filtered_df = df[condition_filter & category_filter]
            
            # 提取Booking taken和Available Capacity
            booking_taken = filtered_df[filtered_df.iloc[:, 5] == 'Booking taken'].iloc[:, time_columns].sum()
            available_capacity = filtered_df[filtered_df.iloc[:, 5] == 'Available Capacity'].iloc[:, time_columns].sum()
            
            # 总容量 = Booking taken + Available Capacity
            total_capacity = booking_taken + available_capacity
            
            # 计算平均每小时容量（除以天数得到平均值）
            num_days = len(filtered_df[filtered_df.iloc[:, 5] == 'Booking taken']['Date_parsed'].unique())
            if num_days > 0:
                avg_capacity = total_capacity / num_days
            else:
                avg_capacity = total_capacity
            
            return {hour: int(round(avg_capacity.iloc[hour])) if hour < len(avg_capacity) else 0 
                    for hour in range(24)}
        
        # 提取四种组合的容量
        dock_capacity = {
            'FG': {
                'loading': extract_capacity(year_data, 'outbound', 'FG'),
                'reception': extract_capacity(year_data, 'inbound', 'FG')
            },
            'RP': {
                'loading': extract_capacity(year_data, 'outbound', 'R&P'),
                'reception': extract_capacity(year_data, 'inbound', 'R&P')
            }
        }
        
        # 打印统计信息
        print("成功提取码头容量数据")
        print(f"    FG Loading: 平均 {np.mean(list(dock_capacity['FG']['loading'].values())):.1f} 个码头/小时")
        print(f"    FG Reception: 平均 {np.mean(list(dock_capacity['FG']['reception'].values())):.1f} 个码头/小时")
        print(f"    R&P Loading: 平均 {np.mean(list(dock_capacity['RP']['loading'].values())):.1f} 个码头/小时")
        print(f"    R&P Reception: 平均 {np.mean(list(dock_capacity['RP']['reception'].values())):.1f} 个码头/小时")
        
        return dock_capacity
        
    except Exception as e:
        print(f"警告: 提取码头容量失败（异常）: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_pallet_distribution():
    """
    从 Total Shipments 分析托盘数分布
    
    Returns:
        dict: 按类别分组的托盘数分布参数
    """
    print("\n" + "=" * 60)
    print("7. 分析托盘数分布")
    print("=" * 60)
    
    # 读取 Inbound 和 Outbound 数据（实际sheet名称）
    inbound_df = pd.read_excel(SHIPMENTS_FILE, sheet_name='Inbound Shipments 2025')
    outbound_df = pd.read_excel(SHIPMENTS_FILE, sheet_name='Outbound Shipments 2025')
    
    # 合并所有数据
    all_shipments = pd.concat([inbound_df, outbound_df], ignore_index=True)
    
    print(f"  总批次数: {len(all_shipments)}")
    
    pallet_distribution = {}
    
    for category in ['FG', 'R&P']:
        category_data = all_shipments[all_shipments['Category'] == category]['Total pal'].dropna()
        
        if len(category_data) == 0:
            print(f"警告: {category}: 无数据")
            continue
        
        # 计算分布参数
        pallets = category_data.values
        
        # 基本统计
        mean_val = float(np.mean(pallets))
        std_val = float(np.std(pallets))
        median_val = float(np.median(pallets))
        min_val = float(np.min(pallets))
        max_val = float(np.max(pallets))
        
        # 估算众数（使用核密度估计的峰值）
        try:
            # 使用直方图近似众数
            hist, bin_edges = np.histogram(pallets, bins=50)
            mode_idx = np.argmax(hist)
            mode_val = float((bin_edges[mode_idx] + bin_edges[mode_idx + 1]) / 2)
        except:
            mode_val = median_val
        
        # 确定分布类型
        # 计算偏度 (利用 pandas Series 的 skew 方法，避免引入 scipy)
        skewness = category_data.skew()
        
        # 基于偏度选择分布类型
        if abs(skewness) < 0.5:
            dist_type = 'normal'
        else:
            dist_type = 'triangular'  # 三角分布对偏斜数据更稳健
        
        pallet_distribution[category] = {
            'type': dist_type,
            'min': int(min_val),
            'mode': int(round(mode_val)),
            'max': int(max_val),
            'mean': mean_val,
            'std': std_val,
            'median': median_val,
            'count': len(category_data)
        }
        
        print(f"\n  {category} 托盘数分布:")
        print(f"    样本量: {len(category_data):,} 批次")
        print(f"    分布类型: {dist_type}")
        print(f"    均值: {mean_val:.1f} 托盘")
        print(f"    标准差: {std_val:.1f}")
        print(f"    中位数: {median_val:.1f}")
        print(f"    众数: {mode_val:.0f}")
        print(f"    范围: [{int(min_val)}, {int(max_val)}]")
        print(f"    偏度: {skewness:.2f}")
    
    return pallet_distribution


def extract_fte_from_kpi():
    """
    从 KPI sheet 提取人力资源数据
    
    Returns:
        dict: FTE总数和分配
    """
    print("\n" + "=" * 60)
    print("8. 提取人力资源数据")
    print("=" * 60)
    
    df = pd.read_excel(KPI_FILE, sheet_name='Hours & volumes per subgroup', header=None)
    
    # 提取工时数据（修复：读取Actual行本身，而不是下一行Delta）
    def extract_hours(df, category):
        """提取特定类别的工时数据"""
        for idx, row in df.iterrows():
            if row[0] == category and row[1] == 'Actual':
                # 直接读取当前行（Actual行），而不是idx+1（Delta行）
                hours_data = df.iloc[idx, 2:13].values
                hours_data = pd.to_numeric(hours_data, errors='coerce')
                return hours_data[~pd.isna(hours_data)]
        return None
    
    rp_hours = extract_hours(df, 'R&P')
    fg_hours = extract_hours(df, 'FG')
    
    if rp_hours is None or fg_hours is None:
        print("警告: 无法提取工时数据，使用默认值")
        return {
            'fte_total': 125,
            'fte_allocation': {'rp_baseline': 28, 'fg_baseline': 97}
        }
    
    # 计算平均月工时
    rp_avg_hours = np.mean(rp_hours)
    fg_avg_hours = np.mean(fg_hours)
    total_avg_hours = rp_avg_hours + fg_avg_hours
    
    # 标准工时/人/月（假设每人每月176小时，即44小时/周 × 4周）
    hours_per_fte_per_month = 176
    
    # 计算 FTE
    rp_fte = rp_avg_hours / hours_per_fte_per_month
    fg_fte = fg_avg_hours / hours_per_fte_per_month
    total_fte = rp_fte + fg_fte
    
    print(f"\n  平均月工时:")
    print(f"    R&P: {rp_avg_hours:.0f} 小时/月")
    print(f"    FG: {fg_avg_hours:.0f} 小时/月")
    print(f"    总计: {total_avg_hours:.0f} 小时/月")
    
    print(f"\n  计算 FTE (按 {hours_per_fte_per_month} 小时/人/月):")
    print(f"    R&P: {rp_fte:.1f} FTE → {int(round(rp_fte))} 人")
    print(f"    FG: {fg_fte:.1f} FTE → {int(round(fg_fte))} 人")
    print(f"    总计: {total_fte:.1f} FTE → {int(round(total_fte))} 人")
    
    return {
        'fte_total': int(round(total_fte)),
        'fte_allocation': {
            'rp_baseline': int(round(rp_fte)),
            'fg_baseline': int(round(fg_fte))
        }
    }


def generate_simulation_config(efficiency_params, demand_distribution, 
                                production_rates, buffer_requirements,
                                dock_capacity=None, pallet_distribution=None, 
                                fte_data=None):
    """
    生成仿真配置文件
    
    Args:
        efficiency_params: 效率参数
        demand_distribution: 需求分布
        production_rates: 生产速率
        buffer_requirements: 缓冲区需求
        dock_capacity: 码头容量（可选）
        pallet_distribution: 托盘数分布（可选）
        fte_data: 人力资源数据（可选）
    
    Returns:
        dict: 完整的仿真配置
    """
    print("\n" + "=" * 60)
    print("9. 生成仿真配置文件")
    print("=" * 60)
    
    # 辅助函数：将numpy类型转换为Python原生类型
    def convert_to_native(obj):
        """递归转换numpy类型为Python原生类型"""
        import numpy as np
        
        if isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return convert_to_native(obj.tolist())
        else:
            return obj
    
    config = {
        'efficiency': {
            'rp_mean': float(efficiency_params['R&P']['mean']),
            'rp_std': float(efficiency_params['R&P']['std']),
            'fg_mean': float(efficiency_params['FG']['mean']),
            'fg_std': float(efficiency_params['FG']['std'])
        },
        'factory_production': {
            'rp_rate': float(production_rates['R&P']['hourly_rate']),
            'fg_rate': float(production_rates['FG']['hourly_rate'])
        },
        'buffer_capacity': {
            'rp_trailers': int(buffer_requirements['R&P']['recommended_trailers']),
            'fg_trailers': int(buffer_requirements['FG']['recommended_trailers']),
            'pallets_per_trailer': 33
        },
        # 修复：使用分类别的到达率数据（与dc_simulation.py格式匹配）
        'truck_arrival_rates': convert_to_native(demand_distribution['hourly_arrival_by_category']),
        'daily_demand': convert_to_native(demand_distribution['daily_demand'])
    }
    
    # 添加码头容量（如果已提取）
    if dock_capacity is not None:
        config['hourly_dock_capacity'] = convert_to_native(dock_capacity)
        print("已包含码头容量数据")
    else:
        print("警告: 码头容量数据未提取，仿真将使用默认值")
    
    # 添加托盘数分布（如果已提取）
    if pallet_distribution is not None:
        config['pallets_distribution'] = convert_to_native(pallet_distribution)
        print("已包含托盘数分布数据")
    else:
        print("警告: 托盘数分布未提取，仿真将使用默认值")
    
    # 添加人力资源数据（如果已提取）
    if fte_data is not None:
        config['fte_total'] = fte_data['fte_total']
        config['fte_allocation'] = fte_data['fte_allocation']
        print("已包含人力资源数据")
    else:
        print("警告: 人力资源数据未提取，仿真将使用默认值")
    
    # 添加数据来源信息
    config['data_source'] = {
        'efficiency_source': 'KPI sheet 2025.xlsx (11 months)',
        'demand_source': 'Total Shipments 2025.xlsx (full year)',
        'dock_capacity_source': 'Timeslot by week W1-W48.xlsx (48 weeks)' if dock_capacity else 'Hardcoded',
        'pallet_distribution_source': 'Total Shipments 2025.xlsx analysis' if pallet_distribution else 'Hardcoded',
        'fte_source': 'KPI sheet 2025.xlsx Hours data' if fte_data else 'Hardcoded',
        'extraction_date': pd.Timestamp.now().strftime('%Y-%m-%d'),
        'year': 2025
    }
    
    # 保存为 JSON 文件
    config_file = OUTPUT_DIR / 'simulation_config.json'
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print(f"  已保存: {config_file.name}")
    
    # 保存为 Excel 文件（便于查看）
    params_file = OUTPUT_DIR / 'simulation_parameters.xlsx'
    with pd.ExcelWriter(params_file, engine='openpyxl') as writer:
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
    
    print(f"  已保存: {params_file.name}")
    
    return config


def main():
    """主函数 - 执行所有数据提取步骤"""
    print("\n" + "="*70)
    print("DC 仿真数据准备脚本 - 完整版")
    print("从现有数据中提取仿真所需的全部7类参数")
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
        
        # 6. 提取码头容量（48周数据）- 新增！
        print("\n提取额外数据维度...")
        dock_capacity = None
        try:
            dock_capacity = extract_dock_capacity_from_timeslot()
        except Exception as e:
            print(f"警告: 提取码头容量失败: {e}")
            print("  将使用默认值")
        
        # 7. 分析托盘数分布 - 新增！
        pallet_distribution = None
        try:
            pallet_distribution = extract_pallet_distribution()
        except Exception as e:
            print(f"警告: 分析托盘数分布失败: {e}")
            print("  将使用默认值")
        
        # 8. 提取人力资源数据 - 新增！
        fte_data = None
        try:
            fte_data = extract_fte_from_kpi()
        except Exception as e:
            print(f"警告: 提取人力资源数据失败: {e}")
            print("  将使用默认值")
        
        # 9. 生成配置文件（包含所有数据）
        config = generate_simulation_config(
            efficiency_params, 
            demand_distribution, 
            production_rates, 
            buffer_requirements,
            dock_capacity=dock_capacity,
            pallet_distribution=pallet_distribution,
            fte_data=fte_data
        )
        
        # 打印汇总
        print("\n" + "="*70)
        print("数据准备完成！")
        print("="*70)
        
        # 统计提取的数据维度
        extracted_params = 4  # 基础4项
        if dock_capacity:
            extracted_params += 1
        if pallet_distribution:
            extracted_params += 1
        if fte_data:
            extracted_params += 1
        
        print(f"\n已提取参数类别: {extracted_params}/7")
        print("\n基础参数 (4项):")
        print("  1. 效率参数 (efficiency)")
        print("  2. 工厂生产速率 (factory_production)")
        print("  3. 缓冲区容量 (buffer_capacity)")
        print("  4. 卡车到达率 (truck_arrival_rates)")
        
        if dock_capacity or pallet_distribution or fte_data:
            print("\n扩展参数:")
        if dock_capacity:
            print("  5. 码头容量 (hourly_dock_capacity) - 96个值")
        if pallet_distribution:
            print("  6. 托盘数分布 (pallets_distribution) - 12个值")
        if fte_data:
            print("  7. 人力资源 (fte_total, fte_allocation) - 3个值")
        
        if not all([dock_capacity, pallet_distribution, fte_data]):
            print("\n缺失参数:")
            if not dock_capacity:
                print("  - 码头容量 (仿真将使用硬编码估计值)")
            if not pallet_distribution:
                print("  - 托盘数分布 (仿真将使用硬编码估计值)")
            if not fte_data:
                print("  - 人力资源 (仿真将使用硬编码估计值)")
        
        print("\n生成的文件:")
        print(f"  1. {OUTPUT_DIR.relative_to(PROJECT_ROOT) / 'simulation_config.json'} - 仿真配置（JSON 格式）")
        print(f"  2. {OUTPUT_DIR.relative_to(PROJECT_ROOT) / 'simulation_parameters.xlsx'} - 参数汇总表（Excel）")
        print(f"  3. {FIGURES_DIR.relative_to(PROJECT_ROOT) / 'hourly_arrival_pattern.png'} - 到达分布可视化")
        print("\n下一步:")
        print("  运行 dc_simulation.py 进行仿真分析")
        print("="*70 + "\n")
        
        return config
        
    except FileNotFoundError as e:
        print(f"\n错误: 找不到数据文件 - {e}")
        print("请确保以下文件存在:")
        print(f"  - {KPI_FILE}")
        print(f"  - {SHIPMENTS_FILE}")
        print(f"  - {DATA_DIR / 'Timeslot by week'} (包含W1-W48.xlsx)")
        return None
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    config = main()
