# Scenario 设定说明（按 3 个大 case）

本文档按你要求，**只分成三个大 case** 来解释所有 scenario 设定：

1) **只改时间窗（Time Window Only）**：只动 `dc_open_time/dc_close_time/operating_hours`，不动效率、不动需求分布。
2) **更改 FTE / 效率（FTE Efficiency Change）**：不改开门时间窗，改“单位时间产能/效率的缩放”。
3) **砍 shift / 周期性关门（Shift Cancel / Dynamic Closures）**：在基础时间窗之上，按星期与周期把某些时段关门。

参考位置：
- 基础时间窗场景： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L46-L141) 的 `SIMULATION_CONFIG`
- 系统参数（效率/到达率/码头能力/FTE 等）： [outputs/simulation_configs/simulation_config.json](outputs/simulation_configs/simulation_config.json)

---

## Case 1：只改时间窗（Time Window Only）

**定义方式**：直接在 `SIMULATION_CONFIG` 里定义，每个场景只包含：

- `dc_open_time` / `dc_close_time`：每天开门/关门小时
- `operating_hours`：每天运营小时（通常等于 `dc_close_time - dc_open_time`）
- `arrival_smoothing`：目前这些基础场景全部是 `False`

**本 case 的口径**：
- 只改变“供给窗口”（DC 可操作时间）；订单/timeslot 分布不变。

### Case 1.1 Baseline

| key | name | open-close | operating_hours |
|---|---|---:|---:|
| `baseline` | Baseline (06:00-24:00) | 06–24 | 18 |

### Case 1.2 固定开始 06:00，逐步提前结束（Fixed Start)

| key | name | open-close | operating_hours |
|---|---|---:|---:|
| `fixed_06_23` | Fixed Start (06:00-23:00) | 06–23 | 17 |
| `fixed_06_22` | Fixed Start (06:00-22:00) | 06–22 | 16 |
| `fixed_06_21` | Fixed Start (06:00-21:00) | 06–21 | 15 |
| `fixed_06_20` | Fixed Start (06:00-20:00) | 06–20 | 14 |

### Case 1.3 开始时间后移（Shifted Start：07:00 / 08:00）

| key | name | open-close | operating_hours |
|---|---|---:|---:|
| `shift_07_23` | Shifted (07:00-23:00) | 07–23 | 16 |
| `shift_07_22` | Shifted (07:00-22:00) | 07–22 | 15 |
| `shift_07_21` | Shifted (07:00-21:00) | 07–21 | 14 |
| `shift_08_23` | Shifted (08:00-23:00) | 08–23 | 15 |
| `shift_08_22` | Shifted (08:00-22:00) | 08–22 | 14 |
| `shift_08_21` | Shifted (08:00-21:00) | 08–21 | 13 |
| `shift_08_20` | Shifted (08:00-20:00) | 08–20 | 12 |

---

## Case 2：更改 FTE / 效率（FTE Efficiency Change）

**定义方式**：通过 scenario transform 注入参数；不新增基础场景 key。

函数定义位置： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L2350-L2358)

### Case 2.1 FTE 幂律（FTE power-law）

函数：`_scenario_transform_fte_power(alpha, baseline_hours)`

注入字段：
- `fte_efficiency_alpha`
- `fte_efficiency_baseline_hours`

### Case 2.1.1 在模型里具体怎么算（公式 + 代码位置）

这一块的核心是：**在“FTE 数量已经按运营小时线性缩放（成本节约型）”的基础上**，再额外给每小时产能乘一个幂律倍数。

代码入口在 DC 仿真实例初始化时计算 `efficiency_multiplier`，然后传入 `FTEManager(...)`：
- 计算位置： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L1058-L1075)
- `FTEManager.get_hourly_capacity()` 最终把该倍数乘进每小时处理能力： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L514-L521)

定义：
- 设基准运营小时为 $H_0$（默认 18 小时，由 `fte_efficiency_baseline_hours` 决定）
- 设当前场景运营小时为 $H$（即 `operating_hours`）
- 设比例 $r = \frac{H}{H_0}$

模型里计算的“效率倍数”为：
$$
	ext{efficiency\_multiplier} = r^{(\alpha - 1)}
$$

同时，`FTEManager` 会把“有效 FTE 数”按运营小时线性缩放：
$$
	ext{adjusted\_fte} = \text{baseline\_fte} \cdot r
$$

因此，**每小时处理能力（pallet/h）** 的缩放关系可以理解为：
$$
	ext{hourly\_capacity} \propto r \cdot r^{(\alpha - 1)} = r^{\alpha}
$$

直观解释：
- `alpha = 1.0`：回到原逻辑（线性缩放）。
- `alpha < 1.0`：运营小时变短时，每小时产能下降得“没那么多”（相当于更高强度、更集中的工作；hourly cap 比线性更高）。
- `alpha > 1.0`：运营小时变短时，每小时产能下降得“更多”（疲劳/交接损耗/效率恶化；hourly cap 比线性更低）。

### Case 2.1.2 alpha 在项目里怎么取值（当前实现口径）

本项目目前的 alpha 不是从数据自动拟合出来的，而是做 **sensitivity sweep（敏感性扫描）**：

- alpha 列表在主程序里写死为 `FTE_POWER_ALPHAS = [0.9, 0.8, 0.7]`
- 基准小时为 `FTE_POWER_BASELINE_HOURS = 18`

代码位置： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L3822-L3856)

也就是说，我们用 3 个不同的 $\alpha$ 值来覆盖“压缩工时后，每小时效率能提升多少/能否保持强度”的不同假设区间，然后把结果与 baseline 同图对比。

如果你后续想用数据去标定 alpha，一种常见做法是拿“可观测吞吐/产能 vs 运营小时”的历史数据，拟合关系 $\text{hourly\_capacity} \propto r^{\alpha}$（取对数就是线性回归）。

---

## Case 3：砍 shift / 周期性关门（Shift Cancel / Dynamic Closures）

这一类不是“新时间窗场景”，而是 **在 Case 1 的基础时间窗之上叠加**：某些 weekday 的某些小时段临时关门。

### Case 3.1 规则在代码里如何生效（每日窗口扣减）

默认每日开门窗口是一个区间：`[dc_open_time, dc_close_time)`。

当场景配置包含以下任意字段时：
- `biweekly_shift_cancel`（单条规则，向后兼容）
- `shift_cancel_rules`（多条规则，推荐；用于多个 weekday）

则每日窗口会在 `_compute_daily_open_windows()` 里被“扣掉”关门区间，形成当天可能为 0 段/1 段/多段的开门窗口。

实现位置： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L145-L209)

规则匹配要点：
- `weekday`：0=Mon … 6=Sun
- `day1_weekday`：声明仿真 Day1 对应真实星期几
- `week_index = day_index // 7`
- 生效条件：`week_index >= start_week_index` 且 `(week_index - start_week_index) % every_n_weeks == 0`

### Case 3.2 单规则格式：biweekly_shift_cancel

字段（每条规则）：
- `day1_weekday`
- `weekday`
- `start_week_index`
- `every_n_weeks`
- `cancel_start_hour`
- `cancel_end_hour`（缺省时用 `dc_close_time`）

### Case 3.3 多规则格式：shift_cancel_rules

结构：`shift_cancel_rules = [rule1, rule2, ...]`。

每个 rule 的字段与 `biweekly_shift_cancel` 相同。

### Case 3.4 本项目里已有的砍班策略（Transforms）

这些 transform 定义在： [src/dc_simulation_plot_update.py](src/dc_simulation_plot_update.py#L2360-L2467)

共同口径：
- **不压缩、不迁移 timeslot 需求**（Scenario A）：需求不变，只改供给窗口。

1) **每两周周五砍晚班（15:00–关门）**
	- 函数：`_scenario_transform_biweekly_cancel_friday_late_shift(...)`
	- 注入：`biweekly_shift_cancel`（weekday=4 Friday；`cancel_start_hour=15`；`cancel_end_hour=dc_close_time`）
	- 默认：Day1=周一（`day1_weekday=0`），从第二个周五开始（`start_week_index=1`），每两周一次（`every_n_weeks=2`）

2) **每周周五砍晚班（15:00–关门）**
	- 函数：`_scenario_transform_weekly_cancel_friday_late_shift(...)`
	- 等价于：把上面规则改成每周生效（`start_week_index=0`，`every_n_weeks=1`）

3) **每周周五整天不开门（全关）**
	- 函数：`_scenario_transform_weekly_cancel_friday_full_day(...)`
	- 注入：`biweekly_shift_cancel`，但关门区间是 `[dc_open_time, dc_close_time)`

4) **每周周二 + 周四砍晚班（15:00–关门）**
	- 函数：`_scenario_transform_weekly_cancel_tue_thu_late_shift(...)`
	- 注入：`shift_cancel_rules`（两条 rule：weekday=1 Tue、weekday=3 Thu；每周生效）

---

## 附：常见误解澄清（只保留与三大 case 直接相关的）

1) JSON 配置文件不是场景定义
- [outputs/simulation_configs/simulation_config.json](outputs/simulation_configs/simulation_config.json) 主要改变系统参数（效率、到达率、小时码头容量、FTE 等），不决定场景集合。

2) Case 3（砍 shift）不是 Case 1 的“新时间窗场景”
- 它是对 Case 1 的开门窗口做按日扣减；因此同一个基础时间窗可以叠加不同砍班策略。
