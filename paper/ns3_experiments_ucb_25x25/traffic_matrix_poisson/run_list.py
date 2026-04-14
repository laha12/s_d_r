from pathlib import Path
import random


dynamic_state_update_interval_ms = 100
simulation_end_time_s = 50
enable_isl_utilization_tracking = True
satellite_network_force_static = True
isl_utilization_tracking_interval_ns = 1 * 1000 * 1000 * 1000

dynamic_state_update_interval_ns = dynamic_state_update_interval_ms * 1000 * 1000
simulation_end_time_ns = simulation_end_time_s * 1000 * 1000 * 1000
satellite_network = "25x25_algorithm_ucb_distributed_routing"

traffic_generation_rates_mbps = [0.001,0.003,0.005,0.008]
traffic_slot_len_ns = dynamic_state_update_interval_ns
tcp_flow_size_byte = 10000
traffic_seed = 123456789
pairing_seed = 987654321

ucb_max_hop_count = 64
ucb_slot_duration_s = 0.1
ucb_reward_weights = "list(0.2,0.2,0.2,0.4)"
ucb_epsilon1 = "1e-9"
ucb_epsilon2 = "1e-9"
ucb_random_select_prob = "0.1"
ucb_dst_arrival_reward = "1.0"

routing_algorithms = [
    {
        "label": "ucb",
        "satellite_network_routing": "ucb_distributed",
        "tcp_socket_type": "TcpVegas",
    },
]


def read_satellite_description(satellite_network_name):
    description_path = (
        Path(__file__).resolve().parents[2]
        / "satellite_networks_state"
        / "gen_data"
        / satellite_network_name
        / "description.txt"
    )
    values = {}
    with description_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    if "max_gsl_length_m" not in values or "max_isl_length_m" not in values:
        raise ValueError("description.txt must contain max_gsl_length_m and max_isl_length_m")
    return values


def count_satellites_and_ground_stations(satellite_network_name):
    base_dir = (
        Path(__file__).resolve().parents[2]
        / "satellite_networks_state"
        / "gen_data"
        / satellite_network_name
    )
    tles_path = base_dir / "tles.txt"
    ground_stations_path = base_dir / "ground_stations.txt"

    tle_lines = [line.strip() for line in tles_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gs_lines = [line.strip() for line in ground_stations_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    if len(tle_lines) < 4:
        raise ValueError("tles.txt 内容异常，无法统计卫星数量")

    num_satellites = (len(tle_lines) - 1) // 3
    num_ground_stations = len(gs_lines)
    return num_satellites, num_ground_stations


def generate_reciprocal_ground_station_pairs(satellite_network_name, seed):
    num_satellites, num_ground_stations = count_satellites_and_ground_stations(satellite_network_name)
    gs_node_ids = list(range(num_satellites, num_satellites + num_ground_stations))
    if len(gs_node_ids) < 2:
        raise ValueError("至少需要两个地面站来构造 traffic matrix")

    rng = random.Random(seed)
    rng.shuffle(gs_node_ids)

    pairs = []
    for i in range(0, len(gs_node_ids) - 1, 2):
        a = gs_node_ids[i]
        b = gs_node_ids[i + 1]
        pairs.append((a, b))
        pairs.append((b, a))
    return pairs


def get_tcp_run_list():
    description_values = read_satellite_description(satellite_network)
    traffic_pairs = generate_reciprocal_ground_station_pairs(satellite_network, pairing_seed)

    run_list = []
    for algorithm in routing_algorithms:
        for rate_mbps in traffic_generation_rates_mbps:
            rate_name = str(rate_mbps).replace(".", "_")
            run_list.append(
                {
                    "name": f"tm_poisson_{rate_name}_Mbps_with_{algorithm['tcp_socket_type']}_{algorithm['label']}",
                    "satellite_network": satellite_network,
                    "satellite_network_routing": algorithm["satellite_network_routing"],
                    "tcp_socket_type": algorithm["tcp_socket_type"],
                    "algorithm_label": algorithm["label"],
                    "dynamic_state_update_interval_ns": dynamic_state_update_interval_ns,
                    "simulation_end_time_ns": simulation_end_time_ns,
                    "satellite_network_force_static": satellite_network_force_static,
                    "data_rate_megabit_per_s": 10.0,
                    "queue_size_pkt": 100,
                    "enable_isl_utilization_tracking": enable_isl_utilization_tracking,
                    "isl_utilization_tracking_interval_ns": isl_utilization_tracking_interval_ns,
                    "ucb_max_hop_count": ucb_max_hop_count,
                    "ucb_slot_duration_s": ucb_slot_duration_s,
                    "ucb_reward_weights": ucb_reward_weights,
                    "ucb_epsilon1": ucb_epsilon1,
                    "ucb_epsilon2": ucb_epsilon2,
                    "ucb_random_select_prob": ucb_random_select_prob,
                    "ucb_dst_arrival_reward": ucb_dst_arrival_reward,
                    "max_gsl_length_m": description_values["max_gsl_length_m"],
                    "max_isl_length_m": description_values["max_isl_length_m"],
                    "traffic_generation_rate_mbps": rate_mbps,
                    "traffic_slot_len_ns": traffic_slot_len_ns,
                    "tcp_flow_size_byte": tcp_flow_size_byte,
                    "traffic_seed": traffic_seed,
                    "traffic_pairs": traffic_pairs,
                }
            )
    return run_list
