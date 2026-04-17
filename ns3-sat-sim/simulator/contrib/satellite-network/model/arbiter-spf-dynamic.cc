#include "arbiter-spf-dynamic.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <sstream>
#include <queue>
#include <set>
#include "ns3/data-rate.h"
#include "ns3/channel.h"
#include "ns3/gsl-net-device.h"
#include "ns3/mobility-model.h"
#include "ns3/net-device.h"
#include "ns3/node.h"
#include "ns3/point-to-point-laser-net-device.h"
#include "ns3/simulator.h"

namespace ns3 {

NS_LOG_COMPONENT_DEFINE("ArbiterSpfDynamic");
NS_OBJECT_ENSURE_REGISTERED(ArbiterSpfDynamic);

TypeId ArbiterSpfDynamic::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::ArbiterSpfDynamic")
        .SetParent<ArbiterSatnet>();
    return tid;
}

ArbiterSpfDynamic::ArbiterSpfDynamic(
    Ptr<Node> this_node,
    NodeContainer nodes,
    double slotDurationS,
    double maxGslLengthM,
    double maxIslLengthM
) : ArbiterSatnet(this_node, nodes) {
    m_node_id = this_node->GetId();
    m_slotDurationS = slotDurationS;
    m_max_gsl_length_m = maxGslLengthM;
    m_max_isl_length_m = maxIslLengthM;
    m_currentSlot = 0;
    m_cacheValid = false;
    m_numSatellites = 0;

    // Count satellites
    for (uint32_t nodeId = 0; nodeId < m_nodes.GetN(); nodeId++) {
        Ptr<Node> node = m_nodes.Get(nodeId);
        bool hasIslDevice = false;
        for (uint32_t devId = 0; devId < node->GetNDevices(); devId++) {
            if (DynamicCast<PointToPointLaserNetDevice>(node->GetDevice(devId)) != 0) {
                hasIslDevice = true;
                break;
            }
        }
        if (hasIslDevice) {
            m_numSatellites++;
        }
    }

    // Enumerate neighbor devices (same pattern as UCB)
    uint32_t nDevices = this_node->GetNDevices();
    for (uint32_t i = 0; i < nDevices; i++) {
        Ptr<NetDevice> dev = this_node->GetDevice(i);
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
            Ptr<Node> destinationNode = islDev->GetDestinationNode();
            if (destinationNode == 0) {
                continue;
            }
            uint32_t neighborNodeId = destinationNode->GetId();
            Ptr<NetDevice> peerDev;
            for (uint32_t k = 0; k < destinationNode->GetNDevices(); k++) {
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
            linkState.propagationDelayMs = 0.0;
            linkState.isIsl = true;
            linkState.isGsl = false;
            linkState.isAvailable = true;
            linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
            Ptr<MobilityModel> mobThis = this_node->GetObject<MobilityModel>();
            Ptr<MobilityModel> mobNeighbor = destinationNode->GetObject<MobilityModel>();
            if (mobThis != 0 && mobNeighbor != 0) {
                double distanceM = mobThis->GetDistanceFrom(mobNeighbor);
                linkState.propagationDelayMs = (distanceM / 299792458.0) * 1000.0;
            }
            m_linkStateMap[neighborNodeId] = linkState;
            continue;
        }

        // GSL device
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
            linkState.propagationDelayMs = 0.0;
            linkState.isIsl = false;
            linkState.isGsl = true;
            linkState.isAvailable = true;
            linkState.neighborIsGroundStation = IsGroundStationNode(neighborNodeId);
            Ptr<MobilityModel> mobNeighbor = peerDev->GetNode()->GetObject<MobilityModel>();
            Ptr<MobilityModel> mobThis = this_node->GetObject<MobilityModel>();
            if (mobThis != 0 && mobNeighbor != 0) {
                double distanceM = mobThis->GetDistanceFrom(mobNeighbor);
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

    // Build global adjacency from actual device topology
    BuildGlobalAdjacency();

    // Schedule periodic slot reset
    Simulator::Schedule(Seconds(m_slotDurationS), &ArbiterSpfDynamic::SlotResetHandler, this);
}

ArbiterSpfDynamic::~ArbiterSpfDynamic() {}

void ArbiterSpfDynamic::SlotResetHandler() {
    m_currentSlot++;
    RefreshLinkAvailability();
    m_cacheValid = false;
    Simulator::Schedule(Seconds(m_slotDurationS), &ArbiterSpfDynamic::SlotResetHandler, this);
}

void ArbiterSpfDynamic::RefreshLinkAvailability() {
    Ptr<MobilityModel> mobThis = m_nodes.Get(m_node_id)->GetObject<MobilityModel>();
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

bool ArbiterSpfDynamic::TryGetCurrentDistanceM(uint32_t neighborId, double &distanceM) const {
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

double ArbiterSpfDynamic::CalculateDistanceBetween(uint32_t nodeA, uint32_t nodeB) const {
    Ptr<Node> aNode = m_nodes.Get(nodeA);
    Ptr<Node> bNode = m_nodes.Get(nodeB);
    Ptr<MobilityModel> mobA = aNode->GetObject<MobilityModel>();
    Ptr<MobilityModel> mobB = bNode->GetObject<MobilityModel>();
    if (mobA == 0 || mobB == 0) {
        return std::numeric_limits<double>::infinity();
    }
    return mobA->GetDistanceFrom(mobB);
}

void ArbiterSpfDynamic::BuildGlobalAdjacency() {
    m_globalAdjacency.clear();
    uint32_t totalNodes = m_nodes.GetN();

    for (uint32_t nodeId = 0; nodeId < totalNodes; nodeId++) {
        Ptr<Node> node = m_nodes.Get(nodeId);
        std::set<uint32_t> neighbors;

        for (uint32_t devId = 0; devId < node->GetNDevices(); devId++) {
            Ptr<NetDevice> dev = node->GetDevice(devId);
            Ptr<PointToPointLaserNetDevice> islDev = DynamicCast<PointToPointLaserNetDevice>(dev);
            Ptr<GSLNetDevice> gslDev = DynamicCast<GSLNetDevice>(dev);

            if (islDev) {
                Ptr<Node> destNode = islDev->GetDestinationNode();
                if (destNode != 0) {
                    neighbors.insert(destNode->GetId());
                }
            } else if (gslDev) {
                Ptr<Channel> channel = dev->GetChannel();
                if (channel != 0) {
                    bool nodeIsSat = IsSatelliteNode(nodeId);
                    for (uint32_t j = 0; j < channel->GetNDevices(); j++) {
                        Ptr<NetDevice> peerDev = channel->GetDevice(j);
                        if (peerDev == dev) continue;
                        uint32_t peerNodeId = peerDev->GetNode()->GetId();
                        bool peerIsSat = IsSatelliteNode(peerNodeId);
                        // Only add cross-type edges: sat <-> gs, not sat-sat or gs-gs
                        if (nodeIsSat != peerIsSat) {
                            neighbors.insert(peerNodeId);
                        }
                    }
                }
            }
        }
        m_globalAdjacency[nodeId] = neighbors;
    }
}

void ArbiterSpfDynamic::ComputeAllShortestPaths() {
    m_spfCache.clear();

    uint32_t totalNodes = m_nodes.GetN();

    // Dijkstra from m_node_id using physical distance as edge weight
    // Uses actual device topology (m_globalAdjacency) for connectivity
    std::vector<double> dist(totalNodes, std::numeric_limits<double>::infinity());
    std::vector<uint32_t> prev(totalNodes, std::numeric_limits<uint32_t>::max());
    std::vector<bool> visited(totalNodes, false);

    dist[m_node_id] = 0.0;

    typedef std::pair<double, uint32_t> PQEntry;
    std::priority_queue<PQEntry, std::vector<PQEntry>, std::greater<PQEntry>> pq;
    pq.push(std::make_pair(0.0, m_node_id));

    while (!pq.empty()) {
        PQEntry top = pq.top();
        pq.pop();
        uint32_t u = top.second;
        double d = top.first;

        if (visited[u]) continue;
        visited[u] = true;

        // Get actual neighbors of node u from global adjacency
        auto adjIt = m_globalAdjacency.find(u);
        if (adjIt == m_globalAdjacency.end()) continue;

        for (uint32_t v : adjIt->second) {
            if (visited[v]) continue;

            // Never route through GS-to-GS links (ground stations only talk to satellites)
            bool uIsSat = IsSatelliteNode(u);
            bool vIsSat = IsSatelliteNode(v);
            if (!uIsSat && !vIsSat) continue;

            // Check link availability
            bool linkAvailable = true;
            if (u == static_cast<uint32_t>(m_node_id)) {
                // For source node, use local linkStateMap
                auto linkIt = m_linkStateMap.find(v);
                if (linkIt != m_linkStateMap.end() && !linkIt->second.isAvailable) {
                    linkAvailable = false;
                }
            }
            // For ALL nodes, check GSL distance constraints
            if (linkAvailable && uIsSat != vIsSat) {
                double distanceM = CalculateDistanceBetween(u, v);
                if (distanceM > m_max_gsl_length_m) {
                    linkAvailable = false;
                }
            }

            if (!linkAvailable) continue;

            double edgeWeight = CalculateDistanceBetween(u, v);
            if (edgeWeight == std::numeric_limits<double>::infinity()) continue;

            if (d + edgeWeight < dist[v]) {
                dist[v] = d + edgeWeight;
                prev[v] = u;
                pq.push(std::make_pair(dist[v], v));
            }
        }
    }

    // Reconstruct first-hop for each destination
    for (uint32_t dest = 0; dest < totalNodes; dest++) {
        if (dest == static_cast<uint32_t>(m_node_id) || dist[dest] == std::numeric_limits<double>::infinity()) {
            m_spfCache[dest] = std::make_tuple(-1, -1, -1);
            continue;
        }
        uint32_t current = dest;
        while (prev[current] != static_cast<uint32_t>(m_node_id) && prev[current] != std::numeric_limits<uint32_t>::max()) {
            current = prev[current];
        }
        if (prev[current] == static_cast<uint32_t>(m_node_id)) {
            auto linkIt = m_linkStateMap.find(current);
            if (linkIt != m_linkStateMap.end()) {
                m_spfCache[dest] = std::make_tuple(
                    static_cast<int32_t>(current),
                    static_cast<int32_t>(linkIt->second.outInterfaceId),
                    static_cast<int32_t>(linkIt->second.nextHopInInterfaceId)
                );
            } else {
                m_spfCache[dest] = std::make_tuple(static_cast<int32_t>(current), -1, -1);
            }
        } else {
            m_spfCache[dest] = std::make_tuple(-1, -1, -1);
        }
    }

    m_cacheValid = true;
}

std::tuple<int32_t, int32_t, int32_t> ArbiterSpfDynamic::TopologySatelliteNetworkDecide(
    int32_t source_node_id,
    int32_t target_node_id,
    Ptr<const Packet> pkt,
    Ipv4Header const &ipHeader,
    bool isRequestForSourceIpSoNoNextHeader
) {
    if (static_cast<uint32_t>(m_node_id) == static_cast<uint32_t>(target_node_id)) {
        return std::make_tuple(-1, -1, -1);
    }

    // Compute SPF if cache is invalid
    if (!m_cacheValid) {
        ComputeAllShortestPaths();
    }

    // Look up cached next hop
    auto it = m_spfCache.find(static_cast<uint32_t>(target_node_id));
    if (it != m_spfCache.end()) {
        int32_t nextHop = std::get<0>(it->second);
        if (nextHop >= 0) {
            // Verify the link is still available
            auto linkIt = m_linkStateMap.find(static_cast<uint32_t>(nextHop));
            if (linkIt != m_linkStateMap.end() && linkIt->second.isAvailable) {
                return it->second;
            }
        }
    }

    // Cache miss or link unavailable - recompute
    ComputeAllShortestPaths();
    it = m_spfCache.find(static_cast<uint32_t>(target_node_id));
    if (it != m_spfCache.end()) {
        if (std::get<0>(it->second) >= 0) {
            return it->second;
        }
    }

    return std::make_tuple(-1, -1, -1);
}

std::string ArbiterSpfDynamic::StringReprOfForwardingState() {
    std::ostringstream oss;
    oss << "SPF Dynamic Routing State of node " << m_node_id << std::endl;
    oss << " -> Current slot: " << m_currentSlot << std::endl;
    oss << " -> Cache valid: " << (m_cacheValid ? "yes" : "no") << std::endl;
    oss << " -> Cached destinations: " << m_spfCache.size() << std::endl;
    return oss.str();
}

bool ArbiterSpfDynamic::IsSatelliteNode(uint32_t nodeId) const {
    return nodeId < m_numSatellites;
}

bool ArbiterSpfDynamic::IsGroundStationNode(uint32_t nodeId) const {
    return !IsSatelliteNode(nodeId);
}

} // namespace ns3
