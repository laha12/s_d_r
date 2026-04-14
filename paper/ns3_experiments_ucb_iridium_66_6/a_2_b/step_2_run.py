import exputil
import shutil

try:
    from .run_list import *
except (ImportError, SystemError):
    from run_list import *

local_shell = exputil.LocalShell()
screen_available = shutil.which("screen") is not None

if screen_available and local_shell.count_screens() != 0:
    print("There is a screen already running, fallback to sequential mode for this run.")
    screen_available = False

commands_to_run = []
run_names = []

for run in get_tcp_run_list():
    logs_ns3_dir = "runs/" + run["name"] + "/logs_ns3"
    local_shell.remove_force_recursive(logs_ns3_dir)
    local_shell.make_full_dir(logs_ns3_dir)
    local_shell.remove_force_recursive(logs_ns3_dir + "/ucb_route_debug.txt")
    commands_to_run.append(
        "cd ../../../ns3-sat-sim/simulator; "
        "UCB_ROUTE_DEBUG_PATH='../../paper/ns3_experiments_ucb_iridium_66_6/a_2_b/" + logs_ns3_dir + "/ucb_route_debug.txt' "
        "./waf --run=\"main_satnet --run_dir='../../paper/ns3_experiments_ucb_iridium_66_6/a_2_b/runs/" + run["name"] + "'\" "
        "2>&1 | tee '../../paper/ns3_experiments_ucb_iridium_66_6/a_2_b/" + logs_ns3_dir + "/console.txt'"
    )
    
    run_names.append(run["name"])

# for run in get_pings_run_list():
#     logs_ns3_dir = "runs/" + run["name"] + "/logs_ns3"
#     local_shell.remove_force_recursive(logs_ns3_dir)
#     local_shell.make_full_dir(logs_ns3_dir)
#     local_shell.remove_force_recursive(logs_ns3_dir + "/ucb_route_debug.txt")
#     commands_to_run.append(
#         "cd ../../ns3-sat-sim/simulator; "
#         "UCB_ROUTE_DEBUG_PATH='../../paper/ns3_experiments_ucb_25x25/" + logs_ns3_dir + "/ucb_route_debug.txt' "
#         "./waf --run=\"main_satnet --run_dir='../../paper/ns3_experiments_ucb_25x25/runs/" + run["name"] + "'\" "
#         "2>&1 | tee '../../paper/ns3_experiments_ucb_25x25/" + logs_ns3_dir + "/console.txt'"
#     )
#     run_names.append(run["name"])

print("Running commands one by one to avoid concurrent waf build conflicts...")
for i in range(len(commands_to_run)):
    print("Running command %d out of %d: %s" % (i + 1, len(commands_to_run), commands_to_run[i]))
    local_shell.perfect_exec(
        commands_to_run[i],
        output_redirect=exputil.OutputRedirect.CONSOLE
    )
failed_runs = []
for run_name in run_names:
    finished_filename = "runs/" + run_name + "/logs_ns3/finished.txt"
    if not local_shell.file_exists(finished_filename):
        failed_runs.append(run_name)
    else:
        if local_shell.read_file(finished_filename).strip() != "Yes":
            failed_runs.append(run_name)
if len(failed_runs) > 0:
    print("Some runs failed:")
    for run_name in failed_runs:
        print(" - " + run_name)
    exit(1)

for run_name in run_names:
    log_file = "runs/" + run_name + "/logs_ns3/ucb_route_debug.txt"
    if local_shell.file_exists(log_file):
        local_shell.perfect_exec(
            "python ../group_ucb_log_by_uid.py --log_file '" + log_file + "'",
            output_redirect=exputil.OutputRedirect.CONSOLE
        )

print("Finished.")
