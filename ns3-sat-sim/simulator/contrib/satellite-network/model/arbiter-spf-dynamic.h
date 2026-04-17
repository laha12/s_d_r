#ifndef ARBITER_SPF_DYNAMIC_H
#define ARBITER_SPF_DYNAMIC_H

#include <map>
#include <vector>
#include <tuple>
#include "ns3/packet.h"
#include "ns3/arbiter-satnet.h"
#include "ns3/ipv4-header.h"
#include "ns3/random-variable-stream.h"
#include "ns3/net-device.h"
#include "ns3/channel.h"
#include "ns3/gsl-net-device.h"
#include "ns3/point-to-point-laser-net-device.h"
#include "ns3/mobility-model.h"
#include "ns3/data-rate.h"

namespace ns3 {

class ArbiterSpfDynamic : public ArbiterSatnet {
public:
    static TypeId GetTypeId(void);

    ArbiterSpfDynamic(
        Ptr<Node> this_node,
        NodeContainer nodes,
        double slotDurationS,
        double maxGslLengthM,
        double maxIslLengthM
    );
    ~ArbiterSpfDynamic() override;

    std::tuple<int32_t, int32_t, int32_t> TopologySatelliteNetworkDecide(
        int32_t source_node_id,
        int32_t target_node_id,
        Ptr<const Packet> pkt,
        Ipv4Header const &ipHeader,
        bool isRequestForSourceIpSoNoNextHeader
    ) override;

    std::string StringReprOfForwardingState() override;

private:
    double m_slotDurationS;
    uint32_t m_currentSlot;
    double m_max_gsl_length_m;
    double m_max_isl_length_m;
    uint32_t m_numSatellites;

    struct LinkState {
        uint32_t neighborNodeId;
        uint32_t outInterfaceId;
        uint32_t nextHopInInterfaceId;
        double propagationDelayMs;
        bool isIsl;
        bool isGsl;
        bool isAvailable;
        bool neighborIsGroundStation;
    };
    std::map<uint32_t, LinkState> m_linkStateMap;

    // SPF cache: targetNodeId -> (nextHopNodeId, outIfId, nextIfId)
    bool m_cacheValid;
    std::map<uint32_t, std::tuple<int32_t, int32_t, int32_t>> m_spfCache;

    // Global adjacency: nodeId -> set of neighbor nodeIds (actual device topology)
    std::map<uint32_t, std::set<uint32_t>> m_globalAdjacency;

    void BuildGlobalAdjacency();
    void SlotResetHandler();
    void RefreshLinkAvailability();
    void ComputeAllShortestPaths();
    bool TryGetCurrentDistanceM(uint32_t neighborId, double &distanceM) const;
    double CalculateDistanceBetween(uint32_t nodeA, uint32_t nodeB) const;
    bool IsSatelliteNode(uint32_t nodeId) const;
    bool IsGroundStationNode(uint32_t nodeId) const;
};

}

#endif
