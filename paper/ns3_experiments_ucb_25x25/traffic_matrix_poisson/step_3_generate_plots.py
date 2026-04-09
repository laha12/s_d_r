import csv
import math
import os
from collections import defaultdict
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


def aggregate_avg_delay_ms(logs_ns3_dir, max_valid_rtt_ns):
    total_rtt_ns = 0.0
    sample_count = 0
    for file_path in Path(logs_ns3_dir).glob("tcp_flow_*_rtt.csv"):
        for row in read_csv_rows(file_path):
            if len(row) < 3:
                continue
            rtt_ns = float(row[2])
            if rtt_ns <= 0 or rtt_ns > max_valid_rtt_ns:
                continue
            total_rtt_ns += rtt_ns
            sample_count += 1
    if sample_count == 0:
        return math.nan
    return (total_rtt_ns / sample_count) / 2.0 / 1e6


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


def aggregate_run_metrics(run):
    logs_ns_dir = Path("runs") / run["name"] / "logs_ns3"
    finished_path = logs_ns_dir / "finished.txt"
    if not finished_path.exists() or finished_path.read_text(encoding="utf-8").strip() != "Yes":
        return None

    tcp_flows_rows = read_csv_rows(logs_ns_dir / "tcp_flows.csv")
    total_size_byte = sum(int(row[3]) for row in tcp_flows_rows if len(row) >= 8)
    total_sent_byte = sum(int(row[7]) for row in tcp_flows_rows if len(row) >= 8)

    throughput_mbps = (total_sent_byte * 8.0) / (run["simulation_end_time_ns"] / 1e9) / 1e6
    drop_rate = 0.0 if total_size_byte == 0 else max(0.0, 1.0 - (total_sent_byte / float(total_size_byte)))
    avg_delay_ms = aggregate_avg_delay_ms(logs_ns_dir, run["simulation_end_time_ns"])
    load_balance_jain = aggregate_load_balance(logs_ns_dir)

    return {
        "run_name": run["name"],
        "algorithm": run["algorithm_label"],
        "traffic_generation_rate_mbps": run["traffic_generation_rate_mbps"],
        "num_flows": len(tcp_flows_rows),
        "throughput_mbps": throughput_mbps,
        "load_balance_jain": load_balance_jain,
        "avg_delay_ms": avg_delay_ms,
        "drop_rate": drop_rate,
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
with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "run_name",
        "algorithm",
        "traffic_generation_rate_mbps",
        "num_flows",
        "throughput_mbps",
        "load_balance_jain",
        "avg_delay_ms",
        "drop_rate",
    ])
    for row in sorted(summary_rows, key=lambda x: (x["algorithm"], x["traffic_generation_rate_mbps"])):
        writer.writerow([
            row["run_name"],
            row["algorithm"],
            row["traffic_generation_rate_mbps"],
            row["num_flows"],
            row["throughput_mbps"],
            row["load_balance_jain"],
            row["avg_delay_ms"],
            row["drop_rate"],
        ])

plot_metric(summary_rows, "throughput_mbps", "Throughput (Mbps)", "pdf/throughput_vs_rate.png", "pdf/throughput_vs_rate.pdf")
plot_metric(summary_rows, "load_balance_jain", "Load Balance (Jain Index)", "pdf/load_balance_vs_rate.png", "pdf/load_balance_vs_rate.pdf")
plot_metric(summary_rows, "avg_delay_ms", "Average End-to-End Delay (ms)", "pdf/avg_delay_vs_rate.png", "pdf/avg_delay_vs_rate.pdf")
plot_metric(summary_rows, "drop_rate", "Drop Rate", "pdf/drop_rate_vs_rate.png", "pdf/drop_rate_vs_rate.pdf")

print("Generated summary metrics and plots.")
