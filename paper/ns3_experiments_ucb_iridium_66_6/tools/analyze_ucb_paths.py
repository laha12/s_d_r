#!/usr/bin/env python3
"""
UCB 路径追踪日志分析脚本

功能：
1. 解析 ucb_route_debug.txt 日志文件
2. 统计路径跳数分布、环路检测、可达性
3. 按源-目的对分组分析
4. 生成分析报告

使用方法：
    python3 analyze_ucb_paths.py <ucb_route_debug.txt路径> [输出目录]
"""

import re
import sys
import os
from collections import defaultdict, Counter

def parse_debug_log(log_path):
    """解析 UCB debug 日志，提取每条包的路径信息"""
    
    # 按 uid 分组的事件
    uid_events = defaultdict(list)
    
    with open(log_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
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
                valid_arms = [int(x) for x in fwd_match.group(6).split(',') if x.strip()]
                path = [int(x) for x in fwd_match.group(7).split(',') if x.strip()]
                
                uid_events[uid].append({
                    'type': 'FWD',
                    'node': node,
                    'src': src,
                    'dst': dst,
                    'selected': selected,
                    'valid_arms': valid_arms,
                    'path': path,
                    'line': line_num
                })
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
                    'line': line_num
                })
                continue
            
            # 解析 [DROP] 行
            drop_match = re.match(
                r'\[UCB_DEBUG\]\[DROP\].*?node=(\d+)\s+src=(\d+)\s+dst=(\d+)\s+uid=(\d+)\s+.*?'
                r'path=\[([^\]]*)\]',
                line
            )
            if drop_match:
                node = int(drop_match.group(1))
                src = int(drop_match.group(2))
                dst = int(drop_match.group(3))
                uid = int(drop_match.group(4))
                path = [int(x) for x in drop_match.group(5).split(',') if x.strip()]
                
                uid_events[uid].append({
                    'type': 'DROP',
                    'node': node,
                    'src': src,
                    'dst': dst,
                    'path': path,
                    'line': line_num
                })
    
    return uid_events


def analyze_packet_path(events):
    """分析单个包的路径特征"""
    
    # 获取最终状态
    final_event = events[-1]
    src = final_event.get('src', events[0].get('src'))
    dst = final_event.get('dst', events[0].get('dst'))
    
    # 获取最长路径（通常是最终路径）
    longest_path = []
    for e in events:
        if 'path' in e and len(e['path']) > len(longest_path):
            longest_path = e['path']
    
    # 确定状态
    status = 'IN_PROGRESS'
    for e in events:
        if e['type'] == 'ARRIVE':
            status = 'ARRIVE'
            break
        elif e['type'] == 'DROP':
            status = 'DROP'
            break
    
    # 跳数
    hop_count = len(longest_path) - 1 if len(longest_path) > 0 else 0
    
    # 环路检测：路径中是否有重复节点
    has_loop = len(longest_path) != len(set(longest_path)) if longest_path else False
    
    # 如果是环路，找出第一个重复节点
    loop_node = None
    if has_loop:
        seen = set()
        for node in longest_path:
            if node in seen:
                loop_node = node
                break
            seen.add(node)
    
    # 候选臂数量统计
    arm_counts = []
    for e in events:
        if e['type'] == 'FWD' and 'valid_arms' in e:
            arm_counts.append(len(e['valid_arms']))
    
    return {
        'src': src,
        'dst': dst,
        'status': status,
        'path': longest_path,
        'hop_count': hop_count,
        'has_loop': has_loop,
        'loop_node': loop_node,
        'total_events': len(events),
        'avg_arm_count': sum(arm_counts) / len(arm_counts) if arm_counts else 0,
        'max_arm_count': max(arm_counts) if arm_counts else 0,
    }


def generate_report(uid_events, output_dir):
    """生成分析报告"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 分析所有包
    all_results = []
    for uid, events in uid_events.items():
        result = analyze_packet_path(events)
        result['uid'] = uid
        all_results.append(result)
    
    # === 总体统计 ===
    total_packets = len(all_results)
    arrived = sum(1 for r in all_results if r['status'] == 'ARRIVE')
    dropped = sum(1 for r in all_results if r['status'] == 'DROP')
    in_progress = sum(1 for r in all_results if r['status'] == 'IN_PROGRESS')
    
    # 跳数统计（只看到达的包）
    arrived_results = [r for r in all_results if r['status'] == 'ARRIVE']
    hop_counts = [r['hop_count'] for r in arrived_results]
    
    # 环路统计
    loops = sum(1 for r in all_results if r['has_loop'])
    
    # 按源-目的对分组
    src_dst_groups = defaultdict(list)
    for r in all_results:
        key = (r['src'], r['dst'])
        src_dst_groups[key].append(r)
    
    # === 生成报告 ===
    report_lines = []
    report_lines.append("# UCB 路径追踪分析报告")
    report_lines.append("")
    report_lines.append("## 一、总体统计")
    report_lines.append("")
    report_lines.append(f"| 指标 | 数值 |")
    report_lines.append(f"|------|------|")
    report_lines.append(f"| 总包数 | {total_packets} |")
    report_lines.append(f"| 成功到达 | {arrived} ({arrived/total_packets*100:.1f}%) |")
    report_lines.append(f"| 被丢弃 | {dropped} ({dropped/total_packets*100:.1f}%) |")
    report_lines.append(f"| 仿真结束仍在传输 | {in_progress} ({in_progress/total_packets*100:.1f}%) |")
    report_lines.append(f"| 存在环路 | {loops} ({loops/total_packets*100:.1f}%) |")
    report_lines.append("")
    
    if hop_counts:
        report_lines.append("## 二、跳数分布（仅成功到达的包）")
        report_lines.append("")
        hop_counter = Counter(hop_counts)
        report_lines.append(f"| 跳数 | 包数 | 占比 |")
        report_lines.append(f"|------|------|------|")
        for hops in sorted(hop_counter.keys()):
            count = hop_counter[hops]
            report_lines.append(f"| {hops} | {count} | {count/len(arrived_results)*100:.1f}% |")
        report_lines.append("")
        report_lines.append(f"- 平均跳数: {sum(hop_counts)/len(hop_counts):.2f}")
        report_lines.append(f"- 最小跳数: {min(hop_counts)}")
        report_lines.append(f"- 最大跳数: {max(hop_counts)}")
        report_lines.append("")
    
    report_lines.append("## 三、源-目的对分析")
    report_lines.append("")
    report_lines.append(f"共 {len(src_dst_groups)} 个源-目的对")
    report_lines.append("")
    report_lines.append("| 源节点 | 目的节点 | 总包数 | 到达率 | 平均跳数 | 环路率 | 平均候选臂数 |")
    report_lines.append("|--------|---------|--------|--------|---------|--------|-------------|")
    
    for (src, dst), results in sorted(src_dst_groups.items()):
        n_total = len(results)
        n_arrived = sum(1 for r in results if r['status'] == 'ARRIVE')
        arrive_rate = n_arrived / n_total * 100 if n_total > 0 else 0
        avg_hops = sum(r['hop_count'] for r in results if r['status'] == 'ARRIVE') / max(n_arrived, 1)
        n_loops = sum(1 for r in results if r['has_loop'])
        loop_rate = n_loops / n_total * 100
        avg_arms = sum(r['avg_arm_count'] for r in results) / n_total
        
        report_lines.append(
            f"| {src} | {dst} | {n_total} | {arrive_rate:.1f}% | {avg_hops:.1f} | {loop_rate:.1f}% | {avg_arms:.1f} |"
        )
    
    report_lines.append("")
    
    # === 典型路径示例 ===
    report_lines.append("## 四、典型路径示例")
    report_lines.append("")
    
    # 展示每个源-目的对的一条成功路径
    for (src, dst), results in sorted(src_dst_groups.items()):
        arrived_pkts = [r for r in results if r['status'] == 'ARRIVE']
        if arrived_pkts:
            # 取第一个到达的包
            sample = arrived_pkts[0]
            path_str = " -> ".join(str(n) for n in sample['path'])
            report_lines.append(f"**{src} -> {dst}** (uid={sample['uid']}, 跳数={sample['hop_count']}):")
            report_lines.append(f"")
            report_lines.append(f"```")
            report_lines.append(f"{path_str}")
            report_lines.append(f"```")
            report_lines.append("")
    
    # === 环路分析 ===
    loop_results = [r for r in all_results if r['has_loop']]
    if loop_results:
        report_lines.append("## 五、环路分析")
        report_lines.append("")
        report_lines.append(f"共发现 {len(loop_results)} 个包存在环路")
        report_lines.append("")
        
        # 按环路节点分组
        loop_node_counter = Counter(r['loop_node'] for r in loop_results if r['loop_node'])
        report_lines.append("### 环路节点分布")
        report_lines.append("")
        report_lines.append("| 环路节点 | 出现次数 |")
        report_lines.append("|---------|---------|")
        for node, count in loop_node_counter.most_common(20):
            report_lines.append(f"| {node} | {count} |")
        report_lines.append("")
        
        # 展示几个典型环路路径
        report_lines.append("### 典型环路路径示例")
        report_lines.append("")
        for r in loop_results[:5]:
            path_str = " -> ".join(str(n) for n in r['path'])
            report_lines.append(f"**uid={r['uid']}, {r['src']}->{r['dst']}, 环路节点={r['loop_node']}:**")
            report_lines.append(f"")
            report_lines.append(f"```")
            report_lines.append(f"{path_str}")
            report_lines.append(f"```")
            report_lines.append("")
    
    # 写入报告
    report_path = os.path.join(output_dir, "ucb_path_analysis_report.md")
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"报告已生成: {report_path}")
    print(f"总包数: {total_packets}")
    print(f"到达率: {arrived/total_packets*100:.1f}%")
    print(f"环路率: {loops/total_packets*100:.1f}%")
    
    return report_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_ucb_paths.py <ucb_route_debug.txt路径> [输出目录]")
        sys.exit(1)
    
    log_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(log_path)
    
    if not os.path.exists(log_path):
        print(f"错误: 文件不存在: {log_path}")
        sys.exit(1)
    
    print(f"正在解析日志: {log_path}")
    uid_events = parse_debug_log(log_path)
    print(f"共解析 {len(uid_events)} 个包的路径")
    
    generate_report(uid_events, output_dir)


if __name__ == '__main__':
    main()
