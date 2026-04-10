# Chaos OOP Design 项目创建总结

## 创建时间
2026-03-24

## 最后更新时间
2026-04-10

## 项目位置
`/home/gsta/chaos_oop_design/`

## 创建方式
**全部使用 sudo 创建和设置权限**，确保没有权限问题

## 项目结构

```
/home/gsta/chaos_oop_design/
├── chaos/                          # Python 主包
│   ├── __init__.py                # 包初始化
│   ├── main.py                    # 命令行入口
│   ├── config.py                  # 配置管理模块
│   ├── constants.py               # 常量定义模块
│   ├── exceptions.py              # 异常类定义
│   ├── handlers.py                # 命令处理器模块
│   ├── case/                      # Case 管理模块
│   │   ├── __init__.py
│   │   └── base.py               # CaseConfig, CaseExecutor, CaseManager
│   ├── fault/                     # 故障注入模块
│   │   ├── __init__.py
│   │   └── base.py              # FaultInjector, NetworkFaultInjector, PodFaultInjector, ProcessFaultInjector, SwitchFaultInjector, FaultFactory
│   ├── state/                     # 状态管理模块
│   │   ├── __init__.py
│   │   └── manager.py           # FaultRecord, FaultRepository, FaultRepository, StateManager
│   ├── scheduler/                 # 调度器模块（待实现）
│   │   └── __init__.py
│   ├── workflow/                  # 工作流编排模块
│   │   ├── __init__.py
│   │   ├── definition.py         # 数据结构定义
│   │   ├── parser.py             # YAML 解析器
│   │   ├── executor.py           # 执行器
│   │   └── monitor.py            # 监控器
│   ├── clearer/                   # 清除功能模块
│   │   ├── __init__.py
│   │   └── network.py           # NetworkFaultClearer, PodNetworkFaultClearer, NetworkFaultClearerFactory
│   └── utils/                     # 工具类模块
│       ├── __init__.py
│       ├── permission.py         # 权限管理器（核心）
│       ├── remote.py            # SSH 远程执行器
│       ├── logger.py            # 日志管理器
│       ├── version.py           # 版本管理器
│       ├── pod.py              # Pod 管理器
│       └── log_collector.py    # 日志收集器
├── cases/                         # Case YAML 文件
│   ├── network_delay.yaml        # 网络延迟 Case
│   ├── pod_failure.yaml          # Pod 故障 Case
│   ├── multi_pod_failure.yaml   # 多 Pod 故障 Case
│   ├── multi_pod_random_select.yaml # 多 Pod 随机选择 Case
│   ├── pod_stop_example.yaml    # Pod 停止容器 Case
│   ├── process_kill.yaml        # 进程 kill Case
│   └── sw_command.yaml          # 交换机命令执行 Case
├── tests/                         # 单元测试目录
│   ├── test_pod_fault_injector.py # Pod 故障注入器测试
│   ├── test_computer_fault_injector.py # 物理机故障注入器测试
│   ├── test_log_collector.py     # 日志收集器测试
│   ├── test_process_fault_injector.py # 进程故障注入器测试
│   └── test_workflow/            # 工作流模块测试
│       └── __init__.py
├── workflows/                     # 工作流配置目录
│   ├── serial_example.yaml       # 串行工作流示例
│   ├── parallel_example.yaml     # 并行工作流示例
│   └── hybrid_example.yaml       # 混合工作流示例
├── scripts/                       # 脚本目录
│   └── version_iterate.sh        # 版本迭代脚本（带权限处理）
├── backups/                       # 备份目录
├── data/                          # 数据目录
├── config.yaml                    # 项目配置文件
├── VERSION                        # 版本文件 (1.0.0)
└── README.md                      # 项目说明
```

## 核心模块说明

### 1. 常量定义模块 (`chaos/constants.py`)
**核心功能**：
- `POD_FILTER_RULES` - Pod 过滤规则映射（upc-talker、ddb-master 等）
- `DEFAULT_NAMESPACE` - 默认命名空间（ns-dupf）
- `VALID_SIGNALS` - 有效信号列表（1, 9, 11, 15, 18, 19）
- `SIGNAL_NAMES` - 信号名称映射

**设计优势**：
- 集中管理常量，避免重复定义
- 新增 Pod 过滤规则只需修改映射字典
- 便于维护和扩展

### 2. 权限管理模块 (`chaos/utils/permission.py`)
**核心功能**：
- `PermissionManager` 类提供统一的权限处理
- `check_sudo_available()` - 检查 sudo 可用性
- `ensure_directory()` - 确保目录存在（支持 sudo）
- `safe_write_file()` - 安全写入文件（支持 sudo）
- `safe_read_file()` - 安全读取文件（支持 sudo）
- `set_file_owner()` - 设置文件所有者
- `set_file_permission()` - 设置文件权限

**权限处理策略**：
1. 先尝试直接操作
2. 失败后尝试使用 sudo
3. 设置正确的文件所有者
4. 提供友好的错误提示

### 3. 命令处理器模块 (`chaos/handlers.py`)
**核心类**：
- `PodActionHandler` - Pod 操作处理器
- `ClearActionHandler` - 清除操作处理器
- `LogActionHandler` - 日志操作处理器

**功能**：
- 将 main.py 中的操作处理逻辑提取到独立类
- 提供清晰的职责分离
- 便于单元测试和维护

**设计优势**：
- 单一职责原则：每个类只负责一种操作
- 开闭原则：新增操作只需添加新方法
- 依赖注入：通过构造函数注入依赖

### 4. 配置管理模块 (`chaos/config.py`)
**核心类**：
- `ConfigManager` - 配置管理器
- `EnvironmentConfig` - 环境配置封装

**功能**：
- 加载 YAML 配置文件
- 管理多环境配置（SSH、交换机）
- 提供默认配置和 UPU 过滤列表
- 提供默认命名空间获取方法（`get_namespace()`）
- 配置验证

### 5. 故障注入模块 (`chaos/fault/base.py`)
**核心类**：
- `FaultInjector` (抽象基类)
- `NetworkFaultInjector` - 网络故障注入器
- `PodFaultInjector` - Pod 故障注入器
- `ComputerFaultInjector` - 物理机故障注入器
- `ProcessFaultInjector` - 进程故障注入器
- `SwitchFaultInjector` - 交换机故障注入器
- `FaultFactory` - 故障注入器工厂

**网络故障注入器特性**：
- **节点感知执行**：自动识别 Pod 所在节点，在正确的节点上执行故障注入
- **pause 容器 ID 获取**：通过 `_get_pause_container_id_and_executor()` 方法获取 pause 容器 ID 和节点执行器
- **容器 PID 获取**：通过 `_get_container_pid()` 方法在正确的节点上获取容器 PID
- **支持的故障类型**：delay（延迟）、loss（丢包）、corrupt（数据包破坏）、duplicate（数据包重复）、reorder（数据包重排序）
- **自动恢复**：通过 `recover()` 方法在正确的节点上清除网络故障

**节点感知执行流程**：
1. 通过 `PodManager.get_pod_node()` 获取 Pod 所在的节点名称
2. 通过 `_get_executor_by_node()` 获取该节点的 SSH 执行器
3. 在正确的节点上执行 `docker ps` 获取 pause 容器 ID
4. 在正确的节点上执行 `docker inspect` 获取 pause 容器 PID
5. 在正确的节点上执行 `nsenter` 和 `tc` 命令注入网络故障

**Pod 故障类型**：
| fault_type | 说明 | 恢复方式 |
|------------|------|----------|
| `delete` | 删除 Pod | Pod 自动重建 |
| `restart` | 重启 Pod | Pod 自动重启 |
| `stop` | 停止容器（不删除 Pod） | `docker start` 恢复 |

**物理机故障类型**：
| fault_type | 说明 | 恢复方式 |
|------------|------|----------|
| `reboot` | 重启物理服务器 | 重启完成后自动恢复 |

**进程故障类型**：
| fault_type | 说明 | 恢复方式 |
|------------|------|----------|
| `kill` | Kill 指定进程 | 进程守护自动拉起 |

**交换机故障类型**：
| fault_type | 说明 | 恢复方式 |
|------------|------|----------|
| `command` | 在交换机上执行命令 | 命令执行完成后自动恢复 |

**交换机故障参数**：
- `command`: 要执行的命令列表（支持单个或多个命令）
- `loop_count`: 循环执行次数（默认 1）

**进程故障参数**：
- `signal`: 信号值（默认 15）或 "random"（从 1, 9, 11, 15, 18, 19 中随机选择）
- `main_process_pid`: 目标进程 PID（默认 1）

**设计模式**：
- 工厂模式：根据类型创建注入器
- 策略模式：不同故障类型使用不同策略

### 6. 状态管理模块 (`chaos/state/manager.py`)
**核心类**：
- `FaultRecord` - 故障记录数据类
- `FaultRepository` (抽象) / `FileFaultRepository` (实现)
- `StateManager` - 状态管理器

**功能**：
- 故障记录持久化（JSON 文件）
- 故障状态追踪（running, recovered, failed）
- 活跃故障查询
- 故障清理

### 7. Case 管理模块 (`chaos/case/base.py`)
**核心类**：
- `CaseConfig` - Case 配置
- `CaseExecutor` - Case 执行器
- `CaseManager` - Case 管理器

**功能**：
- YAML 格式 Case 解析
- 配置验证
- 配置优先级合并（Case > 环境 > 默认）
- 单个/批量 Case 执行
- 循环执行和故障时长控制

### 8. 远程执行模块 (`chaos/utils/remote.py`)
**核心类**：
- `RemoteExecutor` (抽象基类)
- `SSHExecutor` - SSH 远程执行器

**功能**：
- SSH 连接管理
- 远程命令执行
- 文件上传/下载

### 9. 版本管理模块 (`chaos/utils/version.py`)
**核心类**：
- `VersionManager`

**功能**：
- 版本号加载和递增
- 项目自动备份（tar.gz）
- 权限友好的文件写入

### 10. 日志模块 (`chaos/utils/logger.py`)
**核心类**：
- `Logger`
- `JSONFormatter`

**功能**：
- 控制台和文件日志
- JSON 格式支持
- 日志级别控制

### 11. Pod 管理模块 (`chaos/utils/pod.py`)
**核心类**：
- `PodManager`

**功能**：
- 获取 Pod 列表（支持标签过滤）
- 根据节点名称过滤 Pod
- 特殊 Pod 获取（DDB、SDB、etcd、UPC、UPU、RC）
- Pod 名称模式匹配
- **获取 Pod 所在节点**：通过 `get_pod_node()` 方法获取 Pod 运行的节点名称

**get_pod_node 方法**：
- **功能**：获取指定 Pod 所在的节点名称
- **参数**：
  - `pod_name`: Pod 名称
  - `namespace`: 命名空间（可选，默认从配置文件获取）
- **返回值**：节点名称（字符串）或 None
- **实现方式**：执行 `kubectl get pod -o wide` 命令并解析输出
- **用途**：为网络故障注入提供节点感知能力，确保在正确的节点上执行命令

**特殊 Pod 过滤规则**（定义在 `constants.py`）：
| 过滤规则 | 说明 |
|----------|------|
| `upc-talker` | UPC talker Pod |
| `upc-nontalker` | UPC 非 talker Pod |
| `upc-all` | 所有 UPC Pod |
| `etcd-leader` | etcd leader Pod |
| `etcd-follower` | etcd follower Pod |
| `etcd-all` | 所有 etcd Pod |
| `ddb-master` | DDB master Pod |
| `ddb-slave` | DDB slave Pod |
| `ddb-all` | 所有 DDB Pod |
| `sdb-master` | SDB master Pod |
| `sdb-slave` | SDB slave Pod |
| `sdb-all` | 所有 SDB Pod |
| `rc-leader` | RC leader Pod（Registry Center）|
| `rc-nonleader` | RC 非 leader Pod（Registry Center）|
| `rc-all` | 所有 RC Pod（Registry Center）|
| `upu-master` | UPU master Pod |
| `upu-slave` | UPU slave Pod |
| `upu-all` | 所有 UPU Pod |

### 12. 清除模块 (`chaos/clearer/network.py`)
**核心类**：
- `NetworkFaultClearer` (抽象基类)
- `PodNetworkFaultClearer` - Pod 网络故障清除器
- `NetworkFaultClearerFactory` - 清除器工厂

**功能**：
- 清除 Pod 网络故障（使用 nsenter 和 tc 命令）
- 支持自定义网络设备（默认：eth0）
- 支持自定义 Kubernetes 命名空间（默认：ns-dupf）
- 根据节点名称过滤 Pod
- 详细的清除结果统计

**设计模式**：
- 工厂模式：根据类型创建清除器
- 策略模式：不同清除类型使用不同策略

### 13. 日志收集模块 (`chaos/utils/log_collector.py`)
**核心类**：
- `LogCollector` (抽象基类)
- `NodeLogCollector` - 单节点日志收集器
- `MultiNodeLogCollector` - 多节点日志收集器

**功能**：
- 从多节点收集指定日期的日志
- 递归遍历日志目录下的所有子目录
- 支持两种日志过滤方式：文件名匹配和修改时间过滤
- 集中式文件聚合架构
- 支持自定义日志目录和目标目录

**日志过滤策略**：
1. **按文件名过滤**：优先查找文件名中包含指定日期的文件（如 `*2026-03-26*`）
2. **按修改时间过滤**：如果文件名中没有匹配日期，则使用 `find -newermt` 按修改时间过滤当天修改的文件

**集中式聚合架构**：
- 第一个 SSH 节点作为主节点，负责主动拉取其他节点的文件
- 其他节点无需安装 sshpass，只需第一个节点支持 sshpass
- 第一个节点通过 SSH 远程执行 scp 命令，从其他节点拉取文件到本地
- 最后在第一个节点进行统一打包

**工作流程**：
1. 从 config.yaml 读取所有 SSH 环境配置
2. 遍历每个节点，收集指定日期的日志
3. 在每个节点上：
   - 递归遍历日志目录下的所有子目录
   - 查找指定日期的日志文件（优先文件名匹配，其次按修改时间）
   - 打包找到的日志文件
   - 汇总为 ssh_$i.tar
4. 第一个节点主动拉取其他节点的归档文件
5. 在第一个节点打包为 {date_时间戳}.tar

**命令行支持**：
```bash
python3 chaos/main.py log --date 2024-01-15 --log-dir /var/ctin/ctc-upf/var/log/service-logs --target-dir /home/gsta
```

### 14. 工作流编排模块 (`chaos/workflow/`)
**核心类**：
- `ExecutionMode` - 执行模式枚举（serial、parallel、hybrid）
- `TimingConfig` - 时间配置（启动延迟、节点间隔、超时等）
- `CaseDefinition` - Case 定义（嵌入式）
- `Task` - 任务节点
- `TaskGroup` - 任务分组
- `WorkflowDefinition` - 工作流定义抽象类
- `SerialWorkflow` - 串行工作流
- `ParallelWorkflow` - 并行工作流
- `HybridWorkflow` - 混合工作流
- `WorkflowParser` - YAML 解析器
- `WorkflowExecutor` - 工作流执行器
- `TaskExecutor` - 任务执行器
- `WorkflowMonitor` - 工作流监控器

**功能**：
- 支持串行、并行、混合三种执行模式
- 支持嵌入式 Case 定义（无需引用外部 YAML 文件）
- 支持多层级时间配置（Workflow > TaskGroup > Task）
- 支持任务重试机制
- 支持执行监控和报告生成
- 支持信号处理（Ctrl+C 优雅退出）

**执行模式**：
| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `serial` | 串行执行，任务按顺序逐个执行 | 有依赖关系的任务 |
| `parallel` | 并行执行，所有任务同时启动 | 独立无依赖的任务 |
| `hybrid` | 混合执行，分组并行 + 组内串行 | 复杂场景，部分任务有依赖 |

**时间配置**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `start_delay` | 整体启动延迟（秒） | 0 |
| `node_interval` | 节点间延迟（秒） | 0 |
| `task_timeout` | 单任务超时（秒） | 600 |
| `global_timeout` | 全局超时（秒） | 3600 |
| `branch_start_delay` | 分支启动延迟（秒） | 0 |

**设计模式**：
- 工厂模式：根据执行模式创建工作流实例
- 策略模式：不同执行模式使用不同执行策略
- 模板方法模式：工作流定义抽象类定义执行流程
- 观察者模式：监控器记录执行结果

**命令行支持**：
```bash
# 验证工作流配置
python3 chaos/main.py workflow --file workflows/serial_example.yaml --dry-run

# 执行工作流
python3 chaos/main.py workflow --file workflows/hybrid_example.yaml --max-workers 5
```

## 命令行接口

```bash
# 执行 Case
python3 chaos/main.py case --name <case.yaml>
python3 chaos/main.py case --dir <cases_dir>

# 执行工作流
python3 chaos/main.py workflow --file <workflow.yaml> [--dry-run] [--max-workers N]

# 清除故障
python3 chaos/main.py clear --env <env_name> --type <fault_type> --device <device> --namespace <namespace>

# Pod 管理
python3 chaos/main.py pod --action <list|ddb|sdb|etcd|upc|upu>

# 版本管理
python3 chaos/main.py version --action show
python3 chaos/main.py version --action iterate

# 状态管理
python3 chaos/main.py state --action list
python3 chaos/main.py state --action clear

# 日志收集
python3 chaos/main.py log --date <YYYY-MM-DD> --log-dir <log_dir> --target-dir <target_dir>
```

### workflow 命令参数说明
- `--file`: 工作流 YAML 文件路径（必填）
- `--dry-run`: 仅验证配置，不执行（可选）
- `--max-workers`: 最大并行数，默认 10（可选）

### clear 命令参数说明
- `--env`: 环境名称（默认：all）
- `--type`: 故障类型（all、network、pod，默认：all）
- `--device`: 网络设备名称（默认：eth0）
- `--namespace`: Kubernetes 命名空间（默认：ns-dupf）

**节点过滤功能**：
- 根据环境配置中的 `nodename` 字段自动过滤 Pod
- 例如：`1_ssh_remote` 环境的 `nodename` 为 `dupf01`，则只清除 `dupf01` 节点上的 Pod 网络故障
- 例如：`2_ssh_remote` 环境的 `nodename` 为 `dupf02`，则只清除 `dupf02` 节点上的 Pod 网络故障

## 版本迭代脚本

**位置**：`scripts/version_iterate.sh`

**权限处理**：
- 使用 `ensure_directory_with_sudo()` 创建目录
- 使用 `safe_write_with_sudo()` 写入文件
- 所有 sudo 操作后设置正确的所有者

**功能**：
1. 自动备份项目为 tar.gz
2. 版本号自动 +1（补丁版本）
3. 完整的权限处理

## 配置文件

### config.yaml
包含：
- 4 个 SSH 远程环境配置（每个环境包含 nodename 字段）
- 2 个交换机环境配置
- 默认配置（namespace、wait_seconds、cleanup）
- UPU Pod 过滤列表（主节点和从节点）

**环境配置字段**：
- `type`: 连接类型（ssh）
- `ip`: 远程主机 IP
- `port`: SSH 端口
- `user`: SSH 用户名
- `passwd`: SSH 密码
- `nodename`: 节点名称（用于 clear 命令过滤 Pod）

**默认配置字段**：
- `namespace`: 默认命名空间（默认值：ns-dupf）
- `wait_seconds`: 默认等待时间（秒）
- `cleanup`: 是否自动清理故障

**namespace 优先级规则**：
1. YAML 用例中指定的 namespace（最高优先级）
2. config.yaml 中 defaults.namespace 配置
3. 代码中的默认值 `ns-dupf`（最低优先级）

**UPU 过滤列表**：
- `UPU_POD_FILTERS`: UPU Master Pod 过滤列表
- `UPU_POD_FILTERS_SLAVE`: UPU Slave Pod 过滤列表

### Case YAML 示例
- `network_delay.yaml` - 网络延迟 Case
- `pod_failure.yaml` - Pod 故障 Case
- `multi_pod_failure.yaml` - 多 Pod 故障 Case
- `multi_pod_random_select.yaml` - 多 Pod 随机选择 Case
- `pod_stop_example.yaml` - Pod 停止容器 Case
- `computer_reboot.yaml` - 物理机重启 Case

**Case 配置字段**：
- `name`: Case 名称
- `description`: Case 描述
- `type`: 故障类型（pod、network）
- `environment`: 执行环境名称
- `fault_type`: 具体故障类型
- `pod_match`: Pod 匹配规则
  - `name`: Pod 名称（支持数组形式，可匹配多个 Pod）
  - `labels`: Pod 标签
  - `random_select`: 是否随机选择（默认：false）
  - `select_count`: 随机选择数量（默认：1）
  - `interval`: Pod 之间的故障间隔（秒）
- `duration`: 故障持续时间
- `loop_count`: 循环次数
- `parameters`: 故障参数
- `namespace`: 命名空间
- `ssh_config`: SSH 配置覆盖
- `auto_clear`: 故障持续时间结束后是否执行 clear 操作（默认：false）

## 权限处理重点

### 创建时处理
```bash
# 1. 使用 sudo 创建目录
sudo mkdir -p /home/gsta/chaos_oop_design/{directories}

# 2. 设置所有者
sudo chown -R gsta:gsta /home/gsta/chaos_oop_design

# 3. 设置脚本权限
sudo chmod 755 /home/gsta/chaos_oop_design/scripts/*
```

### 运行时处理
```python
# Python 代码中使用 PermissionManager
from chaos.utils.permission import PermissionManager

# 创建目录
success, error = PermissionManager.ensure_directory("/path/to/dir")

# 写入文件
success, error = PermissionManager.safe_write_file("/path/to/file", content)
```

## 已实现功能

1. **Clear 模块** - 故障清除功能 ✅
   - NetworkFaultClearer 抽象类
   - PodNetworkFaultClearer 实现
   - NetworkFaultClearerFactory 工厂
   - 支持节点过滤
   - 支持自定义网络设备和命名空间

2. **Pod 管理模块** - 特殊 Pod 获取逻辑 ✅
   - PodManager 类
   - 支持根据节点名称过滤 Pod
   - 特殊 Pod 获取（DDB、SDB、etcd、UPC、UPU）
   - Pod 名称匹配（支持通配符、前缀、包含匹配）

3. **Case 管理** - 多 Pod 匹配和随机选择 ✅
   - 支持数组形式的 Pod 名称
   - 支持随机选择多个 Pod
   - 支持 Pod 之间的故障间隔

4. **Pod 故障注入** - delete、restart、stop ✅
   - delete: 删除 Pod
   - restart: 重启 Pod
   - stop: 停止容器（不删除 Pod）

5. **单元测试** ✅
   - Pod 故障注入器测试（12 个测试用例）

6. **工作流编排模块** ✅
   - 串行执行模式
   - 并行执行模式
   - 混合执行模式
   - 嵌入式 Case 定义
   - 多层级时间配置
   - 任务重试机制
   - 执行监控和报告
   - 信号处理
   - 单元测试（44 个测试用例）

## 待实现功能

1. **Scheduler 模块** - Case 调度器
2. **网络故障注入实现** - tc 命令集成
3. **更多单元测试** - 各模块测试用例

## 设计文档参考

详细设计文档：`/home/gsta/chaos_oop_design.md`

## 最新实现和测试结果

### 2026-04-10 更新

#### 1. 网络故障注入 - 节点感知执行
- **问题**：之前在获取 Pod 的 pause 容器 ID 时，可能在错误的节点上执行命令，导致找不到容器
- **解决方案**：
  - 添加 `PodManager.get_pod_node()` 方法，获取 Pod 所在的节点名称
  - 添加 `NetworkFaultInjector._get_executor_by_node()` 方法，根据节点名称获取对应的 SSH 执行器
  - 修改 `_get_pause_container_id_and_executor()` 方法，返回 `(container_id, node_executor)` 元组
  - 修改 `_get_container_pid()` 方法，支持在指定节点上执行命令
  - 所有网络故障注入（delay、loss、corrupt、duplicate、reorder）都在正确的节点上执行
  - `recover()` 方法也在正确的节点上清除网络故障
- **测试结果**：所有单元测试通过（176 passed）
- **影响范围**：
  - `chaos/fault/base.py` - NetworkFaultInjector 类
  - `chaos/utils/pod.py` - PodManager 类
  - `tests/test_network_*.py` - 所有网络故障类型的测试文件

#### 2. 测试用例更新
- 更新了所有网络故障类型的测试用例，使其返回正确的元组 `(container_id, node_executor)`
- 验证了正确的执行器调用
- 所有测试通过（176 passed）

### 2026-03-25 更新

#### 1. Pod 故障注入 - stop 类型
- 实现了 `stop` 故障类型，停止 Pod 内容器
- 通过 `docker stop` 命令停止容器
- 自动查找 Pod 所在节点并连接执行
- 支持 `docker start` 恢复容器
- 适用于模拟容器崩溃、进程停止等场景

#### 2. UPU 过滤规则
- 支持 `upu-master`、`upu-slave`、`upu-all` 过滤规则
- `upu-master`: 根据 `config.yaml` 中的 `UPU_POD_FILTERS` 过滤
- `upu-slave`: 根据 `config.yaml` 中的 `UPU_POD_FILTERS_SLAVE` 过滤
- `upu-all`: 获取所有 UPU Pod

#### 3. 单元测试
- 添加了 `tests/test_pod_fault_injector.py` 测试文件
- 12 个测试用例全部通过
- 测试覆盖：delete、restart、stop 操作及恢复功能

#### 4. 网络故障清除功能实现
- 实现了完整的网络故障清除功能，采用 OOP 设计
- 使用 `NetworkFaultClearer` 抽象类定义清除器接口
- 通过 `PodNetworkFaultClearer` 实现具体的 Pod 网络故障清除
- 使用 `nsenter` 进入容器网络命名空间执行 `tc` 命令
- 支持自定义网络设备名称（默认：eth0）
- 支持自定义 Kubernetes 命名空间（默认：ns-dupf）

#### 5. 节点过滤功能
- 在 `PodManager` 中添加了 `get_pods_by_nodename()` 方法
- 根据环境配置中的 `nodename` 字段自动过滤 Pod
- 避免在多节点环境中清除所有 Pod 的故障，提高清除效率

#### 6. SSH 连接管理优化
- 在 `main.py` 的 `handle_clear_command()` 中添加了 `try-finally` 块
- 确保 SSH 连接在任何情况下都会被正确关闭
- 解决了之前 dupf02 节点获取 Pod 超时的问题

#### 7. 测试结果
**单个环境测试**：
- `1_ssh_remote` (dupf01): 成功 16, 失败 0
- `2_ssh_remote` (dupf02): 成功 14, 失败 0
- `3_ssh_remote` (dupf03): 成功 15, 失败 0
- `4_ssh_remote` (dupf04): 成功 16, 失败 0

**所有环境测试**：
- 总共清除了 61 个 Pod 的网络故障
- 执行时间约 40 秒
- 每个环境的清除速度都很快（约 10 秒）

**单元测试**：
- 12 个测试用例全部通过
- 测试时间约 0.2 秒

## 下一步工作

1. 完善网络故障注入的具体实现
2. 添加更多单元测试
3. 完善文档和示例
