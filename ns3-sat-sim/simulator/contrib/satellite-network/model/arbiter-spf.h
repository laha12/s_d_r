#ifndef ARBITER_SPF_H
#define ARBITER_SPF_H

#include <map>
#include <set>
#include <tuple>
#include <vector>
#include <queue>
#include <limits>
#include "ns3/packet.h"
#include "ns3/arbiter-satnet.h"
#include "ns3/ipv4-header.h"
#include "ns3/simulator.h"

namespace ns3 {

// SPF 路径追踪状态（用于 debug 日志）
struct SpfPacketState {
    uint32_t hopCount = 0;
    std::vector<uint32_t> pathHistory;
};

// 全局包状态映射（按 uid 追踪）
extern std::map<uint64_t, SpfPacketState> g_spf_packet_state_by_uid;

// 辅助函数声明
std::string SpfVectorToString(const std::vector<uint32_t>& vec);
void SpfDebugLog(const std::string& msg);
uint64_t SpfGetOriginalNs3PacketUid(Ptr<const Packet> pkt);

class ArbiterSpf : public ArbiterSatnet {
public:
    static TypeId GetTypeId(void);

    ArbiterSpf(
        Ptr<Node> this_node,
        NodeContainer nodes,
        double max_gsl_length_m,
        double max_isl_length_m,
        double refresh_interval_s = 0.1,
        uint32_t queueDropThreshold = 200
    );
    ~ArbiterSpf() override;

    std::tuple<int32_t, int32_t, int32_t> TopologySatelliteNetworkDecide(
        int32_t source_node_id,
        int32_t target_node_id,
        Ptr<const Packet> pkt,
        Ipv4Header const &ipHeader,
        bool is_request_for_source_ip_so_no_next_header
    ) override;

    std::string StringReprOfForwardingState() override;

private:
    struct LinkState {
        uint32_t neighborNodeId;
        uint32_t outInterfaceId;
        uint32_t nextHopInInterfaceId;
        double transmissionRateBps;
        double maxCapacityBit;
        double propagationDelayMs;
        double distanceM;
        double usedCapacityBit;
        uint32_t queueLength;
        uint64_t queuedBytes;
        bool isIsl;
        bool isGsl;
        bool isAvailable;
        bool neighborIsGroundStation;
    };
    std::map<uint32_t, LinkState> m_linkStateMap;

    struct GlobalLink {
        uint32_t fromNodeId;
        uint32_t toNodeId;
        uint32_t outInterfaceId;
        uint32_t nextHopInInterfaceId;
        double distanceM;
        bool isIsl;
        bool isGsl;
        bool isAvailable;
    };
    std::vector<GlobalLink> m_globalTopology;

    uint32_t m_numSatellites;
    double m_maxGslLengthM;
    double m_maxIslLengthM;
    double m_refreshIntervalS;

    std::vector<std::tuple<int32_t, int32_t, int32_t>> m_nextHopList;

    void InitializeLinkState();
    bool TryGetCurrentDistanceM(uint32_t neighborId, double &distanceM) const;
    void RefreshLinkAvailability();
    void ScheduleRefresh();
    void RefreshHandler();
    bool IsSatelliteNode(uint32_t nodeId) const;
    bool IsGroundStationNode(uint32_t nodeId) const;
    void ComputeShortestPaths();
    void BuildGlobalTopology();
    bool TryGetDistanceBetween(uint32_t nodeA, uint32_t nodeB, double &distanceM) const;
    void ResetSlotDynamicState();
    bool IsPacketDrop(uint32_t nextNodeId, Ipv4Header const &ipHeader) const;
    void UpdateLinkState(uint32_t nextNodeId, uint32_t packetSizeByte);
    uint32_t m_queueDropThreshold;
    uint32_t m_totalForwardCount;
    uint32_t m_totalDropCount;
};

}

#endif
