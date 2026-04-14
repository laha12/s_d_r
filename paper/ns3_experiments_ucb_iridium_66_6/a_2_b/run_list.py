from pathlib import Path

dynamic_state_update_interval_ms = 100
simulation_end_time_s = 50
pingmesh_interval_ns = 1 * 1000 * 1000
enable_isl_utilization_tracking = True
isl_utilization_tracking_interval_ns = 1 * 1000 * 1000 * 1000

dynamic_state_update_interval_ns = dynamic_state_update_interval_ms * 1000 * 1000
simulation_end_time_ns = simulation_end_time_s * 1000 * 1000 * 1000
satellite_network = "iridium_789_66_6_isls_plus_grid_ground_stations_top_100_algorithm_ucb_distributed_routing"

satellite_network_force_static=True

ucb_max_hop_count = 64
ucb_slot_duration_s = 0.1
ucb_reward_weights = "list(0.2,0.2,0.2,0.4)"
ucb_epsilon1 = "1e-9"
ucb_epsilon2 = "1e-9"
ucb_random_select_prob = "0.0"
ucb_dst_arrival_reward = "1.0"


def read_satellite_description(satellite_network_name):
    description_path = Path(__file__).resolve().parent.parent.parent / "satellite_networks_state" / "gen_data" / satellite_network_name / "description.txt"
    values = {}
    with description_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    if "max_gsl_length_m" not in values or "max_isl_length_m" not in values:
        raise ValueError("description.txt must contain max_gsl_length_m and max_isl_length_m")
    return values

chosen_pairs = [
    ("iridium_789_66_6", 66, 101, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 69, 75, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 150, 95, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 162, 77, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 74, 164, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 102, 126, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 124, 87, "TcpNewReno", satellite_network),
    ("iridium_789_66_6", 73, 149, "TcpNewReno", satellite_network),
    # ,
    # ("25x25", 651, 683, "TcpVegas", satellite_network)
]


def get_tcp_run_list():
    run_list = []
    for p in chosen_pairs:
        description_values = read_satellite_description(p[4])
        run_list += [
            {
                "name": p[0] + "_" + str(p[1]) + "_to_" + str(p[2]) + "_with_" + p[3] + "_ucb",
                "satellite_network": p[4],
                "dynamic_state_update_interval_ns": dynamic_state_update_interval_ns,
                "simulation_end_time_ns": simulation_end_time_ns,
                "data_rate_megabit_per_s": 10.0,
                "queue_size_pkt": 100,
                "enable_isl_utilization_tracking": enable_isl_utilization_tracking,
                "satellite_network_force_static": satellite_network_force_static,
                "isl_utilization_tracking_interval_ns": isl_utilization_tracking_interval_ns,
                "from_id": p[1],
                "to_id": p[2],
                "tcp_socket_type": p[3],
                "ucb_max_hop_count": ucb_max_hop_count,
                "ucb_slot_duration_s": ucb_slot_duration_s,
                "ucb_reward_weights": ucb_reward_weights,
                "ucb_epsilon1": ucb_epsilon1,
                "ucb_epsilon2": ucb_epsilon2,
                "ucb_random_select_prob": ucb_random_select_prob,
                "ucb_dst_arrival_reward": ucb_dst_arrival_reward,
                "max_gsl_length_m": description_values["max_gsl_length_m"],
                "max_isl_length_m": description_values["max_isl_length_m"],
            },
        ]
    return run_list


# def get_pings_run_list():
#     reduced_chosen_pairs = []
#     for p in chosen_pairs:
#         if not (p[0], p[1], p[2], p[4]) in reduced_chosen_pairs:
#             reduced_chosen_pairs.append((p[0], p[1], p[2], p[4]))

#     run_list = []
#     for p in reduced_chosen_pairs:
#         description_values = read_satellite_description(p[3])
#         run_list += [
#             {
#                 "name": p[0] + "_" + str(p[1]) + "_to_" + str(p[2]) + "_pings_ucb",
#                 "satellite_network": p[3],
#                 "dynamic_state_update_interval_ns": dynamic_state_update_interval_ns,
#                 "simulation_end_time_ns": simulation_end_time_ns,
#                 "data_rate_megabit_per_s": 10000.0,
#                 "queue_size_pkt": 100000,
#                 "enable_isl_utilization_tracking": enable_isl_utilization_tracking,
#                 "isl_utilization_tracking_interval_ns": isl_utilization_tracking_interval_ns,
#                 "from_id": p[1],
#                 "to_id": p[2],
#                 "pingmesh_interval_ns": pingmesh_interval_ns,
#                 "ucb_max_hop_count": ucb_max_hop_count,
#                 "ucb_slot_duration_s": ucb_slot_duration_s,
#                 "ucb_reward_weights": ucb_reward_weights,
#                 "ucb_epsilon1": ucb_epsilon1,
#                 "ucb_epsilon2": ucb_epsilon2,
#                 "ucb_random_select_prob": ucb_random_select_prob,
#                 "ucb_dst_arrival_reward": ucb_dst_arrival_reward,
#                 "max_gsl_length_m": description_values["max_gsl_length_m"],
#                 "max_isl_length_m": description_values["max_isl_length_m"],
#             }
#         ]
#     return run_list
