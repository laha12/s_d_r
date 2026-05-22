#!/usr/bin/env python3
"""
实验四：TCP协议栈对比实验 - 补充图表生成脚本
生成趋势分析图、跨负载对比图等额外图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.font_manager as fm
from pathlib import Path

font_path = Path(__file__).parent.parent / 'fonts' / 'NotoSansSC.ttf'
if font_path.exists():
    fm.fontManager.addfont(str(font_path))
    font_prop = fm.FontProperties(fname=str(font_path))
    matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', font_prop.get_name(), 'SimHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False

matplotlib.rcParams.update({
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.linewidth': 1.5,
    'axes.labelsize': 14,
    'axes.titlesize': 13,
    'xtick.labelsize': 13,
    'ytick.labelsize': 13,
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

TCP_COLORS = {
    'TcpHybla': '#1f77b4',
    'TcpNewReno': '#ff7f0e',
    'TcpBic': '#2ca02c',
    'TcpWestwood': '#d62728',
    'TcpVegas': '#9467bd',
    'TcpVeno': '#8c564b',
}

TCP_MARKERS = {
    'TcpHybla': 'o',
    'TcpNewReno': 's',
    'TcpBic': '^',
    'TcpWestwood': 'D',
    'TcpVegas': 'v',
    'TcpVeno': 'p',
}

TCP_LABELS = {
    'TcpHybla': 'TCP-Hybla',
    'TcpNewReno': 'TCP-NewReno',
    'TcpBic': 'TCP-BIC',
    'TcpWestwood': 'TCP-Westwood',
    'TcpVegas': 'TCP-Vegas',
    'TcpVeno': 'TCP-Veno',
}


def load_ucb_spf_data():
    """加载UCB和SPF两个算法的实验数据"""
    base_dir = Path(__file__).parent
    
    ucb_path = base_dir / 'ucb与6种tcp协议' / 'data' / 'summary_metrics.csv'
    spf_path = base_dir / 'spf算法与6种tcp协议' / 'data' / 'summary_metrics.csv'
    
    df_ucb = pd.read_csv(ucb_path)
    df_ucb['tcp_type'] = df_ucb['run_name'].apply(
        lambda x: x.split('_with_')[1].split('_ucb')[0]
    )
    df_ucb['algorithm'] = 'UCB'
    
    df_spf = pd.read_csv(spf_path)
    df_spf['tcp_type'] = df_spf['run_name'].apply(
        lambda x: x.split('_with_')[1].split('_spf')[0]
    )
    df_spf['algorithm'] = 'SPF'
    
    df_combined = pd.concat([df_ucb, df_spf], ignore_index=True)
    
    return df_combined


def load_data():
    """加载实验数据（合并UCB和SPF数据）"""
    return load_ucb_spf_data()


def plot_throughput_growth_curve(df, output_dir):
    """补充图1: 吞吐量随负载增长曲线（折线图）"""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    
    for tcp in tcp_types:
        subset = df[df['tcp_type'] == tcp]
        throughputs = [subset[subset['traffic_generation_rate_mbps'] == r]['throughput_mbps'].values[0] 
                       for r in rates]
        
        ax.plot(rates, throughputs, 
                marker=TCP_MARKERS[tcp],
                color=TCP_COLORS[tcp],
                linewidth=2.5,
                markersize=10,
                label=TCP_LABELS[tcp],
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('吞吐量 (Mbps)', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xticks(rates)
    ax.set_xticklabels([str(r) for r in rates])
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_throughput_growth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_throughput_growth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_throughput_growth.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_throughput_growth.pdf/png/svg")


def plot_delay_growth_curve(df, output_dir):
    """补充图2: 时延随负载增长曲线（折线图）"""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    
    for tcp in tcp_types:
        subset = df[df['tcp_type'] == tcp]
        delays = [subset[subset['traffic_generation_rate_mbps'] == r]['avg_delay_ms'].values[0] 
                  for r in rates]
        
        ax.plot(rates, delays, 
                marker=TCP_MARKERS[tcp],
                color=TCP_COLORS[tcp],
                linewidth=2.5,
                markersize=10,
                label=TCP_LABELS[tcp],
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('平均端到端时延 (ms)', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xticks(rates)
    ax.set_xticklabels([str(r) for r in rates])
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_delay_growth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_delay_growth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_delay_growth.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_delay_growth.pdf/png/svg")


def plot_completion_rate_decay_curve(df, output_dir):
    """补充图3: 完成率随负载衰减曲线（折线图）"""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    
    for tcp in tcp_types:
        subset = df[df['tcp_type'] == tcp]
        completion_rates = [subset[subset['traffic_generation_rate_mbps'] == r]['completion_rate'].values[0] 
                            for r in rates]
        
        ax.plot(rates, completion_rates, 
                marker=TCP_MARKERS[tcp],
                color=TCP_COLORS[tcp],
                linewidth=2.5,
                markersize=10,
                label=TCP_LABELS[tcp],
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('流完成率', fontweight='bold', fontsize=12)
    ax.legend(loc='upper right', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xticks(rates)
    ax.set_xticklabels([str(r) for r in rates])
    ax.set_ylim(0, 1.0)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_completion_decay.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_completion_decay.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_completion_decay.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_completion_decay.pdf/png/svg")


def plot_drop_rate_growth_curve(df, output_dir):
    """补充图4: 丢包率随负载增长曲线（折线图）"""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    
    for tcp in tcp_types:
        subset = df[df['tcp_type'] == tcp]
        drop_rates = [subset[subset['traffic_generation_rate_mbps'] == r]['drop_rate'].values[0] 
                      for r in rates]
        
        ax.plot(rates, drop_rates, 
                marker=TCP_MARKERS[tcp],
                color=TCP_COLORS[tcp],
                linewidth=2.5,
                markersize=10,
                label=TCP_LABELS[tcp],
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('丢包率', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xticks(rates)
    ax.set_xticklabels([str(r) for r in rates])
    ax.set_ylim(0, 0.5)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_drop_rate_growth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_drop_rate_growth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_drop_rate_growth.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_drop_rate_growth.pdf/png/svg")


def plot_jain_index_decay_curve(df, output_dir):
    """补充图5: Jain指数随负载变化曲线（折线图）"""
    fig, ax = plt.subplots(figsize=(8, 5))
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    
    for tcp in tcp_types:
        subset = df[df['tcp_type'] == tcp]
        jain_indices = [subset[subset['traffic_generation_rate_mbps'] == r]['load_balance_jain'].values[0] 
                        for r in rates]
        
        ax.plot(rates, jain_indices, 
                marker=TCP_MARKERS[tcp],
                color=TCP_COLORS[tcp],
                linewidth=2.5,
                markersize=10,
                label=TCP_LABELS[tcp],
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Jain公平指数', fontweight='bold', fontsize=12)
    ax.legend(loc='lower left', framealpha=0.9, edgecolor='gray', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xticks(rates)
    ax.set_xticklabels([str(r) for r in rates])
    ax.set_ylim(0.85, 1.0)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_jain_decay.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_jain_decay.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_jain_decay.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_jain_decay.pdf/png/svg")


def plot_combined_metrics_bar(df, output_dir):
    """补充图: 时延、丢包率与吞吐量组合柱状图（1.6 Mbps负载）"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    rate = 1.6
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    tcp_labels_cn = ['Hybla', 'NewReno', 'BIC', 'Westwood', 'Vegas', 'Veno']
    
    # 提取数据
    delays = []
    drop_rates = []
    throughputs = []
    
    for tcp in tcp_types:
        subset = df[(df['tcp_type'] == tcp) & (df['traffic_generation_rate_mbps'] == rate)]
        if len(subset) > 0:
            delays.append(subset['avg_delay_ms'].values[0])
            drop_rates.append(subset['drop_rate'].values[0])
            throughputs.append(subset['throughput_mbps'].values[0])
    
    x = np.arange(len(tcp_types))
    width = 0.6
    
    # 时延柱状图
    colors_delay = [TCP_COLORS[t] for t in tcp_types]
    bars1 = axes[0].bar(x, delays, width, color=colors_delay, edgecolor='black', linewidth=1.0)
    axes[0].set_ylabel('平均时延 (ms)', fontweight='bold', fontsize=11)
    axes[0].set_title('(a) 平均时延', fontweight='bold', fontsize=11)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(tcp_labels_cn, fontsize=9)
    axes[0].grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[0].set_axisbelow(True)
    
    # 在柱子上添加数值标签
    for bar, val in zip(bars1, delays):
        axes[0].text(bar.get_x() + bar.get_width()/2., bar.get_height() + 2,
                     f'{val:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # 丢包率柱状图
    colors_drop = [TCP_COLORS[t] for t in tcp_types]
    bars2 = axes[1].bar(x, drop_rates, width, color=colors_drop, edgecolor='black', linewidth=1.0)
    axes[1].set_ylabel('丢包率', fontweight='bold', fontsize=11)
    axes[1].set_title('(b) 丢包率', fontweight='bold', fontsize=11)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(tcp_labels_cn, fontsize=9)
    axes[1].grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[1].set_axisbelow(True)
    
    # 在柱子上添加数值标签
    for bar, val in zip(bars2, drop_rates):
        axes[1].text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.005,
                     f'{val:.3f}', ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # 吞吐量柱状图
    colors_throughput = [TCP_COLORS[t] for t in tcp_types]
    bars3 = axes[2].bar(x, throughputs, width, color=colors_throughput, edgecolor='black', linewidth=1.0)
    axes[2].set_ylabel('吞吐量 (Mbps)', fontweight='bold', fontsize=11)
    axes[2].set_title('(c) 吞吐量', fontweight='bold', fontsize=11)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(tcp_labels_cn, fontsize=9)
    axes[2].grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[2].set_axisbelow(True)
    
    # 在柱子上添加数值标签
    for bar, val in zip(bars3, throughputs):
        axes[2].text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                     f'{val:.2f}', ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_combined_metrics_bar.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_combined_metrics_bar.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_combined_metrics_bar.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_combined_metrics_bar.pdf/png/svg")


def plot_throughput_delay_tradeoff(df, output_dir):
    """补充图6: 吞吐量-时延权衡散点图（1.6 Mbps负载点）"""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    rate = 1.6
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    
    for tcp in tcp_types:
        subset = df[(df['tcp_type'] == tcp) & (df['traffic_generation_rate_mbps'] == rate)]
        if len(subset) == 0:
            continue
        
        throughput = subset['throughput_mbps'].values[0]
        delay = subset['avg_delay_ms'].values[0]
        
        ax.scatter(throughput, delay, 
                   s=200,
                   marker=TCP_MARKERS[tcp],
                   color=TCP_COLORS[tcp],
                   edgecolor='black',
                   linewidth=1.5,
                   label=TCP_LABELS[tcp],
                   zorder=5)
        
        ax.annotate(TCP_LABELS[tcp], 
                    (throughput, delay),
                    textcoords="offset points",
                    xytext=(10, 5),
                    fontsize=9,
                    fontweight='bold')
    
    ax.set_xlabel('吞吐量 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('平均时延 (ms)', fontweight='bold', fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_throughput_delay_tradeoff.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_throughput_delay_tradeoff.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_throughput_delay_tradeoff.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_throughput_delay_tradeoff.pdf/png/svg")


def plot_performance_comparison_heatmap(df, output_dir):
    """补充图7: 多指标综合对比热力图"""
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    metrics = ['throughput_mbps', 'avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain']
    metric_labels = ['吞吐量\n(Mbps)', '平均时延\n(ms)', '丢包率', '完成率', 'Jain指数']
    
    fig, axes = plt.subplots(1, len(rates), figsize=(5 * len(rates), 5))
    
    for idx, rate in enumerate(rates):
        ax = axes[idx]
        
        data_matrix = []
        for tcp in tcp_types:
            subset = df[(df['tcp_type'] == tcp) & (df['traffic_generation_rate_mbps'] == rate)]
            if len(subset) == 0:
                continue
            
            row = []
            for m in metrics:
                val = subset[m].values[0]
                row.append(val)
            data_matrix.append(row)
        
        data_matrix = np.array(data_matrix)
        
        im = ax.imshow(data_matrix.T, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        ax.set_yticks(range(len(metric_labels)))
        ax.set_yticklabels(metric_labels, fontsize=9)
        ax.set_xticks(range(len(tcp_types)))
        ax.set_xticklabels([TCP_LABELS[t] for t in tcp_types], rotation=45, ha='right', fontsize=8)
        
        ax.set_title(f'Load = {rate} Mbps', fontweight='bold', fontsize=11)
        
        for i in range(len(metric_labels)):
            for j in range(len(tcp_types)):
                val = data_matrix[j, i]
                if metrics[i] in ['throughput_mbps', 'avg_delay_ms']:
                    text_color = 'white' if val > 0.5 else 'black'
                    display_val = val
                else:
                    text_color = 'white' if val > 0.5 else 'black'
                    display_val = val
                
                ax.text(j, i, f'{display_val:.2f}',
                        ha='center', va='center', 
                        fontsize=8, fontweight='bold',
                        color=text_color)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp4_supplement_heatmap.pdf', format='pdf')
    plt.savefig(output_dir / 'exp4_supplement_heatmap.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp4_supplement_heatmap.svg', format='svg')
    plt.close()
    print(f"✓ Saved: exp4_supplement_heatmap.pdf/png/svg")


def plot_ucb_spf_comparison_facet(df, output_dir):
    """补充图8: UCB与SPF算法在不同TCP协议栈下的性能对比（分面网格图）"""
    
    tcp_types = ['TcpHybla', 'TcpNewReno', 'TcpBic', 'TcpWestwood', 'TcpVegas', 'TcpVeno']
    tcp_labels_cn = ['Hybla', 'NewReno', 'BIC', 'Westwood', 'Vegas', 'Veno']
    tcp_colors = [TCP_COLORS[t] for t in tcp_types]
    
    algorithms = ['UCB', 'SPF']
    rates = sorted(df['traffic_generation_rate_mbps'].unique())
    
    metrics_config = [
        ('throughput_mbps', '吞吐量 (Mbps)', 0, 11, 'linear'),
        ('avg_delay_ms', '平均时延 (ms)', 0, 180, 'linear'),
        ('drop_rate', '丢包率', 0, 0.35, 'linear'),
        ('completion_rate', '流完成率', 0, 1.1, 'linear'),
        ('load_balance_jain', 'Jain公平指数', 0.005, 1.1, 'log')
    ]
    
    for metric, ylabel, ymin, ymax, yscale in metrics_config:
        fig, axes = plt.subplots(2, 3, figsize=(16, 8))
        
        for row_idx, algorithm in enumerate(algorithms):
            for col_idx, rate in enumerate(rates):
                ax = axes[row_idx, col_idx]
                
                x = np.arange(len(tcp_types))
                width = 0.6
                
                values = []
                for tcp in tcp_types:
                    subset = df[(df['algorithm'] == algorithm) & 
                               (df['tcp_type'] == tcp) & 
                               (df['traffic_generation_rate_mbps'] == rate)]
                    if len(subset) > 0:
                        values.append(subset[metric].values[0])
                    else:
                        values.append(np.nan)
                
                bars = ax.bar(x, values, width,
                             color=tcp_colors,
                             edgecolor='black',
                             linewidth=0.8,
                             alpha=0.85)
                
                ax.set_title(f'{algorithm} - {rate} Mbps', fontweight='bold', fontsize=13)
                ax.set_xticks(x)
                ax.set_xticklabels(tcp_labels_cn, fontsize=12)
                ax.set_ylim(ymin, ymax)
                
                if yscale == 'log':
                    ax.set_yscale('log')
                    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
                    ax.grid(True, alpha=0.3, linestyle='--', axis='y', which='both')
                else:
                    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
                
                ax.set_axisbelow(True)
                
                if col_idx == 0:
                    ax.set_ylabel(ylabel, fontweight='bold', fontsize=14)
        
        plt.tight_layout()
        filename = f'exp4_supplement_ucb_spf_{metric}'
        plt.savefig(output_dir / f'{filename}.pdf', format='pdf')
        plt.savefig(output_dir / f'{filename}.png', format='png', dpi=300)
        plt.savefig(output_dir / f'{filename}.svg', format='svg')
        plt.close()
        print(f"✓ Saved: {filename}.pdf/png/svg")


def main():
    """主函数"""
    print("=" * 60)
    print("实验四：TCP协议栈对比实验 - 补充图表生成")
    print("=" * 60)
    
    df = load_data()
    print(f"\nLoaded {len(df)} experimental runs")
    print(f"TCP variants: {df['tcp_type'].unique()}")
    print(f"Traffic rates: {sorted(df['traffic_generation_rate_mbps'].unique())}")
    
    output_dir = Path(__file__).parent / 'figures'
    output_dir.mkdir(exist_ok=True)
    
    print("\nGenerating supplement figures...")
    plot_throughput_growth_curve(df, output_dir)
    plot_delay_growth_curve(df, output_dir)
    plot_completion_rate_decay_curve(df, output_dir)
    plot_drop_rate_growth_curve(df, output_dir)
    plot_jain_index_decay_curve(df, output_dir)
    plot_combined_metrics_bar(df, output_dir)
    plot_throughput_delay_tradeoff(df, output_dir)
    plot_performance_comparison_heatmap(df, output_dir)
    
    print("\nGenerating UCB vs SPF comparison figure...")
    df_combined = load_ucb_spf_data()
    print(f"Loaded combined data: {len(df_combined)} runs")
    print(f"Algorithms: {df_combined['algorithm'].unique()}")
    plot_ucb_spf_comparison_facet(df_combined, output_dir)
    
    print("\n" + "=" * 60)
    print("All supplement figures generated successfully!")
    print(f"Output directory: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
