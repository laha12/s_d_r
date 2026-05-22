#include "arbiter-spf.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <sstream>
#include <iostream>
#include <fstream>
#include <queue>
#include "ns3/data-rate.h"
#include "ns3/channel.h"
#include "ns3/gsl-net-device.h"
#include "ns3/ground-station.h"
#include "ns3/mobility-model.h"
#include "ns3/net-device.h"
#include "ns3/node.h"
#include "ns3/point-to-point-laser-net-device.h"

namespace ns3 {

NS_LOG_COMPONENT_DEFINE("ArbiterSpf");
NS_OBJECT_ENSURE_REGISTERED(ArbiterSpf);

// ============================================================
// SPF 路径追踪 debug 日志辅助函数（与 UCB 格式一致）
// ============================================================

namespace {
const bool kSpfRouteDebug = true;
const uint64_t kSpfRouteDebugMaxLines = 100000;
uint64_t g_spf_route_debug_line_count = 0;
std::ofstream g_spf_route_debug_file;
bool g_spf_route_debug_file_initialized = false;
}

// 全局包状态映射（按 uid 追踪路径）
std::map<uint64_t, SpfPacketState> g_spf_packet_state_by_uid;

// 将路径向量转为字符串
std::string SpfVectorToString(const std::vector<uint32_t>& vec) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < vec.size(); i++) {
        if (i > 0) {
            oss << ",";
        }
        oss << vec[i];
    }
    oss << "]";
    return oss.str();
}

// 输出 debug 日志到文件（与 UCB 的 DebugLog 一致）
void SpfDebugLog(const std::string& msg) {
    if (!kSpfRouteDebug) {
        return;
    }
    if (g_spf_route_debug_line_count >= kSpfRouteDebugMaxLines) {
        return;
    }
    if (!g_spf_route_debug_file_initialized) {
        const char* env_log_path = std::getenv("SPF_ROUTE_DEBUG_PATH");
        std::string log_path = env_log_path ? std::string(env_log_path) : "spf_route_debug.txt";
        g_spf_route_debug_file.open(log_path, std::ios::out | std::ios::app);
        g_spf_route_debug_file_initialized = true;
    }
    if (g_spf_route_debug_file.is_open()) {
        g_spf_route_debug_file << "[SPF_DEBUG]" << msg << std::endl;
        g_spf_route_debug_file.flush();
        g_spf_route_debug_line_count++;
    }
}

// 获取原始 ns3 packet uid（处理 fragment 情况）
uint64_t SpfGetOriginalNs3PacketUid(Ptr<const Packet> pkt) {
    if (pkt == nullptr) {
        return 0;
    }
    return pkt->GetUid();
}

TypeId ArbiterSpf::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::ArbiterSpf")
        .SetParent<ArbiterSatnet>();
    return tid;
}

ArbiterSpf::ArbiterSpf(
    Ptr<Node> this_node,
    NodeContainer nodes,
    double max_gsl_length_m,
    double max_isl_length_m,
    double refresh_interval_s,
    uint32_t queueDropThreshold
) : ArbiterSatnet(this_node, nodes) {
    m_node_id = this_node->GetId();
    m_numSatellites = 0;
    m_maxGslLengthM = max_gsl_length_m;
    m_maxIslLengthM = max_isl_length_m;
    m_refreshIntervalS = refresh_interval_s;
    m_queueDropThreshold = queueDropThreshold;
    m_totalForwardCount = 0;
    m_totalDropCount = 0;

    for (uint32_t nodeId = 0; nodeId < m_nodes.GetN(); nodeId++) {
        Ptr<Node> node = m_nodes.Get(nodeId);
        bool hasIslDevice = false;
        uint32_t nNodeDevices = node->GetNDevices();
        for (uint32_t devId = 0; devId < nNodeDevices; devId++) {
            if (DynamicCast<PointToPointLaserNetDevice>(node->GetDevice(devId)) != 0) {
                hasIslDevice = true;
                break;
            }
        }
        if (hasIslDevice) {
            m_numSatellites++;
        }
    }

    InitializeLinkState();
    BuildGlobalTopology();
    m_nextHopList.resize(m_nodes.GetN(), std::make_tuple(-1, -1, -1));
    ComputeShortestPaths();

    ScheduleRefresh();
}

ArbiterSpf::~ArbiterSpf() {}

void ArbiterSpf::ScheduleRefresh() {
    Simulator::Schedule(Seconds(m_refreshIntervalS), &ArbiterSpf::RefreshHandler, this);
    Simulator::Schedule(Seconds(m_refreshIntervalS), &ArbiterSpf::ResetSlotDynamicState, this);
}

void ArbiterSpf::RefreshHandler() {
    RefreshLinkAvailability();
    BuildGlobalTopology();
    ComputeShortestPaths();
    ScheduleRefresh();
}

void ArbiterSpf::InitializeLinkState() {
    Ptr<Node> thisNode = m_nodes.Get(m_node_id);
    uint32_t nDevices = thisNode->GetNDevices();

    for (uint32_t i = 0; i < nDevices; i++) {
        Ptr<NetDevice> dev = thisNode->GetDevice(i);
        Ptr<PointToPointLaserNetDevice> islDev = DynamicCast<PointToPointLaserNetDevice>(dev);
        Ptr<GSLNetDevice> gslDev = DynamicCast<GSLNetDevice>(dev);

        if (!islDev && !gslDev) {
            continue;
        }
        Ptr<Channel> channel = dev->GetChannel();
        if (channel == 0) {
            continue;
        }

        DataRateValue dataRateValue;
        if (islDev) {
            islDev->GetAttribute("DataRate", dataRateValue);
        } else {
            gslDev->GetAttribute("DataRate", dataRateValue);
        }
        double transmissionRateBps = static_cast<double>(dataRateValue.Get().GetBitRate());
        Ptr<MobilityModel> mobThis = thisNode->GetObject<MobilityModel>();

        if (islDev) {
            Ptr<Node> destinationNode = islDev->GetDestinationNode();
            if (destinationNode == 0) {
                continue;
            }
            uint32_t neighborNodeId = destinationNode->GetId();
            Ptr<NetDevice> peerDev;
            uint32_t destinationDeviceCount = destinationNode->GetNDevices();
            for (uint32_t k = 0; k < destinationDeviceCount; k++) {
                Ptr<NetDevice> candidate = destinationNode->GetDevice(k);
                if (candidate->GetChannel() == channel) {
                    peerDev = candidate;
                    break;
                }
            }
            if (peerDev == 0) {
                continue;
            }
            LinkState linkState;
            linkState.neighborNodeId = neighborNodeId;
            linkState.outInterfaceId = dev->GetIfIndex();
            linkState.nextHopInInterfaceId = peerDev->GetIfIndex();
            linkState.transmissionRateBps = transmissionRateBps;
            linkState.maxCapacityBit = transmissionRateBps * m_refreshIntervalS;
            linkState.usedCapacityBit = 0.0;
            linkState.queueLength = 0;
            linkState.queuedBytes = 0;
            linkState.distanceM = 0.0;
            linkState.propagationDelayMs = 0.0;
            linkState.isIsl = true;
            linkState.isGsl = false;
            linkState.isAvailable = true;
            linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
            Ptr<MobilityModel> mobNeighbor = destinationNode->GetObject<MobilityModel>();
            double distanceM = 0.0;
            if (mobThis != 0 && mobNeighbor != 0) {
                distanceM = mobThis->GetDistanceFrom(mobNeighbor);
                linkState.distanceM = distanceM;
                linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
            }
            m_linkStateMap[neighborNodeId] = linkState;
            continue;
        }

        uint32_t nChannelDevices = channel->GetNDevices();
        for (uint32_t j = 0; j < nChannelDevices; j++) {
            Ptr<NetDevice> peerDev = channel->GetDevice(j);
            if (peerDev == dev) {
                continue;
            }
            uint32_t neighborNodeId = peerDev->GetNode()->GetId();
            LinkState linkState;
            linkState.neighborNodeId = neighborNodeId;
            linkState.outInterfaceId = dev->GetIfIndex();
            linkState.nextHopInInterfaceId = peerDev->GetIfIndex();
            linkState.transmissionRateBps = transmissionRateBps;
            linkState.maxCapacityBit = transmissionRateBps * m_refreshIntervalS;
            linkState.usedCapacityBit = 0.0;
            linkState.queueLength = 0;
            linkState.queuedBytes = 0;
            linkState.distanceM = 0.0;
            linkState.propagationDelayMs = 0.0;
            linkState.isIsl = false;
            linkState.isGsl = true;
            linkState.isAvailable = true;
            linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
            Ptr<MobilityModel> mobNeighbor = peerDev->GetNode()->GetObject<MobilityModel>();
            double distanceM = 0.0;
            if (mobThis != 0 && mobNeighbor != 0) {
                distanceM = mobThis->GetDistanceFrom(mobNeighbor);
                linkState.distanceM = distanceM;
                linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
            }
            auto existingLinkIt = m_linkStateMap.find(neighborNodeId);
            if (existingLinkIt != m_linkStateMap.end() && existingLinkIt->second.isIsl) {
                continue;
            }
            m_linkStateMap[neighborNodeId] = linkState;
        }
    }
    RefreshLinkAvailability();
}

bool ArbiterSpf::TryGetDistanceBetween(uint32_t nodeA, uint32_t nodeB, double &distanceM) const {
    if (nodeA >= m_nodes.GetN() || nodeB >= m_nodes.GetN()) {
        return false;
    }
    Ptr<Node> nodeA_ptr = m_nodes.Get(nodeA);
    Ptr<Node> nodeB_ptr = m_nodes.Get(nodeB);
    if (nodeA_ptr == 0 || nodeB_ptr == 0) {
        return false;
    }
    Ptr<MobilityModel> mobA = nodeA_ptr->GetObject<MobilityModel>();
    Ptr<MobilityModel> mobB = nodeB_ptr->GetObject<MobilityModel>();
    if (mobA == 0 || mobB == 0) {
        return false;
    }
    distanceM = mobA->GetDistanceFrom(mobB);
    return true;
}

void ArbiterSpf::BuildGlobalTopology() {
    m_globalTopology.clear();

    for (uint32_t fromNodeId = 0; fromNodeId < m_nodes.GetN(); fromNodeId++) {
        Ptr<Node> fromNode = m_nodes.Get(fromNodeId);
        uint32_t nDevices = fromNode->GetNDevices();

        for (uint32_t i = 0; i < nDevices; i++) {
            Ptr<NetDevice> dev = fromNode->GetDevice(i);
            Ptr<PointToPointLaserNetDevice> islDev = DynamicCast<PointToPointLaserNetDevice>(dev);
            Ptr<GSLNetDevice> gslDev = DynamicCast<GSLNetDevice>(dev);

            if (!islDev && !gslDev) {
                continue;
            }
            Ptr<Channel> channel = dev->GetChannel();
            if (channel == 0) {
                continue;
            }

            if (islDev) {
                Ptr<Node> destNode = islDev->GetDestinationNode();
                if (destNode == 0) {
                    continue;
                }
                uint32_t toNodeId = destNode->GetId();

                Ptr<NetDevice> peerDev;
                uint32_t destDevCount = destNode->GetNDevices();
                for (uint32_t k = 0; k < destDevCount; k++) {
                    Ptr<NetDevice> candidate = destNode->GetDevice(k);
                    if (candidate->GetChannel() == channel) {
                        peerDev = candidate;
                        break;
                    }
                }
                if (peerDev == 0) {
                    continue;
                }

                double distanceM = 0.0;
                bool gotDist = TryGetDistanceBetween(fromNodeId, toNodeId, distanceM);
                bool isAvailable = gotDist && (distanceM <= m_maxIslLengthM);

                GlobalLink glink;
                glink.fromNodeId = fromNodeId;
                glink.toNodeId = toNodeId;
                glink.outInterfaceId = dev->GetIfIndex();
                glink.nextHopInInterfaceId = peerDev->GetIfIndex();
                glink.distanceM = distanceM;
                glink.isIsl = true;
                glink.isGsl = false;
                glink.isAvailable = isAvailable;
                m_globalTopology.push_back(glink);
                continue;
            }

            uint32_t nChannelDevices = channel->GetNDevices();
            for (uint32_t j = 0; j < nChannelDevices; j++) {
                Ptr<NetDevice> peerDev = channel->GetDevice(j);
                if (peerDev == dev) {
                    continue;
                }
                uint32_t toNodeId = peerDev->GetNode()->GetId();

                double distanceM = 0.0;
                bool gotDist = TryGetDistanceBetween(fromNodeId, toNodeId, distanceM);
                bool isAvailable = gotDist && (distanceM <= m_maxGslLengthM);

                GlobalLink glink;
                glink.fromNodeId = fromNodeId;
                glink.toNodeId = toNodeId;
                glink.outInterfaceId = dev->GetIfIndex();
                glink.nextHopInInterfaceId = peerDev->GetIfIndex();
                glink.distanceM = distanceM;
                glink.isIsl = false;
                glink.isGsl = true;
                glink.isAvailable = isAvailable;
                m_globalTopology.push_back(glink);
            }
        }
    }

    std::cout << "[SPF] Node " << m_node_id
              << " global topology: " << m_globalTopology.size() << " links" << std::endl;
}

void ArbiterSpf::RefreshLinkAvailability() {
    for (auto &pair : m_linkStateMap) {
        LinkState &linkState = pair.second;
        double distanceM = 0.0;
        if (TryGetCurrentDistanceM(linkState.neighborNodeId, distanceM)) {
            linkState.distanceM = distanceM;
            linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;

            if (linkState.isGsl) {
                linkState.isAvailable = (distanceM <= m_maxGslLengthM);
            } else if (linkState.isIsl) {
                linkState.isAvailable = (distanceM <= m_maxIslLengthM);
            }
        }
    }
}

bool ArbiterSpf::TryGetCurrentDistanceM(uint32_t neighborId, double &distanceM) const {
    return TryGetDistanceBetween(m_node_id, neighborId, distanceM);
}

bool ArbiterSpf::IsSatelliteNode(uint32_t nodeId) const {
    return nodeId < m_numSatellites;
}

bool ArbiterSpf::IsGroundStationNode(uint32_t nodeId) const {
    return nodeId >= m_numSatellites;
}

void ArbiterSpf::ComputeShortestPaths() {
    uint32_t numNodes = m_nodes.GetN();
    std::vector<double> dist(numNodes, std::numeric_limits<double>::max());
    std::vector<int32_t> prev(numNodes, -1);
    std::vector<int32_t> outIf(numNodes, -1);
    std::vector<int32_t> nextIf(numNodes, -1);
    std::priority_queue<std::pair<double, uint32_t>,
                        std::vector<std::pair<double, uint32_t>>,
                        std::greater<std::pair<double, uint32_t>>> pq;

    dist[m_node_id] = 0.0;
    pq.push({0.0, m_node_id});

    while (!pq.empty()) {
        std::pair<double, uint32_t> top = pq.top();
        double currentDist = top.first;
        uint32_t u = top.second;
        pq.pop();

        if (currentDist > dist[u]) {
            continue;
        }

        bool uIsGroundStation = IsGroundStationNode(u);

        for (const auto &glink : m_globalTopology) {
            if (glink.fromNodeId != u) {
                continue;
            }
            if (!glink.isAvailable) {
                continue;
            }

            uint32_t v = glink.toNodeId;
            bool vIsGroundStation = IsGroundStationNode(v);

            if (uIsGroundStation && glink.isIsl) {
                continue;
            }
            if (!uIsGroundStation && vIsGroundStation && !glink.isGsl) {
                continue;
            }

            double weight = glink.distanceM;

            if (dist[v] > dist[u] + weight) {
                dist[v] = dist[u] + weight;
                prev[v] = static_cast<int32_t>(u);
                outIf[v] = static_cast<int32_t>(glink.outInterfaceId);
                nextIf[v] = static_cast<int32_t>(glink.nextHopInInterfaceId);
                pq.push({dist[v], v});
            }
        }
    }

    int reachableCount = 0;
    int unreachableCount = 0;
    std::vector<uint32_t> unreachableDests;

    for (uint32_t dst = 0; dst < numNodes; dst++) {
        if (static_cast<int32_t>(dst) == m_node_id) {
            m_nextHopList[dst] = std::make_tuple(static_cast<int32_t>(m_node_id), -1, -1);
            continue;
        }
        if (prev[dst] == -1) {
            m_nextHopList[dst] = std::make_tuple(-1, -1, -1);
            unreachableCount++;
            unreachableDests.push_back(dst);
            continue;
        }

        uint32_t curr = dst;
        while (prev[curr] != -1 && prev[curr] != static_cast<int32_t>(m_node_id)) {
            curr = prev[curr];
        }

        if (prev[curr] == static_cast<int32_t>(m_node_id)) {
            int32_t nextNode = static_cast<int32_t>(curr);
            int32_t outInterface = outIf[curr];
            int32_t nextInterface = nextIf[curr];
            m_nextHopList[dst] = std::make_tuple(nextNode, outInterface, nextInterface);
            reachableCount++;
        } else {
            m_nextHopList[dst] = std::make_tuple(-1, -1, -1);
            unreachableCount++;
            unreachableDests.push_back(dst);
        }
    }

    if (unreachableCount > 0) {
        std::cout << "[SPF] Node " << m_node_id
                  << ": reachable=" << reachableCount
                  << "/" << numNodes
                  << " UNREACHABLE=[";
        for (size_t i = 0; i < unreachableDests.size(); i++) {
            std::cout << unreachableDests[i];
            if (i + 1 < unreachableDests.size()) std::cout << ",";
        }
        std::cout << "]" << std::endl;
    }
}

std::tuple<int32_t, int32_t, int32_t> ArbiterSpf::TopologySatelliteNetworkDecide(
    int32_t source_node_id,
    int32_t target_node_id,
    Ptr<const Packet> pkt,
    Ipv4Header const &ipHeader,
    bool is_request_for_source_ip_so_no_next_header
) {
    // ============================================================
    // SPF 路径追踪 debug 日志（与 UCB 格式一致）
    // ============================================================
    uint64_t ns3_uid_for_log = SpfGetOriginalNs3PacketUid(pkt);
    uint64_t state_uid = ns3_uid_for_log;

    // 获取或初始化包状态
    SpfPacketState packetState;
    if (state_uid != 0) {
        auto it = g_spf_packet_state_by_uid.find(state_uid);
        if (it != g_spf_packet_state_by_uid.end()) {
            packetState = it->second;
        } else {
            // 首次见到此包，初始化路径历史
            packetState.hopCount = 0;
            packetState.pathHistory.clear();
            g_spf_packet_state_by_uid[state_uid] = packetState;
        }
    }

    // 检查是否有下一跳
    if (target_node_id < 0 || target_node_id >= static_cast<int32_t>(m_nextHopList.size())) {
        // 无下一跳，丢弃
        std::ostringstream oss;
        oss << "[DROP][NO_ROUTE]"
            << " node=" << m_node_id
            << " src=" << source_node_id
            << " dst=" << target_node_id
            << " uid=" << state_uid
            << " ns3_uid=" << ns3_uid_for_log
            << " hop=" << packetState.hopCount
            << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
            << " path=" << SpfVectorToString(packetState.pathHistory);
        SpfDebugLog(oss.str());
        if (state_uid != 0) {
            g_spf_packet_state_by_uid.erase(state_uid);
        }
        return std::make_tuple(-1, -1, -1);
    }

    int32_t nextNode = std::get<0>(m_nextHopList[target_node_id]);
    int32_t outIf = std::get<1>(m_nextHopList[target_node_id]);
    int32_t nextIf = std::get<2>(m_nextHopList[target_node_id]);

    if (nextNode == -1) {
        // 无下一跳，丢弃
        std::ostringstream oss;
        oss << "[DROP][NO_ROUTE]"
            << " node=" << m_node_id
            << " src=" << source_node_id
            << " dst=" << target_node_id
            << " uid=" << state_uid
            << " ns3_uid=" << ns3_uid_for_log
            << " hop=" << packetState.hopCount
            << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
            << " path=" << SpfVectorToString(packetState.pathHistory);
        SpfDebugLog(oss.str());
        if (state_uid != 0) {
            g_spf_packet_state_by_uid.erase(state_uid);
        }
        return std::make_tuple(-1, -1, -1);
    }

    // 检查是否需要丢弃（TTL 或队列满）
    if (IsPacketDrop(static_cast<uint32_t>(nextNode), ipHeader)) {
        m_totalDropCount++;
        auto linkIt = m_linkStateMap.find(static_cast<uint32_t>(nextNode));
        uint32_t qlen = 0;
        if (linkIt != m_linkStateMap.end()) {
            qlen = linkIt->second.queueLength;
        }
        std::ostringstream oss;
        oss << "[DROP][POLICY]"
            << " node=" << m_node_id
            << " src=" << source_node_id
            << " dst=" << target_node_id
            << " uid=" << state_uid
            << " ns3_uid=" << ns3_uid_for_log
            << " hop=" << packetState.hopCount
            << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
            << " selected=" << nextNode
            << " qlen=" << qlen
            << " path=" << SpfVectorToString(packetState.pathHistory);
        SpfDebugLog(oss.str());
        if (state_uid != 0) {
            g_spf_packet_state_by_uid.erase(state_uid);
        }
        return std::make_tuple(-1, -1, -1);
    }

    // 更新路径状态
    packetState.hopCount++;
    if (packetState.pathHistory.empty() || packetState.pathHistory.back() != static_cast<uint32_t>(m_node_id)) {
        packetState.pathHistory.push_back(static_cast<uint32_t>(m_node_id));
    }
    if (state_uid != 0) {
        g_spf_packet_state_by_uid[state_uid] = packetState;
    }

    // 转发日志
    auto linkIt = m_linkStateMap.find(static_cast<uint32_t>(nextNode));
    uint32_t out_if_log = 0, next_if_log = 0;
    if (linkIt != m_linkStateMap.end()) {
        out_if_log = linkIt->second.outInterfaceId;
        next_if_log = linkIt->second.nextHopInInterfaceId;
    }

    std::ostringstream fwd_oss;
    fwd_oss << "[FWD]"
        << " node=" << m_node_id
        << " src=" << source_node_id
        << " dst=" << target_node_id
        << " uid=" << state_uid
        << " ns3_uid=" << ns3_uid_for_log
        << " hop=" << packetState.hopCount
        << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
        << " selected=" << nextNode
        << " out_if=" << out_if_log
        << " next_if=" << next_if_log
        << " path=" << SpfVectorToString(packetState.pathHistory);
    SpfDebugLog(fwd_oss.str());

    // 更新链路状态
    if (pkt != nullptr) {
        uint32_t packetSizeByte = pkt->GetSize();
        UpdateLinkState(static_cast<uint32_t>(nextNode), packetSizeByte);
    }
    m_totalForwardCount++;

    // 检查是否到达目的地
    bool forwardedToDestination = (static_cast<uint32_t>(nextNode) == static_cast<uint32_t>(target_node_id));
    if (forwardedToDestination) {
        std::vector<uint32_t> arrivedPath = packetState.pathHistory;
        if (arrivedPath.empty() || arrivedPath.back() != static_cast<uint32_t>(target_node_id)) {
            arrivedPath.push_back(static_cast<uint32_t>(target_node_id));
        }
        std::ostringstream arrived;
        arrived << "[ARRIVE]"
            << " node=" << target_node_id
            << " src=" << source_node_id
            << " dst=" << target_node_id
            << " uid=" << state_uid
            << " ns3_uid=" << ns3_uid_for_log
            << " hop=" << (packetState.hopCount + 1)
            << " path=" << SpfVectorToString(arrivedPath);
        SpfDebugLog(arrived.str());

        // 清除包状态
        if (state_uid != 0) {
            g_spf_packet_state_by_uid.erase(state_uid);
        }
    }

    return std::make_tuple(nextNode, outIf, nextIf);
}

std::string ArbiterSpf::StringReprOfForwardingState() {
    std::ostringstream res;
    res << "SPF forwarding state of node " << m_node_id << std::endl;
    for (size_t i = 0; i < m_nextHopList.size(); i++) {
        res << "  -> " << i << ": ("
            << std::get<0>(m_nextHopList[i]) << ", "
            << std::get<1>(m_nextHopList[i]) << ", "
            << std::get<2>(m_nextHopList[i]) << ")" << std::endl;
    }
    return res.str();
}

void ArbiterSpf::ResetSlotDynamicState() {
    for (auto &pair : m_linkStateMap) {
        LinkState &linkState = pair.second;
        
        // 使用实际使用的容量来计算已发送的字节数
        double bytesSentThisSlot = linkState.usedCapacityBit / 8.0;
        
        if (linkState.queuedBytes > static_cast<uint64_t>(bytesSentThisSlot)) {
            linkState.queuedBytes -= static_cast<uint64_t>(bytesSentThisSlot);
        } else {
            linkState.queuedBytes = 0;
        }
        
        // 重置usedCapacityBit，准备下一个slot的统计
        linkState.usedCapacityBit = 0.0;
        
        uint64_t avgPacketSize = 1200;
        linkState.queueLength = static_cast<uint32_t>(
            linkState.queuedBytes / std::max(avgPacketSize, static_cast<uint64_t>(1))
        );
    }
}

bool ArbiterSpf::IsPacketDrop(uint32_t nextNodeId, Ipv4Header const &ipHeader) const {
    if (ipHeader.GetTtl() > 0 && ipHeader.GetTtl() <= 1) {
        return true;
    }
    auto linkIt = m_linkStateMap.find(nextNodeId);
    if (linkIt == m_linkStateMap.end()) {
        return true;
    }
    const LinkState &linkState = linkIt->second;
    if (linkState.queueLength >= m_queueDropThreshold) {
        return true;
    }
    return false;
}

void ArbiterSpf::UpdateLinkState(uint32_t nextNodeId, uint32_t packetSizeByte) {
    auto linkIt = m_linkStateMap.find(nextNodeId);
    if (linkIt == m_linkStateMap.end()) {
        return;
    }
    LinkState &linkState = linkIt->second;
    uint64_t packetSizeBit = static_cast<uint64_t>(packetSizeByte) * 8;
    linkState.usedCapacityBit += packetSizeBit;
    linkState.queueLength++;
    linkState.queuedBytes += packetSizeByte;
}

}
