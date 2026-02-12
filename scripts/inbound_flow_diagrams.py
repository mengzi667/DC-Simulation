"""
Generate FG Inbound Order Flow Diagrams for Presentation
- General inbound process flow chart
- Two example order timelines (smooth vs dock-queue bottleneck)
- Summary comparison table
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
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
C_TEAL = '#1ABC9C'
C_LIGHT_TEAL = '#D1F2EB'


# ===================== Figure 1: General Inbound Flow Chart =====================
def draw_inbound_flow_chart():
    """Draw the general FG Inbound process flow chart."""
    fig, ax = plt.subplots(1, 1, figsize=(18, 10))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 10)
    ax.axis('off')

    ax.text(9, 9.5, 'FG Inbound Order Flow Logic', fontsize=22, fontweight='bold',
            ha='center', va='center', color=C_DARK)

    # ---- Main Process Boxes ----
    boxes = [
        # (x, y, width, height, text, facecolor, edgecolor, fontsize)
        (0.5, 7.0, 3.2, 1.3,
         '1  Truck Arrival\n(at scheduled timeslot)\nPallets on board',
         C_LIGHT_BLUE, C_BLUE, 11),

        (4.7, 7.0, 3.2, 1.3,
         '2  Reception Dock\nCheck\nIs dock available?',
         C_LIGHT_ORANGE, C_ORANGE, 11),

        (4.7, 4.0, 3.2, 1.5,
         '3  Unloading\n(fixed 1 hour)\nAll pallets offloaded\nto receiving area',
         C_LIGHT_TEAL, C_TEAL, 10),

        (4.7, 1.2, 3.2, 1.5,
         '4  FTE Put-Away\nProcessing\n(~170 p/h capacity)\nOnly during DC open hours',
         C_LIGHT_GREEN, C_GREEN, 10),

        (0.5, 1.2, 3.2, 1.3,
         '5  Complete\nAll pallets stored\n24h deadline met',
         C_LIGHT_BLUE, C_BLUE, 11),
    ]

    for (x, y, w, h, txt, fc, ec, fs) in boxes:
        fancy = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                               facecolor=fc, edgecolor=ec, linewidth=2.5)
        ax.add_patch(fancy)
        ax.text(x + w / 2, y + h / 2, txt, fontsize=fs, ha='center', va='center',
                color=C_DARK, fontweight='bold', linespacing=1.4)

    # ---- Dock Queue box (right side) ----
    qx, qy, qw, qh = 9.2, 7.0, 3.8, 1.3
    fancy_q = FancyBboxPatch((qx, qy), qw, qh, boxstyle="round,pad=0.15",
                             facecolor=C_LIGHT_RED, edgecolor=C_RED, linewidth=2.5)
    ax.add_patch(fancy_q)
    ax.text(qx + qw / 2, qy + qh / 2,
            'DOCK QUEUE\nWait for dock to free up\n(can be hours!)',
            fontsize=10, ha='center', va='center', color=C_RED, fontweight='bold', linespacing=1.3)

    # ---- DC Closed box (right side) ----
    dx, dy, dw, dh = 9.2, 1.2, 3.8, 1.5
    fancy_d = FancyBboxPatch((dx, dy), dw, dh, boxstyle="round,pad=0.15",
                             facecolor=C_LIGHT_ORANGE, edgecolor=C_ORANGE, linewidth=2.5)
    ax.add_patch(fancy_d)
    ax.text(dx + dw / 2, dy + dh / 2,
            'DC CLOSED\nFTE processing paused\nResumes at 06:00 next day\n(24h deadline still ticking)',
            fontsize=10, ha='center', va='center', color=C_ORANGE, fontweight='bold', linespacing=1.3)

    # ---- 24h deadline info box ----
    ix, iy, iw, ih = 9.2, 4.0, 3.8, 1.5
    fancy_i = FancyBboxPatch((ix, iy), iw, ih, boxstyle="round,pad=0.15",
                             facecolor='#FEF9E7', edgecolor=C_ORANGE, linewidth=2)
    ax.add_patch(fancy_i)
    ax.text(ix + iw / 2, iy + ih / 2,
            '24-HOUR DEADLINE\nStarts after unloading\nFTE must finish put-away\nwithin 24h window',
            fontsize=10, ha='center', va='center', color=C_DARK, fontweight='bold', linespacing=1.3)

    # ---- Arrows ----
    arrow_kw = dict(arrowstyle='->', color=C_DARK, lw=2.2, mutation_scale=18)

    # 1 -> 2
    ax.annotate('', xy=(4.7, 7.65), xytext=(3.7, 7.65), arrowprops=arrow_kw)

    # 2 -> 3 (available)
    ax.annotate('', xy=(6.3, 5.5), xytext=(6.3, 7.0), arrowprops=arrow_kw)
    ax.text(6.5, 6.1, 'Available', fontsize=9, color=C_GREEN, fontweight='bold')

    # 2 -> Dock Queue (full)
    ax.annotate('', xy=(9.2, 7.65), xytext=(7.9, 7.65),
                arrowprops=dict(arrowstyle='->', color=C_RED, lw=2.5, mutation_scale=18))
    ax.text(8.3, 7.9, 'Full', fontsize=9, color=C_RED, fontweight='bold')

    # Dock Queue -> 2 (retry)
    ax.annotate('', xy=(7.0, 8.3), xytext=(10.0, 8.3),
                arrowprops=dict(arrowstyle='->', color=C_RED, lw=2, mutation_scale=15,
                                connectionstyle='arc3,rad=-0.25', linestyle='dashed'))
    ax.text(8.5, 8.85, 'Retry when free', fontsize=8, color=C_RED, fontstyle='italic')

    # 3 -> 4
    ax.annotate('', xy=(6.3, 2.7), xytext=(6.3, 4.0), arrowprops=arrow_kw)
    ax.text(6.5, 3.2, '24h clock\nstarts', fontsize=8, color=C_ORANGE, fontweight='bold')

    # 3 -> 24h info (dashed annotation)
    ax.annotate('', xy=(9.2, 4.75), xytext=(7.9, 4.75),
                arrowprops=dict(arrowstyle='->', color=C_ORANGE, lw=1.5, mutation_scale=12,
                                linestyle='dotted'))

    # 4 -> 5
    ax.annotate('', xy=(3.7, 1.85), xytext=(4.7, 1.85), arrowprops=arrow_kw)

    # 4 -> DC Closed (during night)
    ax.annotate('', xy=(9.2, 1.95), xytext=(7.9, 1.95),
                arrowprops=dict(arrowstyle='->', color=C_ORANGE, lw=2, mutation_scale=15))
    ax.text(8.2, 2.25, 'Night', fontsize=9, color=C_ORANGE, fontweight='bold')

    # DC Closed -> 4 (resume)
    ax.annotate('', xy=(7.9, 1.4), xytext=(9.2, 1.4),
                arrowprops=dict(arrowstyle='->', color=C_ORANGE, lw=2, mutation_scale=15,
                                linestyle='dashed'))
    ax.text(8.2, 1.05, 'DC opens', fontsize=8, color=C_ORANGE, fontstyle='italic')

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, 'fg_inbound_flow_chart.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f'Saved: {path}')
    return path


# ===================== Figure 2: Timeline Comparison =====================
def draw_inbound_timeline_comparison():
    """Draw side-by-side timeline comparison of smooth vs dock-queue inbound."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 9))
    fig.patch.set_facecolor(C_BG)
    fig.suptitle('FG Inbound: Smooth vs Dock-Queue Bottleneck — Order Lifecycle Comparison',
                 fontsize=18, fontweight='bold', color=C_DARK, y=0.97)

    def draw_one_timeline(ax, title, events, total_hours_range, highlight_color, result_text):
        ax.set_facecolor(C_BG)
        ax.set_title(title, fontsize=14, fontweight='bold', color=highlight_color, pad=12)

        n = len(events)
        y_positions = list(range(n - 1, -1, -1))

        for i, (start, end, label, color, icon) in enumerate(events):
            y = y_positions[i]
            duration = end - start
            bar_height = 0.6

            ax.barh(y, duration, left=start, height=bar_height,
                    color=color, edgecolor='white', linewidth=1.5, alpha=0.85, zorder=3)

            mid = start + duration / 2
            if duration > (total_hours_range[1] - total_hours_range[0]) * 0.08:
                ax.text(mid, y, f'{icon} {label}', ha='center', va='center',
                        fontsize=9, fontweight='bold', color='white', zorder=4)
            else:
                ax.text(end + 0.3, y, f'{icon} {label}', ha='left', va='center',
                        fontsize=9, fontweight='bold', color=color, zorder=4)

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

        ax.text(0.98, 0.02, result_text, transform=ax.transAxes,
                fontsize=12, fontweight='bold', ha='right', va='bottom',
                color=highlight_color,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor=highlight_color, alpha=0.9))

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.grid(axis='x', alpha=0.2)

    # ===== Example 1: Smooth (FG_Inbound_01_00006) =====
    # Day 1 = hour 0. Arrival = hour 8.0 (Day 1, 08:00)
    events1 = [
        (8.0,  9.0,   'Unloading (1h)', C_TEAL, '[UNLOAD]'),
        (9.0,  9.35,  'FTE Put-Away (59p)', C_GREEN, '[PUTAWAY]'),
    ]
    draw_one_timeline(ax1,
                      'Smooth: FG_Inbound_01_00006\n59 pallets | Timeslot Day 1 08:00',
                      events1, (7, 11), C_GREEN,
                      'SMOOTH\nTotal: 1.36h')

    # Timeslot marker
    ax1.axvline(x=8.0, color=C_GREEN, linestyle='--', linewidth=2, alpha=0.5, zorder=1)
    ax1.text(8.0, 1.7, 'Scheduled\nTimeslot', ha='center', fontsize=8, color=C_GREEN, fontweight='bold')

    # ===== Example 2: Dock Queue (FG_Inbound_01_00525) =====
    # Day 16 = hour 360. Arrival = 360 + 23 = 383.0 (Day 16, 23:00)
    events2 = [
        (383.0,  398.0, 'Dock Full - Queue 15h!', C_RED, '[QUEUE]'),
        (398.0,  399.0, 'Unloading (1h)', C_TEAL, '[UNLOAD]'),
        (399.0,  399.3, 'FTE Put-Away (54p)', C_GREEN, '[PUTAWAY]'),
    ]
    draw_one_timeline(ax2,
                      'Dock Queue: FG_Inbound_01_00525\n54 pallets | Timeslot Day 16 23:00',
                      events2, (382, 401), C_RED,
                      'DOCK BOTTLENECK\nTotal: 16.31h\n(15h in queue!)')

    # Timeslot marker
    ax2.axvline(x=383.0, color=C_GREEN, linestyle='--', linewidth=2, alpha=0.5, zorder=1)
    ax2.text(383.0, 2.7, 'Scheduled\nTimeslot', ha='center', fontsize=8, color=C_GREEN, fontweight='bold')
    # Actual unloading start marker
    ax2.axvline(x=398.0, color=C_RED, linestyle='--', linewidth=2, alpha=0.5, zorder=1)
    ax2.text(398.0, 2.7, 'Actual\nUnloading', ha='center', fontsize=8, color=C_RED, fontweight='bold')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    path = os.path.join(FIGURES_DIR, 'fg_inbound_timeline_comparison.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f'Saved: {path}')
    return path


# ===================== Figure 3: Comparison Table =====================
def draw_inbound_summary_table():
    """Draw a comparison summary table for two inbound example orders."""
    fig, ax = plt.subplots(1, 1, figsize=(16, 7))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.axis('off')

    ax.text(0.5, 0.96, 'FG Inbound — Two Example Orders Comparison',
            fontsize=18, fontweight='bold', ha='center', va='top',
            transform=ax.transAxes, color=C_DARK)

    columns = ['Metric', 'Order 00006 (Smooth)', 'Order 00525 (Dock Queue)']
    rows = [
        ['Pallets',                '59',                           '54'],
        ['Category',               'FG Inbound',                   'FG Inbound'],
        ['Scheduled Timeslot',     'Day 1, 08:00',                 'Day 16, 23:00'],
        ['Truck Arrival',          'Day 1, 08:00',                 'Day 16, 23:00'],
        ['Reception Dock Status',  'Available',                    'FULL (1/1 used)'],
        ['Dock Queue Wait',        '0h',                           '15h (!!!)'],
        ['Unloading Start',        'Day 1, 08:00 (immediate)',     'Day 17, 14:00 (+15h)'],
        ['Unloading End',          'Day 1, 09:00',                 'Day 17, 15:00'],
        ['FTE Put-Away Duration',  '0.35h (21 min) @ 169 p/h',    '0.30h (18 min) @ 180 p/h'],
        ['Complete',               'Day 1, 09:21',                 'Day 17, 15:18'],
        ['Total End-to-End Time',  '1.36h',                        '16.31h'],
        ['Within 24h Deadline?',   'Yes (used 1.4 / 24h)',         'Yes (used 16.3 / 24h)'],
        ['Result',                 'SMOOTH',                       'DOCK BOTTLENECK'],
        ['Root Cause',             '-',                            'Reception Dock Saturation'],
    ]

    cell_colors = []
    for i, row in enumerate(rows):
        if i >= len(rows) - 2:
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

    for j in range(3):
        cell = table[0, j]
        cell.set_text_props(fontweight='bold', color='white', fontsize=12)
        cell.set_height(0.08)

    for i in range(len(rows)):
        for j in range(3):
            cell = table[i + 1, j]
            cell.set_height(0.06)
            cell.set_edgecolor('#D5D8DC')
            if j == 0:
                cell.set_text_props(fontweight='bold', color=C_DARK)

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, 'fg_inbound_comparison_table.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f'Saved: {path}')
    return path


# ===================== Main =====================
if __name__ == '__main__':
    print('Generating FG Inbound flow diagrams for presentation...\n')
    p1 = draw_inbound_flow_chart()
    p2 = draw_inbound_timeline_comparison()
    p3 = draw_inbound_summary_table()
    print(f'\nAll figures saved to: {FIGURES_DIR}')
    print(f'  1. {os.path.basename(p1)}  -- General inbound process flow chart')
    print(f'  2. {os.path.basename(p2)}  -- Timeline comparison (smooth vs dock-queue)')
    print(f'  3. {os.path.basename(p3)}  -- Summary comparison table')
