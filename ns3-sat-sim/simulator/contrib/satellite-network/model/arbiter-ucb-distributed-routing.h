#ifndef ARBITER_UCB_DISTRIBUTED_ROUTING_H
#define ARBITER_UCB_DISTRIBUTED_ROUTING_H

#include <map>
#include <set>
#include <tuple>
#include <vector>
#include "ns3/packet.h"
#include "ns3/arbiter-satnet.h"
#include "ns3/ipv4-header.h"
#include "ns3/random-variable-stream.h"
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

    uint64_t instanceId = 0;
    uint32_t srcNodeId = 0;
    uint32_t dstNodeId = 0;
    std::vector<uint32_t> pathHistory;
    double accumulatedDelayMs = 0.0;
    uint32_t hopCount = 0;
};

struct UcbPacketState {
    uint32_t srcNodeId;
    uint32_t dstNodeId;
    uint32_t hopCount;
    std::vector<uint32_t> pathHistory;
    uint64_t creationTimeNs;  // Memory fix: TTL tracking
};

// Path cache for business continuity
struct CachedPath {
    uint32_t nextHopNodeId;
    uint64_t lastUsedSlot;
    double confidence;
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
        double epsilon2,
        double maxGslLengthM,
        double maxIslLengthM,
        double randomSelectProb,
        double dstArrivalReward,
        uint32_t queueDropThreshold,
        double referenceDelayMs,
        double referenceDistanceM,
        double slotDecayFactor,
        uint32_t topK,
        uint32_t packetStateTtlSlots,
        bool pathCacheEnabled,
        double pathCachePreferProb
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
    uint32_t m_totalDropCount;
    uint32_t m_maxHopCount;
    uint32_t m_numSatellites;

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
        bool isAvailable;
        bool neighborIsGroundStation;
    };
    std::map<uint32_t, LinkState> m_linkStateMap;

    struct UcbState {
        double avgReward;
        uint32_t selectCount;
    };
    std::map<uint32_t, UcbState> m_ucbStateMap;

    std::vector<double> m_rewardWeights;
    double m_epsilon1;
    double m_epsilon2;
    double m_max_gsl_length_m;
    double m_max_isl_length_m;
    double m_random_select_prob;
    double m_dst_arrival_reward;
    uint32_t m_queue_drop_threshold;
    double m_reference_delay_ms;
    double m_reference_distance_m;
    double m_slot_decay_factor;
    Ptr<UniformRandomVariable> m_randomVariable;

    // Top-K candidate set
    uint32_t m_topK;

    // Memory fix: TTL for packet state
    uint32_t m_packetStateTtlSlots;
    uint64_t m_packetStateMaxAgeNs;

    // Path cache for business continuity
    bool m_pathCacheEnabled;
    double m_pathCachePreferProb;
    std::map<uint32_t, CachedPath> m_cachedPaths;

    UcbPacketState InitPacketState(int32_t sourceNodeId, int32_t targetNodeId) const;
    void SlotResetHandler();
    void ResetSlotDynamicState();
    void RefreshLinkAvailability();
    void CleanupStalePacketStates();
    std::vector<uint32_t> GetValidArms(uint32_t targetNodeId, const UcbPacketState &packetState) const;
    double CalculateUcbWeight(uint32_t neighborId, uint32_t totalForwardCount);
    double CalculateReward(
        uint32_t neighborId,
        uint32_t targetNodeId,
        const std::vector<uint32_t> &candidateArms,
        bool transmitSuccess
    ) const;
    void UpdateUcbState(uint32_t selectedNeighborId, double reward);
    void UpdateLinkState(uint32_t neighborId, uint32_t packetSizeByte);
    bool TryGetCurrentDistanceM(uint32_t neighborId, double &distanceM) const;
    double CalculateDistanceToDestination(uint32_t neighborId, uint32_t dstNodeId) const;
    bool IsPacketDrop(uint32_t neighborId, const UcbPacketState &packetState, const Ipv4Header &ipHeader) const;
    bool IsSatelliteNode(uint32_t nodeId) const;
    bool IsGroundStationNode(uint32_t nodeId) const;
};

}

#endif
