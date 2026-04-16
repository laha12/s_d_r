import exputil

try:
    from .run_list import simulation_end_time_s, dynamic_state_update_interval_ms
except (ImportError, SystemError):
    from run_list import simulation_end_time_s, dynamic_state_update_interval_ms

local_shell = exputil.LocalShell()
local_shell.perfect_exec(
    "cd ../../satellite_networks_state; "
    "python main_custom_66_6.py "
    + str(simulation_end_time_s) + " "
    + str(dynamic_state_update_interval_ms) + " "
    + "isls_plus_grid ground_stations_top_10 algorithm_ucb_distributed_routing 1",
    output_redirect=exputil.OutputRedirect.CONSOLE
)
print("Success: generated Iridium-789 (66 satellites / 6 planes) topology for UCB distributed routing")
