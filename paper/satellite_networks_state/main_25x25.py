# The MIT License (MIT)
#
# Copyright (c) 2020 ETH Zurich
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
sys.path.append("../../satgenpy/satgen")
from description.generate_description import generate_description
from interfaces.generate_simple_gsl_interfaces_info import generate_simple_gsl_interfaces_info
from isls.generate_plus_grid_isls import generate_plus_grid_isls
import os
import shutil


# GENERATION CONSTANTS

BASE_NAME = "25x25"
NICE_NAME = "25x25-Legacy"

# 25x25

MAX_GSL_LENGTH_M = 1089686
MAX_ISL_LENGTH_M = 1000000000
NUM_ORBS = 25
NUM_SATS_PER_ORB = 25

# (Sao-Paolo - Moscow: 632 (7) to 651 (26))

################################################################


def normalize_tle_file(tle_filename):
    with open(tle_filename, "r") as f_in:
        lines = f_in.read().splitlines()
    if len(lines) <= 1:
        return
    normalized = [lines[0]]
    for idx, line in enumerate(lines[1:]):
        if idx % 3 == 0:
            normalized.append(line)
        else:
            if len(line) > 69:
                normalized.append(line[:69])
            elif len(line) < 69:
                normalized.append(line.ljust(69))
            else:
                normalized.append(line)
    with open(tle_filename, "w") as f_out:
        f_out.write("\n".join(normalized) + "\n")


def calculate(duration_s, time_step_ms, dynamic_state_algorithm, num_threads):

    # Add base name to setting
    name = BASE_NAME + "_" + dynamic_state_algorithm

    # Create output directories
    if not os.path.isdir("gen_data"):
        os.makedirs("gen_data")
    if not os.path.isdir("gen_data/" + name):
        os.makedirs("gen_data/" + name)

    # Ground stations
    print("Generating ground stations...")
    shutil.copy("input_data/legacy/ground_stations_first_100.txt", "gen_data/" + name + "/ground_stations.txt")

    # TLEs
    print("Generating TLEs...")
    shutil.copy("input_data/legacy/starlink_tles_25x25.txt", "gen_data/" + name + "/tles.txt")
    normalize_tle_file("gen_data/" + name + "/tles.txt")

    # ISLs
    print("Generating ISLs...")
    generate_plus_grid_isls(
        "gen_data/" + name + "/isls.txt",
        NUM_ORBS,
        NUM_SATS_PER_ORB,
        isl_shift=1,
        idx_offset=0
    )

    # Description
    print("Generating description...")
    generate_description(
        "gen_data/" + name + "/description.txt",
        MAX_GSL_LENGTH_M,
        MAX_ISL_LENGTH_M
    )

    # GSL interfaces
    with open("gen_data/" + name + "/ground_stations.txt", "r") as f_in:
        num_ground_stations = len([line for line in f_in if line.strip() != ""])
    if dynamic_state_algorithm == "algorithm_free_one_only_over_isls" \
            or dynamic_state_algorithm == "algorithm_free_one_only_gs_relays" \
            or dynamic_state_algorithm == "algorithm_ucb_distributed_routing":
        gsl_interfaces_per_satellite = 1
    elif dynamic_state_algorithm == "algorithm_paired_many_only_over_isls":
        gsl_interfaces_per_satellite = num_ground_stations
    else:
        raise ValueError("Unknown dynamic state algorithm")

    print("Generating GSL interfaces info..")
    generate_simple_gsl_interfaces_info(
        "gen_data/" + name + "/gsl_interfaces_info.txt",
        NUM_ORBS * NUM_SATS_PER_ORB,
        num_ground_stations,
        gsl_interfaces_per_satellite,  # GSL interfaces per satellite
        1,  # (GSL) Interfaces per ground station
        1,  # Aggregate max. bandwidth satellite (unit unspecified)
        1   # Aggregate max. bandwidth ground station (same unspecified unit)
    )

    # Forwarding state
    if dynamic_state_algorithm == "algorithm_ucb_distributed_routing":
        print("Skip generating forwarding state for UCB distributed routing.")
    else:
        from dynamic_state.helper_dynamic_state import help_dynamic_state
        print("Generating forwarding state...")
        help_dynamic_state(
            "gen_data",
            num_threads,  # Number of threads
            name,
            time_step_ms,
            duration_s,
            MAX_GSL_LENGTH_M,
            MAX_ISL_LENGTH_M,
            dynamic_state_algorithm,
            True
        )


def main():
    args = sys.argv[1:]
    if len(args) != 4:
        print("Must supply exactly four arguments")
        print("Usage: python main_25x25.py [duration (s)] [time step (ms)] "
              "[algorithm_{free_one_only_over_isls, free_one_only_gs_relays, paired_many_only_over_isls, ucb_distributed_routing, algorithm_ucb_distributed_routing}] "
              "[num threads]")
        exit(1)
    else:
        calculate(
            int(args[0]),
            int(args[1]),
            args[2],
            int(args[3]),
        )


if __name__ == "__main__":
    main()
