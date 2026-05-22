#!/usr/bin/env python3
"""
UCB 路径 3D 可视化脚本（基于 Cesium）

参考 satviz 架构，适配 UCB 分布式路由场景：
- 解析 UCB debug 日志（ucb_route_debug.txt）
- 使用 satviz 的 util.py 计算卫星轨道位置
- 生成 Cesium 3D HTML 可视化，展示数据包转发路径

依赖：
    pip install ephem pandas

使用方法：
    python3 visualize_ucb_paths_3d.py <ucb_route_debug.txt路径> [输出HTML路径]

输出：
    生成一个 HTML 文件，可在浏览器中打开查看 3D 路径可视化
"""

import math
import re
import sys
import os
from collections import defaultdict, Counter

# 添加 satviz 脚本路径以便导入 util.py
# 脚本位置: /root/hypatia/paper/ns3_experiments_ucb_iridium_66_6/tools/
# util.py 位置: /root/hypatia/satviz/scripts/util.py
SATVIZ_SCRIPTS = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'satviz', 'scripts')
)
sys.path.insert(0, SATVIZ_SCRIPTS)

try:
    from . import util
except (ImportError, SystemError):
    import util

# ============================================================
# 星座参数（Iridium 66 卫星 + 10 地面站）
# ============================================================
EARTH_RADIUS = 6378135.0

NAME = "iridium_66"
ECCENTRICITY = 0.0000001
ARG_OF_PERIGEE_DEGREE = 0.0
PHASE_DIFF = True
EPOCH = "2000-01-01 00:00:00"

# Iridium 星座参数
MEAN_MOTION_REV_PER_DAY = 14.34  # 约 780km 高度
ALTITUDE_M = 780000
NUM_ORBS = 6
NUM_SATS_PER_ORB = 11
INCLINATION_DEGREE = 86.4
TOTAL_SATS = NUM_ORBS * NUM_SATS_PER_ORB  # 66

# 地面站起始 ID（节点 ID >= 66 是地面站）
GS_START_ID = TOTAL_SATS  # 66

# ============================================================
# 文件路径
# ============================================================
SATVIZ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SATVIZ_DIR)))

topFile = os.path.join(PROJECT_ROOT, "satviz", "static_html", "top.html")
bottomFile = os.path.join(PROJECT_ROOT, "satviz", "static_html", "bottom.html")

# 地面站城市文件（使用 satviz 的地面站数据）
city_detail_file = os.path.join(
    PROJECT_ROOT, "paper", "satellite_networks_state", "input_data",
    "ground_stations_cities_sorted_by_estimated_2025_pop_top_1000.basic.txt"
)

# ============================================================
# 全局变量
# ============================================================
sat_objs = []
city_details = {}
ucb_paths = []  # 存储解析的 UCB 路径


def parse_ucb_debug_log(log_path):
    """
    解析 UCB debug 日志，提取路径信息
    
    返回: list of dict
        每个 dict 包含:
        - uid: 包唯一 ID
        - src: 源节点 ID
        - dst: 目的节点 ID
        - path: 路径节点列表
        - status: 'ARRIVE' 或 'DROP'
        - hop_count: 跳数
    """
    uid_events = defaultdict(list)
    
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
                    'path': path,
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
                })
    
    # 按 uid 整理路径
    paths = []
    for uid, events in uid_events.items():
        if not events:
            continue
        
        # 获取最终状态和最长路径
        final_status = 'IN_PROGRESS'
        longest_path = []
        src = events[0].get('src', 0)
        dst = events[0].get('dst', 0)
        
        for e in events:
            if e['type'] == 'ARRIVE':
                final_status = 'ARRIVE'
            elif e['type'] == 'DROP':
                final_status = 'DROP'
            
            if 'path' in e and len(e['path']) > len(longest_path):
                longest_path = e['path']
                src = e.get('src', src)
                dst = e.get('dst', dst)
        
        if longest_path:
            paths.append({
                'uid': uid,
                'src': src,
                'dst': dst,
                'path': longest_path,
                'status': final_status,
                'hop_count': len(longest_path) - 1,
            })
    
    return paths


def get_node_position(node_id, sat_objs, city_details, shifted_epoch):
    """
    获取节点在指定时刻的 3D 位置
    
    参数:
        node_id: 节点 ID
        sat_objs: 卫星对象列表
        city_details: 地面站信息
        shifted_epoch: 仿真时刻
    
    返回:
        (longitude, latitude, altitude_m) 或 None
    """
    import ephem
    
    if node_id < GS_START_ID:
        # 卫星节点
        if node_id < len(sat_objs):
            sat_objs[node_id]["sat_obj"].compute(shifted_epoch)
            sat_obj = sat_objs[node_id]["sat_obj"]
            return (
                math.degrees(sat_obj.sublong),
                math.degrees(sat_obj.sublat),
                sat_objs[node_id]["alt_km"] * 1000
            )
    else:
        # 地面站节点
        gs_id = node_id - GS_START_ID
        if gs_id in city_details:
            return (
                float(city_details[gs_id]["long_deg"]),
                float(city_details[gs_id]["lat_deg"]),
                0
            )
    
    return None


def generate_ucb_path_viz(ucb_paths, sat_objs, city_details, out_html_path, 
                          max_paths=20, show_all_sats=True, show_orbit_links=True):
    """
    生成 UCB 路径的 Cesium 3D 可视化 HTML
    
    参数:
        ucb_paths: UCB 路径列表
        sat_objs: 卫星对象列表
        city_details: 地面站信息
        out_html_path: 输出 HTML 路径
        max_paths: 最多展示的路径数
        show_all_sats: 是否显示所有卫星
        show_orbit_links: 是否显示轨道连线
    """
    import ephem
    import pandas as pd
    
    shifted_epoch = (pd.to_datetime(EPOCH) + pd.to_timedelta(0, unit='ms')).strftime(
        format='%Y/%m/%d %H:%M:%S.%f'
    )
    
    viz_string = ""
    
    # ============================================================
    # 1. 绘制所有卫星
    # ============================================================
    if show_all_sats:
        for i in range(len(sat_objs)):
            sat_objs[i]["sat_obj"].compute(shifted_epoch)
            sat_obj = sat_objs[i]["sat_obj"]
            lon = math.degrees(sat_obj.sublong)
            lat = math.degrees(sat_obj.sublat)
            alt = sat_objs[i]["alt_km"] * 1000
            viz_string += (
                "viewer.entities.add({name : 'SAT_" + str(i) + "', "
                "position: Cesium.Cartesian3.fromDegrees(" +
                str(lon) + ", " + str(lat) + ", " + str(alt) + "), "
                "ellipsoid : {radii : new Cesium.Cartesian3(15000.0, 15000.0, 15000.0), "
                "material : Cesium.Color.LIGHTGREY.withAlpha(0.6),}});\n"
            )
    
    # ============================================================
    # 2. 绘制轨道连线
    # ============================================================
    if show_orbit_links:
        orbit_links = util.find_orbit_links(sat_objs, NUM_ORBS, NUM_SATS_PER_ORB)
        for key in orbit_links:
            sat1 = orbit_links[key]["sat1"]
            sat2 = orbit_links[key]["sat2"]
            sat1_obj = sat_objs[sat1]["sat_obj"]
            sat2_obj = sat_objs[sat2]["sat_obj"]
            lon1 = math.degrees(sat1_obj.sublong)
            lat1 = math.degrees(sat1_obj.sublat)
            alt1 = sat_objs[sat1]["alt_km"] * 1000
            lon2 = math.degrees(sat2_obj.sublong)
            lat2 = math.degrees(sat2_obj.sublat)
            alt2 = sat_objs[sat2]["alt_km"] * 1000
            viz_string += (
                "viewer.entities.add({name : '', polyline: { positions: "
                "Cesium.Cartesian3.fromDegreesArrayHeights([" +
                str(lon1) + "," + str(lat1) + "," + str(alt1) + "," +
                str(lon2) + "," + str(lat2) + "," + str(alt2) + "]), "
                "width: 0.5, arcType: Cesium.ArcType.NONE, "
                "material: new Cesium.PolylineOutlineMaterialProperty({ "
                "color: Cesium.Color.GREY.withAlpha(0.2), outlineWidth: 0, "
                "outlineColor: Cesium.Color.BLACK})}});\n"
            )
    
    # ============================================================
    # 3. 绘制地面站
    # ============================================================
    for gs_id, gs_info in city_details.items():
        viz_string += (
            "viewer.entities.add({name : 'GS_" + str(gs_id) + " (" + gs_info['name'] + ")', "
            "position: Cesium.Cartesian3.fromDegrees(" +
            str(gs_info['long_deg']) + ", " + str(gs_info['lat_deg']) + ", 0), "
            "ellipsoid : {radii : new Cesium.Cartesian3(40000.0, 40000.0, 40000.0), "
            "material : Cesium.Color.GREEN.withAlpha(0.8),}});\n"
        )
        # 地面站标签
        viz_string += (
            "viewer.entities.add({name : '', "
            "position: Cesium.Cartesian3.fromDegrees(" +
            str(gs_info['long_deg']) + ", " + str(gs_info['lat_deg']) + ", 50000), "
            "label : {text : 'GS" + str(gs_id) + "', font : '12px sans-serif', "
            "fillColor : Cesium.Color.DARKGREEN, "
            "outlineColor : Cesium.Color.WHITE, outlineWidth : 2, "
            "style: Cesium.LabelStyle.FILL_AND_OUTLINE, "
            "verticalOrigin : Cesium.VerticalOrigin.BOTTOM}});\n"
        )
    
    # ============================================================
    # 4. 选择并绘制 UCB 路径
    # ============================================================
    
    # 按状态和跳数排序：优先展示成功到达的路径，按跳数分布选择代表性路径
    arrived = [p for p in ucb_paths if p['status'] == 'ARRIVE']
    dropped = [p for p in ucb_paths if p['status'] == 'DROP']
    
    # 按跳数分组，选择代表性路径
    def select_representative_paths(paths, max_count):
        """按跳数分布选择代表性路径"""
        if not paths:
            return []
        
        # 按跳数排序
        paths_sorted = sorted(paths, key=lambda x: x['hop_count'])
        
        if len(paths_sorted) <= max_count:
            return paths_sorted
        
        # 均匀采样
        step = len(paths_sorted) / max_count
        selected = []
        for i in range(max_count):
            idx = int(i * step)
            selected.append(paths_sorted[idx])
        
        return selected
    
    selected_arrived = select_representative_paths(arrived, max_paths // 2)
    selected_dropped = select_representative_paths(dropped, max_paths // 4)
    
    # 颜色方案
    PATH_COLORS = [
        "Cesium.Color.RED",
        "Cesium.Color.ORANGE",
        "Cesium.Color.BLUE",
        "Cesium.Color.PURPLE",
        "Cesium.Color.CYAN",
        "Cesium.Color.YELLOW",
        "Cesium.Color.MAGENTA",
        "Cesium.Color.LIME",
    ]
    
    path_index = 0
    
    # 绘制成功到达的路径
    for path_info in selected_arrived:
        color = PATH_COLORS[path_index % len(PATH_COLORS)]
        path = path_info['path']
        uid = path_info['uid']
        hop_count = path_info['hop_count']
        
        # 绘制路径线段
        for i in range(len(path) - 1):
            src_node = path[i]
            dst_node = path[i + 1]
            
            src_pos = get_node_position(src_node, sat_objs, city_details, shifted_epoch)
            dst_pos = get_node_position(dst_node, sat_objs, city_details, shifted_epoch)
            
            if src_pos and dst_pos:
                viz_string += (
                    "viewer.entities.add({name : 'Path_" + str(uid) + " (" + str(src_node) + "->" + str(dst_node) + ")', "
                    "polyline: { positions: "
                    "Cesium.Cartesian3.fromDegreesArrayHeights([" +
                    str(src_pos[0]) + "," + str(src_pos[1]) + "," + str(src_pos[2]) + "," +
                    str(dst_pos[0]) + "," + str(dst_pos[1]) + "," + str(dst_pos[2]) + "]), "
                    "width: 3.0, arcType: Cesium.ArcType.NONE, "
                    "material: new Cesium.PolylineOutlineMaterialProperty({ "
                    "color: " + color + ".withAlpha(0.9), outlineWidth: 1, "
                    "outlineColor: Cesium.Color.WHITE})}});\n"
                )
        
        # 标注起点（绿色星形）
        src_pos = get_node_position(path[0], sat_objs, city_details, shifted_epoch)
        if src_pos:
            viz_string += (
                "viewer.entities.add({name : 'SRC_" + str(uid) + "', "
                "position: Cesium.Cartesian3.fromDegrees(" +
                str(src_pos[0]) + ", " + str(src_pos[1]) + ", " + str(src_pos[2]) + "), "
                "ellipsoid : {radii : new Cesium.Cartesian3(30000.0, 30000.0, 30000.0), "
                "material : Cesium.Color.GREEN.withAlpha(1.0),}});\n"
            )
        
        # 标注终点（红色星形）
        dst_pos = get_node_position(path[-1], sat_objs, city_details, shifted_epoch)
        if dst_pos:
            viz_string += (
                "viewer.entities.add({name : 'DST_" + str(uid) + "', "
                "position: Cesium.Cartesian3.fromDegrees(" +
                str(dst_pos[0]) + ", " + str(dst_pos[1]) + ", " + str(dst_pos[2]) + "), "
                "ellipsoid : {radii : new Cesium.Cartesian3(30000.0, 30000.0, 30000.0), "
                "material : Cesium.Color.RED.withAlpha(1.0),}});\n"
            )
        
        # 路径标签
        mid_idx = len(path) // 2
        mid_node = path[mid_idx]
        mid_pos = get_node_position(mid_node, sat_objs, city_details, shifted_epoch)
        if mid_pos:
            viz_string += (
                "viewer.entities.add({name : '', "
                "position: Cesium.Cartesian3.fromDegrees(" +
                str(mid_pos[0]) + ", " + str(mid_pos[1]) + ", " + str(mid_pos[2] + 50000) + "), "
                "label : {text : 'UID" + str(uid) + " (" + str(hop_count) + "h)', font : '11px sans-serif', "
                "fillColor : " + color + ", "
                "outlineColor : Cesium.Color.WHITE, outlineWidth : 2, "
                "style: Cesium.LabelStyle.FILL_AND_OUTLINE, "
                "verticalOrigin : Cesium.VerticalOrigin.BOTTOM}});\n"
            )
        
        path_index += 1
    
    # 绘制丢弃的路径（灰色虚线）
    for path_info in selected_dropped:
        path = path_info['path']
        uid = path_info['uid']
        hop_count = path_info['hop_count']
        
        for i in range(len(path) - 1):
            src_node = path[i]
            dst_node = path[i + 1]
            
            src_pos = get_node_position(src_node, sat_objs, city_details, shifted_epoch)
            dst_pos = get_node_position(dst_node, sat_objs, city_details, shifted_epoch)
            
            if src_pos and dst_pos:
                viz_string += (
                    "viewer.entities.add({name : 'DROPPED_" + str(uid) + "', "
                    "polyline: { positions: "
                    "Cesium.Cartesian3.fromDegreesArrayHeights([" +
                    str(src_pos[0]) + "," + str(src_pos[1]) + "," + str(src_pos[2]) + "," +
                    str(dst_pos[0]) + "," + str(dst_pos[1]) + "," + str(dst_pos[2]) + "]), "
                    "width: 2.0, arcType: Cesium.ArcType.NONE, "
                    "material: new Cesium.PolylineOutlineMaterialProperty({ "
                    "color: Cesium.Color.GREY.withAlpha(0.5), outlineWidth: 1, "
                    "outlineColor: Cesium.Color.BLACK})}});\n"
                )
        
        # 丢弃路径标签
        if len(path) > 1:
            mid_idx = len(path) // 2
            mid_node = path[mid_idx]
            mid_pos = get_node_position(mid_node, sat_objs, city_details, shifted_epoch)
            if mid_pos:
                viz_string += (
                    "viewer.entities.add({name : '', "
                    "position: Cesium.Cartesian3.fromDegrees(" +
                    str(mid_pos[0]) + ", " + str(mid_pos[1]) + ", " + str(mid_pos[2] + 50000) + "), "
                    "label : {text : 'DROPPED UID" + str(uid) + " (" + str(hop_count) + "h)', font : '10px sans-serif', "
                    "fillColor : Cesium.Color.GREY, "
                    "outlineColor : Cesium.Color.WHITE, outlineWidth : 2, "
                    "style: Cesium.LabelStyle.FILL_AND_OUTLINE, "
                    "verticalOrigin : Cesium.VerticalOrigin.BOTTOM}});\n"
                )
    
    # ============================================================
    # 5. 添加图例
    # ============================================================
    viz_string += """
    // 添加图例
    var legendDiv = document.createElement('div');
    legendDiv.style.position = 'absolute';
    legendDiv.style.top = '10px';
    legendDiv.style.left = '10px';
    legendDiv.style.backgroundColor = 'rgba(255,255,255,0.9)';
    legendDiv.style.padding = '10px';
    legendDiv.style.borderRadius = '5px';
    legendDiv.style.fontSize = '12px';
    legendDiv.style.fontFamily = 'sans-serif';
    legendDiv.style.zIndex = '1000';
    legendDiv.innerHTML = '<b>UCB Path Visualization</b><br>' +
        '<span style="color:green">●</span> Ground Station<br>' +
        '<span style="color:lightgrey">●</span> Satellite<br>' +
        '<span style="color:red">━</span> Arrived Path<br>' +
        '<span style="color:grey">- -</span> Dropped Path<br>' +
        '<span style="color:green">★</span> Path Source<br>' +
        '<span style="color:red">★</span> Path Destination';
    document.body.appendChild(legendDiv);
    """
    
    # ============================================================
    # 6. 添加统计信息
    # ============================================================
    stats_html = """
    // 添加统计信息
    var statsDiv = document.createElement('div');
    statsDiv.style.position = 'absolute';
    statsDiv.style.bottom = '10px';
    statsDiv.style.left = '10px';
    statsDiv.style.backgroundColor = 'rgba(255,255,255,0.9)';
    statsDiv.style.padding = '10px';
    statsDiv.style.borderRadius = '5px';
    statsDiv.style.fontSize = '12px';
    statsDiv.style.fontFamily = 'sans-serif';
    statsDiv.style.zIndex = '1000';
    statsDiv.innerHTML = '<b>Statistics</b><br>' +
        'Total Paths: {total_paths}<br>' +
        'Arrived: {arrived_count}<br>' +
        'Dropped: {dropped_count}<br>' +
        'Displayed: {displayed_paths}<br>' +
        'Constellation: {num_orbs} orbits x {num_sats_per_orb} sats = {total_sats} satellites';
    document.body.appendChild(statsDiv);
    """.format(
        total_paths=len(ucb_paths),
        arrived_count=len(arrived),
        dropped_count=len(dropped),
        displayed_paths=len(selected_arrived) + len(selected_dropped),
        num_orbs=NUM_ORBS,
        num_sats_per_orb=NUM_SATS_PER_ORB,
        total_sats=TOTAL_SATS,
    )
    
    viz_string += stats_html
    
    # ============================================================
    # 7. 写入 HTML 文件
    # ============================================================
    with open(topFile, 'r') as fi:
        top_content = fi.read()
    with open(bottomFile, 'r') as fb:
        bottom_content = fb.read()
    
    with open(out_html_path, 'w') as fo:
        fo.write(top_content)
        fo.write(viz_string)
        fo.write(bottom_content)
    
    print("HTML 可视化文件已生成: " + out_html_path)
    print("  总路径数: " + str(len(ucb_paths)))
    print("  成功到达: " + str(len(arrived)))
    print("  被丢弃: " + str(len(dropped)))
    print("  展示路径: " + str(len(selected_arrived) + len(selected_dropped)))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 visualize_ucb_paths_3d.py <ucb_route_debug.txt路径> [输出HTML路径]")
        sys.exit(1)
    
    log_path = sys.argv[1]
    out_html_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(log_path):
        print("错误: 文件不存在: " + log_path)
        sys.exit(1)
    
    # 默认输出路径
    if out_html_path is None:
        out_dir = os.path.dirname(log_path)
        out_html_path = os.path.join(out_dir, "ucb_path_3d_viz.html")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(out_html_path), exist_ok=True)
    
    print("正在解析 UCB debug 日志: " + log_path)
    ucb_paths = parse_ucb_debug_log(log_path)
    print("共解析 " + str(len(ucb_paths)) + " 条路径")
    
    # 生成卫星对象
    print("正在生成卫星轨道位置...")
    sat_objs = util.generate_sat_obj_list(
        NUM_ORBS,
        NUM_SATS_PER_ORB,
        EPOCH,
        PHASE_DIFF,
        INCLINATION_DEGREE,
        ECCENTRICITY,
        ARG_OF_PERIGEE_DEGREE,
        MEAN_MOTION_REV_PER_DAY,
        ALTITUDE_M
    )
    
    # 读取地面站信息
    city_details = {}
    if os.path.exists(city_detail_file):
        city_details = util.read_city_details(city_details, city_detail_file)
        print("读取 " + str(len(city_details)) + " 个地面站信息")
    else:
        print("警告: 地面站文件不存在: " + city_detail_file)
        # 使用默认地面站
        for i in range(10):
            city_details[i] = {
                "name": "GS_" + str(i),
                "lat_deg": str(40.0 + i * 5),
                "long_deg": str(-70.0 + i * 10),
                "alt_km": 0
            }
    
    # 生成可视化
    print("正在生成 3D 可视化...")
    generate_ucb_path_viz(
        ucb_paths=ucb_paths,
        sat_objs=sat_objs,
        city_details=city_details,
        out_html_path=out_html_path,
        max_paths=20,
        show_all_sats=True,
        show_orbit_links=True
    )
    
    print("\n请在浏览器中打开: " + out_html_path)


if __name__ == '__main__':
    main()
