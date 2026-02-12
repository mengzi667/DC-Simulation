"""
Generate FG Outbound Order Flow Diagrams for Presentation
- General process flow chart
- Two example order timelines (on-time vs delayed)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)

# ===================== Color Palette =====================
C_BG = '#FAFBFC'
C_BLUE = '#4A90D9'
C_GREEN = '#27AE60'
C_ORANGE = '#F39C12'
C_RED = '#E74C3C'
C_PURPLE = '#8E44AD'
C_GRAY = '#95A5A6'
C_DARK = '#2C3E50'
C_LIGHT_BLUE = '#D6EAF8'
C_LIGHT_GREEN = '#D5F5E3'
C_LIGHT_ORANGE = '#FDEBD0'
C_LIGHT_RED = '#FADBD8'
C_LIGHT_PURPLE = '#E8DAEF'


def draw_general_flow_chart():
    """Draw the general FG Outbound process flow chart."""
    fig, ax = plt.subplots(1, 1, figsize=(18, 10))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Title
    ax.text(9, 9.5, 'FG Outbound Order Flow Logic', fontsize=22, fontweight='bold',
            ha='center', va='center', color=C_DARK)

    # ---- Boxes ----
    box_style = dict(boxstyle="round,pad=0.4", linewidth=2)

    boxes = [
        # (x, y, width, height, text, facecolor, edgecolor, fontsize)
        (0.5, 7.0, 3.0, 1.3, '1  Order Created\n(by system/customer)\nCreation Time recorded', C_LIGHT_BLUE, C_BLUE, 11),
        (4.5, 7.0, 3.0, 1.3, '2  Priority Queue\nSorted by\nLatest Start Time', C_LIGHT_BLUE, C_BLUE, 11),
        (8.5, 7.0, 3.0, 1.3, '3  Dispatched\nto FTE Team\n(highest priority first)', C_LIGHT_PURPLE, C_PURPLE, 11),
        (0.5, 4.2, 3.0, 1.5, '4  Preparation\n(FTE picks pallets)\nOnly during DC open hours\nCapacity ~ 170 p/h', C_LIGHT_GREEN, C_GREEN, 10),
        (4.5, 4.2, 3.0, 1.5, '5  Wait for Timeslot\n(if prep done early,\nwait until scheduled\ntimeslot hour)', C_LIGHT_ORANGE, C_ORANGE, 10),
        (8.5, 4.2, 3.0, 1.5, '6  Dock Check\nIs Loading Dock\navailable this hour?\n(capacity = 1-3/h)', C_LIGHT_ORANGE, C_ORANGE, 10),
        (8.5, 1.2, 3.0, 1.3, '7  Loading\n(1 hour at dock)\nTruck departs', C_LIGHT_GREEN, C_GREEN, 11),
    ]

    for (x, y, w, h, txt, fc, ec, fs) in boxes:
        fancy = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                               facecolor=fc, edgecolor=ec, linewidth=2.5)
        ax.add_patch(fancy)
        ax.text(x + w / 2, y + h / 2, txt, fontsize=fs, ha='center', va='center',
                color=C_DARK, fontweight='bold', linespacing=1.4)

    # ---- Decision diamond (prep complete?) ----
    diamond_x, diamond_y = 4.5, 1.6
    diamond = plt.Polygon([[diamond_x + 1.5, diamond_y + 1.1],
                            [diamond_x + 3.0, diamond_y + 0.55],
                            [diamond_x + 1.5, diamond_y + 0.0],
                            [diamond_x + 0.0, diamond_y + 0.55]],
                           closed=True, facecolor=C_LIGHT_RED, edgecolor=C_RED, linewidth=2.5)
    ax.add_patch(diamond)
    ax.text(diamond_x + 1.5, diamond_y + 0.55, 'Prep done\nbefore\ntimeslot?',
            fontsize=10, ha='center', va='center', color=C_DARK, fontweight='bold')

    # ---- Reschedule box ----
    rx, ry, rw, rh = 12.5, 4.2, 3.5, 1.5
    fancy_r = FancyBboxPatch((rx, ry), rw, rh, boxstyle="round,pad=0.15",
                             facecolor=C_LIGHT_RED, edgecolor=C_RED, linewidth=2.5)
    ax.add_patch(fancy_r)
    ax.text(rx + rw / 2, ry + rh / 2,
            'RESCHEDULE\nPrep not done on time\n-> Find next available\ntimeslot (DELAYED)',
            fontsize=10, ha='center', va='center', color=C_RED, fontweight='bold', linespacing=1.3)

    # ---- Wait box (dock full) ----
    wx, wy, ww, wh = 12.5, 1.2, 3.5, 1.3
    fancy_w = FancyBboxPatch((wx, wy), ww, wh, boxstyle="round,pad=0.15",
                             facecolor=C_LIGHT_ORANGE, edgecolor=C_ORANGE, linewidth=2.5)
    ax.add_patch(fancy_w)
    ax.text(wx + ww / 2, wy + wh / 2,
            'DOCK QUEUE\nWait until next hour\nwith available dock',
            fontsize=10, ha='center', va='center', color=C_ORANGE, fontweight='bold', linespacing=1.3)

    # ---- Arrows ----
    arrow_kw = dict(arrowstyle='->', color=C_DARK, lw=2.2, mutation_scale=18)

    # ①→②
    ax.annotate('', xy=(4.5, 7.65), xytext=(3.5, 7.65), arrowprops=arrow_kw)
    # ②→③
    ax.annotate('', xy=(8.5, 7.65), xytext=(7.5, 7.65), arrowprops=arrow_kw)
    # ③→④
    ax.annotate('', xy=(2.0, 5.7), xytext=(10.0, 7.0),
                arrowprops=dict(arrowstyle='->', color=C_DARK, lw=2.2, mutation_scale=18,
                                connectionstyle='arc3,rad=0.25'))
    # ④→⑤
    ax.annotate('', xy=(4.5, 4.95), xytext=(3.5, 4.95), arrowprops=arrow_kw)

    # ⑤ → Decision diamond
    ax.annotate('', xy=(6.0, 2.7), xytext=(6.0, 4.2), arrowprops=arrow_kw)

    # Decision YES → ⑥
    ax.annotate('', xy=(8.5, 4.95), xytext=(7.5, 2.15),
                arrowprops=dict(arrowstyle='->', color=C_GREEN, lw=2.5, mutation_scale=18,
                                connectionstyle='arc3,rad=-0.3'))
    ax.text(8.0, 3.3, 'YES ✓', fontsize=11, color=C_GREEN, fontweight='bold')

    # Decision NO → Reschedule
    ax.annotate('', xy=(12.5, 4.95), xytext=(7.5, 2.15),
                arrowprops=dict(arrowstyle='->', color=C_RED, lw=2.5, mutation_scale=18,
                                connectionstyle='arc3,rad=0.15'))
    ax.text(10.2, 2.7, 'NO ✗', fontsize=11, color=C_RED, fontweight='bold')

    # Reschedule → ⑥ (loop back)
    ax.annotate('', xy=(10.0, 5.7), xytext=(12.5, 4.95),
                arrowprops=dict(arrowstyle='->', color=C_RED, lw=2, mutation_scale=15,
                                connectionstyle='arc3,rad=0.3', linestyle='dashed'))

    # ⑥ → ⑦ (dock available)
    ax.annotate('', xy=(10.0, 2.5), xytext=(10.0, 4.2), arrowprops=arrow_kw)
    ax.text(10.15, 3.2, 'Available', fontsize=9, color=C_GREEN, fontweight='bold')

    # ⑥ → Dock Queue (dock full)
    ax.annotate('', xy=(12.5, 1.85), xytext=(11.5, 4.4),
                arrowprops=dict(arrowstyle='->', color=C_ORANGE, lw=2, mutation_scale=15,
                                connectionstyle='arc3,rad=-0.2'))
    ax.text(12.5, 3.4, 'Full', fontsize=9, color=C_ORANGE, fontweight='bold')

    # Dock Queue → ⑥ (retry next hour)
    ax.annotate('', xy=(11.5, 5.2), xytext=(14.25, 2.5),
                arrowprops=dict(arrowstyle='->', color=C_ORANGE, lw=2, mutation_scale=15,
                                connectionstyle='arc3,rad=-0.4', linestyle='dashed'))

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, 'fg_outbound_flow_chart.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f'Saved: {path}')
    return path


def draw_timeline_comparison():
    """Draw side-by-side timeline comparison of on-time vs delayed order."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 9))
    fig.patch.set_facecolor(C_BG)
    fig.suptitle('FG Outbound: On-Time vs Delayed — Order Lifecycle Comparison',
                 fontsize=18, fontweight='bold', color=C_DARK, y=0.97)

    def draw_one_timeline(ax, title, events, total_hours_range, highlight_color, result_text):
        ax.set_facecolor(C_BG)
        ax.set_title(title, fontsize=14, fontweight='bold', color=highlight_color, pad=12)

        # events: list of (start_h, end_h, label, color, icon)
        n = len(events)
        y_positions = list(range(n - 1, -1, -1))

        for i, (start, end, label, color, icon) in enumerate(events):
            y = y_positions[i]
            duration = end - start
            bar_height = 0.6

            # Draw bar
            ax.barh(y, duration, left=start, height=bar_height,
                    color=color, edgecolor='white', linewidth=1.5, alpha=0.85, zorder=3)

            # Label inside/outside bar
            mid = start + duration / 2
            if duration > (total_hours_range[1] - total_hours_range[0]) * 0.08:
                ax.text(mid, y, f'{icon} {label}', ha='center', va='center',
                        fontsize=9, fontweight='bold', color='white', zorder=4)
            else:
                ax.text(end + 0.3, y, f'{icon} {label}', ha='left', va='center',
                        fontsize=9, fontweight='bold', color=color, zorder=4)

            # Time annotation
            if duration >= 0.5:
                time_str = f'{duration:.1f}h'
            elif duration > 0:
                time_str = f'{duration * 60:.0f}min'
            else:
                time_str = ''
            if time_str:
                ax.text(start + duration / 2, y - 0.38, time_str,
                        ha='center', va='top', fontsize=8, color=C_GRAY, zorder=4)

        ax.set_xlim(total_hours_range)
        ax.set_ylim(-0.8, n - 0.3)
        ax.set_yticks([])

        # X-axis: convert sim hours to Day X, HH:00
        x_min, x_max = total_hours_range
        tick_step = max(1, int((x_max - x_min) / 12))
        xticks = np.arange(int(x_min), int(x_max) + 1, tick_step)
        xlabels = []
        for h in xticks:
            day = h // 24 + 1
            hour = h % 24
            xlabels.append(f'D{day} {hour:02d}:00')
        ax.set_xticks(xticks)
        ax.set_xticklabels(xlabels, fontsize=8, rotation=45, ha='right')
        ax.set_xlabel('Simulation Time', fontsize=10, color=C_DARK)

        # Timeslot marker
        for i, (start, end, label, color, icon) in enumerate(events):
            if 'Timeslot' in label or 'Loading' in label:
                if 'Loading' in label and icon == '🚛':
                    ax.axvline(x=start, color=C_DARK, linestyle='--', alpha=0.3, zorder=1)

        # Result text box
        ax.text(0.98, 0.02, result_text, transform=ax.transAxes,
                fontsize=12, fontweight='bold', ha='right', va='bottom',
                color=highlight_color,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor=highlight_color, alpha=0.9))

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.grid(axis='x', alpha=0.2)

    # ===== Example 1: On-Time (Order 00057) =====
    # Day 2 = hour 24. Creation = 26.33 (Day 2, 02:20)
    events1 = [
        (26.33, 30.0, 'DC Closed - Wait', C_GRAY, '[WAIT]'),
        (30.0,  30.43, 'Preparation (70p)', C_GREEN, '[PREP]'),
        (30.43, 37.0,  'Wait for Timeslot', C_ORANGE, '[IDLE]'),
        (37.0,  38.0,  'Loading @ Dock', C_BLUE, '[LOAD]'),
    ]
    draw_one_timeline(ax1,
                      'On-Time: Order 00057\n70 pallets | G2 Same-Day | Timeslot Day 2 13:00',
                      events1, (25, 39), C_GREEN,
                      'ON TIME\nDelay: 0h')

    # Add timeslot marker
    ax1.axvline(x=37.0, color=C_GREEN, linestyle='--', linewidth=2, alpha=0.5, zorder=1)
    ax1.text(37.0, 3.7, 'Scheduled\nTimeslot', ha='center', fontsize=8, color=C_GREEN, fontweight='bold')

    # ===== Example 2: Delayed (Order 00533) =====
    # Day 14 = hour 312. Creation = 320.73 (Day 14, 08:44)
    events2 = [
        (320.73, 321.02, 'Preparation (52p)', C_GREEN, '[PREP]'),
        (321.02, 327.0,  'Wait for Timeslot', C_ORANGE, '[IDLE]'),
        (327.0,  356.0,  'Dock Full - Queue 29h!', C_RED, '[QUEUE]'),
        (356.0,  357.0,  'Loading @ Dock', C_BLUE, '[LOAD]'),
    ]
    draw_one_timeline(ax2,
                      'Delayed: Order 00533\n52 pallets | G2 Same-Day | Timeslot Day 14 15:00',
                      events2, (319, 358), C_RED,
                      'DELAYED\nDelay: 29h')

    # Add timeslot markers
    ax2.axvline(x=327.0, color=C_GREEN, linestyle='--', linewidth=2, alpha=0.5, zorder=1)
    ax2.text(327.0, 3.7, 'Scheduled\nTimeslot', ha='center', fontsize=8, color=C_GREEN, fontweight='bold')
    ax2.axvline(x=356.0, color=C_RED, linestyle='--', linewidth=2, alpha=0.5, zorder=1)
    ax2.text(356.0, 3.7, 'Actual\nLoading', ha='center', fontsize=8, color=C_RED, fontweight='bold')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    path = os.path.join(FIGURES_DIR, 'fg_outbound_timeline_comparison.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f'Saved: {path}')
    return path


def draw_summary_table():
    """Draw a comparison summary table as an image."""
    fig, ax = plt.subplots(1, 1, figsize=(16, 7))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.axis('off')

    ax.text(0.5, 0.96, 'FG Outbound — Two Example Orders Comparison',
            fontsize=18, fontweight='bold', ha='center', va='top',
            transform=ax.transAxes, color=C_DARK)

    columns = ['Metric', 'Order 00057 (On-Time)', 'Order 00533 (Delayed)']
    rows = [
        ['Pallets',              '70',                      '52'],
        ['Region',               'G2 Same-Day',             'G2 Same-Day'],
        ['Order Created',        'Day 2, 02:20',            'Day 14, 08:44'],
        ['Scheduled Timeslot',   'Day 2, 13:00',            'Day 14, 15:00'],
        ['Prep Start',           'Day 2, 06:00 (DC opens)', 'Day 14, 08:44 (immediate)'],
        ['Prep Duration',        '0.43h (26 min)',           '0.29h (18 min)'],
        ['Prep Complete',        'Day 2, 06:25',            'Day 14, 09:02'],
        ['Idle before Timeslot', '6.57h (OK)',              '5.96h (OK)'],
        ['Dock at Timeslot',     'Available',                'FULL (3/3)'],
        ['Dock Queue Wait',      '0h',                      '29h (!!!)'],
        ['Actual Loading',       'Day 2, 13:00-14:00',      'Day 15, 20:00-21:00'],
        ['Total Delay',          '0h',                       '29h'],
        ['Result',               'ON TIME',                 'DELAYED'],
        ['Root Cause',           '-',                        'Loading Dock Saturation'],
    ]

    # Table colors
    cell_colors = []
    for i, row in enumerate(rows):
        if i == len(rows) - 1:  # Root cause row
            cell_colors.append([C_LIGHT_BLUE, C_LIGHT_GREEN, C_LIGHT_RED])
        elif i == len(rows) - 2:  # Result row
            cell_colors.append([C_LIGHT_BLUE, C_LIGHT_GREEN, C_LIGHT_RED])
        elif i % 2 == 0:
            cell_colors.append(['#F2F3F4', '#F2F3F4', '#F2F3F4'])
        else:
            cell_colors.append(['white', 'white', 'white'])

    table = ax.table(cellText=rows,
                     colLabels=columns,
                     cellColours=cell_colors,
                     colColours=[C_BLUE, C_GREEN, C_RED],
                     cellLoc='center',
                     loc='center',
                     bbox=[0.02, 0.02, 0.96, 0.88])

    table.auto_set_font_size(False)
    table.set_fontsize(11)

    # Style header
    for j in range(3):
        cell = table[0, j]
        cell.set_text_props(fontweight='bold', color='white', fontsize=12)
        cell.set_height(0.08)

    # Style all cells
    for i in range(len(rows)):
        for j in range(3):
            cell = table[i + 1, j]
            cell.set_height(0.06)
            cell.set_edgecolor('#D5D8DC')
            if j == 0:
                cell.set_text_props(fontweight='bold', color=C_DARK)

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, 'fg_outbound_comparison_table.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f'Saved: {path}')
    return path


# ===================== Main =====================
if __name__ == '__main__':
    print('Generating FG Outbound flow diagrams for presentation...\n')
    p1 = draw_general_flow_chart()
    p2 = draw_timeline_comparison()
    p3 = draw_summary_table()
    print(f'\n✅ All figures saved to: {FIGURES_DIR}')
    print(f'  1. {os.path.basename(p1)}  — General process flow chart')
    print(f'  2. {os.path.basename(p2)}  — Timeline comparison (on-time vs delayed)')
    print(f'  3. {os.path.basename(p3)}  — Summary comparison table')
