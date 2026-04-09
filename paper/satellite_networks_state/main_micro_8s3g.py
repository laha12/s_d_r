import math
import sys
from main_helper import MainHelper


EARTH_RADIUS = 6378135.0
BASE_NAME = "micro_8s3g"
NICE_NAME = "Micro-8S3G"
ECCENTRICITY = 0.0000001
ARG_OF_PERIGEE_DEGREE = 0.0
PHASE_DIFF = True
MEAN_MOTION_REV_PER_DAY = 14.80
ALTITUDE_M = 630000
SATELLITE_CONE_RADIUS_M = ALTITUDE_M / math.tan(math.radians(30.0))
MAX_GSL_LENGTH_M = math.sqrt(math.pow(SATELLITE_CONE_RADIUS_M, 2) + math.pow(ALTITUDE_M, 2))
MAX_ISL_LENGTH_M = 2 * math.sqrt(math.pow(EARTH_RADIUS + ALTITUDE_M, 2) - math.pow(EARTH_RADIUS + 80000, 2))
NUM_ORBS = 3
NUM_SATS_PER_ORB = 3
INCLINATION_DEGREE = 53.0


main_helper = MainHelper(
    BASE_NAME,
    NICE_NAME,
    ECCENTRICITY,
    ARG_OF_PERIGEE_DEGREE,
    PHASE_DIFF,
    MEAN_MOTION_REV_PER_DAY,
    ALTITUDE_M,
    MAX_GSL_LENGTH_M,
    MAX_ISL_LENGTH_M,
    NUM_ORBS,
    NUM_SATS_PER_ORB,
    INCLINATION_DEGREE,
)

# 经纬度转为xyz坐标
def latlon_to_cartesian(latitude_deg, longitude_deg, elevation_m):
    lat = math.radians(latitude_deg)
    lon = math.radians(longitude_deg)
    r = EARTH_RADIUS + elevation_m
    x = r * math.cos(lat) * math.cos(lon)
    y = r * math.cos(lat) * math.sin(lon)
    z = r * math.sin(lat)
    return x, y, z


def overwrite_three_ground_stations(run_dir):
    stations = [
        (0, "GS_A", 0.0, 0.0, 0.0),
        (1, "GS_B", 20.0, 60.0, 0.0),
        (2, "GS_C", -20.0, -60.0, 0.0),
    ]
    gs_path = run_dir + "/ground_stations.txt"
    with open(gs_path, "w", encoding="utf-8", newline="\n") as f:
        for gid, name, lat, lon, elev in stations:
            x, y, z = latlon_to_cartesian(lat, lon, elev)
            f.write(f"{gid},{name},{lat:.6f},{lon:.6f},{elev:.6f},{x:.6f},{y:.6f},{z:.6f}\n")

    gsl_if_path = run_dir + "/gsl_interfaces_info.txt"
    total_nodes = NUM_ORBS * NUM_SATS_PER_ORB + len(stations)
    with open(gsl_if_path, "w", encoding="utf-8", newline="\n") as f:
        for node_id in range(total_nodes):
            f.write(f"{node_id},1,1.000000\n")


def main():
    args = sys.argv[1:]
    if len(args) != 6:
        print("Must supply exactly six arguments")
        print("Usage: python main_micro_8s3g.py [duration (s)] [time step (ms)] [isls_plus_grid / isls_none] [ground_stations_top_100 / ground_stations_paris_moscow_grid] [algorithm_free_one_only_over_isls / algorithm_free_one_only_gs_relays / algorithm_paired_many_only_over_isls / algorithm_ucb_distributed_routing] [num threads]")
        exit(1)

    duration_s = int(args[0])
    time_step_ms = int(args[1])
    isl_selection = args[2]
    gs_selection = args[3]
    dynamic_state_algorithm = args[4]
    num_threads = int(args[5])

    main_helper.calculate(
        "gen_data",
        duration_s,
        time_step_ms,
        isl_selection,
        gs_selection,
        dynamic_state_algorithm,
        num_threads,
    )

    run_name = f"{BASE_NAME}_{isl_selection}_{gs_selection}_{dynamic_state_algorithm}"
    run_dir = "gen_data/" + run_name
    overwrite_three_ground_stations(run_dir)
    print(run_dir)


if __name__ == "__main__":
    main()
