#ifndef ARBITER_UCB_DISTRIBUTED_ROUTING_H
#define ARBITER_UCB_DISTRIBUTED_ROUTING_H

#include <map>
#include <set>
#include <tuple>
#include <vector>
#include "ns3/packet.h"
#include "ns3/arbiter-satnet.h"
#include "ns3/ipv4-header.h"
#include "ns3/tag.h"

namespace ns3 {

class UcbRoutingTag : public Tag
{
public:
    static TypeId GetTypeId(void);
    TypeId GetInstanceTypeId(void) const override;
    uint32_t GetSerializedSize(void) const override;
    void Serialize(TagBuffer i) const override;
    void Deserialize(TagBuffer i) override;
    void Print(std::ostream &os) const override;

    uint32_t srcNodeId;
    uint32_t dstNodeId;
    std::vector<uint32_t> pathHistory;
    double accumulatedDelayMs;
    uint32_t hopCount;
};

class ArbiterUcbDistributedRouting : public ArbiterSatnet {
public:
    static TypeId GetTypeId(void);

    ArbiterUcbDistributedRouting(
        Ptr<Node> this_Node,
        NodeContainer nodes,
        uint32_t maxHopCount,
        double slotDurationS,
        std::vector<double> rewardWeights,
        double epsilon1,
        double epsilon2
    );
    ~ArbiterUcbDistributedRouting() override;

    std::tuple<int32_t, int32_t, int32_t> TopologySatelliteNetworkDecide(
        int32_t sourceNodeId,
        int32_t targetNodeId,
        Ptr<const Packet> pkt,
        Ipv4Header const &ipHeader,
        bool isRequestForSourceIpSoNoNextHeader
    ) override;

    std::string StringReprOfForwardingState() override;

private:
    double m_slotDurationS;
    uint64_t m_slotDurationNs;
    uint32_t m_currentSlot;
    uint64_t m_lastSlotUpdateTimeNs;
    uint32_t m_totalForwardCount;
    uint32_t m_maxHopCount;

    struct LinkState {
        uint32_t neighborNodeId;
        uint32_t outInterfaceId;
        uint32_t nextHopInInterfaceId;
        double transmissionRateBps;
        double maxCapacityBit;
        double propagationDelayMs;
        double usedCapacityBit;
        uint32_t queueLength;
        bool isIsl;
        bool isGsl;
        bool neighborIsGroundStation;
    };
    std::map<uint32_t, LinkState> m_linkStateMap;

    struct UcbState {
        double avgReward;
        uint32_t selectCount;
    };
    std::map<uint32_t, UcbState> m_ucbStateMap;

    struct PacketState {
        uint32_t srcNodeId;
        uint32_t dstNodeId;
        uint32_t hopCount;
        std::vector<uint32_t> pathHistory;
    };
    std::map<uint64_t, PacketState> m_packetStateByUid;

    std::vector<double> m_rewardWeights;
    double m_epsilon1;
    double m_epsilon2;

    void SlotResetHandler();
    void ResetSlotDynamicState();
    std::vector<uint32_t> GetValidArms(uint32_t targetNodeId, const PacketState &packetState) const;
    double CalculateUcbWeight(uint32_t neighborId, uint32_t totalForwardCount);
    double CalculateReward(
        uint32_t neighborId,
        uint32_t targetNodeId,
        const std::vector<uint32_t> &candidateArms,
        bool transmitSuccess
    ) const;
    void UpdateUcbState(uint32_t selectedNeighborId, double reward);
    void UpdateLinkState(uint32_t neighborId, uint32_t packetSizeByte);
    double CalculateDistanceToDestination(uint32_t neighborId, uint32_t dstNodeId) const;
    bool IsPacketDrop(uint32_t neighborId, const PacketState &packetState, const Ipv4Header &ipHeader) const;
    bool IsGroundStationNode(uint32_t nodeId) const;
};

}

#endif
