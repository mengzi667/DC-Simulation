"""测试等待时间问题的诊断脚本"""
import sys
sys.path.insert(0, 'src')

from dc_simulation import DCSimulation, SIMULATION_CONFIG
import numpy as np
import simpy

# 设置随机种子
np.random.seed(42)

# 运行一次基准场景
config = SIMULATION_CONFIG['baseline']
print(f"运行场景: {config['name']}")
print(f"DC运营时间: {config['dc_open_time']}:00 - {config['dc_close_time']}:00\n")

env = simpy.Environment()
sim = DCSimulation(env, config, run_id=1)
summary = sim.run(duration_days=1)  # 只运行1天

# 分析等待时间
if sim.kpi.truck_wait_times:
    wait_times = [w['wait_time'] for w in sim.kpi.truck_wait_times]
    print(f"卡车数量: {len(wait_times)}")
    print(f"平均等待时间: {np.mean(wait_times):.2f} 小时 ({np.mean(wait_times)*60:.0f} 分钟)")
    print(f"最大等待时间: {np.max(wait_times):.2f} 小时 ({np.max(wait_times)*60:.0f} 分钟)")
    print(f"中位数等待时间: {np.median(wait_times):.2f} 小时 ({np.median(wait_times)*60:.0f} 分钟)")
    print(f"95分位等待时间: {np.percentile(wait_times, 95):.2f} 小时 ({np.percentile(wait_times, 95)*60:.0f} 分钟)")
    
    # 找出等待超过1小时的卡车
    long_waits = [w for w in sim.kpi.truck_wait_times if w['wait_time'] > 1]
    if long_waits:
        print(f"\n等待超过1小时的卡车: {len(long_waits)}")
        for w in long_waits[:5]:  # 只显示前5个
            print(f"  {w['category']}: 等待 {w['wait_time']:.2f} 小时 ({w['wait_time']*60:.0f} 分钟)")
else:
    print("没有记录到等待时间数据")

# 分析出库操作
if sim.kpi.outbound_operations:
    print(f"\n出库操作数: {len(sim.kpi.outbound_operations)}")
    durations = [(op['start_time'] - op['scheduled_time']) for op in sim.kpi.outbound_operations]
    print(f"平均装车耗时: {np.mean(durations):.2f} 小时")
