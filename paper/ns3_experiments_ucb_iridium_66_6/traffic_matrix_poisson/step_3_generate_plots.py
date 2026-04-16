import csv
import math
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str((Path(__file__).resolve().parent / ".matplotlib_cache")))

import exputil
import matplotlib.pyplot as plt

try:
    from .run_list import get_tcp_run_list
except (ImportError, SystemError):
    from run_list import get_tcp_run_list


def read_csv_rows(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return [row for row in csv.reader(f) if row]


def compute_jains_fairness(values):
    if not values:
        return 0.0
    total = sum(values)
    if total <= 0:
        return 0.0
    total_sq = sum(v * v for v in values)
    if total_sq <= 0:
        return 0.0
    return (total * total) / (len(values) * total_sq)


def aggregate_delay_metrics(logs_ns3_dir, max_valid_rtt_ns, unreachable_pairs=None):
    all_rtts = []
    reachable_rtts = []
    for file_path in Path(logs_ns3_dir).glob("tcp_flow_*_rtt.csv"):
        flow_id = file_path.stem.split("_")[2]
        flow_rtts = []
        for row in read_csv_rows(file_path):
            if len(row) < 3:
                continue
            rtt_ns = float(row[2])
            if rtt_ns <= 0 or rtt_ns > max_valid_rtt_ns:
                continue
            flow_rtts.append(rtt_ns)
            all_rtts.append(rtt_ns)
        is_unreachable = False
        if unreachable_pairs is not None:
            flows_csv_path = Path(logs_ns3_dir) / "tcp_flows.csv"
            if not hasattr(aggregate_delay_metrics, '_flows_cache') or aggregate_delay_metrics._flows_cache_path != str(flows_csv_path):
                aggregate_delay_metrics._flows_cache = read_csv_rows(flows_csv_path)
                aggregate_delay_metrics._flows_cache_path = str(flows_csv_path)
            for fr in aggregate_delay_metrics._flows_cache:
                if fr and fr[0] == flow_id and len(fr) >= 3:
                    if (fr[1], fr[2]) in unreachable_pairs:
                        is_unreachable = True
                    break
        if not is_unreachable:
            reachable_rtts.extend(flow_rtts)

    def calc_stats(rtts):
        if not rtts:
            return math.nan, math.nan, math.nan
        sorted_rtts = sorted(rtts)
        n = len(sorted_rtts)
        mean_delay = (sum(sorted_rtts) / n) / 2.0 / 1e6
        median_delay = sorted_rtts[n // 2] / 2.0 / 1e6
        p95_idx = min(int(n * 0.95), n - 1)
        p95_delay = sorted_rtts[p95_idx] / 2.0 / 1e6
        return mean_delay, median_delay, p95_delay

    all_mean, all_median, all_p95 = calc_stats(all_rtts)
    reach_mean, reach_median, reach_p95 = calc_stats(reachable_rtts)

    return {
        "avg_delay_ms": all_mean,
        "median_delay_ms": all_median,
        "p95_delay_ms": all_p95,
        "reachable_avg_delay_ms": reach_mean,
        "reachable_median_delay_ms": reach_median,
        "reachable_p95_delay_ms": reach_p95,
    }


def aggregate_load_balance(logs_ns3_dir):
    utilization_path = Path(logs_ns3_dir) / "isl_utilization.csv"
    if not utilization_path.exists():
        return math.nan

    per_link_values = defaultdict(list)
    for row in read_csv_rows(utilization_path):
        if len(row) < 5:
            continue
        link_key = (int(row[0]), int(row[1]))
        per_link_values[link_key].append(float(row[4]))

    mean_utilizations = []
    for samples in per_link_values.values():
        if samples:
            mean_utilizations.append(sum(samples) / len(samples))
    return compute_jains_fairness(mean_utilizations)


def identify_unreachable_pairs(tcp_flows_rows, min_flows_threshold=3):
    pair_stats = defaultdict(lambda: {"total": 0, "completed": 0})
    for row in tcp_flows_rows:
        if len(row) >= 9:
            pair = (row[1], row[2])
            pair_stats[pair]["total"] += 1
            if row[8] == "YES":
                pair_stats[pair]["completed"] += 1
    unreachable = set()
    for pair, stats in pair_stats.items():
        if stats["total"] >= min_flows_threshold and stats["completed"] == 0:
            unreachable.add(pair)
    return unreachable


def aggregate_run_metrics(run):
    logs_ns_dir = Path("runs") / run["name"] / "logs_ns3"
    finished_path = logs_ns_dir / "finished.txt"
    if not finished_path.exists() or finished_path.read_text(encoding="utf-8").strip() != "Yes":
        return None

    tcp_flows_rows = read_csv_rows(logs_ns_dir / "tcp_flows.csv")

    unreachable_pairs = identify_unreachable_pairs(tcp_flows_rows)

    reachable_rows = [
        row for row in tcp_flows_rows
        if len(row) >= 3 and (row[1], row[2]) not in unreachable_pairs
    ]
    unreachable_rows = [
        row for row in tcp_flows_rows
        if len(row) >= 3 and (row[1], row[2]) in unreachable_pairs
    ]

    total_size_byte = sum(int(row[3]) for row in tcp_flows_rows if len(row) >= 8)
    total_sent_byte = sum(int(row[7]) for row in tcp_flows_rows if len(row) >= 8)

    r_total_size_byte = sum(int(row[3]) for row in reachable_rows if len(row) >= 8)
    r_total_sent_byte = sum(int(row[7]) for row in reachable_rows if len(row) >= 8)

    u_total_size_byte = sum(int(row[3]) for row in unreachable_rows if len(row) >= 8)
    u_total_sent_byte = sum(int(row[7]) for row in unreachable_rows if len(row) >= 8)

    throughput_mbps = (total_sent_byte * 8.0) / (run["simulation_end_time_ns"] / 1e9) / 1e6
    throughput_active_window_mbps = (total_sent_byte * 8.0) / (run["simulation_end_time_ns"] / 1e9) / 1e6

    drop_rate = 0.0 if total_size_byte == 0 else max(0.0, 1.0 - (total_sent_byte / float(total_size_byte)))
    topology_drop_rate = 0.0 if total_size_byte == 0 else u_total_size_byte / float(total_size_byte)
    congestion_drop_rate = 0.0 if r_total_size_byte == 0 else max(0.0, 1.0 - (r_total_sent_byte / float(r_total_size_byte)))
    reachable_drop_rate = 0.0 if r_total_size_byte == 0 else max(0.0, 1.0 - (r_total_sent_byte / float(r_total_size_byte)))

    delay_metrics = aggregate_delay_metrics(logs_ns_dir, run["simulation_end_time_ns"], unreachable_pairs)

    load_balance_jain = aggregate_load_balance(logs_ns_dir)

    completed_flows = sum(1 for row in tcp_flows_rows if len(row) >= 9 and row[8] == "YES")
    completion_rate = 0.0 if len(tcp_flows_rows) == 0 else completed_flows / float(len(tcp_flows_rows))

    r_completed_flows = sum(1 for row in reachable_rows if len(row) >= 9 and row[8] == "YES")
    reachable_completion_rate = 0.0 if len(reachable_rows) == 0 else r_completed_flows / float(len(reachable_rows))

    all_pairs = set()
    for row in tcp_flows_rows:
        if len(row) >= 3:
            all_pairs.add((row[1], row[2]))
    topology_reachability = 0.0 if len(all_pairs) == 0 else (len(all_pairs) - len(unreachable_pairs)) / float(len(all_pairs))

    return {
        "run_name": run["name"],
        "algorithm": run["algorithm_label"],
        "traffic_generation_rate_mbps": run["traffic_generation_rate_mbps"],
        "num_flows": len(tcp_flows_rows),
        "num_reachable_flows": len(reachable_rows),
        "num_unreachable_flows": len(unreachable_rows),
        "num_unreachable_pairs": len(unreachable_pairs),
        "topology_reachability": topology_reachability,
        "throughput_mbps": throughput_mbps,
        "throughput_active_window_mbps": throughput_active_window_mbps,
        "load_balance_jain": load_balance_jain,
        "avg_delay_ms": delay_metrics["avg_delay_ms"],
        "median_delay_ms": delay_metrics["median_delay_ms"],
        "p95_delay_ms": delay_metrics["p95_delay_ms"],
        "reachable_avg_delay_ms": delay_metrics["reachable_avg_delay_ms"],
        "reachable_median_delay_ms": delay_metrics["reachable_median_delay_ms"],
        "reachable_p95_delay_ms": delay_metrics["reachable_p95_delay_ms"],
        "drop_rate": drop_rate,
        "topology_drop_rate": topology_drop_rate,
        "congestion_drop_rate": congestion_drop_rate,
        "reachable_drop_rate": reachable_drop_rate,
        "completion_rate": completion_rate,
        "reachable_completion_rate": reachable_completion_rate,
    }


def plot_metric(summary_rows, metric_key, ylabel, out_png, out_pdf):
    grouped = defaultdict(list)
    for row in summary_rows:
        if math.isnan(row[metric_key]):
            continue
        grouped[row["algorithm"]].append((row["traffic_generation_rate_mbps"], row[metric_key]))

    plt.figure(figsize=(7, 4.5))
    for algorithm, pairs in grouped.items():
        pairs.sort(key=lambda x: x[0])
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        plt.plot(xs, ys, marker="o", label=algorithm)
    plt.xlabel("Traffic Generation Rate (Mbps)")
    plt.ylabel(ylabel)
    plt.grid(True, linestyle="--", alpha=0.4)
    if grouped:
        plt.legend()
    plt.tight_layout()
    plt.savefig(out_png)
    plt.savefig(out_pdf)
    plt.close()


local_shell = exputil.LocalShell()

if Path("data").exists() or Path("pdf").exists():
    timestamp = datetime.now().strftime("%m%d%H%M")
    archive_dir = f"archive_{timestamp}"
    Path(archive_dir).mkdir(parents=True, exist_ok=True)
    for d in ["data", "pdf"]:
        if Path(d).exists():
            dest = Path(archive_dir) / d
            if not dest.exists():
                print(f"  Archiving {d}/ -> {archive_dir}/{d}/")
                shutil.copytree(d, str(dest), symlinks=True)
            else:
                print(f"  Archive {dest} already exists, skipping.")

local_shell.remove_force_recursive("data")
local_shell.make_full_dir("data")
local_shell.remove_force_recursive("pdf")
local_shell.make_full_dir("pdf")

summary_rows = []
for run in get_tcp_run_list():
    metrics = aggregate_run_metrics(run)
    if metrics is not None:
        summary_rows.append(metrics)

summary_csv_path = Path("data") / "summary_metrics.csv"
csv_columns = [
    "run_name",
    "algorithm",
    "traffic_generation_rate_mbps",
    "num_flows",
    "num_reachable_flows",
    "num_unreachable_flows",
    "num_unreachable_pairs",
    "topology_reachability",
    "throughput_mbps",
    "throughput_active_window_mbps",
    "load_balance_jain",
    "avg_delay_ms",
    "median_delay_ms",
    "p95_delay_ms",
    "reachable_avg_delay_ms",
    "reachable_median_delay_ms",
    "reachable_p95_delay_ms",
    "drop_rate",
    "topology_drop_rate",
    "congestion_drop_rate",
    "reachable_drop_rate",
    "completion_rate",
    "reachable_completion_rate",
]
with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(csv_columns)
    for row in sorted(summary_rows, key=lambda x: (x["algorithm"], x["traffic_generation_rate_mbps"])):
        writer.writerow([row.get(col, "") for col in csv_columns])

plot_metric(summary_rows, "throughput_mbps", "Throughput (Mbps)", "pdf/throughput_vs_rate.png", "pdf/throughput_vs_rate.pdf")
plot_metric(summary_rows, "throughput_active_window_mbps", "Throughput on Active Window (Mbps)", "pdf/throughput_active_window_vs_rate.png", "pdf/throughput_active_window_vs_rate.pdf")
plot_metric(summary_rows, "load_balance_jain", "Load Balance (Jain Index)", "pdf/load_balance_vs_rate.png", "pdf/load_balance_vs_rate.pdf")
plot_metric(summary_rows, "avg_delay_ms", "Average End-to-End Delay (ms)", "pdf/avg_delay_vs_rate.png", "pdf/avg_delay_vs_rate.pdf")
plot_metric(summary_rows, "median_delay_ms", "Median End-to-End Delay (ms)", "pdf/median_delay_vs_rate.png", "pdf/median_delay_vs_rate.pdf")
plot_metric(summary_rows, "p95_delay_ms", "P95 End-to-End Delay (ms)", "pdf/p95_delay_vs_rate.png", "pdf/p95_delay_vs_rate.pdf")
plot_metric(summary_rows, "reachable_avg_delay_ms", "Reachable Avg End-to-End Delay (ms)", "pdf/reachable_avg_delay_vs_rate.png", "pdf/reachable_avg_delay_vs_rate.pdf")
plot_metric(summary_rows, "reachable_median_delay_ms", "Reachable Median End-to-End Delay (ms)", "pdf/reachable_median_delay_vs_rate.png", "pdf/reachable_median_delay_vs_rate.pdf")
plot_metric(summary_rows, "reachable_p95_delay_ms", "Reachable P95 End-to-End Delay (ms)", "pdf/reachable_p95_delay_vs_rate.png", "pdf/reachable_p95_delay_vs_rate.pdf")
plot_metric(summary_rows, "drop_rate", "Drop Rate", "pdf/drop_rate_vs_rate.png", "pdf/drop_rate_vs_rate.pdf")
plot_metric(summary_rows, "topology_drop_rate", "Topology Drop Rate", "pdf/topology_drop_rate_vs_rate.png", "pdf/topology_drop_rate_vs_rate.pdf")
plot_metric(summary_rows, "congestion_drop_rate", "Congestion Drop Rate", "pdf/congestion_drop_rate_vs_rate.png", "pdf/congestion_drop_rate_vs_rate.pdf")
plot_metric(summary_rows, "reachable_drop_rate", "Reachable Drop Rate", "pdf/reachable_drop_rate_vs_rate.png", "pdf/reachable_drop_rate_vs_rate.pdf")
plot_metric(summary_rows, "completion_rate", "Flow Completion Rate", "pdf/completion_rate_vs_rate.png", "pdf/completion_rate_vs_rate.pdf")
plot_metric(summary_rows, "reachable_completion_rate", "Reachable Flow Completion Rate", "pdf/reachable_completion_rate_vs_rate.png", "pdf/reachable_completion_rate_vs_rate.pdf")
plot_metric(summary_rows, "topology_reachability", "Topology Reachability", "pdf/topology_reachability_vs_rate.png", "pdf/topology_reachability_vs_rate.pdf")


def plot_comparison(summary_rows, original_key, corrected_key, ylabel, out_png, out_pdf):
    grouped = defaultdict(list)
    for row in summary_rows:
        if math.isnan(row.get(original_key, math.nan)) and math.isnan(row.get(corrected_key, math.nan)):
            continue
        grouped[row["algorithm"]].append((
            row["traffic_generation_rate_mbps"],
            row.get(original_key, math.nan),
            row.get(corrected_key, math.nan),
        ))

    plt.figure(figsize=(7, 4.5))
    for algorithm, triples in grouped.items():
        triples.sort(key=lambda x: x[0])
        xs = [x for x, _, _ in triples]
        ys_orig = [y for _, y, _ in triples]
        ys_corr = [y for _, _, y in triples]
        plt.plot(xs, ys_orig, marker="o", linestyle="--", alpha=0.6, label=f"{algorithm} (original)")
        plt.plot(xs, ys_corr, marker="s", linestyle="-", label=f"{algorithm} (corrected)")
    plt.xlabel("Traffic Generation Rate (Mbps)")
    plt.ylabel(ylabel)
    plt.grid(True, linestyle="--", alpha=0.4)
    if grouped:
        plt.legend()
    plt.tight_layout()
    plt.savefig(out_png)
    plt.savefig(out_pdf)
    plt.close()


plot_comparison(summary_rows, "drop_rate", "reachable_drop_rate", "Drop Rate (Original vs Corrected)", "pdf/drop_rate_comparison.png", "pdf/drop_rate_comparison.pdf")
plot_comparison(summary_rows, "completion_rate", "reachable_completion_rate", "Completion Rate (Original vs Corrected)", "pdf/completion_rate_comparison.png", "pdf/completion_rate_comparison.pdf")
plot_comparison(summary_rows, "avg_delay_ms", "reachable_avg_delay_ms", "Avg Delay (Original vs Corrected)", "pdf/avg_delay_comparison.png", "pdf/avg_delay_comparison.pdf")

print("Generated summary metrics and plots.")
