#!/usr/bin/env python3
"""
实验一：SPF vs UCB 路由算法性能对比 - 图表生成脚本
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
import matplotlib.font_manager as fm

font_path = Path(__file__).parent.parent / 'fonts' / 'NotoSansSC.ttf'
if font_path.exists():
    fm.fontManager.addfont(str(font_path))
    font_prop = fm.FontProperties(fname=str(font_path))
    matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', font_prop.get_name(), 'SimHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False

matplotlib.rcParams.update({
    'font.size': 10,
    'font.family': 'sans-serif',
    'axes.linewidth': 1.5,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.major.width': 1.5,
    'ytick.major.width': 1.5,
    'xtick.minor.width': 1.0,
    'ytick.minor.width': 1.0,
    'lines.linewidth': 2.0,
    'lines.markersize': 8,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
})

ALGORITHM_COLORS = {
    'spf': '#1f77b4',
    'ucb': '#ff7f0e',
}

ALGORITHM_MARKERS = {
    'spf': 'o',
    'ucb': 's',
}

ALGORITHM_LABELS = {
    'spf': 'SPF算法',
    'ucb': 'UCB算法',
}


def save_figure(fig, output_dir, filename):
    """保存图表为PDF、PNG和SVG三种格式"""
    plt.tight_layout()
    plt.savefig(output_dir / f'{filename}.pdf', format='pdf')
    plt.savefig(output_dir / f'{filename}.png', format='png', dpi=300)
    plt.savefig(output_dir / f'{filename}.svg', format='svg')
    plt.close()
    print(f"✓ 已保存: {filename}.pdf/png/svg")


def load_data(base_dir):
    data_path = base_dir / 'spfvsucb' / 'data' / 'summary_metrics.csv'
    if data_path.exists():
        df = pd.read_csv(data_path)
        print(f"✓ 已加载数据: {len(df)} 条记录")
        return df
    else:
        print(f"✗ 缺失: {data_path}")
        return None


def plot_delay_vs_rate(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for alg in ['spf', 'ucb']:
        subset = df[df['algorithm'] == alg]
        delays = [subset[subset['traffic_generation_rate_mbps'] == r]['avg_delay_ms'].values[0] for r in rates]

        ax.plot(rates, delays,
                marker=ALGORITHM_MARKERS[alg],
                color=ALGORITHM_COLORS[alg],
                linewidth=2.5,
                markersize=10,
                label=ALGORITHM_LABELS[alg],
                markeredgecolor='black',
                markeredgewidth=1.0)

    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('平均端到端时延 (ms)', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xscale('log')
    ax.set_xticks(rates)
    ax.set_xticklabels([f'{r}' for r in rates])

    save_figure(fig, output_dir, 'exp1_delay_vs_rate')


def plot_throughput_vs_rate(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for alg in ['spf', 'ucb']:
        subset = df[df['algorithm'] == alg]
        throughputs = [subset[subset['traffic_generation_rate_mbps'] == r]['throughput_mbps'].values[0] for r in rates]

        ax.plot(rates, throughputs,
                marker=ALGORITHM_MARKERS[alg],
                color=ALGORITHM_COLORS[alg],
                linewidth=2.5,
                markersize=10,
                label=ALGORITHM_LABELS[alg],
                markeredgecolor='black',
                markeredgewidth=1.0)

    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('吞吐量 (Mbps)', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xscale('log')
    ax.set_xticks(rates)
    ax.set_xticklabels([f'{r}' for r in rates])

    save_figure(fig, output_dir, 'exp1_throughput_vs_rate')


def plot_drop_rate_vs_rate(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for alg in ['spf', 'ucb']:
        subset = df[df['algorithm'] == alg]
        drop_rates = [subset[subset['traffic_generation_rate_mbps'] == r]['drop_rate'].values[0] for r in rates]

        ax.plot(rates, drop_rates,
                marker=ALGORITHM_MARKERS[alg],
                color=ALGORITHM_COLORS[alg],
                linewidth=2.5,
                markersize=10,
                label=ALGORITHM_LABELS[alg],
                markeredgecolor='black',
                markeredgewidth=1.0)

    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('丢包率', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xscale('log')
    ax.set_xticks(rates)
    ax.set_xticklabels([f'{r}' for r in rates])
    ax.set_ylim(0, 0.55)

    save_figure(fig, output_dir, 'exp1_drop_rate_vs_rate')


def plot_completion_rate_vs_rate(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for alg in ['spf', 'ucb']:
        subset = df[df['algorithm'] == alg]
        completion_rates = [subset[subset['traffic_generation_rate_mbps'] == r]['completion_rate'].values[0] for r in rates]

        ax.plot(rates, completion_rates,
                marker=ALGORITHM_MARKERS[alg],
                color=ALGORITHM_COLORS[alg],
                linewidth=2.5,
                markersize=10,
                label=ALGORITHM_LABELS[alg],
                markeredgecolor='black',
                markeredgewidth=1.0)

    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('流完成率', fontweight='bold', fontsize=12)
    ax.legend(loc='upper right', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xscale('log')
    ax.set_xticks(rates)
    ax.set_xticklabels([f'{r}' for r in rates])
    ax.set_ylim(0, 1.05)

    save_figure(fig, output_dir, 'exp1_completion_rate_vs_rate')


def plot_jain_index_vs_rate(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for alg in ['spf', 'ucb']:
        subset = df[df['algorithm'] == alg]
        jain_indices = [subset[subset['traffic_generation_rate_mbps'] == r]['load_balance_jain'].values[0] for r in rates]

        ax.plot(rates, jain_indices,
                marker=ALGORITHM_MARKERS[alg],
                color=ALGORITHM_COLORS[alg],
                linewidth=2.5,
                markersize=10,
                label=ALGORITHM_LABELS[alg],
                markeredgecolor='black',
                markeredgewidth=1.0)

    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Jain公平指数', fontweight='bold', fontsize=12)
    ax.legend(loc='lower left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xscale('log')
    ax.set_xticks(rates)
    ax.set_xticklabels([f'{r}' for r in rates])
    ax.set_ylim(0, 1.05)

    save_figure(fig, output_dir, 'exp1_jain_index_vs_rate')


def plot_combined_metrics_bar(df, output_dir):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    rate = 2.0
    algorithms = ['spf', 'ucb']
    alg_labels_cn = ['SPF', 'UCB']

    delays = []
    drop_rates = []
    jains = []

    for alg in algorithms:
        subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
        if len(subset) > 0:
            delays.append(subset['avg_delay_ms'].values[0])
            drop_rates.append(subset['drop_rate'].values[0])
            jains.append(subset['load_balance_jain'].values[0])

    x = np.arange(len(algorithms))
    width = 0.5

    colors = [ALGORITHM_COLORS[a] for a in algorithms]

    bars1 = axes[0].bar(x, delays, width, color=colors, edgecolor='black', linewidth=1.0)
    axes[0].set_ylabel('平均时延 (ms)', fontweight='bold', fontsize=11)
    axes[0].set_title('(a) 平均时延', fontweight='bold', fontsize=11)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(alg_labels_cn, fontsize=10, fontweight='bold')
    axes[0].grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[0].set_axisbelow(True)
    for bar, val in zip(bars1, delays):
        axes[0].text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 2,
                     f'{val:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    bars2 = axes[1].bar(x, drop_rates, width, color=colors, edgecolor='black', linewidth=1.0)
    axes[1].set_ylabel('丢包率', fontweight='bold', fontsize=11)
    axes[1].set_title('(b) 丢包率', fontweight='bold', fontsize=11)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(alg_labels_cn, fontsize=10, fontweight='bold')
    axes[1].grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[1].set_axisbelow(True)
    for bar, val in zip(bars2, drop_rates):
        axes[1].text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.005,
                     f'{val:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    bars3 = axes[2].bar(x, jains, width, color=colors, edgecolor='black', linewidth=1.0)
    axes[2].set_ylabel('Jain公平指数', fontweight='bold', fontsize=11)
    axes[2].set_title('(c) Jain公平指数', fontweight='bold', fontsize=11)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(alg_labels_cn, fontsize=10, fontweight='bold')
    axes[2].grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[2].set_axisbelow(True)
    for bar, val in zip(bars3, jains):
        axes[2].text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.005,
                     f'{val:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_dir / 'exp1_combined_metrics_bar.pdf', format='pdf')
    plt.savefig(output_dir / 'exp1_combined_metrics_bar.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp1_combined_metrics_bar.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp1_combined_metrics_bar.pdf/png/svg")


def plot_metric_trends(df, output_dir):
    algorithms = ['spf', 'ucb']
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain']
    metric_labels = ['平均时延 (ms)', '丢包率', '流完成率', 'Jain公平指数']

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for idx, (metric, label) in enumerate(zip(metrics, metric_labels)):
        ax = axes[idx]

        for alg in algorithms:
            subset = df[df['algorithm'] == alg]
            values = [subset[subset['traffic_generation_rate_mbps'] == r][metric].values[0] for r in rates]

            ax.plot(rates, values,
                    marker=ALGORITHM_MARKERS[alg],
                    color=ALGORITHM_COLORS[alg],
                    linewidth=2.0,
                    markersize=8,
                    label=ALGORITHM_LABELS[alg],
                    markeredgecolor='black',
                    markeredgewidth=0.8)

        ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=11)
        ax.set_ylabel(label, fontweight='bold', fontsize=11)
        ax.set_xscale('log')
        ax.set_xticks(rates)
        ax.set_xticklabels([f'{r}' for r in rates])
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.legend(loc='best', framealpha=0.9, edgecolor='gray', fontsize=9)

    save_figure(fig, output_dir, 'exp1_metric_trends')


def plot_p95_delay_vs_rate(df, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    for alg in ['spf', 'ucb']:
        subset = df[df['algorithm'] == alg]
        delays = [subset[subset['traffic_generation_rate_mbps'] == r]['p95_delay_ms'].values[0] for r in rates]

        ax.plot(rates, delays,
                marker=ALGORITHM_MARKERS[alg],
                color=ALGORITHM_COLORS[alg],
                linewidth=2.5,
                markersize=10,
                label=ALGORITHM_LABELS[alg],
                markeredgecolor='black',
                markeredgewidth=1.0)

    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('P95端到端时延 (ms)', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xscale('log')
    ax.set_xticks(rates)
    ax.set_xticklabels([f'{r}' for r in rates])

    save_figure(fig, output_dir, 'exp1_p95_delay_vs_rate')


def plot_performance_heatmap(df, output_dir):
    algorithms = ['spf', 'ucb']
    alg_labels_cn = ['SPF', 'UCB']
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain', 'throughput_mbps']
    metric_labels_cn = ['平均时延', '丢包率', '流完成率', 'Jain公平指数', '吞吐量']

    all_rates = sorted(df['traffic_generation_rate_mbps'].unique())
    if len(all_rates) >= 3:
        selected_rates = [all_rates[0], all_rates[len(all_rates) // 2], all_rates[-1]]
    else:
        selected_rates = all_rates

    fig, axes = plt.subplots(len(selected_rates), len(algorithms), figsize=(10, 2.5 * len(selected_rates)))
    if len(selected_rates) == 1:
        axes = axes.reshape(1, -1)

    global_min = {}
    global_max = {}
    for metric in metrics:
        global_min[metric] = df[metric].min()
        global_max[metric] = df[metric].max()

    for rate_idx, rate in enumerate(selected_rates):
        for alg_idx, alg in enumerate(algorithms):
            if len(selected_rates) > 1:
                ax = axes[rate_idx, alg_idx]
            else:
                ax = axes[alg_idx]

            subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
            if len(subset) == 0:
                ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
                ax.set_title(f'{alg_labels_cn[alg_idx]}', fontweight='bold', fontsize=11)
                ax.axis('off')
                continue

            data_matrix = []
            for metric in metrics:
                val = subset[metric].values[0]
                if global_max[metric] > global_min[metric]:
                    normalized = (val - global_min[metric]) / (global_max[metric] - global_min[metric])
                else:
                    normalized = 0.5
                data_matrix.append(normalized)

            data_matrix = np.array(data_matrix).reshape(-1, 1)

            im = ax.imshow(data_matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)

            ax.set_yticks(range(len(metrics)))
            ax.set_yticklabels(metric_labels_cn, fontsize=9)
            ax.set_xticks([])

            if alg_idx == 0:
                ax.set_ylabel(f'{rate} Mbps', fontweight='bold', fontsize=10, rotation=0, ha='right', va='center', labelpad=20)

            if rate_idx == 0:
                ax.set_title(alg_labels_cn[alg_idx], fontweight='bold', fontsize=11)

            for i in range(len(metrics)):
                val = subset[metrics[i]].values[0]
                if metrics[i] == 'avg_delay_ms':
                    display_val = f'{val:.1f}'
                elif metrics[i] == 'throughput_mbps':
                    display_val = f'{val:.2f}'
                else:
                    display_val = f'{val:.3f}'
                text_color = 'white' if 0.3 < data_matrix[i, 0] < 0.7 else 'black'
                ax.text(0, i, display_val, ha='center', va='center', fontsize=9, color=text_color, fontweight='bold')

    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label('归一化性能值', fontweight='bold', fontsize=10)

    plt.suptitle('SPF vs UCB 多负载性能对比热力图', fontweight='bold', fontsize=13, y=0.98)
    plt.tight_layout(rect=[0, 0, 0.9, 0.96])
    plt.savefig(output_dir / 'exp1_performance_heatmap.pdf', format='pdf')
    plt.savefig(output_dir / 'exp1_performance_heatmap.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp1_performance_heatmap.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp1_performance_heatmap.pdf/png/svg")


def generate_summary_table(df, output_dir):
    algorithms = ['spf', 'ucb']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())

    rows = []
    for alg in algorithms:
        for rate in rates:
            subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
            if len(subset) == 0:
                continue

            row = {
                '算法': ALGORITHM_LABELS[alg],
                '流量速率 (Mbps)': rate,
                '流数量': int(subset['num_flows'].values[0]),
                '平均时延 (ms)': round(subset['avg_delay_ms'].values[0], 2),
                'P95时延 (ms)': round(subset['p95_delay_ms'].values[0], 2),
                '丢包率': round(subset['drop_rate'].values[0], 4),
                '完成率': round(subset['completion_rate'].values[0], 4),
                'Jain指数': round(subset['load_balance_jain'].values[0], 4),
                '吞吐量 (Mbps)': round(subset['throughput_mbps'].values[0], 2),
            }
            rows.append(row)

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(output_dir / 'exp1_summary_table.csv', index=False)
    print("✓ 已保存: exp1_summary_table.csv")

    return summary_df


def main():
    print("=" * 60)
    print("实验一：SPF vs UCB 路由算法性能对比 - 图表生成")
    print("=" * 60)

    base_dir = Path(__file__).parent
    output_dir = base_dir / 'figures'
    output_dir.mkdir(exist_ok=True)

    df = load_data(base_dir)

    if df is None or len(df) == 0:
        print("错误: 未找到数据!")
        return

    print(f"\n已加载 {len(df)} 条实验记录")
    print(f"算法: {df['algorithm'].unique()}")
    print(f"流量速率: {sorted(df['traffic_generation_rate_mbps'].unique())}")

    print("\n生成图表中...")
    plot_delay_vs_rate(df, output_dir)
    plot_throughput_vs_rate(df, output_dir)
    plot_drop_rate_vs_rate(df, output_dir)
    plot_completion_rate_vs_rate(df, output_dir)
    plot_jain_index_vs_rate(df, output_dir)
    plot_p95_delay_vs_rate(df, output_dir)
    plot_performance_heatmap(df, output_dir)
    plot_combined_metrics_bar(df, output_dir)
    plot_metric_trends(df, output_dir)

    print("\n生成汇总表...")
    generate_summary_table(df, output_dir)

    print("\n" + "=" * 60)
    print("所有图表生成完成!")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
