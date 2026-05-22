import exputil

try:
    from .run_list import simulation_end_time_s, dynamic_state_update_interval_ms
except (ImportError, SystemError):
    from run_list import simulation_end_time_s, dynamic_state_update_interval_ms

local_shell = exputil.LocalShell()

def generate_topology(dynamic_state_algorithm):
    local_shell.perfect_exec(
        "cd ../../satellite_networks_state; "
        "python main_custom_66_6.py "
        + str(simulation_end_time_s) + " "
        + str(dynamic_state_update_interval_ms) + " "
        + "isls_plus_grid ground_stations_top_10 "
        + dynamic_state_algorithm + " 1",
        output_redirect=exputil.OutputRedirect.CONSOLE
    )


# UCB routing topology
generate_topology("algorithm_ucb_distributed_routing")
# # BFS(shortest-path forwarding table) topology
# generate_topology("algorithm_free_one_only_over_isls")

print("Success: generated Iridium-789 topology for UCB and BFS(single_forward) experiments")
