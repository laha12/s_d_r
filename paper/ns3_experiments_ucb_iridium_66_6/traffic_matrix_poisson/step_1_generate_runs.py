import csv
import exputil
import importlib.util
import shutil
from datetime import datetime
from pathlib import Path

try:
    from .run_list import get_tcp_run_list
except (ImportError, SystemError):
    from run_list import get_tcp_run_list


def archive_if_exists(local_shell, dir_name):
    if not Path(dir_name).exists():
        return
    timestamp = datetime.now().strftime("%m%d%H%M")
    archive_dir = f"archive_{timestamp}"
    Path(archive_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(archive_dir) / dir_name
    if dest.exists():
        print(f"  Archive {dest} already exists, skipping.")
        return
    print(f"  Archiving {dir_name}/ -> {archive_dir}/{dir_name}/")
    shutil.copytree(dir_name, str(dest), symlinks=True)


def load_generate_data_module():
    module_path = Path(__file__).resolve().parents[3] / "ns3-sat-sim" / "simulator" / "test_data" / "generate_data.py"
    spec = importlib.util.spec_from_file_location("generate_data_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pairs_to_string(pairs):
    return ",".join(f"{src}:{dst}" for src, dst in pairs)


def build_tcp_flow_log_set(num_flows):
    if num_flows <= 0:
        return "set()"
    return "set(" + ",".join(str(i) for i in range(num_flows)) + ")"


def generate_dynamic_state_dir_name(dynamic_state_update_interval_ns, simulation_end_time_ns):
    interval_ms = dynamic_state_update_interval_ns // 1000000
    duration_s = simulation_end_time_ns // 1000000000
    return f"dynamic_state_{interval_ms}ms_for_{duration_s}s"


local_shell = exputil.LocalShell()
generate_data_module = load_generate_data_module()

print("Archiving existing data/pdf/runs before removal...")
archive_if_exists(local_shell, "runs")
archive_if_exists(local_shell, "pdf")
archive_if_exists(local_shell, "data")

local_shell.remove_force_recursive("runs")
local_shell.remove_force_recursive("pdf")
local_shell.remove_force_recursive("data")

for run in get_tcp_run_list():
    run_dir = "runs/" + run["name"]
    local_shell.remove_force_recursive(run_dir)
    local_shell.make_full_dir(run_dir)
    local_shell.make_full_dir(run_dir + "/logs_ns3")
    local_shell.write_file(run_dir + "/.gitignore", "logs_ns3")

    local_shell.copy_file("templates/template_tcp_tm_config_ns3.properties", run_dir + "/config_ns3.properties")
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SATELLITE-NETWORK]", str(run["satellite_network"]))
    dynamic_state_dir = generate_dynamic_state_dir_name(run["dynamic_state_update_interval_ns"], run["simulation_end_time_ns"])
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DYNAMIC-STATE-DIR]", dynamic_state_dir)
    local_shell.sed_replace_in_file_plain(
        run_dir + "/config_ns3.properties",
        "[SATELLITE-NETWORK-FORCE-STATIC]",
        "true" if run["satellite_network_force_static"] else "false"
    )
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DYNAMIC-STATE-UPDATE-INTERVAL-NS]", str(run["dynamic_state_update_interval_ns"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SIMULATION-END-TIME-NS]", str(run["simulation_end_time_ns"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ISL-DATA-RATE-MEGABIT-PER-S]", str(run["data_rate_megabit_per_s"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[GSL-DATA-RATE-MEGABIT-PER-S]", str(run["data_rate_megabit_per_s"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ISL-MAX-QUEUE-SIZE-PKTS]", str(run["queue_size_pkt"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[GSL-MAX-QUEUE-SIZE-PKTS]", str(run["queue_size_pkt"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ENABLE-ISL-UTILIZATION-TRACKING]", "true" if run["enable_isl_utilization_tracking"] else "false")
    if run["enable_isl_utilization_tracking"]:
        local_shell.sed_replace_in_file_plain(
            run_dir + "/config_ns3.properties",
            "[ISL-UTILIZATION-TRACKING-INTERVAL-NS-COMPLETE]",
            "isl_utilization_tracking_interval_ns=" + str(run["isl_utilization_tracking_interval_ns"])
        )
    else:
        local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ISL-UTILIZATION-TRACKING-INTERVAL-NS-COMPLETE]", "")
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[TCP-SOCKET-TYPE]", str(run["tcp_socket_type"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SATELLITE-NETWORK-ROUTING]", str(run["satellite_network_routing"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-MAX-HOP-COUNT]", str(run["ucb_max_hop_count"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-SLOT-DURATION-S]", str(run["ucb_slot_duration_s"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-REWARD-WEIGHTS]", str(run["ucb_reward_weights"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-EPSILON1]", str(run["ucb_epsilon1"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-EPSILON2]", str(run["ucb_epsilon2"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-RANDOM-SELECT-PROB]", str(run["ucb_random_select_prob"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-DST-ARRIVAL-REWARD]", str(run["ucb_dst_arrival_reward"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-QUEUE-DROP-THRESHOLD]", str(run["ucb_queue_drop_threshold"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-REFERENCE-DELAY-MS]", str(run["ucb_reference_delay_ms"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-REFERENCE-DISTANCE-M]", str(run["ucb_reference_distance_m"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-SLOT-DECAY-FACTOR]", str(run["ucb_slot_decay_factor"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[MAX-GSL-LENGTH-M]", str(run["max_gsl_length_m"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[MAX-ISL-LENGTH-M]", str(run["max_isl_length_m"]))

    schedule_path = str(Path(run_dir) / "tcp_flow_schedule.csv")
    generate_data_module.generate_tcp_flow_schedule(
        out_csv_path=schedule_path,
        node_pairs=run["traffic_pairs"],
        slot_len_ns=run["traffic_slot_len_ns"],
        sim_end_ns=run["simulation_end_time_ns"],
        rate_mbps=run["traffic_generation_rate_mbps"],
        flow_size_byte=run["tcp_flow_size_byte"],
        min_flow_interval_ns=run["min_flow_interval_ns"],
        seed=run["traffic_seed"],
    )

    with open(schedule_path, "r", encoding="utf-8") as f:
        num_flows = sum(1 for _ in f)

    local_shell.sed_replace_in_file_plain(
        run_dir + "/config_ns3.properties",
        "[TCP-FLOW-LOG-SET]",
        build_tcp_flow_log_set(num_flows)
    )

    with open(run_dir + "/traffic_pairs.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["src_id", "dst_id"])
        for src_id, dst_id in run["traffic_pairs"]:
            writer.writerow([src_id, dst_id])

print("Success: generated traffic matrix poisson runs")
