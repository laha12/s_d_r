# 基于UCB分布式多臂赌博机的LEO卫星网络路由算法研究

## 研究概述

本研究探索将 **Upper Confidence Bound (UCB) 分布式多臂赌博机算法** 应用于低轨(LEO)卫星星座网络的在线路由决策问题。核心思路是将卫星网络中每个节点的下一跳选择建模为一个多臂赌博机(Multi-Armed Bandit, MAB)问题，各节点以完全分布式的方式独立学习最优路由策略，无需全局网络状态信息交换。

### 研究问题

LEO卫星网络具有以下路由挑战：
- **动态拓扑**：卫星高速运动导致星间链路(ISL)和星地链路(GSL)频繁断连与重建
- **分布式约束**：星上计算资源有限，难以运行全局优化算法
- **负载不均衡**：静态路由容易导致链路拥塞热点
- **时延敏感**：端到端时延直接影响QoS

### 核心方法

每个网络节点（卫星/地面站）将邻居节点视为赌博机的"臂"(arm)，在转发数据包时通过UCB公式选择下一跳：

```
weight(neighbor) = avg_reward(neighbor) + sqrt(3 * ln(total_count) / (2 * select_count + ε))
```

算法在每个时间槽内维护每条链路的UCB状态（平均奖励、选择次数），周期性地衰减历史统计量以适应网络拓扑的动态变化。

---

## 研究人员

- 雷宇航

---

## 仿真平台

本研究基于 **Hypatia** (ACM IMC 2020) LEO卫星网络仿真框架进行实验：

> "Exploring the 'Internet from space' with Hypatia"
> Simon Kassing*, Debopam Bhattacherjee*, Andre Baptista Aguas, Jens Eirik Saethre and Ankit Singla

Hypatia提供：
- `satgenpy`：Python卫星网络生成框架（轨道计算、拓扑生成、路由计算）
- `ns3-sat-sim`：基于ns-3的分组级仿真器
- `satviz`：Cesium 3D可视化管线
- `paper`：论文复现实验代码

原文引用：
```bibtex
@inproceedings{hypatia,
    author = {Kassing, Simon and Bhattacherjee, Debopam and Aguas, Andre Baptista and Saethre, Jens Eirik and Singla, Ankit},
    title = {{Exploring the "Internet from space" with Hypatia}},
    booktitle = {{ACM IMC}},
    year = {2020}
}
```

---

## UCB路由算法设计

### 算法架构

UCB路由算法实现为ns-3的自定义仲裁器(Arbiter)，位于 `ns3-sat-sim/simulator/contrib/satellite-network/model/arbiter-ucb-distributed-routing.{h,cc}`。

### 奖励函数

奖励函数由三个分量组成，加权求和：

```
R(neighbor) = w1 * delay_reward + w2 * load_balance_reward + w3 * distance_reward
```

| 分量 | 公式 | 含义 |
| :--- | :--- | :--- |
| **时延奖励** | `exp(-total_delay_ms / reference_delay_ms)` | 惩罚高传播时延+排队时延的链路 |
| **负载均衡奖励** | `1.0 - min(used_capacity / max_capacity, 1.0)` | 避免选择已拥塞的链路 |
| **距离奖励** | `exp(-distance_to_dst / reference_distance_m)` | 偏好距离目的地更近的邻居 |

**特殊奖励：**
- 数据包成功到达目的地：`dst_arrival_reward = 1.0`
- 传输失败（丢包/队列溢出）：`-1.0`

### 关键机制

| 机制 | 说明 |
| :--- | :--- |
| **时间槽衰减** | 每个时间槽结束时，UCB状态（selectCount、avgReward）按 `decay_factor` 衰减，使算法适应拓扑变化 |
| **Top-K候选集** | 按距离筛选UCB可选邻居，限制搜索空间至Top-K个最近邻居（默认K=4） |
| **路径缓存** | 缓存已验证成功的路径，以概率 `path_cache_prefer_prob` 复用，保障TCP业务连续性 |
| **随机探索** | 以概率 `random_select_prob` 随机选择邻居，保证探索能力 |
| **数据包状态TTL** | 全局数据包状态表定时清理（每TTL个slot过期），防止内存无限增长 |
| **跳数限制** | 超过 `max_hop_count`（默认64跳）的数据包被丢弃 |
| **队列丢包** | 队列长度超过阈值时丢弃数据包，防止拥塞扩散 |
| **路径历史追踪** | 每个数据包携带已访问节点列表，避免环路 |

### 拓扑约束

路由决策受以下拓扑规则约束：
- 地面站只能通过GSL连接到卫星
- 卫星之间通过ISL互连（Plus-Grid拓扑）
- 链路距离超过阈值时标记为不可用
- 优先直接发送至目标地面站（如果GSL可用）

---

## 对比基线算法

### SPF动态最短路径

为公平评估UCB性能，实现了基于实际设备拓扑的Dijkstra最短路径基线算法（`arbiter-spf-dynamic`），以物理距离为权重。与UCB的关键区别：SPF拥有全局拓扑视图，UCB仅基于本地邻居信息做分布式决策。

实现过程中修复了三个关键Bug：
1. **距离→设备拓扑**：Dijkstra使用距离判断邻居连通性，在max_isl_length_m很大的场景下形成完全图。修复为从实际设备/通道枚举邻居。
2. **GS-to-GS环路**：GSL共享信道导致地面站间"直接连通"。修复为过滤GS-to-GS边。
3. **GSL卫星互连**：GSL共享介质使卫星间也通过GSL"直接连通"。修复为GSL设备仅添加跨类型邻居（sat↔gs）。

---

## 实验场景

### 场景一：25x25均匀网格星座

| 参数 | 值 |
| :--- | :--- |
| 卫星数量 | 625 (25x25) |
| 拓扑类型 | Plus-Grid ISL |
| 仿真时长 | 点对点: 2s / 流量矩阵: 50s |
| ISL数据率 | 10 Mbps |
| 队列大小 | 100 packets |
| TCP类型 | TcpVegas |
| 动态状态 | 静态（force_static=True） |

### 场景二：Iridium铱星星座（789km, 66卫星6轨道）

| 参数 | 值 |
| :--- | :--- |
| 卫星数量 | 66 (6轨道x11卫星) |
| 轨道高度 | 789 km |
| 拓扑类型 | Plus-Grid ISL |
| 地面站 | Top 10 |
| 仿真时长 | 点对点: 10s / 流量矩阵: 200s |
| ISL数据率 | 10 Mbps |
| 队列大小 | 200 packets |
| TCP类型 | TcpHybla |
| 动态状态 | 动态（force_static=False） |

### 实验类型

#### 点对点测试 (A-to-B)
- 单条TCP流从源地面站到目标地面站
- 测试端到端吞吐量、时延、丢包率
- 用于验证算法基本连通性和收敛行为

#### 泊松流量矩阵测试 (Traffic Matrix Poisson)
- 多条TCP流以泊松过程生成
- 地面站两两配对的对称流量矩阵
- 测试不同流量负载下的网络性能

---

## 实验结果摘要

### 25x25流量矩阵（278条泊松流，0.005 Mbps/流，50秒模拟）

| 配置 | decay | 完成率 | 完成流数 | 仿真墙钟 |
| :--- | :--- | :--- | :--- | :--- |
| **SPF动态基线** | N/A | **100%** | 278/278 | 3112s |
| UCB改进基线 (Top-K+Cache) | 0.5 | 14.7% | 41/278 | 1723s |
| UCB保守调优 (方案A) | 0.98 | 22.7% | 63/278 | 180s |
| UCB激进调优 (方案B) | 0.99 | 24.5% | 68/278 | 179s |

### 关键发现

1. **decay_factor是最关键参数**：从0.5调到0.98后，完成率+57.6%，仿真速度10x加速。decay=0.5导致selectCount每slot减半，3个slot后仅剩12.5%，UCB永远不收敛。
2. **UCB vs SPF仍有4倍差距**（24.5% vs 100%）：UCB完全分布式无全局拓扑信息，50秒学习时间不足。
3. **奖励权重Bug**：配置4个权重但代码只使用前3个，第4个被忽略。详见 `UCB_PARAMETER_TUNING_REPORT.md`。

> 详细参数调优分析和文献依据见 [UCB_PARAMETER_TUNING_REPORT.md](UCB_PARAMETER_TUNING_REPORT.md)
> 完整实验报告见 [EXPERIMENT_REPORT_V2.md](EXPERIMENT_REPORT_V2.md)

---

## 项目结构

```
s_d_r/
├── README.md                           # 本文档
├── EXPERIMENT_REPORT_V2.md             # 实验报告（SPF基线+UCB改进）
├── UCB_PARAMETER_TUNING_REPORT.md      # UCB参数调优研究报告
├── hypatia_install_dependencies.sh     # 依赖安装脚本
├── hypatia_build.sh                    # 构建脚本
├── hypatia_run_tests.sh                # 测试脚本
│
├── satgenpy/                           # 卫星网络生成 (Python)
│   └── satgen/                         # 核心模块
│       ├── tles/                       # TLE轨道数据生成
│       ├── isls/                       # 星间链路拓扑生成
│       ├── ground_stations/            # 地面站配置
│       ├── dynamic_state/              # 动态路由状态生成
│       ├── description/                # 网络描述文件
│       ├── interfaces/                 # 接口配置
│       ├── post_analysis/              # 后分析工具
│       └── plot/                       # 可视化
│
├── ns3-sat-sim/                        # ns-3仿真器
│   └── simulator/
│       ├── contrib/satellite-network/  # 卫星网络ns-3模块
│       │   └── model/
│       │       ├── arbiter-ucb-distributed-routing.h  # UCB路由头文件
│       │       ├── arbiter-ucb-distributed-routing.cc  # UCB路由实现
│       │       ├── arbiter-spf-dynamic.h              # SPF动态基线头文件
│       │       └── arbiter-spf-dynamic.cc              # SPF动态基线实现
│       └── scratch/
│           └── main_satnet.cc          # 仿真入口
│
├── paper/                              # 实验脚本
│   ├── satellite_networks_state/       # 星座状态生成脚本
│   ├── ns3_experiments_spf_25x25/      # 25x25网格SPF基线实验
│   ├── ns3_experiments_spf_iridium_66_6/  # 铱星SPF基线实验
│   ├── ns3_experiments_ucb_25x25/      # 25x25网格UCB基础实验
│   ├── ns3_experiments_ucb_improved_25x25/     # 25x25 UCB改进(Top-K+Cache)实验
│   ├── ns3_experiments_ucb_improved_iridium_66_6/  # 铱星UCB改进实验
│   ├── ns3_experiments_ucb_tuned_25x25/        # 25x25 UCB参数调优实验
│   ├── ns3_experiments_ucb_iridium_66_6/       # 铱星UCB基础实验
│   ├── figures/                        # 绘图脚本
│   └── satviz_plots/                   # 可视化绘图
│
├── satviz/                             # Cesium 3D可视化
└── integration_tests/                  # 集成测试
```

---

## 快速开始

### 环境要求

- Python 3.7+
- Linux (推荐 Ubuntu 18+)
- C++编译器（用于ns-3构建）

### 安装依赖

```bash
# 系统依赖
sudo apt-get install libproj-dev proj-data proj-bin libgeos-dev
sudo apt-get install openmpi-bin openmpi-common openmpi-doc libopenmpi-dev lcov gnuplot

# Python依赖
pip install numpy astropy ephem networkx sgp4 geopy matplotlib statsmodels cartopy
pip install git+https://github.com/snkas/exputilpy.git@v1.6
pip install git+https://github.com/snkas/networkload.git@v1.3

# 或使用一键脚本
bash hypatia_install_dependencies.sh
```

### 构建

```bash
bash hypatia_build.sh
```

### 运行实验

```bash
# 25x25网格 - 点对点测试
cd paper/ns3_experiments_ucb_25x25/a_2_b
python step_0_generate_topology.py
python step_1_generate_runs.py
python step_2_run.py
python step_3_generate_plots.py

# 25x25网格 - 流量矩阵测试
cd paper/ns3_experiments_ucb_25x25/traffic_matrix_poisson
python step_0_generate_topology.py
python step_1_generate_runs.py
python step_2_run.py
python step_3_generate_plots.py

# 铱星 - 流量矩阵测试
cd paper/ns3_experiments_ucb_iridium_66_6/traffic_matrix_poisson
python step_0_generate_topology.py
python step_1_generate_runs.py
python step_2_run.py
python step_3_generate_plots.py
```

---

## UCB算法参数配置

| 参数 | 说明 | 代码默认值 |
| :--- | :--- | :--- |
| `ucb_max_hop_count` | 最大跳数 | 30 |
| `ucb_slot_duration_s` | UCB时间槽(s) | 1.0 |
| `ucb_reward_weights` | 奖励权重 [w1,w2,w3]（时延,负载均衡,距离） | [0.333,0.333,0.334] |
| `ucb_epsilon1` / `ucb_epsilon2` | UCB探索参数 | 1e-9 |
| `ucb_random_select_prob` | 随机探索概率 | 0.1 |
| `ucb_dst_arrival_reward` | 到达目的地奖励 | 2.0 |
| `ucb_reference_delay_ms` | 参考时延(ms) | 100.0 |
| `ucb_reference_distance_m` | 参考距离(m) | 10,000,000 |
| `ucb_slot_decay_factor` | 时间槽衰减因子 | 0.5 |
| `ucb_top_k` | Top-K候选集大小（0=不过滤） | 4 |
| `ucb_packet_state_ttl_slots` | 数据包状态TTL(slot数) | 10 |
| `ucb_path_cache_enabled` | 是否启用路径缓存 | true |
| `ucb_path_cache_prefer_prob` | 路径缓存复用概率 | 0.7 |
| `ucb_queue_drop_threshold` | 队列丢包阈值 | 100 |

> **调优建议**：`ucb_slot_decay_factor` 是影响性能最关键的参数。代码默认值0.5导致UCB永远不收敛，建议设为0.95-0.99。详见 [UCB_PARAMETER_TUNING_REPORT.md](UCB_PARAMETER_TUNING_REPORT.md)。

## SPF基线算法参数配置

| 参数 | 说明 | 代码默认值 |
| :--- | :--- | :--- |
| `satellite_network_routing` | 路由模式 | 设为 `spf_dynamic` 启用 |
| `ucb_slot_duration_s` | 时槽长度（SPF复用此参数做缓存刷新） | 1.0 |

---

## 研究路线

- [x] 搭建Hypatia仿真环境
- [x] 实现UCB分布式路由算法
- [x] 25x25均匀网格星座基础验证
- [x] Iridium铱星星座适配
- [x] 奖励函数设计（时延 + 负载均衡 + 距离）
- [x] 点对点连通性测试
- [x] 泊松流量矩阵测试
- [x] 实现SPF动态基线算法（含设备拓扑/GSL环路修复）
- [x] UCB内存崩溃修复（TTL清理 + 计数器uint64扩容）
- [x] Top-K候选集 + 路径缓存改进
- [x] 与最短路径路由(SPF)的对比实验
- [x] UCB参数调优研究（文献调研 + 实验验证）
- [ ] Iridium铱星场景SIGSEGV修复
- [ ] 不同星座规模的泛化性测试
- [ ] 奖励函数权重敏感性分析
- [ ] 探索-利用策略调优（更长仿真时间验证收敛）
- [ ] 撰写研究报告

---

## 许可证

- satgenpy / paper / satviz: MIT License
- ns3-sat-sim: GNU GPL v2
