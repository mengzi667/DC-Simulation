"""
订单流程追踪器 - 运行仿真并导出每个订单的详细生命周期日志到Excel

用途：演讲/展示时详细跟踪单个订单（如FG Outbound）从生成到完成的全流程。

输出：
  - outputs/results/order_flow_tracking.xlsx
    - Order_Summary:         所有订单关键时间戳汇总（一行一个订单）
    - Event_Log:             完整事件日志（一行一个事件）
    - Example_Order_Detail:  第一个追踪订单的完整事件
    - Example_Narrative:     叙述性流程描述（可直接用于演示）
    - FG_Outbound_Summary:   FG Outbound订单筛选汇总
    - Delayed_Orders:        延误订单专题分析
"""

import sys
import os
import numpy as np
import simpy

# 确保能导入 src 模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from dc_simulation_plot_update import (
    DCSimulation, SIMULATION_CONFIG, OrderTracker, RESULTS_DIR
)
import pandas as pd


def run_order_tracking(
    scenario_name='baseline',
    target_month=1,
    duration_days=30,
    track_category='FG',
    track_direction='Outbound',
    track_specific_ids=None,
    seed=42
):
    """
    运行仿真并追踪指定类型的订单。

    Args:
        scenario_name: 场景名称（如 'baseline'）
        target_month: 目标月份
        duration_days: 仿真天数
        track_category: 追踪的货物类别 ('FG' / 'R&P' / None=全部)
        track_direction: 追踪的方向 ('Outbound' / 'Inbound' / None=全部)
        track_specific_ids: 指定追踪的订单ID列表（None=追踪所有匹配订单）
        seed: 随机种子

    Returns:
        tracker: OrderTracker 实例
        sim: DCSimulation 实例
    """
    np.random.seed(seed)

    scenario_config = SIMULATION_CONFIG[scenario_name].copy()
    print(f"\n{'='*70}")
    print(f"订单流程追踪器")
    print(f"{'='*70}")
    print(f"场景: {scenario_config['name']}")
    print(f"月份: {target_month}")
    print(f"追踪范围: {track_category or 'ALL'} {track_direction or 'ALL'}")
    print(f"{'='*70}\n")

    # 创建追踪器（追踪所有订单，后续再筛选）
    tracker = OrderTracker(enabled=True, track_order_ids=track_specific_ids)

    # 创建仿真环境
    env = simpy.Environment()
    sim = DCSimulation(env, scenario_config, run_id=1, order_tracker=tracker)

    # 运行仿真
    result = sim.run(duration_days=duration_days, target_month=target_month)

    print(f"\n仿真完成！追踪到 {len(tracker.order_summary)} 个订单, {len(tracker.event_log)} 个事件")

    return tracker, sim, result


def export_tracking_results(tracker, output_path=None, 
                            highlight_category='FG', 
                            highlight_direction='Outbound'):
    """
    导出追踪结果到Excel（增强版，增加筛选sheet和延误分析）。

    Args:
        tracker: OrderTracker 实例
        output_path: 输出文件路径
        highlight_category: 重点展示的类别
        highlight_direction: 重点展示的方向
    """
    if output_path is None:
        output_path = os.path.join(RESULTS_DIR, 'order_flow_tracking.xlsx')

    if not tracker.event_log:
        print("无事件日志可导出")
        return

    print(f"\n导出追踪结果到: {output_path}")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # ===== Sheet 1: 全部订单汇总 =====
        summary_df = pd.DataFrame(list(tracker.order_summary.values()))
        if not summary_df.empty:
            summary_df.to_excel(writer, sheet_name='Order_Summary', index=False)
            print(f"  Order_Summary: {len(summary_df)} 个订单")

        # ===== Sheet 2: 完整事件日志 =====
        log_df = pd.DataFrame(tracker.event_log)
        log_df.to_excel(writer, sheet_name='Event_Log', index=False)
        print(f"  Event_Log: {len(log_df)} 个事件")

        # ===== Sheet 3: FG Outbound 订单筛选 =====
        if not summary_df.empty:
            fg_out = summary_df[
                (summary_df['category'] == highlight_category) & 
                (summary_df['direction'] == highlight_direction)
            ].copy()
            if not fg_out.empty:
                fg_out.to_excel(writer, sheet_name=f'{highlight_category}_{highlight_direction}_Summary', index=False)
                print(f"  {highlight_category}_{highlight_direction}_Summary: {len(fg_out)} 个订单")

        # ===== Sheet 4: 延误订单分析 =====
        if not summary_df.empty and 'on_time' in summary_df.columns:
            delayed = summary_df[summary_df['on_time'] == False].copy()
            if not delayed.empty:
                delayed.to_excel(writer, sheet_name='Delayed_Orders', index=False)
                print(f"  Delayed_Orders: {len(delayed)} 个延误订单")

        # ===== Sheet 5-6: 挑选示例订单（一个on-time，一个delayed） =====
        fg_out_orders = [oid for oid, s in tracker.order_summary.items() 
                         if s.get('category') == highlight_category 
                         and s.get('direction') == highlight_direction]
        
        # 找一个准时订单作为示例（pallets > 25 更有展示效果）
        on_time_example = None
        delayed_example = None
        for oid in fg_out_orders:
            s = tracker.order_summary[oid]
            pallets = s.get('pallets', 0)
            if s.get('on_time') is True and on_time_example is None and pallets > 25:
                on_time_example = oid
            elif s.get('on_time') is False and delayed_example is None and pallets > 25:
                delayed_example = oid
            if on_time_example and delayed_example:
                break
        # fallback: 如果没找到大订单, 用任意
        if on_time_example is None:
            on_time_example = next((oid for oid in fg_out_orders 
                                    if tracker.order_summary[oid].get('on_time') is True), None)
        if delayed_example is None:
            delayed_example = next((oid for oid in fg_out_orders 
                                     if tracker.order_summary[oid].get('on_time') is False), None)

        for label, example_id in [('OnTime_Example', on_time_example), ('Delayed_Example', delayed_example)]:
            if example_id:
                example_events = [e for e in tracker.event_log if e['order_id'] == example_id]
                if example_events:
                    ex_df = pd.DataFrame(example_events)
                    ex_df.to_excel(writer, sheet_name=label, index=False)
                    
                    # 叙述
                    narrative = tracker._generate_narrative(example_id)
                    nar_df = pd.DataFrame({f'{label} Narrative': narrative})
                    nar_df.to_excel(writer, sheet_name=f'{label}_Narrative', index=False)
                    
                    print(f"  {label}: {example_id} ({len(example_events)} events)")

    print(f"\n✅ 导出完成: {output_path}")
    return output_path


def print_example_order_flow(tracker, order_id=None, category='FG', direction='Outbound'):
    """
    在终端打印一个示例订单的完整流程（用于快速预览）。

    Args:
        tracker: OrderTracker 实例
        order_id: 指定订单ID（None=自动选择第一个匹配的）
        category: 筛选类别
        direction: 筛选方向
    """
    if order_id is None:
        # 自动选择一个有代表性的订单（pallets > 20，便于展示prep过程）
        candidates = [
            (oid, s) for oid, s in tracker.order_summary.items()
            if s.get('category') == category and s.get('direction') == direction
            and s.get('pallets', 0) > 20
        ]
        if candidates:
            # 优先选一个delayed的（更有故事性）
            delayed_candidates = [(oid, s) for oid, s in candidates if s.get('on_time') is False]
            if delayed_candidates:
                order_id = delayed_candidates[0][0]
            else:
                order_id = candidates[0][0]

    if order_id is None:
        print("未找到匹配的订单")
        return

    summary = tracker.order_summary.get(order_id, {})
    events = [e for e in tracker.event_log if e['order_id'] == order_id]

    print(f"\n{'='*80}")
    print(f"📦 Order Flow Example: {order_id}")
    print(f"{'='*80}")
    print(f"Category: {summary.get('category')} | Direction: {summary.get('direction')}")
    print(f"Pallets: {summary.get('pallets')} | Region: {summary.get('region', 'N/A')}")
    print(f"Scheduled Timeslot: {summary.get('scheduled_timeslot')} | Actual: {summary.get('actual_timeslot')}")
    print(f"On-time: {summary.get('on_time')} | Delay: {summary.get('delay_hours', 0)}h")
    print(f"{'='*80}")

    for i, e in enumerate(events, 1):
        icon = {
            'ORDER_ARRIVED': '📥',
            'DISPATCHED': '🚀',
            'PREP_START': '🔧',
            'PREP_PROGRESS': '⚙️',
            'PREP_DC_CLOSED': '🌙',
            'PREP_TIMESLOT_REACHED': '⏰',
            'PREP_COMPLETE': '✅',
            'LOADING_WAIT_TIMESLOT': '⏳',
            'LOADING_PREP_READY': '✅',
            'LOADING_PREP_NOT_READY': '❌',
            'LOADING_RESCHEDULED': '🔄',
            'LOADING_WAIT_CAPACITY': '🚧',
            'LOADING_START': '🚛',
            'LOADING_COMPLETE': '🎉',
            'INBOUND_ARRIVAL': '📥',
            'INBOUND_UNLOADING': '📦',
            'INBOUND_PROCESSING_START': '🔧',
            'INBOUND_DC_CLOSED': '🌙',
            'INBOUND_DEADLINE_EXCEEDED': '❌',
            'INBOUND_COMPLETE': '✅',
        }.get(e['event_type'], '📌')

        print(f"  {icon} Step {i:2d} | {e['readable_time']:>15s} | {e['event_type']:<25s}")
        print(f"          | {e['details']}")
        print()

    if summary.get('on_time') is True:
        print(f"  ✅ RESULT: Order completed ON TIME")
    elif summary.get('on_time') is False:
        print(f"  ⚠️ RESULT: Order DELAYED by {summary.get('delay_hours', 0)} hours")
    print(f"{'='*80}\n")


# ==================== 主程序 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("DC 仿真 - 订单流程追踪器")
    print("用于演讲展示：详细跟踪FG Outbound订单的完整生命周期")
    print("=" * 70)

    # 运行仿真（Baseline场景，Month 1，追踪所有订单）
    tracker, sim, result = run_order_tracking(
        scenario_name='baseline',
        target_month=1,
        duration_days=30,
        track_category='FG',
        track_direction='Outbound',
        seed=42
    )

    # 导出到Excel
    output_path = export_tracking_results(tracker)

    # 在终端展示一个示例订单的完整流程
    print_example_order_flow(tracker, category='FG', direction='Outbound')

    # 打印统计摘要
    fg_out = {oid: s for oid, s in tracker.order_summary.items() 
              if s.get('category') == 'FG' and s.get('direction') == 'Outbound'}
    
    total = len(fg_out)
    completed = sum(1 for s in fg_out.values() if s.get('completed'))
    on_time = sum(1 for s in fg_out.values() if s.get('on_time') is True)
    delayed = sum(1 for s in fg_out.values() if s.get('on_time') is False)
    
    print(f"\n📊 FG Outbound 统计:")
    print(f"  总订单数: {total}")
    print(f"  已完成: {completed}")
    print(f"  准时: {on_time} ({on_time/total*100:.1f}%)" if total else "  准时: 0")
    print(f"  延误: {delayed} ({delayed/total*100:.1f}%)" if total else "  延误: 0")
    print(f"\n输出文件: {output_path}")
