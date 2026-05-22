#!/usr/bin/env python3
"""
实验三：链路带宽对比实验 - 图表生成脚本
生成带宽对比分析图，符合顶刊顶会要求，支持中文
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

BANDWIDTHS = [5.0, 10.0, 20.0, 50.0, 100.0]
BANDWIDTH_LABELS = ['5', '10', '20', '50', '100']
RATES = [0.05, 0.8, 1.6]
RATE_LABELS = ['0.05', '0.8', '1.6']


def load_all_data(base_dir):
    """加载所有带宽配置的实验数据"""
    all_data = {}
    for bw in BANDWIDTHS:
        dir_name = f'bandwidth{bw}'
        data_path = base_dir / dir_name / 'data' / 'summary_metrics.csv'
        if data_path.exists():
            df = pd.read_csv(data_path)
            all_data[bw] = df
            print(f"✓ 已加载 {dir_name}: {len(df)} 条记录")
        else:
            print(f"✗ 缺失: {data_path}")
    return all_data


def plot_delay_vs_bandwidth(all_data, output_dir):
    """图1: 平均时延随带宽变化曲线（分面网格：每个子图一种负载速率）"""
    fig, axes = plt.subplots(1, len(RATES), figsize=(15, 5))
    
    for idx, rate in enumerate(RATES):
        ax = axes[idx]
        
        for alg in ['spf', 'ucb']:
            delays = []
            for bw in BANDWIDTHS:
                if bw not in all_data:
                    continue
                df = all_data[bw]
                subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
                if len(subset) > 0:
                    delays.append(subset['avg_delay_ms'].values[0])
                else:
                    delays.append(np.nan)
            
            ax.plot(BANDWIDTHS, delays,
                    marker=ALGORITHM_MARKERS[alg],
                    color=ALGORITHM_COLORS[alg],
                    linewidth=2.5,
                    markersize=10,
                    label=ALGORITHM_LABELS[alg],
                    markeredgecolor='black',
                    markeredgewidth=1.0)
        
        ax.set_xlabel('链路带宽 (Mbps)', fontweight='bold', fontsize=11)
        if idx == 0:
            ax.set_ylabel('平均端到端时延 (ms)', fontweight='bold', fontsize=11)
        ax.set_title(f'负载 = {rate} Mbps', fontweight='bold', fontsize=12)
        ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.set_xscale('log')
        ax.set_xticks(BANDWIDTHS)
        ax.set_xticklabels(BANDWIDTH_LABELS)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_delay_vs_bandwidth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_delay_vs_bandwidth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_delay_vs_bandwidth.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_delay_vs_bandwidth.pdf/png/svg")


def plot_drop_rate_vs_bandwidth(all_data, output_dir):
    """图2: 丢包率随带宽变化曲线（分面网格）"""
    fig, axes = plt.subplots(1, len(RATES), figsize=(15, 5))
    
    for idx, rate in enumerate(RATES):
        ax = axes[idx]
        
        for alg in ['spf', 'ucb']:
            drop_rates = []
            for bw in BANDWIDTHS:
                if bw not in all_data:
                    continue
                df = all_data[bw]
                subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
                if len(subset) > 0:
                    drop_rates.append(subset['drop_rate'].values[0])
                else:
                    drop_rates.append(np.nan)
            
            ax.plot(BANDWIDTHS, drop_rates,
                    marker=ALGORITHM_MARKERS[alg],
                    color=ALGORITHM_COLORS[alg],
                    linewidth=2.5,
                    markersize=10,
                    label=ALGORITHM_LABELS[alg],
                    markeredgecolor='black',
                    markeredgewidth=1.0)
        
        ax.set_xlabel('链路带宽 (Mbps)', fontweight='bold', fontsize=11)
        if idx == 0:
            ax.set_ylabel('丢包率', fontweight='bold', fontsize=11)
        ax.set_title(f'负载 = {rate} Mbps', fontweight='bold', fontsize=12)
        ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.set_xscale('log')
        ax.set_xticks(BANDWIDTHS)
        ax.set_xticklabels(BANDWIDTH_LABELS)
        ax.set_ylim(0, 0.35)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_drop_rate_vs_bandwidth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_drop_rate_vs_bandwidth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_drop_rate_vs_bandwidth.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_drop_rate_vs_bandwidth.pdf/png/svg")


def plot_throughput_vs_bandwidth(all_data, output_dir):
    """图3: 吞吐量随带宽变化曲线（分面网格）"""
    fig, axes = plt.subplots(1, len(RATES), figsize=(15, 5))
    
    for idx, rate in enumerate(RATES):
        ax = axes[idx]
        
        for alg in ['spf', 'ucb']:
            throughputs = []
            for bw in BANDWIDTHS:
                if bw not in all_data:
                    continue
                df = all_data[bw]
                subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
                if len(subset) > 0:
                    throughputs.append(subset['throughput_mbps'].values[0])
                else:
                    throughputs.append(np.nan)
            
            ax.plot(BANDWIDTHS, throughputs,
                    marker=ALGORITHM_MARKERS[alg],
                    color=ALGORITHM_COLORS[alg],
                    linewidth=2.5,
                    markersize=10,
                    label=ALGORITHM_LABELS[alg],
                    markeredgecolor='black',
                    markeredgewidth=1.0)
        
        ax.set_xlabel('链路带宽 (Mbps)', fontweight='bold', fontsize=11)
        if idx == 0:
            ax.set_ylabel('吞吐量 (Mbps)', fontweight='bold', fontsize=11)
        ax.set_title(f'负载 = {rate} Mbps', fontweight='bold', fontsize=12)
        ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.set_xscale('log')
        ax.set_xticks(BANDWIDTHS)
        ax.set_xticklabels(BANDWIDTH_LABELS)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_throughput_vs_bandwidth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_throughput_vs_bandwidth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_throughput_vs_bandwidth.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_throughput_vs_bandwidth.pdf/png/svg")


def plot_completion_rate_vs_bandwidth(all_data, output_dir):
    """图4: 完成率随带宽变化曲线（分面网格）"""
    fig, axes = plt.subplots(1, len(RATES), figsize=(15, 5))
    
    for idx, rate in enumerate(RATES):
        ax = axes[idx]
        
        for alg in ['spf', 'ucb']:
            completion_rates = []
            for bw in BANDWIDTHS:
                if bw not in all_data:
                    continue
                df = all_data[bw]
                subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
                if len(subset) > 0:
                    completion_rates.append(subset['completion_rate'].values[0])
                else:
                    completion_rates.append(np.nan)
            
            ax.plot(BANDWIDTHS, completion_rates,
                    marker=ALGORITHM_MARKERS[alg],
                    color=ALGORITHM_COLORS[alg],
                    linewidth=2.5,
                    markersize=10,
                    label=ALGORITHM_LABELS[alg],
                    markeredgecolor='black',
                    markeredgewidth=1.0)
        
        ax.set_xlabel('链路带宽 (Mbps)', fontweight='bold', fontsize=11)
        if idx == 0:
            ax.set_ylabel('流完成率', fontweight='bold', fontsize=11)
        ax.set_title(f'负载 = {rate} Mbps', fontweight='bold', fontsize=12)
        ax.legend(loc='lower left', framealpha=0.9, edgecolor='gray', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.set_xscale('log')
        ax.set_xticks(BANDWIDTHS)
        ax.set_xticklabels(BANDWIDTH_LABELS)
        ax.set_ylim(0, 1.0)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_completion_rate_vs_bandwidth.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_completion_rate_vs_bandwidth.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_completion_rate_vs_bandwidth.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_completion_rate_vs_bandwidth.pdf/png/svg")


def plot_jain_index_comparison(all_data, output_dir):
    """图5: Jain指数对比（双Y轴：左轴SPF，右轴UCB，解决数量级差异）"""
    fig, ax1 = plt.subplots(figsize=(8, 5))
    
    # 绘制SPF数据（左Y轴）
    for rate in RATES:
        jain_values = []
        for bw in BANDWIDTHS:
            if bw not in all_data:
                continue
            df = all_data[bw]
            subset = df[(df['algorithm'] == 'spf') & (df['traffic_generation_rate_mbps'] == rate)]
            if len(subset) > 0:
                jain_values.append(subset['load_balance_jain'].values[0])
            else:
                jain_values.append(np.nan)
        
        rate_idx = RATES.index(rate)
        ax1.plot(BANDWIDTHS, jain_values,
                marker=ALGORITHM_MARKERS['spf'],
                color=ALGORITHM_COLORS['spf'],
                linewidth=2.5,
                markersize=10,
                label=f'SPF - {rate} Mbps',
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax1.set_xlabel('链路带宽 (Mbps)', fontweight='bold', fontsize=12)
    ax1.set_ylabel('SPF算法 - Jain指数', fontweight='bold', fontsize=12, color=ALGORITHM_COLORS['spf'])
    ax1.set_ylim(0, 0.15)
    ax1.tick_params(axis='y', labelcolor=ALGORITHM_COLORS['spf'])
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_axisbelow(True)
    ax1.set_xscale('log')
    ax1.set_xticks(BANDWIDTHS)
    ax1.set_xticklabels(BANDWIDTH_LABELS)
    
    # 创建右Y轴绘制UCB数据
    ax2 = ax1.twinx()
    
    for rate in RATES:
        jain_values = []
        for bw in BANDWIDTHS:
            if bw not in all_data:
                continue
            df = all_data[bw]
            subset = df[(df['algorithm'] == 'ucb') & (df['traffic_generation_rate_mbps'] == rate)]
            if len(subset) > 0:
                jain_values.append(subset['load_balance_jain'].values[0])
            else:
                jain_values.append(np.nan)
        
        ax2.plot(BANDWIDTHS, jain_values,
                marker=ALGORITHM_MARKERS['ucb'],
                color=ALGORITHM_COLORS['ucb'],
                linewidth=2.5,
                markersize=10,
                label=f'UCB - {rate} Mbps',
                markeredgecolor='black',
                markeredgewidth=1.0)
    
    ax2.set_ylabel('UCB算法 - Jain指数', fontweight='bold', fontsize=12, color=ALGORITHM_COLORS['ucb'])
    ax2.set_ylim(0.7, 1.0)
    ax2.tick_params(axis='y', labelcolor=ALGORITHM_COLORS['ucb'])
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, 
               loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_jain_index_comparison.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_jain_index_comparison.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_jain_index_comparison.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_jain_index_comparison.pdf/png/svg")


def plot_performance_bar_comparison(all_data, output_dir):
    """图6: 关键指标分组柱状图（1.6 Mbps高负载下，对比不同带宽）"""
    rate = 1.6
    
    fig, axes = plt.subplots(1, 4, figsize=(16, 5))
    
    algorithms = ['spf', 'ucb']
    alg_labels = ['SPF', 'UCB']
    
    x = np.arange(len(BANDWIDTHS))
    width = 0.35
    
    metrics_config = [
        ('avg_delay_ms', '平均时延 (ms)', '(a)'),
        ('drop_rate', '丢包率', '(b)'),
        ('completion_rate', '流完成率', '(c)'),
        ('load_balance_jain', 'Jain指数', '(d)')
    ]
    
    for idx, (metric, ylabel, title) in enumerate(metrics_config):
        ax = axes[idx]
        
        spf_values = []
        ucb_values = []
        
        for bw in BANDWIDTHS:
            if bw not in all_data:
                continue
            df = all_data[bw]
            
            spf_subset = df[(df['algorithm'] == 'spf') & (df['traffic_generation_rate_mbps'] == rate)]
            ucb_subset = df[(df['algorithm'] == 'ucb') & (df['traffic_generation_rate_mbps'] == rate)]
            
            if len(spf_subset) > 0:
                spf_values.append(spf_subset[metric].values[0])
            else:
                spf_values.append(np.nan)
            
            if len(ucb_subset) > 0:
                ucb_values.append(ucb_subset[metric].values[0])
            else:
                ucb_values.append(np.nan)
        
        bars1 = ax.bar(x - width/2, spf_values, width, 
                       label='SPF算法', color=ALGORITHM_COLORS['spf'], 
                       edgecolor='black', linewidth=1.0)
        bars2 = ax.bar(x + width/2, ucb_values, width,
                       label='UCB算法', color=ALGORITHM_COLORS['ucb'],
                       edgecolor='black', linewidth=1.0)
        
        ax.set_ylabel(ylabel, fontweight='bold', fontsize=10)
        ax.set_title(f'{title} 负载={rate} Mbps', fontweight='bold', fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(BANDWIDTH_LABELS, fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax.set_axisbelow(True)
        
        if idx == 0:
            ax.legend(fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_performance_bar_comparison.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_performance_bar_comparison.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_performance_bar_comparison.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_performance_bar_comparison.pdf/png/svg")


def plot_algorithm_comparison_heatmap(all_data, output_dir):
    """图7: 算法性能对比热力图（算法×带宽×指标）"""
    algorithms = ['spf', 'ucb']
    rates = [0.05, 0.8, 1.6]
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain']
    metric_labels = ['平均时延', '丢包率', '流完成率', 'Jain指数']
    
    fig, axes = plt.subplots(1, len(rates), figsize=(16, 5))
    
    for idx, rate in enumerate(rates):
        ax = axes[idx]
        
        data_matrix = []
        labels = []
        for alg in algorithms:
            for bw in BANDWIDTHS:
                if bw not in all_data:
                    continue
                df = all_data[bw]
                subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
                if len(subset) == 0:
                    continue
                
                row = []
                for m in metrics:
                    val = subset[m].values[0]
                    row.append(val)
                data_matrix.append(row)
                labels.append(f"{ALGORITHM_LABELS[alg]}-{bw}")
        
        data_matrix = np.array(data_matrix)
        
        im = ax.imshow(data_matrix.T, cmap='RdYlGn_r', aspect='auto')
        
        ax.set_yticks(range(len(metric_labels)))
        ax.set_yticklabels(metric_labels, fontsize=9)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
        
        ax.set_title(f'负载 = {rate} Mbps', fontweight='bold', fontsize=11)
        
        for i in range(len(metric_labels)):
            for j in range(len(labels)):
                val = data_matrix[j, i]
                text_color = 'white' if val > 0.5 else 'black'
                if metrics[i] == 'avg_delay_ms':
                    display_val = f'{val:.1f}'
                else:
                    display_val = f'{val:.2f}'
                
                ax.text(j, i, display_val,
                        ha='center', va='center',
                        fontsize=7, fontweight='bold',
                        color=text_color)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'exp3_algorithm_heatmap.pdf', format='pdf')
    plt.savefig(output_dir / 'exp3_algorithm_heatmap.png', format='png', dpi=300)
    plt.savefig(output_dir / 'exp3_algorithm_heatmap.svg', format='svg')
    plt.close()
    print("✓ 已保存: exp3_algorithm_heatmap.pdf/png/svg")


def generate_summary_table(all_data, output_dir):
    """生成实验三关键指标汇总表"""
    algorithms = ['spf', 'ucb']
    rows = []
    for bw in BANDWIDTHS:
        if bw not in all_data:
            continue
        df = all_data[bw]
        for alg in algorithms:
            for rate in RATES:
                subset = df[(df['algorithm'] == alg) & (df['traffic_generation_rate_mbps'] == rate)]
                if len(subset) == 0:
                    continue
                
                row = {
                    '带宽 (Mbps)': bw,
                    '算法': ALGORITHM_LABELS[alg],
                    '负载速率 (Mbps)': rate,
                    '平均时延 (ms)': round(subset['avg_delay_ms'].values[0], 2),
                    '丢包率': round(subset['drop_rate'].values[0], 4),
                    '流完成率': round(subset['completion_rate'].values[0], 4),
                    'Jain指数': round(subset['load_balance_jain'].values[0], 4),
                    '吞吐量 (Mbps)': round(subset['throughput_mbps'].values[0], 2),
                }
                rows.append(row)
    
    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(output_dir / 'exp3_summary_table.csv', index=False)
    print("✓ 已保存: exp3_summary_table.csv")
    
    return summary_df


def main():
    """主函数"""
    print("=" * 60)
    print("实验三：链路带宽对比实验 - 图表生成")
    print("=" * 60)
    
    base_dir = Path(__file__).parent
    output_dir = base_dir / 'figures'
    output_dir.mkdir(exist_ok=True)
    
    all_data = load_all_data(base_dir)
    
    if len(all_data) == 0:
        print("错误: 未找到数据!")
        return
    
    print("\n生成图表中...")
    plot_delay_vs_bandwidth(all_data, output_dir)
    plot_drop_rate_vs_bandwidth(all_data, output_dir)
    plot_throughput_vs_bandwidth(all_data, output_dir)
    plot_completion_rate_vs_bandwidth(all_data, output_dir)
    plot_jain_index_comparison(all_data, output_dir)
    plot_performance_bar_comparison(all_data, output_dir)
    plot_algorithm_comparison_heatmap(all_data, output_dir)
    
    print("\n生成汇总表...")
    generate_summary_table(all_data, output_dir)
    
    print("\n" + "=" * 60)
    print("所有图表生成成功!")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
