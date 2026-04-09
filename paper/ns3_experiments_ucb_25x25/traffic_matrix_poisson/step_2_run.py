import exputil

try:
    from .run_list import get_tcp_run_list
except (ImportError, SystemError):
    from run_list import get_tcp_run_list


local_shell = exputil.LocalShell()

commands_to_run = []
run_names = []

for run in get_tcp_run_list():
    logs_ns3_dir = "runs/" + run["name"] + "/logs_ns3"
    local_shell.remove_force_recursive(logs_ns3_dir)
    local_shell.make_full_dir(logs_ns3_dir)
    command = (
        "cd ../../../ns3-sat-sim/simulator; "
        "UCB_ROUTE_DEBUG_PATH='../../paper/ns3_experiments_ucb_25x25/traffic_matrix_poisson/" + logs_ns3_dir + "/ucb_route_debug.txt' "
        "./waf --run=\"main_satnet --run_dir='../../paper/ns3_experiments_ucb_25x25/traffic_matrix_poisson/runs/" + run["name"] + "'\" "
        "2>&1 | tee '../../paper/ns3_experiments_ucb_25x25/traffic_matrix_poisson/" + logs_ns3_dir + "/console.txt'"
    )
    commands_to_run.append(command)
    run_names.append(run["name"])

print("Running traffic matrix poisson commands one by one...")
for i, command in enumerate(commands_to_run):
    print("Running command %d out of %d: %s" % (i + 1, len(commands_to_run), command))
    local_shell.perfect_exec(command, output_redirect=exputil.OutputRedirect.CONSOLE)

failed_runs = []
for run_name in run_names:
    finished_filename = "runs/" + run_name + "/logs_ns3/finished.txt"
    if not local_shell.file_exists(finished_filename):
        failed_runs.append(run_name)
    elif local_shell.read_file(finished_filename).strip() != "Yes":
        failed_runs.append(run_name)

if failed_runs:
    print("Some runs failed:")
    for run_name in failed_runs:
        print(" - " + run_name)
    exit(1)

print("Finished.")
