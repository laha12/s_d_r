#!/usr/bin/env python3
"""
实验二：UCB奖励权重敏感性实验 - 图表生成脚本
生成权重对比分析图，符合顶刊顶会要求
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

def save_figure(fig, output_dir, filename):
    """保存图表为PDF、PNG和SVG三种格式"""
    plt.tight_layout()
    plt.savefig(output_dir / f'{filename}.pdf', format='pdf')
    plt.savefig(output_dir / f'{filename}.png', format='png', dpi=300)
    plt.savefig(output_dir / f'{filename}.svg', format='svg')
    plt.savefig(output_dir / f'{filename}.emf', format='emf')
    plt.close()
    print(f"✓ Saved: {filename}.pdf/png/svg/emf")



WEIGHT_CONFIGS = {
    'SPF': {'label': 'SPF', 'weights': 'N/A', 'color': '#000000', 'marker': 'x', 'linestyle': '--'},
    'DelayOnly': {'label': 'Delay-Only', 'weights': '[1.0, 0.0, 0.0]', 'color': '#1f77b4', 'marker': 'o', 'linestyle': '-'},
    'LoadOnly': {'label': 'Load-Only', 'weights': '[0.0, 1.0, 0.0]', 'color': '#ff7f0e', 'marker': 's', 'linestyle': '-'},
    'DistOnly': {'label': 'Distance-Only', 'weights': '[0.0, 0.0, 1.0]', 'color': '#2ca02c', 'marker': '^', 'linestyle': '-'},
    'DelayLoad': {'label': 'Delay+Load', 'weights': '[0.5, 0.5, 0.0]', 'color': '#d62728', 'marker': 'D', 'linestyle': '-'},
    'DelayDist': {'label': 'Delay+Dist', 'weights': '[0.5, 0.0, 0.5]', 'color': '#9467bd', 'marker': 'v', 'linestyle': '-'},
    'LoadDist': {'label': 'Load+Dist', 'weights': '[0.0, 0.5, 0.5]', 'color': '#8c564b', 'marker': 'p', 'linestyle': '-'},
    'Default': {'label': 'Default', 'weights': '[0.6, 0.2, 0.2]', 'color': '#e377c2', 'marker': '*', 'linestyle': '-'},
    'Uniform': {'label': 'Uniform', 'weights': '[0.33, 0.33, 0.34]', 'color': '#7f7f7f', 'marker': 'H', 'linestyle': '-'},
}

RATES = [0.05, 0.8, 1.6]
RATE_LABELS = ['0.05', '0.8', '1.6']


def load_all_data(base_dir):
    """加载所有权重配置的实验数据（包括SPF基准）"""
    all_data = {}
    for config_name in WEIGHT_CONFIGS.keys():
        # SPF数据在小写目录，其他配置在对应大写目录
        dir_name = config_name.lower() if config_name == 'SPF' else config_name
        data_path = base_dir / dir_name / 'data' / 'summary_metrics.csv'
        if data_path.exists():
            df = pd.read_csv(data_path)
            all_data[config_name] = df
            print(f"✓ Loaded {config_name}: {len(df)} runs")
        else:
            print(f"✗ Missing: {data_path}")
    return all_data


def plot_delay_comparison(all_data, output_dir):
    """图1: 平均时延对比（分组柱状图，含SPF基准）"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(RATES))
    width = 0.09
    configs = list(WEIGHT_CONFIGS.keys())
    
    for i, config in enumerate(configs):
        if config not in all_data:
            continue
        df = all_data[config]
        delays = []
        for rate in RATES:
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) > 0:
                delays.append(subset['avg_delay_ms'].values[0])
            else:
                delays.append(np.nan)
        
        linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
        if linestyle == '--':
            ax.bar(x + i * width, delays, width, 
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8,
                   hatch='///',
                   alpha=0.7)
        else:
            ax.bar(x + i * width, delays, width, 
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('平均端到端时延 (ms)', fontweight='bold', fontsize=12)
    ax.set_xticks(x + width * (len(configs) - 1) / 2)
    ax.set_xticklabels(RATE_LABELS)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=7.5, ncol=3)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.set_axisbelow(True)
    
    save_figure(fig, output_dir, 'exp2_delay_comparison')


def plot_drop_rate_comparison(all_data, output_dir):
    """图2: 丢包率对比（分组柱状图，含SPF基准）"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(RATES))
    width = 0.09
    configs = list(WEIGHT_CONFIGS.keys())
    
    for i, config in enumerate(configs):
        if config not in all_data:
            continue
        df = all_data[config]
        drop_rates = []
        for rate in RATES:
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) > 0:
                drop_rates.append(subset['drop_rate'].values[0])
            else:
                drop_rates.append(np.nan)
        
        linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
        if linestyle == '--':
            ax.bar(x + i * width, drop_rates, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8,
                   hatch='///',
                   alpha=0.7)
        else:
            ax.bar(x + i * width, drop_rates, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('丢包率', fontweight='bold', fontsize=12)
    ax.set_xticks(x + width * (len(configs) - 1) / 2)
    ax.set_xticklabels(RATE_LABELS)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=7.5, ncol=3)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.set_axisbelow(True)
    ax.set_ylim(0, 0.5)
    
    save_figure(fig, output_dir, 'exp2_drop_rate_comparison')


def plot_jain_index_comparison(all_data, output_dir):
    """图3: Jain负载均衡指数对比（分组柱状图，含SPF基准，对数坐标）"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(RATES))
    width = 0.09
    configs = list(WEIGHT_CONFIGS.keys())
    
    for i, config in enumerate(configs):
        if config not in all_data:
            continue
        df = all_data[config]
        jain_values = []
        for rate in RATES:
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) > 0:
                jain_values.append(subset['load_balance_jain'].values[0])
            else:
                jain_values.append(np.nan)
        
        linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
        if linestyle == '--':
            ax.bar(x + i * width, jain_values, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8,
                   hatch='///',
                   alpha=0.7)
        else:
            ax.bar(x + i * width, jain_values, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Jain公平指数', fontweight='bold', fontsize=12)
    ax.set_xticks(x + width * (len(configs) - 1) / 2)
    ax.set_xticklabels(RATE_LABELS)
    ax.set_yscale('log')
    ax.set_ylim(0.005, 1.1)
    ax.set_yticks([0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0])
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.grid(True, alpha=0.3, linestyle='--', axis='y', which='both')
    ax.set_axisbelow(True)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=7.5, ncol=3)
    
    save_figure(fig, output_dir, 'exp2_jain_comparison')


def plot_completion_rate_comparison(all_data, output_dir):
    """图4: 完成率对比（分组柱状图，含SPF基准）"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(RATES))
    width = 0.09
    configs = list(WEIGHT_CONFIGS.keys())
    
    for i, config in enumerate(configs):
        if config not in all_data:
            continue
        df = all_data[config]
        completion_rates = []
        for rate in RATES:
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) > 0:
                completion_rates.append(subset['completion_rate'].values[0])
            else:
                completion_rates.append(np.nan)
        
        linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
        if linestyle == '--':
            ax.bar(x + i * width, completion_rates, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8,
                   hatch='///',
                   alpha=0.7)
        else:
            ax.bar(x + i * width, completion_rates, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('流完成率', fontweight='bold', fontsize=12)
    ax.set_xticks(x + width * (len(configs) - 1) / 2)
    ax.set_xticklabels(RATE_LABELS)
    ax.legend(loc='upper right', framealpha=0.9, edgecolor='gray', fontsize=7.5, ncol=3)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.set_axisbelow(True)
    ax.set_ylim(0, 1.0)
    
    save_figure(fig, output_dir, 'exp2_completion_rate_comparison')


def plot_throughput_comparison(all_data, output_dir):
    """图5: 吞吐量对比（分组柱状图，含SPF基准）"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(RATES))
    width = 0.09
    configs = list(WEIGHT_CONFIGS.keys())
    
    for i, config in enumerate(configs):
        if config not in all_data:
            continue
        df = all_data[config]
        throughputs = []
        for rate in RATES:
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) > 0:
                throughputs.append(subset['throughput_mbps'].values[0])
            else:
                throughputs.append(np.nan)
        
        linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
        if linestyle == '--':
            ax.bar(x + i * width, throughputs, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8,
                   hatch='///',
                   alpha=0.7)
        else:
            ax.bar(x + i * width, throughputs, width,
                   label=WEIGHT_CONFIGS[config]['label'],
                   color=WEIGHT_CONFIGS[config]['color'],
                   edgecolor='black',
                   linewidth=0.8)
    
    ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_ylabel('吞吐量 (Mbps)', fontweight='bold', fontsize=12)
    ax.set_xticks(x + width * (len(configs) - 1) / 2)
    ax.set_xticklabels(RATE_LABELS)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=7.5, ncol=3)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.set_axisbelow(True)
    
    save_figure(fig, output_dir, 'exp2_throughput_comparison')


def plot_radar_chart_1_6mbps(all_data, output_dir):
    """图6: 1.6 Mbps负载下的雷达图（综合性能对比，含SPF基准）"""
    rate = 1.6
    
    configs = ['SPF', 'DelayOnly', 'LoadOnly', 'DistOnly', 'DelayLoad', 'DelayDist', 'LoadDist', 'Default', 'Uniform']
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain', 'throughput_mbps']
    metric_labels = ['延迟\n(逆)', '丢包率\n(逆)', '完成率', 'Jain指数', '吞吐量\n(归一化)']
    
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    for config in configs:
        if config not in all_data:
            continue
        df = all_data[config]
        subset = df[df['traffic_generation_rate_mbps'] == rate]
        if len(subset) == 0:
            continue
        
        values = []
        delay = subset['avg_delay_ms'].values[0]
        drop = subset['drop_rate'].values[0]
        completion = subset['completion_rate'].values[0]
        jain = subset['load_balance_jain'].values[0]
        throughput = subset['throughput_mbps'].values[0]
        
        values.append(1.0 / (1.0 + delay / 100.0))
        values.append(1.0 - drop)
        values.append(completion)
        values.append(jain)
        values.append(throughput / 10.0)
        
        values += values[:1]
        
        linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
        ax.plot(angles, values, 
                marker=WEIGHT_CONFIGS[config]['marker'],
                color=WEIGHT_CONFIGS[config]['color'],
                linewidth=2.0,
                markersize=6,
                label=WEIGHT_CONFIGS[config]['label'],
                linestyle=linestyle)
        ax.fill(angles, values, alpha=0.1, color=WEIGHT_CONFIGS[config]['color'])
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels, fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), framealpha=0.9, edgecolor='gray', fontsize=7.5)
    ax.set_title(f'性能雷达图 (负载 = {rate} Mbps)', 
                 fontweight='bold', fontsize=12, pad=20)
    
    save_figure(fig, output_dir, 'exp2_radar_1_6mbps')


def plot_performance_heatmap(all_data, output_dir):
    """图7: 多权重多指标综合对比热力图（含SPF基准）"""
    configs = ['SPF', 'DelayOnly', 'LoadOnly', 'DistOnly', 'DelayLoad', 'DelayDist', 'LoadDist', 'Default', 'Uniform']
    rates = [0.05, 0.8, 1.6]
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain']
    metric_labels = ['平均延迟', '丢包率', '完成率', 'Jain指数']
    
    fig, axes = plt.subplots(1, len(rates), figsize=(18, 5))
    
    for idx, rate in enumerate(rates):
        ax = axes[idx]
        
        data_matrix = []
        config_labels = []
        for config in configs:
            if config not in all_data:
                continue
            df = all_data[config]
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) == 0:
                continue
            
            row = []
            for m in metrics:
                val = subset[m].values[0]
                row.append(val)
            data_matrix.append(row)
            config_labels.append(WEIGHT_CONFIGS[config]['label'])
        
        data_matrix = np.array(data_matrix)
        
        im = ax.imshow(data_matrix.T, cmap='RdYlGn_r', aspect='auto')
        
        ax.set_yticks(range(len(metric_labels)))
        ax.set_yticklabels(metric_labels, fontsize=9)
        ax.set_xticks(range(len(config_labels)))
        ax.set_xticklabels(config_labels, rotation=45, ha='right', fontsize=7)
        
        ax.set_title(f'负载 = {rate} Mbps', fontweight='bold', fontsize=11)
        
        for i in range(len(metric_labels)):
            for j in range(len(config_labels)):
                val = data_matrix[j, i]
                text_color = 'white' if val > 0.5 else 'black'
                if metrics[i] == 'avg_delay_ms':
                    display_val = f'{val:.1f}'
                elif metrics[i] in ['drop_rate', 'completion_rate', 'load_balance_jain']:
                    display_val = f'{val:.2f}'
                else:
                    display_val = f'{val:.2f}'
                
                ax.text(j, i, display_val,
                        ha='center', va='center',
                        fontsize=7, fontweight='bold',
                        color=text_color)
    
    save_figure(fig, output_dir, 'exp2_performance_heatmap')


def plot_metric_trends(all_data, output_dir):
    """图8: 各指标随负载变化趋势（折线图，含SPF基准）"""
    configs = ['SPF', 'DelayOnly', 'LoadOnly', 'DistOnly', 'DelayLoad', 'DelayDist', 'LoadDist', 'Default', 'Uniform']
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain']
    metric_labels = ['平均时延 (ms)', '丢包率', '完成率', 'Jain公平指数']
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, (metric, label) in enumerate(zip(metrics, metric_labels)):
        ax = axes[idx]
        
        for config in configs:
            if config not in all_data:
                continue
            df = all_data[config]
            values = []
            for rate in RATES:
                subset = df[df['traffic_generation_rate_mbps'] == rate]
                if len(subset) > 0:
                    values.append(subset[metric].values[0])
                else:
                    values.append(np.nan)
            
            linestyle = WEIGHT_CONFIGS[config].get('linestyle', '-')
            ax.plot(RATES, values,
                    marker=WEIGHT_CONFIGS[config]['marker'],
                    color=WEIGHT_CONFIGS[config]['color'],
                    linewidth=2.0,
                    markersize=8,
                    label=WEIGHT_CONFIGS[config]['label'],
                    markeredgecolor='black',
                    markeredgewidth=0.8,
                    linestyle=linestyle)
        
        ax.set_xlabel('流量生成速率 (Mbps)', fontweight='bold', fontsize=11)
        ax.set_ylabel(label, fontweight='bold', fontsize=11)
        ax.set_xticks(RATES)
        ax.set_xticklabels(RATE_LABELS)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        if idx == 0:
            ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', fontsize=7, ncol=3)
    
    save_figure(fig, output_dir, 'exp2_metric_trends')


def generate_summary_table(all_data, output_dir):
    """生成实验二关键指标汇总表（含SPF基准）"""
    configs = ['SPF', 'DelayOnly', 'LoadOnly', 'DistOnly', 'DelayLoad', 'DelayDist', 'LoadDist', 'Default', 'Uniform']
    rates = [0.05, 0.8, 1.6]
    metrics = ['avg_delay_ms', 'drop_rate', 'completion_rate', 'load_balance_jain', 'throughput_mbps']
    
    rows = []
    for config in configs:
        if config not in all_data:
            continue
        df = all_data[config]
        for rate in rates:
            subset = df[df['traffic_generation_rate_mbps'] == rate]
            if len(subset) == 0:
                continue
            
            row = {
                '权重配置': WEIGHT_CONFIGS[config]['label'],
                '流量速率 (Mbps)': rate,
                '平均时延 (ms)': round(subset['avg_delay_ms'].values[0], 2),
                '丢包率': round(subset['drop_rate'].values[0], 4),
                '完成率': round(subset['completion_rate'].values[0], 4),
                'Jain指数': round(subset['load_balance_jain'].values[0], 4),
                '吞吐量 (Mbps)': round(subset['throughput_mbps'].values[0], 2),
            }
            rows.append(row)
    
    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(output_dir / 'exp2_summary_table.csv', index=False)
    print("✓ Saved: exp2_summary_table.csv")
    
    return summary_df


def main():
    """主函数"""
    print("=" * 60)
    print("实验二：UCB奖励权重敏感性实验 - 图表生成")
    print("=" * 60)
    
    base_dir = Path(__file__).parent
    output_dir = base_dir / 'figures'
    output_dir.mkdir(exist_ok=True)
    
    all_data = load_all_data(base_dir)
    
    if len(all_data) == 0:
        print("ERROR: No data found!")
        return
    
    print("\nGenerating figures...")
    plot_delay_comparison(all_data, output_dir)
    plot_drop_rate_comparison(all_data, output_dir)
    plot_jain_index_comparison(all_data, output_dir)
    plot_completion_rate_comparison(all_data, output_dir)
    plot_throughput_comparison(all_data, output_dir)
    plot_radar_chart_1_6mbps(all_data, output_dir)
    plot_performance_heatmap(all_data, output_dir)
    plot_metric_trends(all_data, output_dir)
    
    print("\nGenerating summary table...")
    generate_summary_table(all_data, output_dir)
    
    print("\n" + "=" * 60)
    print("All figures generated successfully!")
    print(f"Output directory: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
