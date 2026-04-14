# Chaos OOP Design Project

混沌工程工具包 - 面向对象重构版本

## 项目结构

```
/home/gsta/chaos_oop_design/
├── chaos/                    # 主包
│   ├── __init__.py
│   ├── main.py               # 命令行入口
│   ├── config.py             # 配置管理
│   ├── constants.py          # 常量定义
│   ├── exceptions.py         # 异常定义
│   ├── handlers.py           # 命令处理器
│   ├── clear/                # 清除功能
│   ├── case/                 # Case 管理
│   │   └── base.py          # Case 配置和执行
│   ├── fault/               # 故障注入
│   │   └── base.py         # 故障注入器
│   ├── state/              # 状态管理
│   │   └── manager.py     # 状态管理器
│   ├── scheduler/         # 调度器
│   ├── workflow/          # 工作流编排
│   │   ├── definition.py  # 数据结构定义
│   │   ├── parser.py      # YAML 解析器
│   │   ├── executor.py    # 执行器
│   │   └── monitor.py     # 监控器
│   └── utils/            # 工具类
│       ├── permission.py  # 权限管理
│       ├── remote.py      # 远程执行（含 SSH 连接池）
│       ├── logger.py      # 日志管理
│       ├── log_collector.py # 日志收集
│       └── version.py     # 版本管理
├── config.yaml            # 配置文件
├── cases/                 # Case YAML 文件
│   ├── network_delay.yaml
│   ├── pod_failure.yaml
│   └── ddb_master_failure.yaml
├── workflows/             # 工作流配置文件
│   ├── serial_example.yaml
│   ├── parallel_example.yaml
│   └── hybrid_example.yaml
├── scripts/              # 脚本目录
│   └── version_iterate.sh
├── backups/             # 备份目录
├── data/               # 数据目录
├── VERSION            # 版本文件
└── README.md         # 项目说明
```

## 快速开始

### 1. 查看版本

```bash
cd /home/gsta/chaos_oop_design
python3 chaos/main.py version --action show
```

### 2. 迭代版本

```bash
cd /home/gsta/chaos_oop_design
./scripts/version_iterate.sh
```

### 3. 执行 Case

```bash
# 执行单个 Case
python3 chaos/main.py case --name cases/network_delay.yaml

# 批量执行目录下的所有 Case
python3 chaos/main.py case --dir cases/
```

### 4. 查看故障状态

```bash
# 列出所有活跃故障
python3 chaos/main.py state --action list

# 清除所有故障
python3 chaos/main.py state --action clear
```

## YAML 配置参数说明

### 1. config.yaml - 环境配置文件

#### 环境配置 (environments)

```yaml
environments:
  <环境名称>:
    type: "ssh"              # 连接类型，目前仅支持 ssh
    ip: "10.230.246.167"     # 远程主机 IP
    port: 50163              # SSH 端口
    user: "root"             # SSH 用户名
    passwd: "Gsta@123"       # SSH 密码
    nodename: "dupf01"       # 节点名称（可选）
```

**示例：**
```yaml
environments:
  1_ssh_remote:
    type: "ssh"
    ip: "10.230.246.167"
    port: 50163
    user: "root"
    passwd: "Gsta@123"
    nodename: "dupf01"
```

#### 交换机环境配置 (sw_environments)

```yaml
sw_environments:
  <交换机名称>:
    type: "ssh"              # 连接类型
    ip: "10.230.246.153"     # 交换机 IP
    port: 50163              # SSH 端口
    user: "admin"            # SSH 用户名
    passwd: "Gsta.123yjy"    # SSH 密码
    nodename: "tor1"         # 交换机名称（可选）
```

#### 默认配置 (defaults)

```yaml
defaults:
  namespace: "ns-dupf"       # 默认命名空间
  wait_seconds: 30            # 默认等待时间（秒）
  cleanup: true               # 是否自动清理故障
```

**namespace 优先级规则**：
1. YAML 用例中指定的 namespace（最高优先级）
2. config.yaml 中 defaults.namespace 配置
3. 代码中的默认值 `ns-dupf`（最低优先级）

#### UPU Pod 过滤列表

```yaml
UPU_POD_FILTERS:              # UPU 主节点 Pod 列表
  - "dupf-upu-dupf01-1"
  - "dupf-upu-dupf01-2"

UPU_POD_FILTERS_SLAVE:        # UPU 备节点 Pod 列表
  - "dupf-upu-dupf02-4"
  - "dupf-upu-dupf03-8"
```

### 2. Case YAML - 测试用例配置文件

#### 基本参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 用例名称，唯一标识 |
| `description` | string | 否 | 用例描述 |
| `type` | string | 是 | 故障类型：`pod` 或 `network` |
| `environment` | string | 是 | 执行环境，对应 config.yaml 中的环境名称 |
| `fault_type` | string | 是 | 具体故障类型（见下文） |
| `duration` | string | 是 | 故障持续时间，如 `60s`、`5m`、`1h` |
| `loop_count` | integer | 是 | 循环执行次数 |
| `namespace` | string | 否 | 默认命名空间 |

#### Pod 匹配规则 (pod_match)

##### 普通 Pod 匹配

```yaml
pod_match:
  name: "dupf-upu-dupf01-1"   # Pod 名称（支持通配符、前缀匹配和数组形式）
  namespace: "ns-dupf"        # 命名空间
  labels:                     # 标签选择器（可选）
    app: dupf
    component: upu
  random: true                # 是否随机选择（可选，默认 true）
  count: 1                    # 选择数量（可选，默认 1）
```

**名称匹配规则：**
- **精确匹配**：`dupf-upu-dupf01-1` 匹配完全相同的名称
- **通配符匹配**：`dupf-upu-*` 匹配所有以 `dupf-upu-` 开头的 Pod
- **前缀匹配**：`dupf-upu-dupf01-1` 自动匹配 `dupf-upu-dupf01-1-688fc66ddb-bpd5h`（处理 Deployment 后缀）
- **包含匹配**：如果名称包含在 Pod 名称中，也会匹配成功
- **数组形式**：支持多个名称模式，如 `name: ["dupf-upu-dupf01-1", "dupf-upu-dupf01-2"]`
- **UPC 特殊过滤规则**：支持 UPC Pod 的特殊过滤
  - `upc-talker`：只获取 UPC talker Pod（排除 upc-lb）
  - `upc-nontalker`：只获取 UPC 非talker Pod（即 upc-lb）
  - `upc-all`：获取所有 UPC Pod（包括 upc-lb）
  - 示例：`name: ["upc-talker"]` 或 `name: "upc-talker"`
- **etcd 特殊过滤规则**：支持 etcd Pod 的特殊过滤
  - `etcd-leader`：只获取 etcd Leader Pod
  - `etcd-follower`：只获取 etcd Follower Pod
  - `etcd-all`：获取所有 etcd Pod
  - 示例：`name: ["etcd-leader"]` 或 `name: "etcd-leader"`
- **DDB 特殊过滤规则**：支持 DDB Pod 的特殊过滤
  - `ddb-master`：只获取 DDB Master Pod
  - `ddb-slave`：只获取 DDB Slave Pod
  - `ddb-all`：获取所有 DDB Pod
  - 示例：`name: ["ddb-master"]` 或 `name: "ddb-master"`
- **SDB 特殊过滤规则**：支持 SDB Pod 的特殊过滤
  - `sdb-master`：只获取 SDB Master Pod
  - `sdb-slave`：只获取 SDB Slave Pod
  - `sdb-all`：获取所有 SDB Pod
  - 示例：`name: ["sdb-master"]` 或 `name: "sdb-master"`
- **RC 特殊过滤规则**：支持 RC（Registry Center）Pod 的特殊过滤
  - `rc-leader`：只获取 RC Leader Pod
  - `rc-nonleader`：只获取 RC Non-Leader Pod
  - `rc-all`：获取所有 RC Pod
  - 示例：`name: ["rc-leader"]` 或 `name: "rc-leader"`
  - 注意：RC 指 Registry Center（注册中心），Pod 名称格式为 `dupf-registry-center-*`
- **UPU 特殊过滤规则**：支持 UPU Pod 的特殊过滤
  - `upu-master`：只获取 UPU Master Pod（根据 `config.yaml` 中的 `UPU_POD_FILTERS` 过滤）
  - `upu-slave`：只获取 UPU Slave Pod（根据 `config.yaml` 中的 `UPU_POD_FILTERS_SLAVE` 过滤）
  - `upu-all`：获取所有 UPU Pod
  - 示例：`name: ["upu-master"]` 或 `name: "upu-master"`

**选择参数：**
- **random**：是否随机选择 Pod（默认 true）
- **count**：选择 Pod 的数量（默认 1）
  - 如果 count = 1，默认随机选择一个 Pod
  - 如果 count > 1，随机选择指定数量的 Pod
  - 如果 count >= 匹配的 Pod 数量，选择所有匹配的 Pod
- **interval**：不同匹配规则之间的时间间隔（秒，默认 0）
  - 如果 interval = 0，所有匹配规则同时开始故障
  - 如果 interval > 0，按顺序执行故障，每个故障之间等待指定的时间间隔

##### 特殊 Pod 匹配

```yaml
pod_match:
  type: "special"             # 指定为特殊 Pod
  special_type: "ddb"         # 特殊 Pod 类型
  role: "master"              # 角色
  namespace: "ns-dupf"        # 命名空间
```

**支持的 special_type 和 role：**

| special_type | role | 说明 |
|--------------|------|------|
| `ddb` | `master` | DDB 主节点 |
| `ddb` | `slave` | DDB 从节点 |
| `sdb` | `master` | SDB 主节点 |
| `sdb` | `slave` | SDB 从节点 |
| `etcd` | `leader` | etcd Leader 节点 |
| `etcd` | `follower` | etcd Follower 节点 |
| `upc` | `talker` | UPC Talker Pod |

#### Pod 故障参数 (type: pod)

```yaml
type: pod
fault_type: delete            # 故障类型：delete、restart 或 stop
parameters:
  action: delete              # 动作：delete（删除）、restart（重启）或 stop（停止容器）
  grace_period: 30            # 优雅终止时间（秒），0 表示立即强制删除
```

**fault_type 可选值：**
- `delete`: 删除 Pod
- `restart`: 重启 Pod
- `stop`: 停止 Pod 容器（不删除 Pod）

**parameters 参数：**
- `action`: 故障动作
  - `delete`: 删除 Pod
  - `restart`: 重启 Pod
  - `stop`: 停止容器
- `grace_period`: 优雅终止时间（秒）
  - `> 0`: 等待指定时间让 Pod 优雅关闭
  - `= 0`: 立即强制删除 Pod
  - 注意：仅适用于 `delete` 操作

**stop 操作说明：**
- 停止 Pod 内容器的运行，但不删除 Pod 对象
- 通过 `docker stop` 命令停止容器
- 系统会自动查找 Pod 所在的节点，并连接到对应节点执行停止操作
- 在 duration 时间结束后，会自动执行 `docker start` 恢复容器
- 适用于模拟容器崩溃、进程停止等场景

#### 网络故障参数 (type: network)

**节点感知执行**：
- 系统会自动识别 Pod 所在的节点，并在正确的节点上执行网络故障注入
- 通过 `kubectl get pod -o wide` 获取 Pod 所在的节点名称
- 根据节点名称从 `config.yaml` 中找到对应的 SSH 连接信息
- 在正确的节点上执行 `docker ps`、`docker inspect`、`nsenter` 和 `tc` 命令
- 确保故障注入命令在 Pod 实际运行的节点上执行，避免"找不到容器"的错误

```yaml
type: network
fault_type: delay             # 故障类型：delay、loss、corrupt、duplicate 或 reorder
parameters:
  delay: "1000ms"             # 延迟时间
  device: "eth0"              # 网络设备名称
  direction: "both"           # 方向：both、in、out
  jitter: "100ms"             # 抖动（可选）
  loss: "0%"                  # 丢包率（可选）
```

**fault_type 可选值：**
- `delay`: 网络延迟
- `loss`: 网络丢包
- `corrupt`: 网络数据包破坏
- `duplicate`: 网络数据包重复
- `reorder`: 网络数据包重排序

**parameters 参数：**
- `device`: 网络设备名称，默认从 `config.yaml` 获取或 `eth0`
- `delay`: 延迟时间，如 `100ms`、`1s`（仅 delay 类型）
- `loss`: 丢包率，如 `10%`、`5%`（仅 loss 类型）
- `percent`: 破坏/重复/重排序比例，如 `1%`、`5%`（corrupt、duplicate、reorder 类型）
- `correlation`: 相关性，如 `25%`（可选）
- `jitter`: 延迟抖动（可选，仅 delay 类型）
- `direction`: 延迟方向（可选）
  - `both`: 双向延迟
  - `in`: 入站延迟
  - `out`: 出站延迟

#### 物理机故障参数 (type: computer)

```yaml
type: computer
fault_type: reboot            # 故障类型：reboot
computer_match:
  name:                       # 环境名称列表（对应 config.yaml 中的环境）
    - 1_ssh_remote
    - 2_ssh_remote
```

**fault_type 可选值：**
- `reboot`: 重启物理服务器

**computer_match 参数：**
- `name`: 环境名称列表，对应 `config.yaml` 中定义的环境名称
  - 支持单个环境：`name: 1_ssh_remote`
  - 支持多个环境：`name: [1_ssh_remote, 2_ssh_remote]`

**注意事项：**
- 重启操作会立即执行，服务器将不可用
- 重启完成后服务器会自动恢复
- 建议在测试环境中谨慎使用
- 支持同时重启多台物理服务器

#### 进程故障参数 (type: process)

```yaml
type: process
fault_type: kill            # 故障类型：kill
pod_match:
  name:                     # Pod 名称列表
    - upc-talker
    - ddb-master
  namespace: ns-dupf        # 命名空间
  random: true              # 是否随机选择
  count: 1                  # 选择数量
parameters:
  signal: 15                # 信号值（默认 15）或 "random"
  main_process_pid: 1       # 目标进程 PID（默认 1）
```

**fault_type 可选值：**
- `kill`: Kill 指定 Pod 中的进程

**parameters 参数：**
- `signal`: 信号值
  - 整数值：指定信号（支持 1, 9, 11, 15, 18, 19）
  - `"random"`：从支持的信号列表中随机选择一个
  - 默认值：15 (SIGTERM)
- `main_process_pid`: 目标进程 PID
  - 默认值：1（主进程）
  - 支持指定其他 PID

**常用信号说明：**
| 信号值 | 名称 | 说明 |
|--------|------|------|
| 1 | SIGHUP | 挂起信号 |
| 9 | SIGKILL | 强制终止 |
| 11 | SIGSEGV | 段错误 |
| 15 | SIGTERM | 正常终止（默认）|
| 18 | SIGCONT | 继续执行 |
| 19 | SIGSTOP | 暂停执行 |

**恢复方式：**
- 进程被 kill 后，由进程守护自动拉起恢复
- 无需手动恢复操作

#### 交换机故障参数 (type: sw)

```yaml
type: sw
fault_type: command           # 故障类型：command
environment: sw_ssh_remote1   # 交换机环境名称（对应 config.yaml 中的 sw_environments）
sw_match:
  commands:                   # 要执行的命令列表
    - cmd: screen-length disable
      wait: 2                 # 此命令执行后等待 2 秒
    - cmd: display bgp peer ipv4 vpn-instance-all  # 使用默认等待时间
    - cmd: display interface brief
  loop_count: 2               # 循环执行次数（默认 1）
```

**fault_type 可选值：**
- `command`: 在交换机上执行指定命令

**sw_match 参数：**
- `commands`: 要执行的命令列表
  - **字符串形式**：直接指定命令，使用默认等待时间（1.0 秒）
    ```yaml
    commands:
      - display version
      - display interface brief
    ```
  - **字典形式**：指定命令和自定义等待时间
    ```yaml
    commands:
      - cmd: display bgp peer ipv4 vpn-instance-all
        wait: 3  # 此命令执行后等待 3 秒
      - cmd: display interface brief  # 使用默认等待时间
    ```
  - **混合使用**：可以在同一个命令列表中混合使用两种形式
  - 命令按顺序依次执行
- `loop_count`: 循环执行次数
  - 默认值：1
  - 所有命令执行完成后，按指定次数重复执行

**wait 说明：**
- 默认值：1.0 秒（定义在 `constants.py` 中的 `SW_CMD_WAIT`）
- 每条命令发送后等待的时间，用于确保命令执行完成
- 对于输出较长的命令，可适当增大此值
- 可在每个命令中单独指定，未指定则使用默认值

**向后兼容：**
- `commands` 与 `command` 字段均支持
- `cmd` 与 `command` 字段均支持
- `wait` 与 `sw_command_wait` 字段均支持

**使用场景：**
- 批量执行交换机巡检命令
- 收集交换机状态信息
- 执行交换机配置变更命令

**注意事项：**
- 确保交换机 SSH 连接信息在 `config.yaml` 的 `sw_environments` 中正确配置
- 命令执行超时时间为 300 秒
- 所有命令执行完成后自动恢复（无需手动操作）

### 3. 完整示例

#### Pod 故障用例示例

```yaml
# Pod 故障 Case 示例
name: pod_failure
description: Pod failure fault test
type: pod
environment: 1_ssh_remote
fault_type: delete
pod_match:
  name: dupf-upu-dupf01-1
  namespace: ns-dupf
  labels:
    app: dupf
    component: upu
duration: 60s
loop_count: 2
parameters:
  action: delete
  grace_period: 30
namespace: ns-dupf
auto_clear: false  # 在 duration 结束后不执行 clear 操作
```

#### 多 Pod 故障用例示例

```yaml
# 多 Pod 故障 Case 示例
name: multi_pod_failure
description: Multiple pod failure fault test
type: pod
environment: 1_ssh_remote
fault_type: delete
pod_match:
  name:
    - dupf-upu-dupf01-1
    - dupf-upu-dupf01-2
  namespace: ns-dupf
  labels:
    app: dupf
    component: upu
  random: true  # 随机选择
  count: 1      # 每个名称模式选择 1 个 Pod
duration: 30s
loop_count: 1
parameters:
  action: delete
  grace_period: 30
namespace: ns-dupf
```

#### 多 Pod 随机选择示例

```yaml
# 多 Pod 随机选择示例
name: multi_pod_random_select
description: Multiple pod random selection test
type: pod
environment: 1_ssh_remote
fault_type: delete
pod_match:
  name: dupf-upu-dupf01-*
  namespace: ns-dupf
  labels:
    app: dupf
    component: upu
  random: true  # 随机选择
  count: 2      # 选择 2 个 Pod
duration: 30s
loop_count: 1
parameters:
  action: delete
  grace_period: 30
namespace: ns-dupf
```

#### DDB Master 故障用例示例

```yaml
# 特殊 Pod 故障 Case 示例（DDB Master）
name: ddb_master_failure
description: DDB master pod failure test
type: pod
environment: 1_ssh_remote
fault_type: delete
pod_match:
  type: special
  special_type: ddb
  role: master
  namespace: ns-dupf
duration: 60s
loop_count: 1
parameters:
  action: delete
  grace_period: 30
```

#### 网络延迟用例示例

```yaml
# 网络延迟 Case 示例
name: network_delay
description: Network delay fault test
type: network
environment: 1_ssh_remote
fault_type: delay
pod_match:
  name: dupf-upu-dupf01-1
  namespace: ns-dupf
  labels:
    app: dupf
    component: upu
duration: 60s
loop_count: 3
parameters:
  delay: 1000ms
  device: eth0
  direction: both
  jitter: 100ms
  loss: 0%
namespace: ns-dupf
```

#### 网络延迟用例示例（带 auto_clear）

```yaml
# 网络延迟 Case 示例（带 auto_clear）
name: network_delay_with_clear
description: Network delay fault test with auto clear
type: network
environment: 1_ssh_remote
fault_type: delay
pod_match:
  name: dupf-upu-dupf01-1
  namespace: ns-dupf
  labels:
    app: dupf
    component: upu
duration: 60s
loop_count: 1
parameters:
  delay: 1000ms
  device: eth0
  direction: both
  jitter: 100ms
  loss: 0%
namespace: ns-dupf
auto_clear: true  # 在 duration 结束后自动清除网络故障
```

#### 物理机重启用例示例

```yaml
# 物理机重启 Case 示例
name: computer_reboot
description: Reboot physical server nodes
type: computer
fault_type: reboot
computer_match:
  name:
    - 1_ssh_remote
    - 2_ssh_remote
duration: 0
loop_count: 1
auto_clear: false
```

### 4. 配置优先级

配置加载遵循以下优先级（从高到低）：

1. **Case YAML 配置**：用例文件中指定的参数
2. **环境配置**：config.yaml 中的 environments 配置
3. **默认配置**：config.yaml 中的 defaults 配置

**示例：**
- 如果 Case YAML 中指定了 `namespace: ns-test`，则使用 `ns-test`
- 如果未指定，则使用 config.yaml 中 defaults 的 `namespace: chaos-testing`

## 命令行参数说明

### 1. case 子命令 - 执行测试用例

```bash
python3 chaos/main.py case [选项]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--name` | string | 否* | Case 名称或 YAML 文件路径 |
| `--dir` | string | 否* | Case 目录路径（批量执行） |
| `--env` | string | 否 | 执行环境，默认 `all` |
| `--namespace` | string | 否 | 命名空间 |
| `--cleanup` | flag | 否 | 执行后清理故障 |
| `--timeout` | integer | 否 | 执行超时时间（秒），默认 `300` |

**注意**：`--name` 和 `--dir` 必须指定其中一个

**示例：**
```bash
# 执行单个 Case
python3 chaos/main.py case --name cases/pod_failure.yaml

# 批量执行目录下的所有 Case
python3 chaos/main.py case --dir cases/ --timeout 600

# 指定环境和命名空间
python3 chaos/main.py case --name cases/network_delay.yaml --env 1_ssh_remote --namespace ns-test
```

### 2. clear 子命令 - 清除故障

```bash
python3 chaos/main.py clear [选项]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--env` | string | 否 | 清除环境，默认 `all` |
| `--type` | string | 否 | 故障类型：`all`、`network`、`pod`，默认 `all` |
| `--device` | string | 否 | 网络设备名称，默认 `eth0` |
| `--namespace` | string | 否 | Kubernetes 命名空间，默认 `ns-dupf` |

**说明：**
- `--device`：指定要清除网络故障的网络设备名称（如 `eth0`、`eth1`）
- `--namespace`：指定要清除网络故障的 Kubernetes 命名空间
- 网络故障清除采用 OOP 设计，通过 `NetworkFaultClearer` 类实现
- 支持逐个 Pod 清除网络故障，使用 `nsenter` 进入容器网络命名空间执行 `tc` 命令
- **节点过滤**：根据环境配置中的 `nodename` 字段自动过滤 Pod，只清除指定节点上的 Pod 故障
  - 例如：`1_ssh_remote` 环境配置的 `nodename` 为 `dupf01`，则只清除 `dupf01` 节点上的 Pod 网络故障
  - 例如：`2_ssh_remote` 环境配置的 `nodename` 为 `dupf02`，则只清除 `dupf02` 节点上的 Pod 网络故障

**示例：**
```bash
# 清除所有环境的所有故障
python3 chaos/main.py clear

# 清除指定环境的网络故障
python3 chaos/main.py clear --env 1_ssh_remote --type network

# 清除指定网络设备的故障
python3 chaos/main.py clear --device eth1

# 清除指定命名空间的网络故障
python3 chaos/main.py clear --namespace ns-test

# 清除指定环境、指定网络设备、指定命名空间的网络故障
python3 chaos/main.py clear --env 1_ssh_remote --type network --device eth0 --namespace ns-dupf
```

### 3. pod 子命令 - Pod 管理

```bash
python3 chaos/main.py pod --action <动作> [选项]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--action` | string | 是 | Pod 操作动作（见下表） |
| `--namespace` | string | 否 | 命名空间，默认 `all` |
| `--env` | string | 否 | 环境，默认 `all` |

**action 可选值：**

| 动作 | 说明 |
|------|------|
| `list` | 列出所有 Pod |
| `ddb` | 获取 DDB 主备 Pod（支持多个主节点） |
| `sdb` | 获取 SDB 主备 Pod |
| `etcd` | 获取 etcd 主从 Pod |
| `upc` | 获取 UPC talker Pod（已过滤 upc-lb） |
| `upu` | 获取 UPU Pod |
| `rc` | 获取 RC（Replication Controller）主从 Pod |

**说明：**
- **容错机制**：
  - 当 `--env` 参数为 `all`（默认）时，系统会按顺序尝试从各个环境获取 Pod 信息
  - 默认从 `1_ssh_remote` 环境获取，如果失败则尝试 `2_ssh_remote`，以此类推
  - 一旦成功获取到 Pod 信息，立即返回结果，不再尝试其他环境
  - 如果所有环境都尝试失败，则报告错误
  - 这种机制适用于所有 pod 操作（list、ddb、sdb、etcd、upc、upu）
  - 可以提高获取 Pod 信息的成功率，避免因单个环境故障导致整个操作失败
  - 当 `--env` 参数指定了具体环境时，直接从该环境获取 Pod 信息，不进行容错重试
- **upc 操作的特殊处理**：
  - 在获取 UPC Pod 时，系统会自动过滤掉 `upc-lb` Pod
  - `upc-lb` 是负载均衡器 Pod，通常不需要在故障测试中操作
  - 过滤后只返回实际的 UPC 应用 Pod（如 `dupf-upc-56bf54fb76-*`）
  - 这样可以避免误操作负载均衡器 Pod，提高测试的准确性和安全性
- **etcd 操作的特殊处理**：
  - 在获取 etcd Leader 和 Follower 时，系统通过 registry-center 服务获取角色信息
  - 使用命令：`kubectl get svc -A | grep registry-center | grep -v headless` 获取 registry-center IP
  - 使用 curl 命令调用 registry-center API 获取 etcd 集群健康状态
  - Leader 端点：`curl -X GET http://{ip}:8158/api/paas/v1/maintenance/db/health | jq '.Endpoints[] | select(.Leader == 1) | .Endpoint'`
  - Follower 端点：`curl -X GET http://{ip}:8158/api/paas/v1/maintenance/db/health | jq '.Endpoints[] | select(.Leader == 0) | .Endpoint'`
  - 这种方法比直接执行 etcdctl 命令更可靠，避免了权限和网络问题
- **DDB 操作的特殊处理**：
  - 在获取 DDB 主从信息时，系统通过 DDB Service API 获取角色信息
  - 使用命令：`kubectl get svc -n {namespace} | grep dupf-db-operator-svc | grep -v headless` 获取 DDB Service IP
  - 使用 curl 命令调用 DDB API 获取节点角色信息
  - API 端点：`curl -X GET 'http://{service_ip}:8082/api/ddb/node/info?type=role&fields=role&node={pod_name}'`
  - 支持识别多个 DDB Master 和 Slave 节点
- **RC 操作的特殊处理**：
  - 在获取 RC Leader 和 Non-Leader 时，系统通过 registry-center 服务获取角色信息
  - 使用命令：`kubectl get svc -A | grep registry-center | grep -v headless` 获取 registry-center IP
  - 使用 curl 命令调用 registry-center API 获取 RC 集群信息
  - API 端点：`curl -X GET http://{ip}:8158/api/paas/v1/maintenance/rc/cluster -H 'Content-Type: application/json' -k`
  - 从返回的 JSON 数据中提取 Leader 和 Non-Leader Pod 名称
  - 支持识别 RC Leader 和多个 Non-Leader 节点

**示例：**
```bash
# 列出所有 Pod
python3 chaos/main.py pod --action list

# 获取 DDB 主备信息
python3 chaos/main.py pod --action ddb --namespace ns-dupf

# 获取 etcd 主从信息
python3 chaos/main.py pod --action etcd --namespace ns-dupf
```

### 4. version 子命令 - 版本管理

```bash
python3 chaos/main.py version --action <动作> [选项]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--action` | string | 是 | 版本操作：`show`、`iterate` |
| `--backup-dir` | string | 否 | 备份目录，默认 `backups` |

**示例：**
```bash
# 显示当前版本
python3 chaos/main.py version --action show

# 迭代版本并备份
python3 chaos/main.py version --action iterate --backup-dir backups
```

### 5. state 子命令 - 状态管理

```bash
python3 chaos/main.py state --action <动作> [选项]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--action` | string | 是 | 状态操作：`list`、`clear` |
| `--format` | string | 否 | 输出格式：`table`、`json`，默认 `table` |
| `--fault-id` | string | 否 | 指定故障 ID |

**示例：**
```bash
# 列出所有活跃故障（表格格式）
python3 chaos/main.py state --action list

# 列出所有活跃故障（JSON 格式）
python3 chaos/main.py state --action list --format json

# 清除指定故障
python3 chaos/main.py state --action clear --fault-id delete_pod_ns-test_1234567890

# 清除所有故障
python3 chaos/main.py state --action clear
```

### log 命令

收集多节点日志并汇总打包。

```bash
python3 chaos/main.py log --date <日期> [选项]
```

**参数说明：**
- `--date`: 要收集的日志日期（格式：YYYY-MM-DD）
- `--log-dir`: 日志基础目录（默认：/var/ctin/ctc-upf/var/log/service-logs）
- `--target-dir`: 最终归档存放目录（默认：/home/gsta）

**示例：**

```bash
# 收集 2024-01-15 的日志
python3 chaos/main.py log --date 2024-01-15

# 指定日志目录
python3 chaos/main.py log --date 2024-01-15 --log-dir /var/log/service-logs

# 指定目标目录
python3 chaos/main.py log --date 2024-01-15 --target-dir /home/user/logs
```

**日志过滤说明：**

支持两种日志文件过滤方式：
1. **按文件名过滤**：优先查找文件名中包含指定日期的文件（如 `*2026-03-26*`）
2. **按修改时间过滤**：如果文件名中没有匹配日期，则按文件修改时间过滤（当天修改的文件）

**工作流程：**
1. 从 config.yaml 读取所有 SSH 环境配置
2. 遍历每个节点，收集指定日期的日志
3. 在每个节点上：
   - 递归遍历日志目录下的所有子目录
   - 查找指定日期的日志文件（优先文件名匹配，其次按修改时间）
   - 打包找到的日志文件
   - 汇总为 ssh_$i.tar
4. 从第一个节点主动拉取其他节点的归档文件
5. 在第一个节点打包为 {date_时间戳}.tar

**文件聚合说明：**

采用集中式聚合架构：
- 第一个 SSH 节点作为主节点，负责主动拉取其他节点的文件
- 其他节点无需安装 sshpass，只需第一个节点支持 sshpass
- 第一个节点通过 SSH 远程执行 scp 命令，从其他节点拉取文件到本地
- 最后在第一个节点进行统一打包

**故障排查：**

如果文件拉取失败，请检查：
1. 第一个节点是否安装了 sshpass
2. 第一个节点是否可以 SSH 连接到其他节点
3. 其他节点的 SSH 服务是否正常运行
4. 网络连通性是否正常

## 其他参数说明

### 1. 故障记录参数

故障记录存储在 `data/faults.json` 文件中，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `fault_id` | string | 故障唯一标识 |
| `case_name` | string | Case 名称 |
| `fault_type` | string | 故障类型 |
| `target` | dict | 目标信息（Pod 名称、IP、命名空间等） |
| `parameters` | dict | 故障参数 |
| `status` | string | 故障状态：`running`、`recovered`、`failed` |
| `start_time` | datetime | 故障开始时间 |
| `end_time` | datetime | 故障结束时间（可选） |
| `error_message` | string | 错误信息（可选） |

### 2. 环境配置参数

环境配置对象包含以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | string | 环境名称 |
| `type` | string | 连接类型，默认 `ssh` |
| `ip` | string | 远程主机 IP |
| `port` | integer | SSH 端口，默认 `22` |
| `user` | string | SSH 用户名 |
| `passwd` | string | SSH 密码 |
| `nodename` | string | 节点名称（用于 clear 命令过滤 Pod） |
| `key_file` | string | SSH 密钥文件路径（可选） |
| `default_namespace` | string | 默认命名空间（可选） |

**说明：**
- `nodename`：节点名称，用于 clear 命令中过滤 Pod
  - 当执行 clear 命令时，系统会根据环境的 `nodename` 字段自动过滤 Pod
  - 例如：`1_ssh_remote` 环境的 `nodename` 为 `dupf01`，则只清除 `dupf01` 节点上的 Pod 网络故障
  - 例如：`2_ssh_remote` 环境的 `nodename` 为 `dupf02`，则只清除 `dupf02` 节点上的 Pod 网络故障
  - 这样可以避免在多节点环境中清除所有 Pod 的故障，提高清除效率
- **SSH 连接超时**：SSH 连接建立的超时时间为 10 秒
  - 如果在 10 秒内无法建立连接，系统会自动重试或报告错误
- **命令执行超时**：远程命令执行的超时时间为 120 秒
  - 适用于 `kubectl get pod`、`docker ps` 等可能需要较长时间的命令
  - 如果命令执行超过 120 秒，系统会自动终止命令并报告超时错误
  - 这个超时时间可以避免在某些节点响应慢时导致整个操作卡住

### 3. Case 配置参数

Case 配置对象包含以下属性：

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | Case 名称 |
| `description` | string | 否 | Case 描述 |
| `type` | string | 是 | 故障类型：`pod`、`network` |
| `environment` | string | 是 | 执行环境名称 |
| `fault_type` | string | 是 | 具体故障类型 |
| `pod_match` | dict | 是 | Pod 匹配规则 |
| `duration` | string | 是 | 故障持续时间 |
| `loop_count` | integer | 是 | 循环次数 |
| `parameters` | dict | 否 | 故障参数 |
| `namespace` | string | 否 | 命名空间 |
| `ssh_config` | dict | 否 | SSH 配置覆盖 |
| `auto_clear` | boolean | 否 | 故障持续时间结束后是否执行 clear 操作，默认 `false` |

**说明：**
- `auto_clear`：布尔类型字段，用于控制在故障持续时间结束后是否自动执行 clear 操作
  - `true`：在 duration 时间结束后，自动清除该环境节点上的网络故障
  - `false`：在 duration 时间结束后，不执行 clear 操作（默认值）
  - 该功能适用于网络故障类型，可以确保故障测试完成后自动清理网络配置
  - clear 操作会根据环境配置中的 `nodename` 字段过滤 Pod，只清除指定节点上的网络故障

### 4. 网络设备参数

网络故障注入支持以下设备参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `device` | `eth0` | 网络设备名称 |
| `direction` | `both` | 延迟方向：`both`、`in`、`out` |

### 5. 优雅终止参数

Pod 删除操作支持以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `grace_period` | `0` | 优雅终止时间（秒） |
| - | `> 0` | 等待 Pod 优雅关闭 |
| - | `= 0` | 立即强制删除 |

### 6. 日志参数

日志系统支持以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `name` | `chaos` | 日志记录器名称 |
| `level` | `INFO` | 日志级别 |
| `format` | 见代码 | 日志格式 |
| `output` | 控制台 | 日志输出位置 |

### 7. 备份参数

版本备份支持以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `backup_dir` | `backups` | 备份目录 |
| `version_file` | `VERSION` | 版本文件路径 |
| `backup_format` | `tar.gz` | 备份文件格式 |

### 8. 网络故障清除参数

网络故障清除支持以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `device` | `eth0` | 网络设备名称 |
| `namespace` | `ns-dupf` | Kubernetes 命名空间 |
| `nodename` | 从环境配置获取 | 节点名称（用于过滤 Pod） |

**说明：**
- `device`：指定要清除网络故障的网络设备名称
- `namespace`：指定要清除网络故障的 Kubernetes 命名空间
- `nodename`：节点名称，从环境配置中自动获取，用于过滤 Pod
  - 例如：`1_ssh_remote` 环境的 `nodename` 为 `dupf01`，则只清除 `dupf01` 节点上的 Pod 网络故障
  - 例如：`2_ssh_remote` 环境的 `nodename` 为 `dupf02`，则只清除 `dupf02` 节点上的 Pod 网络故障
- 网络故障清除使用 `nsenter` 进入容器网络命名空间执行 `tc` 命令
- 支持逐个 Pod 清除网络故障，提供详细的清除结果统计

## 核心功能

### 配置管理

- 支持多环境配置（SSH 远程）
- 支持交换机环境配置
- 支持默认配置和 UPU Pod 过滤列表
- 配置优先级：Case YAML > 环境配置 > 默认配置
- **SSH 连接池管理**：采用单例模式的连接池，提供高效的连接复用
  - **连接复用**：相同环境的多次操作复用同一连接，减少连接建立开销
  - **自动重连**：连接断开时自动检测并重新建立连接
  - **空闲清理**：自动清理超过 300 秒未使用的空闲连接
  - **连接限制**：最大支持 10 个并发连接，超出时自动清理最旧连接
  - **线程安全**：使用线程锁保护共享资源，支持多线程环境
  - **连接健康检查**：每次使用前检查连接状态，确保连接可用
  - 支持连接超时配置，默认 10 秒
  - 支持命令执行超时配置，默认 120 秒

### 故障注入

- **网络故障**：延迟、丢包等
- **Pod 故障**：删除、重启等
- **特殊 Pod 支持**：DDB、SDB、etcd、UPC、UPU 主备节点

### Case 管理

- YAML 格式定义 Case
- 支持单个和批量执行
- 支持循环执行和故障时长控制
- 自动故障恢复和状态记录
- **自动清除功能**：支持在故障持续时间结束后自动执行 clear 操作
  - 通过 `auto_clear` 字段控制，默认为 `false`
  - 当设置为 `true` 时，在 duration 时间结束后自动清除该环境节点上的网络故障
  - 适用于网络故障类型，可以确保故障测试完成后自动清理网络配置

### 故障清除

- **网络故障清除**：采用 OOP 设计，支持逐个 Pod 清除网络故障
  - 使用 `NetworkFaultClearer` 抽象类定义清除器接口
  - 通过 `PodNetworkFaultClearer` 实现具体的 Pod 网络故障清除
  - 使用 `nsenter` 进入容器网络命名空间执行 `tc` 命令
  - 支持自定义网络设备名称（默认：`eth0`）
  - 支持自定义 Kubernetes 命名空间（默认：`ns-dupf`）
  - **节点过滤**：根据环境配置中的 `nodename` 字段自动过滤 Pod，只清除指定节点上的 Pod 故障
    - 例如：`1_ssh_remote` 环境配置的 `nodename` 为 `dupf01`，则只清除 `dupf01` 节点上的 Pod 网络故障
    - 例如：`2_ssh_remote` 环境配置的 `nodename` 为 `dupf02`，则只清除 `dupf02` 节点上的 Pod 网络故障
    - 这样可以避免在多节点环境中清除所有 Pod 的故障，提高清除效率
- **状态记录清除**：清除所有故障状态记录

### 状态管理

- 故障记录持久化
- 故障状态追踪
- 支持故障查询和清理

### 版本管理

- 自动版本号递增
- 项目自动备份
- 权限友好（支持 sudo）

## 权限处理

本项目特别注重权限处理，所有文件操作都经过权限检查：

- 使用 `PermissionManager` 统一管理权限
- 支持 sudo 创建和修改文件
- 友好的错误提示和解决建议

## 开发指南

### 常量定义

项目常量集中在 `chaos/constants.py` 中管理：

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `SSH_DEFAULT_TIMEOUT` | 10 | SSH 连接超时时间（秒） |
| `SSH_POOL_MAX_CONNECTIONS` | 10 | SSH 连接池最大连接数 |
| `SSH_POOL_IDLE_TIMEOUT` | 300 | SSH 连接空闲超时时间（秒） |
| `DEFAULT_NAMESPACE` | ns-dupf | 默认 Kubernetes 命名空间 |
| `VALID_SIGNALS` | [1, 9, 11, 15, 18, 19] | 进程信号有效值列表 |

### 故障类型总览

| type | fault_type | 说明 | 恢复方式 |
|------|------------|------|----------|
| `pod` | `delete` | 删除 Pod | Pod 自动重建 |
| `pod` | `restart` | 重启 Pod | Pod 自动重启 |
| `pod` | `stop` | 停止容器（不删除 Pod） | 手动或自动执行 `docker start` |
| `network` | `delay` | 网络延迟 | 执行 `tc qdisc del` 清除 |
| `network` | `loss` | 网络丢包 | 执行 `tc qdisc del` 清除 |
| `computer` | `reboot` | 重启物理服务器 | 重启完成后自动恢复 |
| `process` | `kill` | 终止指定进程 | 进程守护自动拉起 |
| `tor` | `command` | 在交换机上执行命令 | 命令执行完成后自动恢复 |

### 添加新的故障类型

1. 在 `chaos/fault/` 目录下创建新的注入器类
2. 继承 `FaultInjector` 抽象类
3. 在 `FaultFactory` 中注册新的注入器

### 添加新的 Case 类型

1. 创建 Case YAML 文件
2. 定义故障类型和参数
3. 使用 `case` 命令执行

## 设计文档

详细设计文档请参考：`/home/gsta/chaos_oop_design.md`

## 注意事项

1. **权限问题**：如遇权限错误，请使用 sudo 运行脚本
2. **配置修改**：修改 `config.yaml` 前请备份原文件
3. **版本迭代**：执行版本迭代前确保项目已保存所有更改
4. **Pod 名称匹配**：支持自动匹配 Deployment 后缀，无需手动查询完整 Pod 名称

## 联系方式

项目设计文档：`/home/gsta/chaos_oop_design.md`

## 工作流配置参数说明

### 工作流 YAML 配置

工作流支持串行、并行、混合三种执行模式，用于编排多个 Case 的执行顺序。

#### 基本结构

```yaml
workflow:
  id: workflow_001              # 工作流 ID（必填）
  name: 工作流名称               # 工作流名称（必填）
  description: 工作流描述        # 工作流描述（可选）
  execution_mode: serial        # 执行模式：serial、parallel、hybrid（必填）
  auto_clear: false             # 工作流级别的自动清理（可选，默认 false）
  
  timing:                       # 时间配置（可选）
    start_delay: 5              # 整体启动延迟（秒）
    node_interval: 10           # 节点间延迟（秒）
    task_timeout: 600           # 单任务超时（秒）
    global_timeout: 3600        # 全局超时（秒）
    branch_start_delay: 5       # 分支启动延迟（秒，仅并行模式）
  
  tasks:                        # 任务列表（串行/并行模式）
    - id: task_1
      name: 任务名称
      case: { ... }             # 嵌入式 Case 定义
  
  groups:                       # 任务分组（混合模式）
    - id: group_1
      name: 分组名称
      execution_mode: serial    # 组内执行模式
      tasks: [ ... ]
  
  final_tasks:                  # 收尾任务（可选，混合模式）
    - id: cleanup
      name: 清理环境
      case: { ... }
```

#### 执行模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `serial` | 串行执行，任务按顺序逐个执行 | 有依赖关系的任务 |
| `parallel` | 并行执行，所有任务同时启动 | 独立无依赖的任务 |
| `hybrid` | 混合执行，分组并行 + 组内串行 | 复杂场景，部分任务有依赖 |

#### 时间配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `start_delay` | 整体启动延迟（秒） | 0 |
| `node_interval` | 节点间延迟（秒） | 0 |
| `task_timeout` | 单任务超时（秒） | 600 |
| `global_timeout` | 全局超时（秒） | 3600 |
| `branch_start_delay` | 分支启动延迟（秒） | 0 |

#### 自动清理配置

工作流支持 `auto_clear` 配置，用于在工作流执行完成后自动清理网络故障：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `auto_clear` | 工作流级别的自动清理 | false |

**使用说明：**

1. **workflow级别**：在workflow执行完成后统一清理所有网络故障
   ```yaml
   workflow:
     auto_clear: true  # 工作流执行完成后清理
   ```

2. **task级别**：在task执行完成后立即清理（不推荐，会导致并行任务竞争）
   ```yaml
   tasks:
     - id: task_1
       case:
         auto_clear: true  # task执行完成后清理
   ```

3. **推荐做法**：使用workflow级别的 `auto_clear`，避免并行任务竞争资源

**注意事项：**
- workflow级别的 `auto_clear` 不会继承到task
- task级别的 `auto_clear` 会覆盖workflow配置
- 对于网络故障（delay、corrupt、loss等），建议使用workflow级别的清理

#### 任务参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 任务唯一标识 |
| `name` | string | 是 | 任务名称 |
| `case` | object | 是 | 嵌入式 Case 定义 |
| `timing` | object | 否 | 任务级时间配置（覆盖工作流配置） |
| `retry_count` | integer | 否 | 重试次数，默认 0 |
| `retry_interval` | float | 否 | 重试间隔（秒），默认 5.0 |

#### 嵌入式 Case 定义

Case 直接定义在工作流中，无需引用外部 YAML 文件：

```yaml
case:
  name: case_name               # Case 名称
  type: sw                      # 类型：sw、pod、network、computer、process
  environment: sw_ssh_remote1   # 执行环境
  fault_type: command           # 故障类型
  sw_match:                     # 匹配规则（根据类型选择）
    commands:
      - cmd: display version
        wait: 2
    loop_count: 1
```

### 工作流示例

#### 串行工作流示例

```yaml
workflow:
  id: serial_example_001
  name: 串行测试工作流
  execution_mode: serial
  timing:
    start_delay: 5
    node_interval: 10
  
  tasks:
    - id: task_sw_command
      name: 交换机命令执行
      case:
        name: sw_command_execution
        type: sw
        environment: sw_ssh_remote1
        fault_type: command
        sw_match:
          commands:
            - cmd: display interface brief
              wait: 5
          loop_count: 1

    - id: task_pod_failure
      name: Pod 故障测试
      case:
        name: upc_pod_failure
        type: pod
        environment: 1_ssh_remote
        fault_type: delete
        pod_match:
          name: upc-talker
          namespace: ns-dupf
        duration: 30s
        loop_count: 0
```

#### 并行工作流示例

```yaml
workflow:
  id: parallel_example_001
  name: 并行测试工作流
  execution_mode: parallel
  timing:
    branch_start_delay: 5       # 分支启动延迟 5 秒
  
  tasks:
    - id: task_sw_1
      name: 交换机命令执行 1
      case:
        name: sw_command_1
        type: sw
        environment: sw_ssh_remote1
        fault_type: command
        sw_match:
          commands:
            - cmd: display interface brief
              wait: 5
          loop_count: 1

    - id: task_sw_2
      name: 交换机命令执行 2
      case:
        name: sw_command_2
        type: sw
        environment: sw_ssh_remote2
        fault_type: command
        sw_match:
          commands:
            - cmd: display bgp peer
              wait: 5
          loop_count: 1
```

#### 混合工作流示例

```yaml
workflow:
  id: hybrid_example_001
  name: 混合测试工作流
  execution_mode: hybrid
  timing:
    branch_start_delay: 10
  
  groups:
    - id: branch_sw
      name: 交换机测试分支
      execution_mode: serial
      timing:
        node_interval: 5
      tasks:
        - id: sw_1
          name: SW1 命令测试
          case:
            name: sw1_command
            type: sw
            environment: sw_ssh_remote1
            fault_type: command
            sw_match:
              commands:
                - cmd: display interface brief
                  wait: 5
              loop_count: 1

    - id: branch_pod
      name: Pod 故障测试分支
      execution_mode: serial
      start_delay: 10
      tasks:
        - id: pod_upc
          name: UPC Pod 故障
          case:
            name: upc_pod_failure
            type: pod
            environment: 1_ssh_remote
            fault_type: delete
            pod_match:
              name: upc-talker
              namespace: ns-dupf
            duration: 30s
            loop_count: 0

  final_tasks:
    - id: cleanup
      name: 清理环境
      case:
        name: cleanup_all
        type: sw
        environment: sw_ssh_remote1
        fault_type: command
        sw_match:
          commands:
            - cmd: display current-configuration
              wait: 2
          loop_count: 1
```

### 工作流命令行

```bash
# 验证工作流配置（dry-run 模式）
python3 chaos/main.py workflow --file workflows/serial_example.yaml --dry-run

# 执行工作流
python3 chaos/main.py workflow --file workflows/hybrid_example.yaml

# 指定最大并行数
python3 chaos/main.py workflow --file workflows/parallel_example.yaml --max-workers 5
```

**参数说明**：
- `--file`: 工作流 YAML 文件路径（必填）
- `--dry-run`: 仅验证配置，不执行（可选）
- `--max-workers`: 最大并行数，默认 10（可选）
