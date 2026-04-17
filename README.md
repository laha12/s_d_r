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
| **时间槽衰减** | 每个时间槽结束时，UCB状态按 `decay_factor` 衰减（默认0.5），使算法快速适应拓扑变化 |
| **随机探索** | 以概率 `random_select_prob` 随机选择邻居，保证探索能力 |
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

## 实验场景

### 场景一：25x25均匀网格星座

| 参数 | 值 |
| :--- | :--- |
| 卫星数量 | 625 (25x25) |
| 拓扑类型 | Plus-Grid ISL |
| 仿真时长 | 点对点: 2s / 流量矩阵: 50s |
| ISL数据率 | 10 Mbps |
| 队列大小 | 100 packets |
| UCB时间槽 | 0.1s |
| 探索概率 | 0.1 |
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
| UCB时间槽 | 1.0s |
| 探索概率 | 0.0 |
| TCP类型 | TcpHybla |
| 动态状态 | 动态（force_static=False） |
| 奖励权重 | [0.2, 0.4, 0.4] |
| 参考时延 | 100 ms |
| 参考距离 | 10,000 km |
| 衰减因子 | 0.5 |

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

## 项目结构

```
s_d_r/
├── README.md                           # 本文档
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
│       │       └── arbiter-ucb-distributed-routing.cc  # UCB路由实现
│       └── scratch/
│           └── main_satnet.cc          # 仿真入口
│
├── paper/                              # 实验脚本
│   ├── satellite_networks_state/       # 星座状态生成脚本
│   ├── ns3_experiments_ucb_25x25/      # 25x25网格UCB实验
│   │   ├── a_2_b/                      # 点对点测试
│   │   │   ├── step_0_generate_topology.py
│   │   │   ├── step_1_generate_runs.py
│   │   │   ├── step_2_run.py
│   │   │   └── step_3_generate_plots.py
│   │   ├── traffic_matrix_poisson/     # 流量矩阵测试
│   │   │   ├── step_0_generate_topology.py
│   │   │   ├── step_1_generate_runs.py
│   │   │   ├── step_2_run.py
│   │   │   └── step_3_generate_plots.py
│   │   └── group_ucb_log_by_uid.py    # UCB日志分组分析
│   ├── ns3_experiments_ucb_iridium_66_6/  # 铱星UCB实验
│   │   ├── a_2_b/
│   │   ├── traffic_matrix_poisson/
│   │   └── group_ucb_log_by_uid.py
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

| 参数 | 说明 | 25x25默认值 | 铱星默认值 |
| :--- | :--- | :--- | :--- |
| `ucb_max_hop_count` | 最大跳数 | 64 | 64 |
| `ucb_slot_duration_s` | UCB时间槽(s) | 0.1 | 1.0 |
| `ucb_reward_weights` | 奖励权重 [w1,w2,w3] | [0.2,0.2,0.2,0.4] | [0.2,0.4,0.4] |
| `ucb_random_select_prob` | 随机探索概率 | 0.1 | 0.0 |
| `ucb_dst_arrival_reward` | 到达目的地奖励 | 1.0 | 1.0 |
| `ucb_reference_delay_ms` | 参考时延(ms) | - | 100.0 |
| `ucb_reference_distance_m` | 参考距离(m) | - | 10,000,000 |
| `ucb_slot_decay_factor` | 时间槽衰减因子 | - | 0.5 |
| `ucb_queue_drop_threshold` | 队列丢包阈值 | - | 200 |

---

## 研究路线

- [x] 搭建Hypatia仿真环境
- [x] 实现UCB分布式路由算法
- [x] 25x25均匀网格星座基础验证
- [x] Iridium铱星星座适配
- [x] 奖励函数设计（时延 + 负载均衡 + 距离）
- [x] 点对点连通性测试
- [x] 泊松流量矩阵测试
- [ ] 与最短路径路由(BFS)的对比实验
- [ ] 不同星座规模的泛化性测试
- [ ] 奖励函数权重敏感性分析
- [ ] 探索-利用策略调优
- [ ] 撰写研究报告

---

## 许可证

- satgenpy / paper / satviz: MIT License
- ns3-sat-sim: GNU GPL v2
