#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTE Analysis Visualization Script
=====================================

专门的FTE分析绘图脚本，基于已生成的Excel文件创建FTE相关图表。

功能特性:
- 从Excel文件加载FTE分析结果
- 生成FTE利用率图表
- 生成FTE实际使用量图表
- 支持多种输出格式和样式
- 时间窗口标签格式化
- 内存优化的图表生成
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path
import re

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class FTEVisualizer:
    """FTE分析可视化器"""
    
    def __init__(self, results_dir=None, figures_dir=None):
        """初始化FTE可视化器
        
        Args:
            results_dir: 结果目录路径，默认为项目的outputs/results
            figures_dir: 图表输出目录，默认为项目的outputs/figures
        """
        # 设置目录路径
        if results_dir is None:
            project_root = Path(__file__).parent.parent
            self.results_dir = project_root / "outputs" / "results"
        else:
            self.results_dir = Path(results_dir)
            
        if figures_dir is None:
            project_root = Path(__file__).parent.parent
            self.figures_dir = project_root / "outputs" / "figures"
        else:
            self.figures_dir = Path(figures_dir)
        
        # 确保目录存在
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"FTE可视化器初始化:")
        print(f"  结果目录: {self.results_dir}")
        print(f"  图表输出目录: {self.figures_dir}")
    
    def _generate_time_window_labels(self, scenarios):
        """生成时间窗口格式的标签
        
        Args:
            scenarios: 场景名称列表
            
        Returns:
            list: 时间窗口格式标签列表 (如 "06:00-24:00")
        """
        scenario_labels = []
        for s in scenarios:
            s_lower = str(s).lower()
            if 'baseline' in s_lower:
                scenario_labels.append('06:00-24:00')
            else:
                # 尝试从场景名称中解析开始和结束时间
                # 支持格式: fixed_06_23, shift_07_22, shift_08_20等
                m = re.search(r'(?:fixed|shift)_(\d{2})_(\d{2})', s_lower)
                if m:
                    start_hour = m.group(1)
                    end_hour = m.group(2)
                    scenario_labels.append(f"{start_hour}:00-{end_hour}:00")
                elif '24' in s:
                    scenario_labels.append('06:00-24:00')
                elif '23' in s:
                    scenario_labels.append('06:00-23:00')
                elif '22' in s:
                    scenario_labels.append('06:00-22:00')
                elif '21' in s:
                    scenario_labels.append('06:00-21:00')
                elif '20' in s:
                    scenario_labels.append('06:00-20:00')
                else:
                    # 尝试从场景名称中提取时间模式
                    m = re.search(r'(\d{2}):(\d{2})', str(s))
                    if m:
                        scenario_labels.append(f"06:00-{m.group(1)}:{m.group(2)}")
                    else:
                        # 简化场景名称
                        scenario_labels.append(str(s)[:12] + '...' if len(str(s)) > 12 else str(s))
        
        return scenario_labels
    
    def load_fte_data(self, excel_file):
        """从Excel文件加载FTE数据
        
        Args:
            excel_file: Excel文件路径或文件名
            
        Returns:
            dict: 包含各个工作表数据的字典
        """
        if not str(excel_file).endswith('.xlsx'):
            excel_file = self.results_dir / excel_file
        else:
            excel_file = Path(excel_file)
            
        if not excel_file.exists():
            raise FileNotFoundError(f"FTE Excel文件不存在: {excel_file}")
        
        print(f"加载FTE数据: {excel_file}")
        
        try:
            # 加载所有工作表
            excel_data = pd.read_excel(excel_file, sheet_name=None)
            
            print(f"成功加载 {len(excel_data)} 个工作表:")
            for sheet_name in excel_data.keys():
                print(f"  - {sheet_name}: {len(excel_data[sheet_name])} 行")
            
            return excel_data
        
        except Exception as e:
            print(f"加载Excel文件失败: {e}")
            raise
    
    def create_comprehensive_fte_dashboard(self, summary_df, fg_df, rp_df, output_suffix=''):
        """创建综合FTE仪表板 - 将利用率和使用量整合到一个图表中
        
        Args:
            summary_df: 总体数据DataFrame
            fg_df: FG详细数据DataFrame  
            rp_df: R&P详细数据DataFrame
            output_suffix: 输出文件后缀
        """
        scenarios = summary_df['Scenario'].tolist()
        scenario_labels = self._generate_time_window_labels(scenarios)
        
        # 创建大型综合图表 - 2行3列布局（横向）
        fig, axes = plt.subplots(2, 3, figsize=(20, 12))
        fig.suptitle('Comprehensive FTE Analysis Dashboard', fontsize=16, fontweight='bold', y=0.95)
        
        # 调整子图间距
        plt.subplots_adjust(hspace=0.3, wspace=0.25, top=0.92, bottom=0.08)
        
        # === 第一行：总体概览 + FG分析 ===
        # 左上：总体FTE利用率
        ax1 = axes[0, 0]
        overall_rates = [r for r in summary_df['Overall Utilization Rate (%)'].tolist()]
        bars1 = ax1.bar(range(len(scenarios)), overall_rates, 
                        color='steelblue', alpha=0.7, edgecolor='navy', linewidth=0.8)
        ax1.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='100% Capacity')
        ax1.set_title('Overall FTE Utilization (%)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Utilization (%)', fontsize=10)
        ax1.set_xticks(range(len(scenarios)))
        ax1.set_xticklabels(scenario_labels, rotation=45, ha='right', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 110)
        ax1.legend(loc='upper left', fontsize=9)
        
        # 添加数值标签
        for i, bar in enumerate(bars1):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
        
        # 中上：总体FTE使用量 vs 可用量
        ax2 = axes[0, 1]
        total_used = summary_df['Total FTE Used'].tolist()
        total_available = summary_df['Total FTE Available'].tolist()
        
        x = np.arange(len(scenarios))
        width = 0.35
        bars2a = ax2.bar(x - width/2, total_used, width, label='Used', 
                        color='steelblue', alpha=0.7, edgecolor='navy', linewidth=0.8)
        bars2b = ax2.bar(x + width/2, total_available, width, label='Available', 
                        color='lightgreen', alpha=0.7, edgecolor='darkgreen', linewidth=0.8)
        
        # 添加数值标签到Used柱子上
        for i, bar in enumerate(bars2a):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        
        ax2.set_title('Total FTE: Used vs Available', fontsize=12, fontweight='bold')
        ax2.set_ylabel('FTE Count', fontsize=10)
        ax2.set_xticks(x)
        ax2.set_xticklabels(scenario_labels, rotation=45, ha='right', fontsize=9)
        ax2.legend(loc='upper right', fontsize=9)
        ax2.grid(True, alpha=0.3)
        
        # 右上：FG利用率对比
        ax3 = axes[0, 2]
        fg_in_rates = [r for r in fg_df['FG Inbound Utilization (%)'].tolist()]
        fg_out_rates = [r for r in fg_df['FG Outbound Utilization (%)'].tolist()]
        
        x = np.arange(len(scenarios))
        width = 0.35
        ax3.bar(x - width/2, fg_in_rates, width, label='FG Inbound', 
                color='lightcoral', alpha=0.7, edgecolor='darkred', linewidth=0.8)
        ax3.bar(x + width/2, fg_out_rates, width, label='FG Outbound', 
                color='lightblue', alpha=0.7, edgecolor='darkblue', linewidth=0.8)
        ax3.axhline(y=100, color='red', linestyle='--', alpha=0.7)
        
        ax3.set_title('FG FTE Utilization (%)', fontsize=12, fontweight='bold')
        ax3.set_ylabel('Utilization (%)', fontsize=10)
        ax3.set_xticks(x)
        ax3.set_xticklabels(scenario_labels, rotation=45, ha='right', fontsize=9)
        ax3.legend(loc='upper left', fontsize=9)
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(0, 110)
        
        # === 第二行：FG + R&P使用量分析 ===
        # 左下：FG使用量对比
        ax4 = axes[1, 0]
        fg_in_used = fg_df['FG Inbound Used'].tolist()
        fg_out_used = fg_df['FG Outbound Used'].tolist()
        
        bars4a = ax4.bar(x - width/2, fg_in_used, width, label='FG Inbound', 
                color='lightcoral', alpha=0.7, edgecolor='darkred', linewidth=0.8)
        bars4b = ax4.bar(x + width/2, fg_out_used, width, label='FG Outbound', 
                color='lightblue', alpha=0.7, edgecolor='darkblue', linewidth=0.8)
        
        # 添加数值标签
        for i, bar in enumerate(bars4a):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 0.3,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        for i, bar in enumerate(bars4b):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 0.3,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        
        ax4.set_title('FG FTE Usage (Count)', fontsize=12, fontweight='bold')
        ax4.set_ylabel('FTE Count', fontsize=10)
        ax4.set_xlabel('Scenarios', fontsize=10)
        ax4.set_xticks(x)
        ax4.set_xticklabels(scenario_labels, rotation=45, ha='right', fontsize=9)
        ax4.legend(loc='upper right', fontsize=9)
        ax4.grid(True, alpha=0.3)
        
        # 中下：R&P利用率对比
        ax5 = axes[1, 1]
        rp_in_rates = [r for r in rp_df['R&P Inbound Utilization (%)'].tolist()]
        rp_out_rates = [r for r in rp_df['R&P Outbound Utilization (%)'].tolist()]
        
        ax5.bar(x - width/2, rp_in_rates, width, label='R&P Inbound', 
                color='lightsalmon', alpha=0.7, edgecolor='darkorange', linewidth=0.8)
        ax5.bar(x + width/2, rp_out_rates, width, label='R&P Outbound', 
                color='lightseagreen', alpha=0.7, edgecolor='darkseagreen', linewidth=0.8)
        ax5.axhline(y=100, color='red', linestyle='--', alpha=0.7)
        
        ax5.set_title('R&P FTE Utilization (%)', fontsize=12, fontweight='bold')
        ax5.set_ylabel('Utilization (%)', fontsize=10)
        ax5.set_xlabel('Scenarios', fontsize=10)
        ax5.set_xticks(x)
        ax5.set_xticklabels(scenario_labels, rotation=45, ha='right', fontsize=9)
        ax5.legend(loc='upper left', fontsize=9)
        ax5.grid(True, alpha=0.3)
        ax5.set_ylim(0, 110)
        
        # 右下：R&P使用量对比
        ax6 = axes[1, 2]
        rp_in_used = rp_df['R&P Inbound Used'].tolist()
        rp_out_used = rp_df['R&P Outbound Used'].tolist()
        
        bars6a = ax6.bar(x - width/2, rp_in_used, width, label='R&P Inbound', 
                color='lightsalmon', alpha=0.7, edgecolor='darkorange', linewidth=0.8)
        bars6b = ax6.bar(x + width/2, rp_out_used, width, label='R&P Outbound', 
                color='lightseagreen', alpha=0.7, edgecolor='darkseagreen', linewidth=0.8)
        
        # 添加数值标签
        for i, bar in enumerate(bars6a):
            height = bar.get_height()
            ax6.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        for i, bar in enumerate(bars6b):
            height = bar.get_height()
            ax6.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        
        ax6.set_title('R&P FTE Usage (Count)', fontsize=12, fontweight='bold')
        ax6.set_ylabel('FTE Count', fontsize=10)
        ax6.set_xlabel('Scenarios', fontsize=10)
        ax6.set_xticks(x)
        ax6.set_xticklabels(scenario_labels, rotation=45, ha='right', fontsize=9)
        ax6.legend(loc='upper right', fontsize=9)
        ax6.grid(True, alpha=0.3)
        
        # 保存图表
        output_path = self.figures_dir / f"fte_comprehensive_dashboard{output_suffix}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"FTE综合仪表板已保存: {output_path}")
        
        # 立即关闭释放内存
        plt.close(fig)
    
    def create_comprehensive_fte_analysis(self, excel_file, output_suffix=''):
        """创建全面的FTE分析图表
        
        Args:
            excel_file: Excel文件路径
            output_suffix: 输出文件后缀
        """
        print(f"\n开始创建FTE分析图表: {excel_file}")
        
        # 加载数据
        excel_data = self.load_fte_data(excel_file)
        
        # 检查必需的工作表
        required_sheets = ['Summary', 'FG Details', 'R&P Details']
        missing_sheets = [sheet for sheet in required_sheets if sheet not in excel_data]
        
        if missing_sheets:
            print(f"警告: Excel文件缺少工作表: {missing_sheets}")
            print("跳过FTE图表生成")
            return
        
        summary_df = excel_data['Summary']
        fg_df = excel_data['FG Details'] 
        rp_df = excel_data['R&P Details']
        
        print(f"数据加载成功:")
        print(f"  Summary: {len(summary_df)} 个场景")
        print(f"  FG Details: {len(fg_df)} 个场景")
        print(f"  R&P Details: {len(rp_df)} 个场景")
        
        # 创建综合FTE仪表板
        self.create_comprehensive_fte_dashboard(summary_df, fg_df, rp_df, output_suffix)
        
        print(f"FTE分析图表创建完成!")
    
    def process_all_fte_files(self):
        """处理所有FTE相关的Excel文件"""
        print("扫描FTE相关Excel文件...")
        
        # 查找真正的FTE专用Excel文件（排除普通比较结果文件）
        all_files = list(self.results_dir.glob("*.xlsx"))
        fte_files = []
        
        for f in all_files:
            filename = f.name.lower()
            # 只包含以"fte_results"开头的文件，排除普通的comparison文件
            if filename.startswith("fte_results") and not filename.startswith("simulation_results"):
                fte_files.append(f)
        
        if not fte_files:
            print("未找到FTE专用Excel文件")
            print("提示: FTE专用文件应以 'fte_results' 开头")
            print("如需生成FTE专用文件，请先运行主仿真程序")
            return
        
        print(f"找到 {len(fte_files)} 个FTE专用文件:")
        for f in fte_files:
            print(f"  - {f.name}")
        
        # 处理每个文件
        for fte_file in fte_files:
            try:
                # 根据文件名生成后缀
                base_name = fte_file.stem  # 不含扩展名的文件名
                suffix = base_name.replace('fte_results', '').replace('fte_', '_')
                if not suffix:
                    suffix = '_standard'
                
                self.create_comprehensive_fte_analysis(fte_file, suffix)
                
            except Exception as e:
                print(f"处理文件 {fte_file.name} 时出错: {e}")
                continue
        
        print("所有FTE专用文件处理完成!")


def main():
    """主函数"""
    print("="*60)
    print("FTE Analysis Visualization Script")
    print("="*60)
    
    # 创建FTE可视化器
    visualizer = FTEVisualizer()
    
    if len(sys.argv) > 1:
        # 如果提供了文件名参数，处理特定文件
        excel_file = sys.argv[1]
        output_suffix = sys.argv[2] if len(sys.argv) > 2 else ''
        visualizer.create_comprehensive_fte_analysis(excel_file, output_suffix)
    else:
        # 处理所有FTE文件
        visualizer.process_all_fte_files()
    
    print("\nFTE可视化脚本执行完成!")


if __name__ == "__main__":
    main()