import exputil

from run_list import get_tcp_run_list, get_pings_run_list

local_shell = exputil.LocalShell()

local_shell.remove_force_recursive("pdf")
local_shell.make_full_dir("pdf")
local_shell.remove_force_recursive("data")
local_shell.make_full_dir("data")

for run in get_tcp_run_list():
    local_shell.make_full_dir("pdf/" + run["name"])
    local_shell.make_full_dir("data/" + run["name"])
    local_shell.perfect_exec(
        "cd ../../ns3-sat-sim/simulator/contrib/basic-sim/tools/plotting/plot_tcp_flow; "
        "python plot_tcp_flow.py "
        "../../../../../../../paper/ns3_experiments_ucb_25x25/runs/" + run["name"] + "/logs_ns3 "
        "../../../../../../../paper/ns3_experiments_ucb_25x25/data/" + run["name"] + " "
        "../../../../../../../paper/ns3_experiments_ucb_25x25/pdf/" + run["name"] + " "
        "0 " + str(1 * 1000 * 1000 * 1000),
        output_redirect=exputil.OutputRedirect.CONSOLE
    )

for run in get_pings_run_list():
    local_shell.make_full_dir("pdf/" + run["name"])
    local_shell.make_full_dir("data/" + run["name"])
    local_shell.perfect_exec(
        "cd ../../ns3-sat-sim/simulator/contrib/basic-sim/tools/plotting/plot_ping; "
        "python plot_ping.py "
        "../../../../../../../paper/ns3_experiments_ucb_25x25/runs/" + run["name"] + "/logs_ns3 "
        "../../../../../../../paper/ns3_experiments_ucb_25x25/data/" + run["name"] + " "
        "../../../../../../../paper/ns3_experiments_ucb_25x25/pdf/" + run["name"] + " "
        "" + str(run["from_id"]) + " " + str(run["to_id"]) + " " + str(1 * 1000 * 1000 * 1000),
        output_redirect=exputil.OutputRedirect.CONSOLE
    )
