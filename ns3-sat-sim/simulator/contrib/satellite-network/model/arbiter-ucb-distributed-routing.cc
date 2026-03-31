#include "arbiter-ucb-distributed-routing.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <sstream>
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
    double epsilon2
) : ArbiterSatnet(this_Node, nodes) {
    m_node_id = this_Node->GetId();
    m_maxHopCount = maxHopCount;
    m_slotDurationS = slotDurationS;
    m_slotDurationNs = (uint64_t)(slotDurationS * 1e9);
    // 默认均分
    m_rewardWeights = std::vector<double>{0.25, 0.25, 0.25, 0.25};
    // 自定义奖励权重 截断处理
    for (size_t i = 0; i < std::min(m_rewardWeights.size(), rewardWeights.size()); i++) {
        m_rewardWeights[i] = rewardWeights[i];
    }
    m_epsilon1 = epsilon1;
    m_epsilon2 = epsilon2;
    m_currentSlot = 0;
    m_totalForwardCount = 0;
    m_lastSlotUpdateTimeNs = Simulator::Now().GetNanoSeconds();
    // 获取当前节点网络设备数目
    uint32_t nDevices = this_Node->GetNDevices();
    for (uint32_t i = 0; i < nDevices; i++) {
        Ptr<NetDevice> dev = this_Node->GetDevice(i);
        // 类型转换 检查是否为ISL或GSL设备 失败为Null
        Ptr<PointToPointLaserNetDevice> islDev = DynamicCast<PointToPointLaserNetDevice>(dev);
        Ptr<GSLNetDevice> gslDev = DynamicCast<GSLNetDevice>(dev);
        if (!islDev && !gslDev) continue;
        // check网卡是否连接到通道
        if (dev->GetChannel() == 0) continue;

        Ptr<Channel> channel = dev->GetChannel();
        Ptr<NetDevice> dev0 = channel->GetDevice(0);
        Ptr<NetDevice> dev1 = channel->GetDevice(1);
        // 判断邻居
        Ptr<NetDevice> peerDev = dev0->GetNode()->GetId() == (uint32_t)m_node_id ? dev1 : dev0;
        uint32_t neighborNodeId = peerDev->GetNode()->GetId();

        LinkState linkState;
        linkState.neighborNodeId = neighborNodeId;
        linkState.outInterfaceId = dev->GetIfIndex();
        linkState.nextHopInInterfaceId = peerDev->GetIfIndex();
        DataRateValue dataRateValue;
        if (islDev) {
            islDev->GetAttribute("DataRate", dataRateValue);
            linkState.transmissionRateBps = (double) dataRateValue.Get().GetBitRate();
        } else {
            gslDev->GetAttribute("DataRate", dataRateValue);
            linkState.transmissionRateBps = (double) dataRateValue.Get().GetBitRate();
        }
        linkState.maxCapacityBit = linkState.transmissionRateBps * slotDurationS;
        linkState.usedCapacityBit = 0.0;
        linkState.queueLength = 0;
        linkState.isIsl = (islDev != 0);
        linkState.isGsl = (gslDev != 0);
        linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
        // 获取当前节点和邻居节点的位置信息
        Ptr<MobilityModel> mobThis = this_Node->GetObject<MobilityModel>();
        Ptr<MobilityModel> mobNeighbor = peerDev->GetNode()->GetObject<MobilityModel>();
        if (mobThis != 0 && mobNeighbor != 0) {
            double distanceM = mobThis->GetDistanceFrom(mobNeighbor);
            linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
        } else {
            linkState.propagationDelayMs = 0.0;
        }

        m_linkStateMap[neighborNodeId] = linkState;
        // 若该邻居未初始化过ucb 则初始化
        if (m_ucbStateMap.find(neighborNodeId) == m_ucbStateMap.end()) {
            m_ucbStateMap[neighborNodeId] = {1.0, 0};
        }
    }
    // 定时执行重置链路状态
    Simulator::Schedule(Seconds(m_slotDurationS), &ArbiterUcbDistributedRouting::SlotResetHandler, this);
}

ArbiterUcbDistributedRouting::~ArbiterUcbDistributedRouting() {}

void ArbiterUcbDistributedRouting::SlotResetHandler() {
    m_currentSlot++;
    m_lastSlotUpdateTimeNs = Simulator::Now().GetNanoSeconds();
    ResetSlotDynamicState();
    Simulator::Schedule(Seconds(m_slotDurationS), &ArbiterUcbDistributedRouting::SlotResetHandler, this);
}

void ArbiterUcbDistributedRouting::ResetSlotDynamicState() {
    for (auto &pair : m_linkStateMap) {
        pair.second.usedCapacityBit = 0.0;
    }
}

std::vector<uint32_t> ArbiterUcbDistributedRouting::GetValidArms(
    uint32_t targetNodeId,
    const PacketState &packetState
) const {
    bool currentIsGroundStation = IsGroundStationNode(m_node_id);
    bool targetIsGroundStation = IsGroundStationNode(targetNodeId);
    std::vector<uint32_t> unvisitedNeighbors;
    for (const auto &pair : m_linkStateMap) {
        uint32_t neighborId = pair.first;
        bool isVisited = std::find(
            packetState.pathHistory.begin(),
            packetState.pathHistory.end(),
            neighborId
        ) != packetState.pathHistory.end();
        if (!isVisited) {
            unvisitedNeighbors.push_back(neighborId);
        }
    }

    std::vector<uint32_t> strictCandidates;
    for (uint32_t neighborId : unvisitedNeighbors) {
        const LinkState &linkState = m_linkStateMap.at(neighborId);
        // 当前是地球站
        if (currentIsGroundStation && linkState.isGsl) {
            strictCandidates.push_back(neighborId);
            continue;
        }
        if (!currentIsGroundStation && targetIsGroundStation) {
            // 当前卫星 且 目标是卫星
            bool directToTargetGround = (neighborId == targetNodeId && linkState.isGsl);
            bool relayBySatellite = (!linkState.neighborIsGroundStation && linkState.isIsl);
            if (directToTargetGround || relayBySatellite) {
                strictCandidates.push_back(neighborId);
            }
            continue;
        }
        // 当前是卫星 且 目标是卫星
        if (!currentIsGroundStation && !targetIsGroundStation && !linkState.neighborIsGroundStation && linkState.isIsl) {
            strictCandidates.push_back(neighborId);
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

    return unvisitedNeighbors;
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

    double throughputReward = transmitSuccess
        ? (linkState.maxCapacityBit - linkState.usedCapacityBit) / std::max(linkState.maxCapacityBit, m_epsilon2)
        : 0.0;
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
    const PacketState &packetState,
    const Ipv4Header &ipHeader
) const {
    if (packetState.hopCount >= m_maxHopCount) {
        return true;
    }
    if (ipHeader.GetTtl() <= 1) {
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
    if (m_node_id == targetNodeId) {
        return std::make_tuple(-1, -1, -1);
    }

    bool isDryRun = isRequestForSourceIpSoNoNextHeader;
    PacketState packetState;
    if (!isDryRun) {
        uint64_t uid = pkt->GetUid();
        auto it = m_packetStateByUid.find(uid);
        // 新包
        if (it == m_packetStateByUid.end()) {
            packetState.srcNodeId = static_cast<uint32_t>(sourceNodeId);
            packetState.dstNodeId = static_cast<uint32_t>(targetNodeId);
            packetState.hopCount = 0;
            packetState.pathHistory = {static_cast<uint32_t>(m_node_id)};
            m_packetStateByUid[uid] = packetState;
        } else {
            packetState = it->second;
            packetState.hopCount++;
            packetState.pathHistory.push_back(static_cast<uint32_t>(m_node_id));
            it->second = packetState;
        }
    } else {
        packetState.srcNodeId = static_cast<uint32_t>(sourceNodeId);
        packetState.dstNodeId = static_cast<uint32_t>(targetNodeId);
        packetState.hopCount = 0;
        packetState.pathHistory = {static_cast<uint32_t>(m_node_id)};
    }

    std::vector<uint32_t> validArms = GetValidArms(static_cast<uint32_t>(targetNodeId), packetState);
    // 无有效臂丢包
    if (validArms.empty()) {
        if (!isDryRun) {
            m_packetStateByUid.erase(pkt->GetUid());
        }
        return std::make_tuple(-1, -1, -1);
    }

    double maxWeight = -std::numeric_limits<double>::infinity();
    uint32_t selectedNeighborId = validArms[0];
    for (uint32_t neighborId : validArms) {
        double weight = CalculateUcbWeight(neighborId, m_totalForwardCount);
        if (weight > maxWeight) {
            maxWeight = weight;
            selectedNeighborId = neighborId;
        }
    }
    // 判断是否丢包
    bool isDrop = IsPacketDrop(selectedNeighborId, packetState, ipHeader);
    if (isDrop) {
        if (!isDryRun) {
            m_packetStateByUid.erase(pkt->GetUid());
        }
        return std::make_tuple(-1, -1, -1);
    }

    LinkState &selectedLink = m_linkStateMap[selectedNeighborId];
    if (!isDryRun) {
        m_totalForwardCount++;
        uint32_t packetSizeByte = pkt->GetSize();
        UpdateLinkState(selectedNeighborId, packetSizeByte);
        double reward = CalculateReward(selectedNeighborId, static_cast<uint32_t>(targetNodeId), validArms, true);
        UpdateUcbState(selectedNeighborId, reward);
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
    for (auto &pair : m_ucbStateMap) {
        oss << " -> Neighbor " << pair.first
            << ": avgReward=" << pair.second.avgReward
            << ", selectCount=" << pair.second.selectCount << std::endl;
    }
    return oss.str();
}

bool ArbiterUcbDistributedRouting::IsGroundStationNode(uint32_t nodeId) const {
    return m_nodes.Get(nodeId)->GetObject<GroundStation>() != 0;
}

} // namespace ns3
