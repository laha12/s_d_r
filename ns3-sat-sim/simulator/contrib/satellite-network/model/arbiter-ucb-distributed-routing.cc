#include "arbiter-ucb-distributed-routing.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <sstream>
#include <iostream>
#include <fstream>
#include <cstdlib>
#include "ns3/data-rate.h"
#include "ns3/channel.h"
#include "ns3/gsl-net-device.h"
#include "ns3/ground-station.h"
#include "ns3/mobility-model.h"
#include "ns3/net-device.h"
#include "ns3/node.h"
#include "ns3/point-to-point-laser-net-device.h"
#include "ns3/simulator.h"

namespace ns3 {

namespace {
const bool kUcbRouteDebug = true;
const uint64_t kUcbRouteDebugMaxLines = 100000;
const size_t kUcbRouteDebugMaxArmsToPrint = 32;
uint64_t g_ucb_route_debug_line_count = 0;
std::ofstream g_ucb_route_debug_file;
bool g_ucb_route_debug_file_initialized = false;
std::map<uint64_t, UcbPacketState> g_ucb_packet_state_by_uid;

std::string VectorToString(const std::vector<uint32_t>& vec) {
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

std::string ArmSummaryToString(const std::vector<uint32_t>& vec) {
    if (vec.size() > kUcbRouteDebugMaxArmsToPrint) {
        std::ostringstream oss;
        oss << "[omitted,size=" << vec.size() << "]";
        return oss.str();
    }
    return VectorToString(vec);
}

void DebugLog(const std::string& msg) {
    if (!kUcbRouteDebug) {
        return;
    }
    if (g_ucb_route_debug_line_count >= kUcbRouteDebugMaxLines) {
        return;
    }
    if (!g_ucb_route_debug_file_initialized) {
        const char* env_log_path = std::getenv("UCB_ROUTE_DEBUG_PATH");
        std::string log_path = env_log_path ? std::string(env_log_path) : "ucb_distributed_routing_debug.txt";
        g_ucb_route_debug_file.open(log_path, std::ios::out | std::ios::app);
        g_ucb_route_debug_file_initialized = true;
    }
    if (g_ucb_route_debug_file.is_open()) {
        g_ucb_route_debug_file << msg << std::endl;
        g_ucb_route_debug_file.flush();
        g_ucb_route_debug_line_count++;
    }
}
}

NS_LOG_COMPONENT_DEFINE("ArbiterUcbDistributedRouting");
NS_OBJECT_ENSURE_REGISTERED(ArbiterUcbDistributedRouting);
NS_OBJECT_ENSURE_REGISTERED(UcbRoutingTag);

TypeId UcbRoutingTag::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::UcbRoutingTag")
        .SetParent<Tag>()
        .AddConstructor<UcbRoutingTag>();
    return tid;
}

TypeId UcbRoutingTag::GetInstanceTypeId(void) const {
    return GetTypeId();
}

uint32_t UcbRoutingTag::GetSerializedSize(void) const {
    return 4 + 4 + 4 + 8 + 4 + pathHistory.size() * 4;
}

void UcbRoutingTag::Serialize(TagBuffer i) const {
    i.WriteU32(srcNodeId);
    i.WriteU32(dstNodeId);
    i.WriteU32(hopCount);
    i.WriteDouble(accumulatedDelayMs);
    i.WriteU32(pathHistory.size());
    for (auto nodeId : pathHistory) {
        i.WriteU32(nodeId);
    }
}

void UcbRoutingTag::Deserialize(TagBuffer i) {
    srcNodeId = i.ReadU32();
    dstNodeId = i.ReadU32();
    hopCount = i.ReadU32();
    accumulatedDelayMs = i.ReadDouble();
    uint32_t pathSize = i.ReadU32();
    pathHistory.clear();
    for (uint32_t j = 0; j < pathSize; j++) {
        pathHistory.push_back(i.ReadU32());
    }
}

void UcbRoutingTag::Print(std::ostream &os) const {
    os << "src=" << srcNodeId << ", dst=" << dstNodeId << ", hops=" << hopCount;
}

// ==================== ArbiterUcbDistributedRouting 实现 ====================
TypeId ArbiterUcbDistributedRouting::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::ArbiterUcbDistributedRouting")
        .SetParent<ArbiterSatnet>();
    return tid;
}


ArbiterUcbDistributedRouting::ArbiterUcbDistributedRouting(
    Ptr<Node> this_Node,
    NodeContainer nodes,
    uint32_t maxHopCount,
    double slotDurationS,
    std::vector<double> rewardWeights,
    double epsilon1,
    double epsilon2,
    double maxGslLengthM,
    double maxIslLengthM,
    double randomSelectProb,
    double dstArrivalReward
) : ArbiterSatnet(this_Node, nodes) {
    m_node_id = this_Node->GetId();
    m_maxHopCount = maxHopCount;
    m_slotDurationS = slotDurationS;
    m_slotDurationNs = (uint64_t)(slotDurationS * 1e9);
    m_numSatellites = 0;
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
    // 默认均分
    m_rewardWeights = std::vector<double>{0.25, 0.25, 0.25, 0.25};
    // 自定义奖励权重 截断处理
    for (size_t i = 0; i < std::min(m_rewardWeights.size(), rewardWeights.size()); i++) {
        m_rewardWeights[i] = rewardWeights[i];
    }
    m_epsilon1 = epsilon1;
    m_epsilon2 = epsilon2;
    m_max_gsl_length_m = maxGslLengthM;
    m_max_isl_length_m = maxIslLengthM;
    m_random_select_prob = randomSelectProb;
    m_dst_arrival_reward = dstArrivalReward;
    NS_ABORT_MSG_IF(
        m_random_select_prob < 0.0 || m_random_select_prob > 1.0,
        "ucb_random_select_prob must be in [0, 1]"
    );
    m_randomVariable = CreateObject<UniformRandomVariable>();
    m_currentSlot = 0;
    m_totalForwardCount = 0;
    m_totalDropCount = 0;
    m_lastSlotUpdateTimeNs = Simulator::Now().GetNanoSeconds();
    // 获取当前节点网络设备数目
    uint32_t nDevices = this_Node->GetNDevices();
    for (uint32_t i = 0; i < nDevices; i++) {
        Ptr<NetDevice> dev = this_Node->GetDevice(i);
        // 识别GSL/ISl设备
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
        Ptr<MobilityModel> mobThis = this_Node->GetObject<MobilityModel>();

        if (islDev) {
            // 获取ISL设备的接收节点
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
            linkState.maxCapacityBit = transmissionRateBps * slotDurationS;
            linkState.usedCapacityBit = 0.0;
            linkState.queueLength = 0;
            linkState.isIsl = true;
            linkState.isGsl = false;
            linkState.isAvailable = true;
            linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
            Ptr<MobilityModel> mobNeighbor = destinationNode->GetObject<MobilityModel>();
            double distanceM = 0.0;
            if (mobThis != 0 && mobNeighbor != 0) {
                distanceM = mobThis->GetDistanceFrom(mobNeighbor);
                linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
            } else {
                linkState.propagationDelayMs = 0.0;
            }
            m_linkStateMap[neighborNodeId] = linkState;
            if (m_ucbStateMap.find(neighborNodeId) == m_ucbStateMap.end()) {
                double initialReward = 1.0 / (1.0 + (distanceM / 1000000.0));
                m_ucbStateMap[neighborNodeId] = {initialReward, 0};
            }
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
            linkState.maxCapacityBit = transmissionRateBps * slotDurationS;
            linkState.usedCapacityBit = 0.0;
            linkState.queueLength = 0;
            linkState.isIsl = false;
            linkState.isGsl = true;
            linkState.isAvailable = true;
            linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
            Ptr<MobilityModel> mobNeighbor = peerDev->GetNode()->GetObject<MobilityModel>();
            double distanceM = 0.0;
            if (mobThis != 0 && mobNeighbor != 0) {
                distanceM = mobThis->GetDistanceFrom(mobNeighbor);
                linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
            } else {
                linkState.propagationDelayMs = 0.0;
            }
            auto existingLinkIt = m_linkStateMap.find(neighborNodeId);
            if (existingLinkIt != m_linkStateMap.end() && existingLinkIt->second.isIsl) {
                continue;
            }
            m_linkStateMap[neighborNodeId] = linkState;
            if (m_ucbStateMap.find(neighborNodeId) == m_ucbStateMap.end()) {
                double initialReward = 1.0 / (1.0 + (distanceM / 1000000.0));
                m_ucbStateMap[neighborNodeId] = {initialReward, 0};
            }
        }
    }
    RefreshLinkAvailability();
    // 定时执行重置链路状态
    Simulator::Schedule(Seconds(m_slotDurationS), &ArbiterUcbDistributedRouting::SlotResetHandler, this);
}

ArbiterUcbDistributedRouting::~ArbiterUcbDistributedRouting() {}

UcbPacketState ArbiterUcbDistributedRouting::InitPacketState(int32_t sourceNodeId, int32_t targetNodeId) const
{
    UcbPacketState state;
    state.srcNodeId = static_cast<uint32_t>(sourceNodeId);
    state.dstNodeId = static_cast<uint32_t>(targetNodeId);
    state.hopCount = 0;
    state.pathHistory.clear();
    state.pathHistory.push_back(static_cast<uint32_t>(sourceNodeId));
    if (static_cast<uint32_t>(m_node_id) != static_cast<uint32_t>(sourceNodeId)) {
        state.pathHistory.push_back(static_cast<uint32_t>(m_node_id));
    }
    return state;
}

void ArbiterUcbDistributedRouting::SlotResetHandler()
{
    m_currentSlot++;
    m_lastSlotUpdateTimeNs = Simulator::Now().GetNanoSeconds();
    ResetSlotDynamicState();
    Simulator::Schedule(Seconds(m_slotDurationS), &ArbiterUcbDistributedRouting::SlotResetHandler, this);
}

void ArbiterUcbDistributedRouting::ResetSlotDynamicState() {
    const double packetSizeBit = 1500.0 * 8.0;
    // TODO: 考虑将链路已使用容量调整一下 是否可以调整为非0
    for (auto &pair : m_linkStateMap) {
        LinkState &linkState = pair.second;
        
        uint32_t maxProcessablePackets = static_cast<uint32_t>(linkState.maxCapacityBit / packetSizeBit);
        if (linkState.queueLength > maxProcessablePackets) {
            linkState.queueLength -= maxProcessablePackets;
        } else {
            linkState.queueLength = 0;
        }
        linkState.usedCapacityBit = 0.0;
    }
    RefreshLinkAvailability();
}

void ArbiterUcbDistributedRouting::RefreshLinkAvailability()
{
    for (auto &pair : m_linkStateMap) {
        LinkState &linkState = pair.second;
        double distanceM = 0.0;
        if (!TryGetCurrentDistanceM(linkState.neighborNodeId, distanceM)) {
            linkState.propagationDelayMs = 0.0;
            linkState.isAvailable = true;
            continue;
        }

        linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
        if (linkState.isGsl) {
            linkState.isAvailable = distanceM <= m_max_gsl_length_m;
        } else if (linkState.isIsl) {
            linkState.isAvailable = distanceM <= m_max_isl_length_m;
        } else {
            linkState.isAvailable = true;
        }
    }
}

std::vector<uint32_t> ArbiterUcbDistributedRouting::GetValidArms(
    uint32_t targetNodeId,
    const UcbPacketState &packetState
) const {
    bool currentIsGroundStation = IsGroundStationNode(m_node_id);
    if (!IsGroundStationNode(targetNodeId)) {
        return {};
    }
    auto targetLinkIt = m_linkStateMap.find(targetNodeId);
    if (targetLinkIt != m_linkStateMap.end()) {
        const LinkState &targetLink = targetLinkIt->second;
        bool targetVisited = std::find(
            packetState.pathHistory.begin(),
            packetState.pathHistory.end(),
            targetNodeId
        ) != packetState.pathHistory.end();
        bool allowDirectTarget = !targetVisited
                                 && !currentIsGroundStation
                                 && targetLink.isGsl
                                 && targetLink.isAvailable;
        if (allowDirectTarget) {
            return {targetNodeId};
        }
    }
    std::vector<uint32_t> unvisitedNeighbors;
    for (const auto &pair : m_linkStateMap) {
        uint32_t neighborId = pair.first;
        const LinkState &linkState = pair.second;

        if (!linkState.isAvailable) {
            continue;
        }
        
        bool isVisited = std::find(
            packetState.pathHistory.begin(),
            packetState.pathHistory.end(),
            neighborId
        ) != packetState.pathHistory.end();

        if (isVisited) {
            continue;
        }

        unvisitedNeighbors.push_back(neighborId);
    }

    std::vector<uint32_t> strictCandidates;
    for (uint32_t neighborId : unvisitedNeighbors) {
        const LinkState &linkState = m_linkStateMap.at(neighborId);

        if (currentIsGroundStation) {
            if (linkState.isGsl && !linkState.neighborIsGroundStation) {
                strictCandidates.push_back(neighborId);
            }
        } 
        else {
            bool directToTargetGround = (neighborId == targetNodeId && linkState.isGsl);
            bool relayBySatellite = (!linkState.neighborIsGroundStation && linkState.isIsl);
            if (directToTargetGround || relayBySatellite) {
                strictCandidates.push_back(neighborId);
            }
        }
    }

    if (!strictCandidates.empty()) {
        return strictCandidates;
    }

    std::vector<uint32_t> fallbackNonGround;
    for (uint32_t neighborId : unvisitedNeighbors) {
        const LinkState &linkState = m_linkStateMap.at(neighborId);
        if (!linkState.neighborIsGroundStation) {
            fallbackNonGround.push_back(neighborId);
        }
    }

    if (!fallbackNonGround.empty()) {
        return fallbackNonGround;
    }

    return {};
}

double ArbiterUcbDistributedRouting::CalculateUcbWeight(uint32_t neighborId, uint32_t totalForwardCount) {
    UcbState &ucbState = m_ucbStateMap[neighborId];
    double explorationTerm = std::sqrt(
        (3 * std::log(totalForwardCount + 1))
        / (2 * ucbState.selectCount + m_epsilon1)
    );
    return ucbState.avgReward + explorationTerm;
}

double ArbiterUcbDistributedRouting::CalculateReward(
    uint32_t neighborId,
    uint32_t targetNodeId,
    const std::vector<uint32_t> &candidateArms,
    bool transmitSuccess
) const {
    if (neighborId == targetNodeId && transmitSuccess) {
        return m_dst_arrival_reward;
    }
    
    const LinkState &linkState = m_linkStateMap.at(neighborId);
    double w1 = m_rewardWeights[0];
    double w2 = m_rewardWeights[1];
    double w3 = m_rewardWeights[2];
    double w4 = m_rewardWeights[3];

    NS_ABORT_MSG_IF(candidateArms.empty(), "candidateArms must not be empty when calculating reward.");
    NS_ABORT_MSG_IF
    (
        std::find(candidateArms.begin(), candidateArms.end(), neighborId) == candidateArms.end(),
        "neighborId must be one of candidateArms when calculating reward."
    );

    double maxDelayMs = m_epsilon2;
    double maxLoadRate = m_epsilon2;
    double maxDist = m_epsilon2;
    for (uint32_t candidateId : candidateArms)
    {
        const LinkState &candidateLink = m_linkStateMap.at(candidateId);
        double qd = (candidateLink.queueLength * 1500.0 * 8.0) / std::max(candidateLink.transmissionRateBps, m_epsilon2) * 1000.0;
        double td = candidateLink.propagationDelayMs + qd;
        maxDelayMs = std::max(maxDelayMs, td);
        double lr = candidateLink.usedCapacityBit / std::max(candidateLink.maxCapacityBit, m_epsilon2);
        maxLoadRate = std::max(maxLoadRate, lr);
        double dist = CalculateDistanceToDestination(candidateId, targetNodeId);
        maxDist = std::max(maxDist, dist);
    }

    double throughputReward = (linkState.maxCapacityBit - linkState.usedCapacityBit)
        / std::max(linkState.maxCapacityBit, m_epsilon2);
    throughputReward = std::max(0.0, throughputReward);

    double queuingDelayMs = (linkState.queueLength * 1500.0 * 8.0) / std::max(linkState.transmissionRateBps, m_epsilon2) * 1000.0;
    double totalDelayMs = linkState.propagationDelayMs + queuingDelayMs;
    double delayReward = 1.0 - (totalDelayMs / std::max(maxDelayMs, m_epsilon2));
    delayReward = std::max(0.0, delayReward);

    double currentLoadRate = linkState.usedCapacityBit / std::max(linkState.maxCapacityBit, m_epsilon2);
    double loadBalanceReward = 1.0 - (currentLoadRate / std::max(maxLoadRate, m_epsilon2));
    loadBalanceReward = std::max(0.0, loadBalanceReward);

    double currentDist = CalculateDistanceToDestination(neighborId, targetNodeId);
    double distanceReward = 1.0 - (currentDist / std::max(maxDist, m_epsilon2));
    distanceReward = std::max(0.0, distanceReward);

    double totalReward = w1 * throughputReward + w2 * delayReward + w3 * loadBalanceReward + w4 * distanceReward;
    return std::max(0.0, totalReward);
}

void ArbiterUcbDistributedRouting::UpdateUcbState(uint32_t selectedNeighborId, double reward) {
    UcbState &ucbState = m_ucbStateMap[selectedNeighborId];
    ucbState.selectCount++;
    ucbState.avgReward = ucbState.avgReward + (1.0 / ucbState.selectCount) * (reward - ucbState.avgReward);
}

void ArbiterUcbDistributedRouting::UpdateLinkState(uint32_t neighborId, uint32_t packetSizeByte) {
    LinkState &linkState = m_linkStateMap[neighborId];
    uint64_t packetSizeBit = static_cast<uint64_t>(packetSizeByte) * 8;
    linkState.usedCapacityBit += packetSizeBit;
    linkState.queueLength++;
}

bool ArbiterUcbDistributedRouting::TryGetCurrentDistanceM(uint32_t neighborId, double &distanceM) const {
    Ptr<Node> thisNode = m_nodes.Get(m_node_id);
    Ptr<Node> neighborNode = m_nodes.Get(neighborId);
    if (thisNode == 0 || neighborNode == 0) {
        return false;
    }
    Ptr<MobilityModel> mobThis = thisNode->GetObject<MobilityModel>();
    Ptr<MobilityModel> mobNeighbor = neighborNode->GetObject<MobilityModel>();
    if (mobThis == 0 || mobNeighbor == 0) {
        return false;
    }
    distanceM = mobThis->GetDistanceFrom(mobNeighbor);
    return true;
}

double ArbiterUcbDistributedRouting::CalculateDistanceToDestination(uint32_t neighborId, uint32_t dstNodeId) const {
    Ptr<Node> neighborNode = m_nodes.Get(neighborId);
    Ptr<Node> dstNode = m_nodes.Get(dstNodeId);
    Ptr<MobilityModel> mobNeighbor = neighborNode->GetObject<MobilityModel>();
    Ptr<MobilityModel> mobDst = dstNode->GetObject<MobilityModel>();
    if (mobNeighbor == 0 || mobDst == 0) {
        return 0.0;
    }
    return mobNeighbor->GetDistanceFrom(mobDst);
}

bool ArbiterUcbDistributedRouting::IsPacketDrop(
    uint32_t neighborId,
    const UcbPacketState &packetState,
    const Ipv4Header &ipHeader
) const {
    if (packetState.hopCount >= m_maxHopCount) {
        return true;
    }
    if (ipHeader.GetTtl() > 0 && ipHeader.GetTtl() <= 1) {
        return true;
    }
    const LinkState &linkState = m_linkStateMap.at(neighborId);
    if (linkState.queueLength >= 100) {
        return true;
    }
    return false;
}
// 路由决策
std::tuple<int32_t, int32_t, int32_t> ArbiterUcbDistributedRouting::TopologySatelliteNetworkDecide(
    int32_t sourceNodeId,
    int32_t targetNodeId,
    Ptr<const Packet> pkt,
    Ipv4Header const &ipHeader,
    bool isRequestForSourceIpSoNoNextHeader
) {
    bool isDryRun = isRequestForSourceIpSoNoNextHeader;
    bool allowLearning = !isDryRun && ipHeader.GetTtl() > 0;
    if (m_node_id == targetNodeId) {
        if (allowLearning && pkt) {
            g_ucb_packet_state_by_uid.erase(pkt->GetUid());
        }
        return std::make_tuple(-1, -1, -1);
    }

    uint64_t uid_for_log = pkt ? pkt->GetUid() : 0;
    UcbPacketState packetState;
    if (allowLearning) {
        uint64_t uid = pkt->GetUid();
        auto it = g_ucb_packet_state_by_uid.find(uid);
        if (it == g_ucb_packet_state_by_uid.end()) {
            packetState = InitPacketState(sourceNodeId, targetNodeId);
            g_ucb_packet_state_by_uid[uid] = packetState;
        } else {
            UcbPacketState &globalState = it->second;
            // 做一致性校验
            bool stateMismatch =
                globalState.srcNodeId != static_cast<uint32_t>(sourceNodeId) ||
                globalState.dstNodeId != static_cast<uint32_t>(targetNodeId);
            // 不一致则重新初始化
            if (stateMismatch) {
                packetState = InitPacketState(sourceNodeId, targetNodeId);
                globalState = packetState;
            }
            else {
                packetState.srcNodeId = globalState.srcNodeId;
                packetState.dstNodeId = globalState.dstNodeId;
                packetState.hopCount = globalState.hopCount;
                packetState.pathHistory = globalState.pathHistory;
                packetState.hopCount++;
                if (packetState.pathHistory.empty() || packetState.pathHistory.back() != static_cast<uint32_t>(m_node_id)) {
                    packetState.pathHistory.push_back(static_cast<uint32_t>(m_node_id));
                }
                globalState.hopCount = packetState.hopCount;
                globalState.pathHistory = packetState.pathHistory;
            }
        }
    } else {
        packetState = InitPacketState(sourceNodeId, targetNodeId);
    }

    std::vector<uint32_t> validArms = GetValidArms(static_cast<uint32_t>(targetNodeId), packetState);
    if (validArms.empty()) {
        std::ostringstream oss;
        oss << "[UCB_DEBUG][DROP][NO_ARM]"
            << " dry_run=" << (isDryRun ? 1 : 0)
            << " node=" << m_node_id
            << " src=" << sourceNodeId
            << " dst=" << targetNodeId
            << " uid=" << uid_for_log
            << " hop=" << packetState.hopCount
            << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
            << " path=" << VectorToString(packetState.pathHistory);
        DebugLog(oss.str());
        if (allowLearning) {
            g_ucb_packet_state_by_uid.erase(pkt->GetUid());
        }
        return std::make_tuple(-1, -1, -1);
    }

    uint32_t selectedNeighborId = validArms[0];

    bool randomSelect = false;
    if (validArms.size() > 1 && m_randomVariable->GetValue(0.0, 1.0) < m_random_select_prob) {
        randomSelect = true;
    }
    if (randomSelect) {
        uint32_t randomIndex = m_randomVariable->GetInteger(0, validArms.size() - 1);
        selectedNeighborId = validArms[randomIndex];
    } else {
        double maxWeight = -std::numeric_limits<double>::infinity();
        for (uint32_t neighborId : validArms) {
            double weight = CalculateUcbWeight(neighborId, m_totalForwardCount);
            if (weight > maxWeight) {
                maxWeight = weight;
                selectedNeighborId = neighborId;
            }
        }
    }
    // 选完最优臂就总次数加1 防止丢包更新奖励加不上
    if (allowLearning) {
        m_totalForwardCount++;
    }
    bool isDrop = allowLearning && IsPacketDrop(selectedNeighborId, packetState, ipHeader);
    if (isDrop) {
        m_totalDropCount++;
        const LinkState &selectedLink = m_linkStateMap.at(selectedNeighborId);
        std::ostringstream oss;
        oss << "[UCB_DEBUG][DROP][POLICY]"
            << " dry_run=" << (isDryRun ? 1 : 0)
            << " node=" << m_node_id
            << " src=" << sourceNodeId
            << " dst=" << targetNodeId
            << " uid=" << uid_for_log
            << " hop=" << packetState.hopCount
            << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
            << " selected=" << selectedNeighborId
            << " valid_arms=" << ArmSummaryToString(validArms)
            << " qlen=" << selectedLink.queueLength
            << " path=" << VectorToString(packetState.pathHistory);
        DebugLog(oss.str());
        if (allowLearning) {
            g_ucb_packet_state_by_uid.erase(pkt->GetUid());
            double reward = CalculateReward(
                selectedNeighborId,
                static_cast<uint32_t>(targetNodeId),
                validArms,
                false
            );
            UpdateUcbState(selectedNeighborId, reward);
        }
        return std::make_tuple(-1, -1, -1);
    }

    LinkState &selectedLink = m_linkStateMap[selectedNeighborId];
    if (!selectedLink.isAvailable) {
        if (allowLearning && pkt) {
            g_ucb_packet_state_by_uid.erase(pkt->GetUid());
        }
        return std::make_tuple(-1, -1, -1);
    }
    bool forwardedToDestination = (selectedNeighborId == static_cast<uint32_t>(targetNodeId));
    {
        std::ostringstream oss;
        oss << "[UCB_DEBUG][FWD]"
            << " dry_run=" << (isDryRun ? 1 : 0)
            << " node=" << m_node_id
            << " src=" << sourceNodeId
            << " dst=" << targetNodeId
            << " uid=" << uid_for_log
            << " hop=" << packetState.hopCount
            << " ttl=" << static_cast<uint32_t>(ipHeader.GetTtl())
            << " selected=" << selectedNeighborId
            << " out_if=" << selectedLink.outInterfaceId
            << " next_if=" << selectedLink.nextHopInInterfaceId
            << " valid_arms=" << ArmSummaryToString(validArms)
            << " path=" << VectorToString(packetState.pathHistory);
        DebugLog(oss.str());
    }
    if (allowLearning) {
        uint32_t packetSizeByte = pkt->GetSize();
        UpdateLinkState(selectedNeighborId, packetSizeByte);
        double reward = CalculateReward(selectedNeighborId, static_cast<uint32_t>(targetNodeId), validArms, true);
        UpdateUcbState(selectedNeighborId, reward);
        std::ostringstream oss;
        oss << "[UCB_DEBUG][LEARN]"
            << " node=" << m_node_id
            << " src=" << sourceNodeId
            << " dst=" << targetNodeId
            << " uid=" << uid_for_log
            << " selected=" << selectedNeighborId
            << " reward=" << reward
            << " qlen_after=" << selectedLink.queueLength
            << " used_bits_after=" << selectedLink.usedCapacityBit;
        DebugLog(oss.str());
        if (forwardedToDestination) {
            std::vector<uint32_t> arrivedPath = packetState.pathHistory;
            if (arrivedPath.empty() || arrivedPath.back() != static_cast<uint32_t>(targetNodeId)) {
                arrivedPath.push_back(static_cast<uint32_t>(targetNodeId));
            }
            std::ostringstream arrived;
            arrived << "[UCB_DEBUG][ARRIVE]"
                << " node=" << targetNodeId
                << " src=" << sourceNodeId
                << " dst=" << targetNodeId
                << " uid=" << uid_for_log
                << " hop=" << (packetState.hopCount + 1)
                << " path=" << VectorToString(arrivedPath);
            DebugLog(arrived.str());
        }
        if (forwardedToDestination && pkt) {
            g_ucb_packet_state_by_uid.erase(pkt->GetUid());
        }
    }

    return std::make_tuple(
        static_cast<int32_t>(selectedNeighborId),
        static_cast<int32_t>(selectedLink.outInterfaceId),
        static_cast<int32_t>(selectedLink.nextHopInInterfaceId)
    );
}

std::string ArbiterUcbDistributedRouting::StringReprOfForwardingState() {
    std::ostringstream oss;
    oss << "UCB Distributed Routing State of node " << m_node_id << std::endl;
    oss << " -> Total forward count: " << m_totalForwardCount << std::endl;
    oss << " -> Total drop count: " << m_totalDropCount << std::endl;
    for (auto &pair : m_ucbStateMap) {
        oss << " -> Neighbor " << pair.first
            << ": avgReward=" << pair.second.avgReward
            << ", selectCount=" << pair.second.selectCount << std::endl;
    }
    return oss.str();
}

bool ArbiterUcbDistributedRouting::IsSatelliteNode(uint32_t nodeId) const {
    return nodeId < m_numSatellites;
}

bool ArbiterUcbDistributedRouting::IsGroundStationNode(uint32_t nodeId) const {
    return !IsSatelliteNode(nodeId);
}

} // namespace ns3
