# UCB卫星路由实验复现报告

**日期**：2026-04-17
**实验人员**：Claude Code (AI辅助)
**项目路径**：`/home/anyflow/projects/s_d_r`
**分支**：AF

---

## 1. 实验环境

| 项目 | 配置 |
| :--- | :--- |
| 操作系统 | Rocky Linux 9.7 (Blue Onyx) |
| Python | 3.13.11 |
| GCC | 11.5.0 |
| ns-3 | 3.31 (debug_minimal, MPI enabled) |
| CPU | 多核 |
| 仿真框架 | Hypatia (ACM IMC 2020) + 自定义UCB路由模块 |

### 环境搭建修复记录

原始项目基于 Python 3.7-3.11 和 Ubuntu 开发，在当前环境需要以下兼容性修复：

1. **waf `imp` 模块**：Python 3.12+ 移除了 `imp` 模块 → 替换为 `types.ModuleType`
2. **waf `pipes` 模块**：Python 3.13 移除了 `pipes` 模块 → 创建 `shlex.quote` shim
3. **basic-sim C++ 编译**：GCC 11 的 `-Werror=range-loop-construct` → 修复 `auto&` 类型推导

---

## 2. 实验场景与结果

### 场景A：25x25均匀网格星座 — 点对点测试

| 参数 | 值 |
| :--- | :--- |
| 拓扑 | 25x25 均匀网格（625颗卫星 + 100个地面站） |
| 测试路径 | 地面站632 → 地面站651 |
| TCP类型 | TcpVegas |
| ISL数据率 | 10 Mbps |
| 仿真时长 | 2s |
| 静态拓扑 | 是 (force_static=True) |
| UCB时间槽 | 0.1s |
| UCB探索概率 | 0.1 |
| 奖励权重 | [0, 0, 0, 1] (仅距离) |

**结果：**

| 指标 | 值 |
| :--- | :--- |
| 仿真状态 | 成功完成 |
| 仿真墙钟时间 | 66.4s |
| TCP流进度 | 9.2% (1380/15000 bytes) |
| 数据包路由统计 | 27个唯一UID，共28条路由记录 |
| 成功到达(ARRIVE) | 9 |
| 丢包(DROP) | 16 |
| 进行中(IN_PROGRESS) | 3 |
| 总转发事件 | 1,384 |

**分析：** 在2秒仿真时间内，UCB路由算法已能够成功传递部分数据包。约32%的数据包成功到达目的地，57%被丢弃（主要因为跳数限制和队列拥塞）。TCP流整体进度9.2%，说明UCB在初始学习阶段还未收敛到最优路径。

---

### 场景B：25x25均匀网格星座 — 泊松流量矩阵

| 参数 | 值 |
| :--- | :--- |
| 拓扑 | 同场景A |
| TCP类型 | TcpVegas |
| 仿真时长 | 50s |
| 流大小 | 10,000 bytes |
| 流量速率 | 0.001 / 0.003 / 0.008 Mbps |

**结果：**

| 流量速率 | 总流数 | 完成流数 | 平均进度 | 总发送量 |
| :--- | :---: | :---: | :---: | :---: |
| 0.001 Mbps | 49 | 2 (4.1%) | 7.7% | 37,940 bytes |
| 0.003 Mbps | 172 | 15 (8.7%) | 11.8% | 202,440 bytes |
| 0.005 Mbps | - | - | SIGSEGV | - |
| 0.008 Mbps | 454 | 56 (12.3%) | 15.1% | 685,580 bytes |

**分析：**

- 随着流量速率增加，完成流的比例和平均进度逐步提高，说明UCB路由在高流量下通过更多的探索样本能更快学习到有效路径。
- 0.005 Mbps 测试遇到 SIGSEGV（段错误），可能是由于UCB全局数据包状态表在debug模式下增长过大导致的内存问题。
- 在50秒仿真时间下，平均进度仍然偏低（7.7%-15.1%），说明UCB路由在25x25这种大规模拓扑（625节点）中需要更长的收敛时间。

---

### 场景C：Iridium铱星星座 — 点对点测试

| 参数 | 值 |
| :--- | :--- |
| 拓扑 | Iridium 789km（66颗卫星 + 10个地面站） |
| 测试路径 | 地面站75→71, 71→75 |
| TCP类型 | TcpNewReno |
| ISL数据率 | 10 Mbps |
| 仿真时长 | 10s |
| 动态拓扑 | 是 (force_static=False) |
| UCB时间槽 | 1.0s |
| UCB探索概率 | 0.0 |
| 奖励权重 | [0.2, 0.2, 0.2, 0.4] |

**结果：**

| 路径 | 仿真状态 | TCP流进度 |
| :--- | :---: | :---: |
| 75 → 71 | 成功完成 | 0.0% |
| 71 → 75 | 成功完成 | 0.0% |

**分析：** 两个方向的TCP流进度均为0%。这可能是因为：

1. **铱星拓扑特殊性**：66颗卫星在6个极轨道上，ISL连接稀疏，UCB路由的搜索空间有限。
2. **动态拓扑影响**：卫星运动导致ISL频繁断连，UCB学到的路由经验快速失效。
3. **探索概率为0**：铱星配置中 `random_select_prob=0.0`，完全依赖UCB权重选择，可能导致早期陷入次优路径无法跳出。
4. **时间槽过长**：1秒的时间槽在789km轨道上可能不够频繁来适应拓扑变化。

---

### 场景D：Iridium铱星星座 — 泊松流量矩阵

| 参数 | 值 |
| :--- | :--- |
| 流量速率 | 0.1 Mbps |
| 流大小 | 500,000 bytes |
| 仿真时长 | 200s |

**结果：** 仿真在52.8%进度（约105.6s仿真时间）时因SIGSEGV崩溃。

**分析：** SIGSEGV极可能与UCB路由模块中全局数据包状态映射（`g_ucb_packet_state_by_uid`）过度膨胀有关。在200秒仿真 + 46条并发TCP流的情况下，大量的TCP重传和重试会导致数据包实例计数持续增长，全局映射表消耗过多内存。

---

## 3. 关键发现

### 3.1 UCB路由收敛性

- **小规模静态拓扑（25x25）**：UCB能在2秒内建立基本路由连通性，但完全收敛需要更长时间。
- **大规模动态拓扑（Iridium）**：UCB在10秒内未能建立有效路由，收敛速度不足。

### 3.2 探索-利用平衡

- 25x25场景使用 `random_select_prob=0.1`，表现出一定的路由学习能力。
- Iridium场景使用 `random_select_prob=0.0`，完全缺乏随机探索，可能导致陷入局部最优。

### 3.3 奖励函数敏感性

- 25x25点对点测试使用 `[0,0,0,1]`（纯距离奖励），能引导数据包向目的地前进。
- Iridium使用 `[0.2,0.2,0.2,0.4]`（混合奖励），但未能产生有效路由。

### 3.4 稳定性问题

- 在长时间仿真中（50s+, 200s），UCB路由模块存在内存管理和稳定性问题，导致SIGSEGV。
- 问题根源可能在于全局数据包状态跟踪机制（`g_ucb_packet_state_by_uid`）缺乏有效的清理策略。

---

## 4. 改进建议

1. **修复内存泄漏**：为 `g_ucb_packet_state_by_uid` 添加超时清理机制，避免长时间运行时内存膨胀。
2. **自适应探索概率**：考虑根据路由成功率动态调整 `random_select_prob`，避免在稀疏拓扑中完全失去探索能力。
3. **增量式UCB**：引入折扣因子或滑动窗口统计，使UCB在动态拓扑中更快遗忘过时的路由经验。
4. **分层路由**：在大规模拓扑中结合全局拓扑信息（如最短路径方向）与UCB局部探索，减少搜索空间。
5. **更短的时间槽**：在动态拓扑中使用更短的UCB时间槽（如0.1s而非1s），以更快适应链路变化。

---

## 5. 实验文件清单

| 文件 | 说明 |
| :--- | :--- |
| `paper/ns3_experiments_ucb_25x25/a_2_b/runs/` | 25x25点对点测试结果 |
| `paper/ns3_experiments_ucb_25x25/traffic_matrix_poisson/runs/` | 25x25流量矩阵结果 |
| `paper/ns3_experiments_ucb_iridium_66_6/a_2_b/runs/` | 铱星点对点测试结果 |
| `paper/ns3_experiments_ucb_iridium_66_6/traffic_matrix_poisson/runs/` | 铱星流量矩阵结果 |
| `paper/satellite_networks_state/gen_data/` | 生成的星座拓扑数据 |

---

## 6. 环境修复补丁

为支持 Python 3.13 和 GCC 11，以下文件被修改：

| 文件 | 修改内容 |
| :--- | :--- |
| `ns3-sat-sim/simulator/.waf3-.../waflib/Context.py` | `import imp` → `import types as _types`，`imp.new_module` → `_types.ModuleType` |
| `ns3-sat-sim/simulator/.waf3-.../waflib/Tools/python.py` | `import imp;print(imp.get_tag())` → `import sysconfig` |
| `~/miniconda3/lib/python3.13/pipes.py` | 新建兼容性 shim（`from shlex import quote`） |
| `ns3-sat-sim/simulator/contrib/basic-sim/model/core/basic-simulation.cc` | `std::pair<std::string, std::string>&` → `auto&` |
