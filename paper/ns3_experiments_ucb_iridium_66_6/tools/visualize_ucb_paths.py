#!/usr/bin/env python3
"""
UCB 路径可视化脚本

功能：
1. 解析 UCB debug 日志提取路径
2. 生成星座拓扑图（2D 投影）
3. 路径叠加图：标注每条路径的走向
4. 链路热力图：显示哪些链路被频繁使用

依赖：
    pip install matplotlib numpy

使用方法：
    python3 visualize_ucb_paths.py <ucb_route_debug.txt路径> <topology文件路径> [输出目录]
"""

import re
import sys
import os
import json
from collections import defaultdict, Counter

def parse_debug_log(log_path):
    """解析 UCB debug 日志，提取路径和链路使用信息"""
    
    # 按 uid 分组
    uid_events = defaultdict(list)
    # 链路使用计数: (node_a, node_b) -> count
    link_usage = Counter()
    # 节点转发计数
    node_forward_count = Counter()
    
    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 解析 [FWD] 行
            fwd_match = re.match(
                r'\[UCB_DEBUG\]\[FWD\].*?node=(\d+)\s+src=(\d+)\s+dst=(\d+)\s+uid=(\d+)\s+.*?'
                r'selected=(\d+)\s+.*?valid_arms=\[([^\]]*)\]\s+path=\[([^\]]*)\]',
                line
            )
            if fwd_match:
                node = int(fwd_match.group(1))
                src = int(fwd_match.group(2))
                dst = int(fwd_match.group(3))
                uid = int(fwd_match.group(4))
                selected = int(fwd_match.group(5))
                path = [int(x) for x in fwd_match.group(7).split(',') if x.strip()]
                
                uid_events[uid].append({
                    'type': 'FWD',
                    'node': node,
                    'src': src,
                    'dst': dst,
                    'selected': selected,
                    'path': path,
                })
                
                # 统计链路使用
                if len(path) >= 2:
                    for i in range(len(path) - 1):
                        link = (min(path[i], path[i+1]), max(path[i], path[i+1]))
                        link_usage[link] += 1
                
                # 统计节点转发
                node_forward_count[node] += 1
                continue
            
            # 解析 [ARRIVE] 行
            arrive_match = re.match(
                r'\[UCB_DEBUG\]\[ARRIVE\].*?node=(\d+)\s+src=(\d+)\s+dst=(\d+)\s+uid=(\d+)\s+.*?'
                r'path=\[([^\]]*)\]',
                line
            )
            if arrive_match:
                node = int(arrive_match.group(1))
                src = int(arrive_match.group(2))
                dst = int(arrive_match.group(3))
                uid = int(arrive_match.group(4))
                path = [int(x) for x in arrive_match.group(5).split(',') if x.strip()]
                
                uid_events[uid].append({
                    'type': 'ARRIVE',
                    'node': node,
                    'src': src,
                    'dst': dst,
                    'path': path,
                })
    
    return uid_events, link_usage, node_forward_count


def parse_topology(topo_path):
    """解析拓扑文件获取节点坐标"""
    
    nodes = {}  # node_id -> (x, y, is_ground_station)
    
    # 尝试多种拓扑格式
    if topo_path.endswith('.json'):
        with open(topo_path, 'r') as f:
            data = json.load(f)
            # 根据实际 JSON 结构解析
            if 'nodes' in data:
                for node in data['nodes']:
                    nodes[node['id']] = (node.get('x', 0), node.get('y', 0), node.get('is_gs', False))
    elif topo_path.endswith('.txt'):
        with open(topo_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        node_id = int(parts[0])
                        x = float(parts[1])
                        y = float(parts[2])
                        is_gs = len(parts) > 3 and parts[3] == 'GS'
                        nodes[node_id] = (x, y, is_gs)
                    except ValueError:
                        continue
    
    return nodes


def generate_node_positions_from_paths(uid_events, link_usage):
    """从路径数据推断节点位置（基于路径拓扑的力导向布局）"""
    
    import numpy as np
    
    # 收集所有节点
    all_nodes = set()
    # 收集边
    edges = defaultdict(int)
    
    for uid, events in uid_events.items():
        for e in events:
            if 'path' in e:
                path = e['path']
                for i in range(len(path)):
                    all_nodes.add(path[i])
                    if i < len(path) - 1:
                        edge = (min(path[i], path[i+1]), max(path[i], path[i+1]))
                        edges[edge] += 1
    
    # 添加链路使用数据中的边
    for (a, b), count in link_usage.items():
        all_nodes.add(a)
        all_nodes.add(b)
        edges[(a, b)] += count
    
    all_nodes = sorted(all_nodes)
    node_idx = {n: i for i, n in enumerate(all_nodes)}
    n = len(all_nodes)
    
    if n == 0:
        return {}, {}
    
    # 简单的力导向布局
    np.random.seed(42)
    positions = np.random.randn(n, 2) * 0.1
    
    # 归一化到 [0, 1]
    positions = (positions - positions.min(axis=0)) / (positions.max(axis=0) - positions.min(axis=0) + 1e-10)
    
    # 迭代优化
    for iteration in range(200):
        # 斥力（所有节点之间）
        forces = np.zeros_like(positions)
        for i in range(n):
            for j in range(i+1, n):
                diff = positions[i] - positions[j]
                dist = np.linalg.norm(diff) + 1e-10
                force = 0.01 / dist
                forces[i] += force * diff / dist
                forces[j] -= force * diff / dist
        
        # 引力（有边的节点之间）
        for (a, b), weight in edges.items():
            if a in node_idx and b in node_idx:
                ia, ib = node_idx[a], node_idx[b]
                diff = positions[ia] - positions[ib]
                dist = np.linalg.norm(diff) + 1e-10
                force = dist * 0.1 * min(weight / 10, 5)
                forces[ia] -= force * diff / dist
                forces[ib] += force * diff / dist
        
        # 更新位置
        positions += forces * 0.01
        positions = np.clip(positions, 0, 1)
    
    # 构建结果
    node_positions = {}
    for node, idx in node_idx.items():
        node_positions[node] = (float(positions[idx, 0]), float(positions[idx, 1]))
    
    return node_positions, edges


def create_topology_visualization(node_positions, edges, link_usage, output_path, title="UCB 路由链路热力图"):
    """创建拓扑可视化图"""
    
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    
    if not node_positions:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        return
    
    # 分离卫星和地面站节点
    sat_nodes = []
    gs_nodes = []
    for node_id in node_positions:
        if node_id >= 66:  # 假设节点 ID >= 66 是地面站
            gs_nodes.append(node_id)
        else:
            sat_nodes.append(node_id)
    
    # 绘制边（链路）- 按使用频率着色
    max_usage = max(link_usage.values()) if link_usage else 1
    
    for (a, b), count in link_usage.items():
        if a in node_positions and b in node_positions:
            x1, y1 = node_positions[a]
            x2, y2 = node_positions[b]
            
            # 颜色强度与使用频率成正比
            intensity = count / max_usage
            color = plt.cm.YlOrRd(0.1 + 0.9 * intensity)
            linewidth = 0.5 + 3 * intensity
            
            ax.plot([x1, x2], [y1, y2], color=color, linewidth=linewidth, alpha=0.7, zorder=1)
    
    # 绘制卫星节点
    if sat_nodes:
        sat_x = [node_positions[n][0] for n in sat_nodes]
        sat_y = [node_positions[n][1] for n in sat_nodes]
        ax.scatter(sat_x, sat_y, c='steelblue', s=80, zorder=3, edgecolors='white', linewidth=0.5, label='Satellite')
        for n in sat_nodes:
            ax.annotate(str(n), node_positions[n], fontsize=6, ha='center', va='center', color='white', fontweight='bold')
    
    # 绘制地面站节点
    if gs_nodes:
        gs_x = [node_positions[n][0] for n in gs_nodes]
        gs_y = [node_positions[n][1] for n in gs_nodes]
        ax.scatter(gs_x, gs_y, c='red', s=120, zorder=4, marker='s', edgecolors='darkred', linewidth=1, label='Ground Station')
        for n in gs_nodes:
            ax.annotate(str(n), node_positions[n], fontsize=7, ha='center', va='center', color='white', fontweight='bold')
    
    # 添加颜色条
    sm = plt.cm.ScalarMappable(cmap=plt.cm.YlOrRd, norm=plt.Normalize(vmin=0, vmax=max_usage))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label('Link Usage Count', fontsize=12)
    
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('X (normalized)', fontsize=12)
    ax.set_ylabel('Y (normalized)', fontsize=12)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"拓扑图已保存: {output_path}")


def create_path_sample_visualization(uid_events, node_positions, output_path, max_paths=10):
    """创建路径示例可视化（展示几条典型路径）"""
    
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    
    # 选择几条成功到达的路径
    arrived_paths = []
    for uid, events in uid_events.items():
        for e in events:
            if e['type'] == 'ARRIVE' and len(e.get('path', [])) > 0:
                arrived_paths.append({
                    'uid': uid,
                    'src': e['src'],
                    'dst': e['dst'],
                    'path': e['path'],
                    'hops': len(e['path']) - 1
                })
                break
    
    # 按跳数排序，选择最短、中等、最长的路径
    arrived_paths.sort(key=lambda x: x['hops'])
    
    if len(arrived_paths) < 3:
        return
    
    # 选择代表性路径
    selected = []
    selected.append(arrived_paths[0])  # 最短
    if len(arrived_paths) > 1:
        mid = len(arrived_paths) // 2
        selected.append(arrived_paths[mid])  # 中等
    if len(arrived_paths) > 2:
        selected.append(arrived_paths[-1])  # 最长
    
    # 限制数量
    selected = selected[:max_paths]
    
    # 创建子图
    n_rows = (len(selected) + 1) // 2
    fig, axes = plt.subplots(n_rows, 2, figsize=(16, 6 * n_rows))
    if n_rows == 1:
        axes = axes.reshape(1, -1)
    
    for idx, path_info in enumerate(selected):
        row = idx // 2
        col = idx % 2
        ax = axes[row, col]
        
        path = path_info['path']
        
        # 绘制所有节点
        all_nodes_in_path = set(path)
        for node in all_nodes_in_path:
            if node in node_positions:
                x, y = node_positions[node]
                if node >= 66:
                    ax.scatter(x, y, c='red', s=100, marker='s', zorder=3, edgecolors='darkred')
                else:
                    ax.scatter(x, y, c='lightgray', s=60, zorder=2, edgecolors='gray')
                ax.annotate(str(node), (x, y), fontsize=8, ha='center', va='center')
        
        # 绘制路径
        path_coords = [node_positions[n] for n in path if n in node_positions]
        if len(path_coords) >= 2:
            xs, ys = zip(*path_coords)
            ax.plot(xs, ys, 'b-', linewidth=2, marker='o', markersize=6, zorder=4)
            
            # 标注方向箭头
            for i in range(len(path_coords) - 1):
                x1, y1 = path_coords[i]
                x2, y2 = path_coords[i + 1]
                dx, dy = x2 - x1, y2 - y1
                length = (dx**2 + dy**2) ** 0.5
                if length > 0:
                    ax.annotate('', xy=(x1 + dx*0.6, y1 + dy*0.6),
                               xytext=(x1 + dx*0.4, y1 + dy*0.4),
                               arrowprops=dict(arrowstyle='->', color='blue', lw=2))
        
        # 标注起点和终点
        if path[0] in node_positions:
            x, y = node_positions[path[0]]
            ax.scatter(x, y, c='green', s=150, marker='*', zorder=5, edgecolors='darkgreen', linewidth=2)
        if path[-1] in node_positions:
            x, y = node_positions[path[-1]]
            ax.scatter(x, y, c='red', s=150, marker='*', zorder=5, edgecolors='darkred', linewidth=2)
        
        ax.set_title(f"Path: {path_info['src']} -> {path_info['dst']} ({path_info['hops']} hops)", fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
    
    # 隐藏多余的子图
    for idx in range(len(selected), n_rows * 2):
        row = idx // 2
        col = idx % 2
        axes[row, col].axis('off')
    
    plt.suptitle("UCB Routing Path Samples", fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"路径示例图已保存: {output_path}")


def create_hop_distribution_chart(uid_events, output_path):
    """创建跳数分布图"""
    
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from collections import Counter
    
    # 收集跳数
    hop_counts = []
    for uid, events in uid_events.items():
        for e in events:
            if e['type'] == 'ARRIVE' and 'path' in e:
                hops = len(e['path']) - 1
                hop_counts.append(hops)
                break
    
    if not hop_counts:
        return
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 跳数分布直方图
    hop_counter = Counter(hop_counts)
    hops_sorted = sorted(hop_counter.keys())
    counts = [hop_counter[h] for h in hops_sorted]
    
    ax1.bar(hops_sorted, counts, color='steelblue', edgecolor='white')
    ax1.set_xlabel('Hop Count', fontsize=12)
    ax1.set_ylabel('Number of Packets', fontsize=12)
    ax1.set_title('Hop Count Distribution (Arrived Packets)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 累积分布
    total = len(hop_counts)
    cumulative = []
    cum_sum = 0
    for h in hops_sorted:
        cum_sum += hop_counter[h]
        cumulative.append(cum_sum / total * 100)
    
    ax2.plot(hops_sorted, cumulative, 'ro-', linewidth=2, markersize=4)
    ax2.fill_between(hops_sorted, cumulative, alpha=0.3, color='red')
    ax2.set_xlabel('Hop Count', fontsize=12)
    ax2.set_ylabel('Cumulative Percentage (%)', fontsize=12)
    ax2.set_title('Cumulative Hop Distribution', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 105)
    
    # 标注关键点
    for threshold in [50, 80, 95]:
        for i, pct in enumerate(cumulative):
            if pct >= threshold:
                ax2.axhline(y=threshold, color='gray', linestyle='--', alpha=0.5)
                ax2.annotate(f'{threshold}% at {hops_sorted[i]} hops',
                           xy=(hops_sorted[i], threshold), fontsize=9,
                           xytext=(hops_sorted[i] + 1, threshold - 5),
                           arrowprops=dict(arrowstyle='->', color='gray'))
                break
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"跳数分布图已保存: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 visualize_ucb_paths.py <ucb_route_debug.txt路径> [topology文件路径] [输出目录]")
        sys.exit(1)
    
    log_path = sys.argv[1]
    topo_path = sys.argv[2] if len(sys.argv) > 2 else None
    output_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(log_path)
    
    if not os.path.exists(log_path):
        print(f"错误: 文件不存在: {log_path}")
        sys.exit(1)
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"正在解析日志: {log_path}")
    uid_events, link_usage, node_forward_count = parse_debug_log(log_path)
    print(f"共解析 {len(uid_events)} 个包的路径")
    print(f"共发现 {len(link_usage)} 条被使用的链路")
    
    # 生成节点位置
    print("正在生成节点布局...")
    node_positions, edges = generate_node_positions_from_paths(uid_events, link_usage)
    
    # 创建可视化
    print("正在生成可视化图...")
    
    # 1. 链路热力图
    create_topology_visualization(
        node_positions, edges, link_usage,
        os.path.join(output_dir, "ucb_link_heatmap.png"),
        "UCB Routing Link Heatmap"
    )
    
    # 2. 路径示例图
    create_path_sample_visualization(
        uid_events, node_positions,
        os.path.join(output_dir, "ucb_path_samples.png")
    )
    
    # 3. 跳数分布图
    create_hop_distribution_chart(
        uid_events,
        os.path.join(output_dir, "ucb_hop_distribution.png")
    )
    
    print(f"\n所有可视化图已保存到: {output_dir}")


if __name__ == '__main__':
    main()
