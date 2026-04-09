/*
 * Copyright (c) 2020 ETH Zurich
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Simon               2020
 */

#include <map>
#include <iostream>
#include <fstream>
#include <string>
#include <ctime>
#include <iostream>
#include <fstream>
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>
#include <chrono>
#include <stdexcept>

#include "ns3/basic-simulation.h"
#include "ns3/tcp-flow-scheduler.h"
#include "ns3/udp-burst-scheduler.h"
#include "ns3/pingmesh-scheduler.h"
#include "ns3/topology-satellite-network.h"
#include "ns3/tcp-optimizer.h"
#include "ns3/arbiter-single-forward-helper.h"
#include "../../contrib/satellite-network/model/arbiter-ucb-distributed-routing.h"
#include "ns3/ipv4-arbiter-routing-helper.h"
#include "ns3/gsl-if-bandwidth-helper.h"
#include "ns3/exp-util.h"

using namespace ns3;

int main(int argc, char *argv[]) {

    // No buffering of printf
    setbuf(stdout, nullptr);

    // Retrieve run directory
    CommandLine cmd;
    std::string run_dir = "";
    cmd.Usage("Usage: ./waf --run=\"main_satnet --run_dir='<path/to/run/directory>'\"");
    cmd.AddValue("run_dir",  "Run directory", run_dir);
    cmd.Parse(argc, argv);
    if (run_dir.compare("") == 0) {
        printf("Usage: ./waf --run=\"main_satnet --run_dir='<path/to/run/directory>'\"");
        return 0;
    }

    // Load basic simulation environment
    Ptr<BasicSimulation> basicSimulation = CreateObject<BasicSimulation>(run_dir);

    // Setting socket type
    Config::SetDefault ("ns3::TcpL4Protocol::SocketType", StringValue ("ns3::" + basicSimulation->GetConfigParamOrFail("tcp_socket_type")));

    // Optimize TCP
    TcpOptimizer::OptimizeBasic(basicSimulation);

    // Read topology
    Ptr<TopologySatelliteNetwork> topology = CreateObject<TopologySatelliteNetwork>(basicSimulation, Ipv4ArbiterRoutingHelper());

    // Install routing arbiters
    std::string routing_mode = basicSimulation->GetConfigParamOrDefault("satellite_network_routing", "single_forward");
    if (routing_mode == "ucb_distributed") {

        uint32_t max_hop_count = (uint32_t) parse_positive_int64(
            basicSimulation->GetConfigParamOrDefault("ucb_max_hop_count", "30")
        );
        double slot_duration_s = parse_positive_double(
            basicSimulation->GetConfigParamOrDefault("ucb_slot_duration_s", "1.0")
        );
        double epsilon1 = parse_positive_double(
            basicSimulation->GetConfigParamOrDefault("ucb_epsilon1", "1e-9")
        );
        double epsilon2 = parse_positive_double(
            basicSimulation->GetConfigParamOrDefault("ucb_epsilon2", "1e-9")
        );
        double max_gsl_length_m = parse_positive_double(
            basicSimulation->GetConfigParamOrDefault("max_gsl_length_m", "1089686.0")
        );
        double max_isl_length_m = parse_positive_double(
            basicSimulation->GetConfigParamOrDefault("max_isl_length_m", "5442958.2030362869")
        );
        double random_select_prob = parse_double(
            basicSimulation->GetConfigParamOrDefault("ucb_random_select_prob", "0.1")
        );
        double dst_arrival_reward = parse_double(
            basicSimulation->GetConfigParamOrDefault("ucb_dst_arrival_reward", "2.0")
        );

        std::vector<double> reward_weights;
        std::string reward_weights_str = basicSimulation->GetConfigParamOrDefault(
            "ucb_reward_weights", "list(0.25,0.25,0.25,0.25)"
        );
        std::vector<std::string> w_str_list = parse_list_string(reward_weights_str);
        for (std::string &s : w_str_list) {
            reward_weights.push_back(parse_double(s));
        }
        int64_t dynamic_state_update_interval_ns = parse_positive_int64(
            basicSimulation->GetConfigParamOrDefault("dynamic_state_update_interval_ns", "100000000")
        );
        (void) dynamic_state_update_interval_ns;
        // 每个节点绑定一个ucb
        for (size_t i = 0; i < topology->GetNodes().GetN(); i++) {
            Ptr<ArbiterUcbDistributedRouting> arbiter = CreateObject<ArbiterUcbDistributedRouting>(
                topology->GetNodes().Get(i),
                topology->GetNodes(),
                max_hop_count,
                slot_duration_s,
                reward_weights,
                epsilon1,
                epsilon2,
                max_gsl_length_m,
                max_isl_length_m,
                random_select_prob,
                dst_arrival_reward
            );
            topology->GetNodes().Get(i)->GetObject<Ipv4>()->GetRoutingProtocol()->GetObject<Ipv4ArbiterRouting>()->SetArbiter(arbiter);
        }

    } else {
        ArbiterSingleForwardHelper arbiterHelper(basicSimulation, topology->GetNodes());
        GslIfBandwidthHelper gslIfBandwidthHelper(basicSimulation, topology->GetNodes());
    }

    // Schedule flows
    TcpFlowScheduler tcpFlowScheduler(basicSimulation, topology); // Requires enable_tcp_flow_scheduler=true

    // Schedule UDP bursts
    UdpBurstScheduler udpBurstScheduler(basicSimulation, topology); // Requires enable_udp_burst_scheduler=true

    // Schedule pings
    PingmeshScheduler pingmeshScheduler(basicSimulation, topology); // Requires enable_pingmesh_scheduler=true

    // Run simulation
    basicSimulation->Run();

    // Write flow results
    tcpFlowScheduler.WriteResults();

    // Write UDP burst results
    udpBurstScheduler.WriteResults();

    // Write pingmesh results
    pingmeshScheduler.WriteResults();

    // Collect utilization statistics
    topology->CollectUtilizationStatistics();

    // Finalize the simulation
    basicSimulation->Finalize();

    return 0;

}
