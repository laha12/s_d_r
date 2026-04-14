import exputil

try:
    from .run_list import *
except (ImportError, SystemError):
    from run_list import *

local_shell = exputil.LocalShell()

local_shell.remove_force_recursive("runs")
local_shell.remove_force_recursive("pdf")
local_shell.remove_force_recursive("data")

for run in get_tcp_run_list():
    run_dir = "runs/" + run["name"]
    local_shell.remove_force_recursive(run_dir)
    local_shell.make_full_dir(run_dir)

    local_shell.copy_file("templates/template_tcp_a_b_config_ns3.properties", run_dir + "/config_ns3.properties")
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SATELLITE-NETWORK]", str(run["satellite_network"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DYNAMIC-STATE-UPDATE-INTERVAL-NS]", str(run["dynamic_state_update_interval_ns"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SIMULATION-END-TIME-NS]", str(run["simulation_end_time_ns"]))
    # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ENABLE-DISTRIBUTED]", "true" if run["enable_distributed"] else "false")
    # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DISTRIBUTED-SIMULATOR-IMPLEMENTATION-TYPE]", str(run["distributed_simulator_implementation_type"]))
    # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DISTRIBUTED-SYSTEMS-COUNT]", str(run["distributed_systems_count"]))
    # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[TOTAL-NUM-NODES]", str(run["total_num_nodes"]))
    # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DISTRIBUTED-NODE-SYSTEM-ID-ASSIGNMENT]", str(run["distributed_node_system_id_assignment"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SATELLITE-NETWORK-FORCE-STATIC]", "true" if run["satellite_network_force_static"] else "false")
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
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-MAX-HOP-COUNT]", str(run["ucb_max_hop_count"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-SLOT-DURATION-S]", str(run["ucb_slot_duration_s"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-REWARD-WEIGHTS]", str(run["ucb_reward_weights"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-EPSILON1]", str(run["ucb_epsilon1"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-EPSILON2]", str(run["ucb_epsilon2"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-RANDOM-SELECT-PROB]", str(run["ucb_random_select_prob"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-DST-ARRIVAL-REWARD]", str(run["ucb_dst_arrival_reward"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[MAX-GSL-LENGTH-M]", str(run["max_gsl_length_m"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[MAX-ISL-LENGTH-M]", str(run["max_isl_length_m"]))

    local_shell.copy_file("templates/template_tcp_a_b_schedule.csv", run_dir + "/schedule.csv")
    local_shell.sed_replace_in_file_plain(run_dir + "/schedule.csv", "[FROM]", str(run["from_id"]))
    local_shell.sed_replace_in_file_plain(run_dir + "/schedule.csv", "[TO]", str(run["to_id"]))

# for run in get_pings_run_list():
#     run_dir = "runs/" + run["name"]
#     local_shell.remove_force_recursive(run_dir)
#     local_shell.make_full_dir(run_dir)

#     local_shell.copy_file("templates/template_pings_a_b_config_ns3.properties", run_dir + "/config_ns3.properties")
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SATELLITE-NETWORK]", str(run["satellite_network"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DYNAMIC-STATE-UPDATE-INTERVAL-NS]", str(run["dynamic_state_update_interval_ns"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[SIMULATION-END-TIME-NS]", str(run["simulation_end_time_ns"]))
#     # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ENABLE-DISTRIBUTED]", "true" if run["enable_distributed"] else "false")
#     # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DISTRIBUTED-SIMULATOR-IMPLEMENTATION-TYPE]", str(run["distributed_simulator_implementation_type"]))
#     # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DISTRIBUTED-SYSTEMS-COUNT]", str(run["distributed_systems_count"]))
#     # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[TOTAL-NUM-NODES]", str(run["total_num_nodes"]))
#     # local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[DISTRIBUTED-NODE-SYSTEM-ID-ASSIGNMENT]", str(run["distributed_node_system_id_assignment"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ISL-DATA-RATE-MEGABIT-PER-S]", str(run["data_rate_megabit_per_s"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[GSL-DATA-RATE-MEGABIT-PER-S]", str(run["data_rate_megabit_per_s"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ISL-MAX-QUEUE-SIZE-PKTS]", str(run["queue_size_pkt"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[GSL-MAX-QUEUE-SIZE-PKTS]", str(run["queue_size_pkt"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ENABLE-ISL-UTILIZATION-TRACKING]", "true" if run["enable_isl_utilization_tracking"] else "false")
#     if run["enable_isl_utilization_tracking"]:
#         local_shell.sed_replace_in_file_plain(
#             run_dir + "/config_ns3.properties",
#             "[ISL-UTILIZATION-TRACKING-INTERVAL-NS-COMPLETE]",
#             "isl_utilization_tracking_interval_ns=" + str(run["isl_utilization_tracking_interval_ns"])
#         )
#     else:
#         local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[ISL-UTILIZATION-TRACKING-INTERVAL-NS-COMPLETE]", "")
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[PINGMESH-INTERVAL-NS]", str(run["pingmesh_interval_ns"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[FROM]", str(run["from_id"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[TO]", str(run["to_id"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-MAX-HOP-COUNT]", str(run["ucb_max_hop_count"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-SLOT-DURATION-S]", str(run["ucb_slot_duration_s"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-REWARD-WEIGHTS]", str(run["ucb_reward_weights"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-EPSILON1]", str(run["ucb_epsilon1"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-EPSILON2]", str(run["ucb_epsilon2"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-RANDOM-SELECT-PROB]", str(run["ucb_random_select_prob"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[UCB-DST-ARRIVAL-REWARD]", str(run["ucb_dst_arrival_reward"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[MAX-GSL-LENGTH-M]", str(run["max_gsl_length_m"]))
#     local_shell.sed_replace_in_file_plain(run_dir + "/config_ns3.properties", "[MAX-ISL-LENGTH-M]", str(run["max_isl_length_m"]))

print("Success: generated runs")
