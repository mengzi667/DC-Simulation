#!/usr/bin/env python3
"""
演示：动态优先级队列调度
展示订单如何按creation_time逐步到达，并被动态放入优先级队列处理
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import numpy as np
import simpy
from dc_simulation_plot_update import DCSimulation

def demonstrate_dynamic_scheduling():
    """演示动态优先级队列调度"""
    print("\n" + "="*110)
    print("演示：Outbound订单的动态优先级队列调度")
    print("="*110)
    print("""
场景说明：
  - 订单数据预生成（代表了整月的订单）
  - 但在仿真中，订单按 creation_time 逐步到达（工厂每隔一段时间收到新订单）
  - FTE 看不到未来的订单，只能从已到达的订单中选择处理优先级最高的
  
调度算法：
  1. 订单到达 → 加入优先级队列（优先级 = latest_start_time）
  2. FTE空闲 → 从队列中选择 latest_start_time 最早的订单处理
  3. 这样保证了时间窗口最紧张的订单优先处理
  
预期效果：
  ✓ 减少时间紧张订单的延误
  ✓ 更好地利用 FTE 资源
  ✓ 模拟工厂的真实决策过程
    """)
    
    print("\n启动仿真...\n")
    
    # 创建仿真环境
    env = simpy.Environment()
    
    # 配置
    scenario_config = {
        'name': '动态优先级队列演示',
        'dc_open_time': 6,
        'dc_close_time': 24,
        'operating_hours': 18,
        'arrival_smoothing': False
    }
    
    # 创建仿真
    sim = DCSimulation(env, scenario_config, run_id=1)
    
    print("""
注意查看仿真输出中的两部分日志：
  
  [时刻 XXXh] 订单到达：...
    ↓ 表示订单动态到达，被加入优先级队列
    
  [时刻 XXXh] 开始处理：...
    ↓ 表示 FTE 从队列中选择优先级最高的订单进行备货
    
观察要点：
  1. 订单到达时间不一定，有早有晚
  2. 处理顺序≠到达顺序（按优先级重新排列）
  3. 优先级高的（latest_start最早）会被优先处理
    """)
    
    print("\n" + "="*110)
    print("【仿真日志开始】")
    print("="*110 + "\n")
    
    # 运行仿真（3天的数据）
    sim.env.process(sim.inbound_order_scheduler(target_month=1))
    sim.env.process(sim.outbound_order_scheduler(target_month=1))
    
    env.run(until=3 * 24)  # 仿真 3 天
    
    print("\n" + "="*110)
    print("【仿真日志结束】")
    print("="*110)
    
    print("""
分析：
  ✓ 看到 [订单到达] 事件表示订单动态被添加到队列
  ✓ 看到 [开始处理] 事件表示 FTE 按优先级选择订单
  ✓ 队列剩余数 = 当前在队列中等待的订单数
  ✓ 处理序号 = 这是第几个被选中处理的订单
  
这就是动态优先级队列调度的效果！
    """)

if __name__ == '__main__':
    try:
        demonstrate_dynamic_scheduling()
    except KeyboardInterrupt:
        print("\n\n仿真被中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
