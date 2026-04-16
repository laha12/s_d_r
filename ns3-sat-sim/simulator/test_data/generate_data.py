import argparse
import math
import random


def poisson_sample(lmbda):
    L = math.exp(-lmbda)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def parse_pairs(pairs_str):
    pairs = []
    for item in pairs_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"节点对格式错误: {item}，正确格式示例: 9:11,10:12")
        src, dst = item.split(":", 1)
        src_id = int(src.strip())
        dst_id = int(dst.strip())
        if src_id < 0 or dst_id < 0:
            raise ValueError("节点 ID 必须是非负整数")
        if src_id == dst_id:
            raise ValueError(f"源和目的节点不能相同: {src_id}")
        pairs.append((src_id, dst_id))
    if not pairs:
        raise ValueError("至少需要一个源-目的节点对")
    return pairs


def parse_pair_start_or_end_times(pair_start_or_end_times_str):
    pair_start_or_end_times = {}
    for item in pair_start_or_end_times_str.split(","):
        item = item.strip()
        if not item:
            continue
        if "@" not in item:
            raise ValueError(f"pair_start_times 格式错误: {item}，正确格式示例: 9:11@0,10:11@2000000000")
        pair_part, start_part = item.split("@", 1)
        if ":" not in pair_part:
            raise ValueError(f"pair_start_times 节点对格式错误: {item}，正确格式示例: 9:11@0")
        src, dst = pair_part.split(":", 1)
        src_id = int(src.strip())
        dst_id = int(dst.strip())
        start_ns = int(start_part.strip())
        if src_id < 0 or dst_id < 0:
            raise ValueError("节点 ID 必须是非负整数")
        if src_id == dst_id:
            raise ValueError(f"源和目的节点不能相同: {src_id}")
        if start_ns < 0:
            raise ValueError("每个 pair 的起始时间必须是非负整数")
        pair_start_or_end_times[(src_id, dst_id)] = start_ns
    return pair_start_or_end_times


def generate(
    out_csv_path,
    node_pairs,
    slot_len_ns,
    sim_end_ns,
    lambda_per_s,
    traffic_start_ns=0,
    traffic_end_ns=None,
    pair_start_times=None,
    pair_end_times=None,
    seed=1,
    print_samples=False,
):
    if slot_len_ns <= 0:
        raise ValueError("slot_len_ns 必须大于 0")
    if sim_end_ns <= 0:
        raise ValueError("sim_end_ns 必须大于 0")
    if lambda_per_s < 0:
        raise ValueError("lambda_per_s 不能为负数")
    if traffic_start_ns < 0:
        raise ValueError("traffic_start_ns 不能为负数")
    if traffic_end_ns is None:
        traffic_end_ns = int(sim_end_ns * 0.7)
    if traffic_end_ns <= traffic_start_ns:
        raise ValueError("traffic_end_ns 必须大于 traffic_start_ns")
    if traffic_start_ns >= sim_end_ns:
        raise ValueError("traffic_start_ns 必须小于 sim_end_ns")
    if pair_start_times is None:
        pair_start_times = {}
    if pair_end_times is None:
        pair_end_times = {}

    pair_windows = {}
    for src_id, dst_id in node_pairs:
        pair_start_ns = pair_start_times.get((src_id, dst_id), traffic_start_ns)
        pair_end_ns = pair_end_times.get((src_id, dst_id), traffic_end_ns)
        # 时间窗口调整
        effective_start_ns = max(traffic_start_ns, pair_start_ns)
        effective_end_ns = min(traffic_end_ns, pair_end_ns)
        if pair_start_ns >= sim_end_ns:
            raise ValueError(f"pair {src_id}:{dst_id} 的起始时间必须小于 sim_end_ns")
        if pair_end_ns <= 0:
            raise ValueError(f"pair {src_id}:{dst_id} 的结束时间必须大于 0")
        if effective_end_ns <= effective_start_ns:
            raise ValueError(
                f"pair {src_id}:{dst_id} 的有效时间窗口为空: "
                f"start={effective_start_ns}, end={effective_end_ns}"
            )
        pair_windows[(src_id, dst_id)] = (effective_start_ns, effective_end_ns)

    random.seed(seed)

    slot_len_s = slot_len_ns / 1e9
    num_slots = sim_end_ns // slot_len_ns

    udp_burst_id = 0
    lines = []

    for t in range(num_slots - 1):
        slot_start_ns = t * slot_len_ns
        if slot_start_ns < traffic_start_ns or slot_start_ns >= traffic_end_ns:
            continue

        start_next_ns = (t + 1) * slot_len_ns
        if start_next_ns >= sim_end_ns:
            break
        # 当前时隙是否在有效时间窗口内 是否有数据产生
        for src_id, dst_id in node_pairs:
            effective_start_ns, effective_end_ns = pair_windows[(src_id, dst_id)]
            if slot_start_ns < effective_start_ns or slot_start_ns >= effective_end_ns:
                continue
            n_pkts = poisson_sample(lambda_per_s * slot_len_s)
            if print_samples:
                print(f"slot={t};src={src_id};dst={dst_id};n={n_pkts}")
            if n_pkts <= 0:
                continue

            rate_mbps = (n_pkts * 1500.0 * 8000.0) / float(slot_len_ns)
            metadata = f"slot={t};src={src_id};dst={dst_id};n={n_pkts}"
            line = f"{udp_burst_id},{src_id},{dst_id},{rate_mbps},{start_next_ns},{slot_len_ns},,{metadata}"
            lines.append(line)
            udp_burst_id += 1

    with open(out_csv_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    print(f"写入完成: {out_csv_path}")
    print(f"总 burst 条数: {len(lines)}")


def generate_tcp_flow_schedule(
    out_csv_path,
    node_pairs,
    slot_len_ns,
    sim_end_ns,
    rate_mbps=None,
    flow_size_byte=1000000,
    packet_lambda_per_s=None,
    packet_size_byte=1500,
    traffic_start_ns=0,
    traffic_end_ns=None,
    pair_start_times=None,
    pair_end_times=None,
    min_flow_interval_ns=0,
    seed=1,
    print_samples=False,
):
    if slot_len_ns <= 0:
        raise ValueError("slot_len_ns 必须大于 0")
    if sim_end_ns <= 0:
        raise ValueError("sim_end_ns 必须大于 0")
    if rate_mbps is not None and rate_mbps < 0:
        raise ValueError("rate_mbps 不能为负数")
    if packet_lambda_per_s is not None and packet_lambda_per_s < 0:
        raise ValueError("packet_lambda_per_s 不能为负数")
    if rate_mbps is None and packet_lambda_per_s is None:
        raise ValueError("TCP 模式下至少需要提供 rate_mbps 或 packet_lambda_per_s")
    if flow_size_byte <= 0:
        raise ValueError("flow_size_byte 必须大于 0")
    if packet_size_byte <= 0:
        raise ValueError("packet_size_byte 必须大于 0")
    if traffic_start_ns < 0:
        raise ValueError("traffic_start_ns 不能为负数")
    if traffic_end_ns is None:
        traffic_end_ns = int(sim_end_ns * 0.85)
    if traffic_end_ns <= traffic_start_ns:
        raise ValueError("traffic_end_ns 必须大于 traffic_start_ns")
    if traffic_start_ns >= sim_end_ns:
        raise ValueError("traffic_start_ns 必须小于 sim_end_ns")
    if pair_start_times is None:
        pair_start_times = {}
    if pair_end_times is None:
        pair_end_times = {}
    if not node_pairs:
        raise ValueError("至少需要一个源-目的节点对")
    if min_flow_interval_ns < 0:
        raise ValueError("min_flow_interval_ns 不能为负数")

    pair_windows = {}
    for src_id, dst_id in node_pairs:
        pair_start_ns = pair_start_times.get((src_id, dst_id), traffic_start_ns)
        pair_end_ns = pair_end_times.get((src_id, dst_id), traffic_end_ns)
        effective_start_ns = max(traffic_start_ns, pair_start_ns)
        effective_end_ns = min(traffic_end_ns, pair_end_ns)
        if pair_start_ns >= sim_end_ns:
            raise ValueError(f"pair {src_id}:{dst_id} 的起始时间必须小于 sim_end_ns")
        if pair_end_ns <= 0:
            raise ValueError(f"pair {src_id}:{dst_id} 的结束时间必须大于 0")
        if effective_end_ns <= effective_start_ns:
            raise ValueError(
                f"pair {src_id}:{dst_id} 的有效时间窗口为空: "
                f"start={effective_start_ns}, end={effective_end_ns}"
            )
        pair_windows[(src_id, dst_id)] = (effective_start_ns, effective_end_ns)

    random.seed(seed)

    slot_len_s = slot_len_ns / 1e9
    num_slots = sim_end_ns // slot_len_ns
    if packet_lambda_per_s is not None:
        lambda_per_s = packet_lambda_per_s
        schedule_size_byte = packet_size_byte
        lambda_mode = "packet"
    else:
        # IMPORTANT:
        # rate_mbps is interpreted as per source-destination pair (i.e., per ground station source stream),
        # not as a global aggregate rate over all pairs.
        per_pair_rate_bps = rate_mbps * 1e6
        lambda_per_s = per_pair_rate_bps / (flow_size_byte * 8.0)
        schedule_size_byte = flow_size_byte
        lambda_mode = "flow_per_pair_rate_mbps"

    events = []
    for t in range(num_slots):
        slot_start_ns = t * slot_len_ns
        if slot_start_ns < traffic_start_ns or slot_start_ns >= traffic_end_ns:
            continue

        slot_end_ns = min((t + 1) * slot_len_ns, sim_end_ns)
        for src_id, dst_id in node_pairs:
            effective_start_ns, effective_end_ns = pair_windows[(src_id, dst_id)]
            if slot_start_ns >= effective_end_ns or slot_end_ns <= effective_start_ns:
                continue

            n_flows = poisson_sample(lambda_per_s * slot_len_s)
            if print_samples:
                print(f"slot={t};src={src_id};dst={dst_id};n={n_flows}")
            if n_flows <= 0:
                continue

            for _ in range(n_flows):
                start_low_ns = max(slot_start_ns, effective_start_ns)
                start_high_ns = min(slot_end_ns, effective_end_ns)
                if start_high_ns <= start_low_ns:
                    continue
                start_time_ns = start_low_ns + int(random.random() * (start_high_ns - start_low_ns))
                metadata = (
                    f"slot={t};src={src_id};dst={dst_id};"
                    f"rate_mbps={rate_mbps};flow_size_byte={flow_size_byte};"
                    f"packet_lambda_per_s={packet_lambda_per_s};packet_size_byte={packet_size_byte};"
                    f"lambda_mode={lambda_mode}"
                )
                events.append((start_time_ns, src_id, dst_id, metadata))

    events.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    if min_flow_interval_ns > 0:
        pair_last_start = {}
        filtered_events = []
        for event in events:
            start_time_ns, src_id, dst_id, metadata = event
            pair_key = (src_id, dst_id)
            effective_start_ns, effective_end_ns = pair_windows[pair_key]
            if pair_key in pair_last_start:
                earliest_start = pair_last_start[pair_key] + min_flow_interval_ns
                if start_time_ns < earliest_start:
                    start_time_ns = earliest_start
            if start_time_ns >= effective_end_ns:
                continue
            pair_last_start[pair_key] = start_time_ns
            filtered_events.append((start_time_ns, src_id, dst_id, metadata))
        events = filtered_events
        events.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    with open(out_csv_path, "w", encoding="utf-8") as f:
        for flow_id, event in enumerate(events):
            start_time_ns, src_id, dst_id, metadata = event
            line = f"{flow_id},{src_id},{dst_id},{schedule_size_byte},{start_time_ns},,{metadata}"
            f.write(line + "\n")

    print(f"写入完成: {out_csv_path}")
    print(f"总 tcp flow 条数: {len(events)}")


def build_arg_parser():
    parser = argparse.ArgumentParser(description="生成 UDP burst schedule CSV")
    parser.add_argument("--protocol", choices=["udp", "tcp"], default="udp")
    parser.add_argument("--out-csv-path", default="./ucb_run/ucb_udp_burst_schedule.csv")
    parser.add_argument("--pairs", default="9:11,10:11", help="源-目的节点对，格式: src:dst,src:dst")
    parser.add_argument("--slot-len-ns", type=int, default=100000000)
    parser.add_argument("--sim-end-ns", type=int, default=5000000000)
    parser.add_argument("--traffic-start-ns", type=int, default=0)
    parser.add_argument("--traffic-end-ns", type=int, default=None)
    parser.add_argument(
        "--pair-start-times",
        default="",
        help="每个节点对独立起始时间，格式: src:dst@start_ns,src:dst@start_ns",
    )
    parser.add_argument(
        "--pair-end-times",
        default="",
        help="每个节点对独立结束时间，格式: src:dst@end_ns,src:dst@end_ns",
    )
    # *0.012
    parser.add_argument("--lambda-per-s", type=float, default=10)
    parser.add_argument(
        "--rate-mbps",
        type=float,
        default=None,
        help="TCP flow mode: per source-destination pair rate in Mbps (not global aggregate rate)",
    )
    parser.add_argument("--packet-lambda-per-s", type=float, default=None)
    parser.add_argument("--flow-size-byte", type=int, default=1000000)
    parser.add_argument("--packet-size-byte", type=int, default=1500)
    parser.add_argument("--min-flow-interval-ns", type=int, default=0, help="同一节点对相邻流的最小启动间隔(ns)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--print-samples", action="store_true")
    return parser


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    node_pairs = parse_pairs(args.pairs)
    pair_start_times = parse_pair_start_or_end_times(args.pair_start_times)
    pair_end_times = parse_pair_start_or_end_times(args.pair_end_times)
    
    if args.protocol == "udp":
        generate(
            out_csv_path=args.out_csv_path,
            node_pairs=node_pairs,
            slot_len_ns=args.slot_len_ns,
            sim_end_ns=args.sim_end_ns,
            lambda_per_s=args.lambda_per_s,
            traffic_start_ns=args.traffic_start_ns,
            traffic_end_ns=args.traffic_end_ns,
            pair_start_times=pair_start_times,
            pair_end_times=pair_end_times,
            seed=args.seed,
            print_samples=args.print_samples,
        )
    else:
        if args.rate_mbps is None and args.packet_lambda_per_s is None:
            raise ValueError("TCP 模式下必须提供 --rate-mbps 或 --packet-lambda-per-s")
        generate_tcp_flow_schedule(
            out_csv_path=args.out_csv_path,
            node_pairs=node_pairs,
            slot_len_ns=args.slot_len_ns,
            sim_end_ns=args.sim_end_ns,
            rate_mbps=args.rate_mbps,
            packet_lambda_per_s=args.packet_lambda_per_s,
            flow_size_byte=args.flow_size_byte,
            packet_size_byte=args.packet_size_byte,
            traffic_start_ns=args.traffic_start_ns,
            traffic_end_ns=args.traffic_end_ns,
            pair_start_times=pair_start_times,
            pair_end_times=pair_end_times,
            min_flow_interval_ns=args.min_flow_interval_ns,
            seed=args.seed,
            print_samples=args.print_samples,
        )
