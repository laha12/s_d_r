import exputil

try:
    from .run_list import simulation_end_time_s, dynamic_state_update_interval_ms
except (ImportError, SystemError):
    from run_list import simulation_end_time_s, dynamic_state_update_interval_ms

local_shell = exputil.LocalShell()
local_shell.perfect_exec(
    "cd ../../satellite_networks_state; "
    "python main_25x25.py "
    + str(simulation_end_time_s) + " "
    + str(dynamic_state_update_interval_ms) + " "
    + "algorithm_ucb_distributed_routing 1",
    output_redirect=exputil.OutputRedirect.CONSOLE
)
print("Success: generated 25x25 topology for UCB distributed routing")
