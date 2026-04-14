"""Case 管理模块
负责 Case 的解析、验证和执行
"""

import yaml
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime

from ..constants import POD_FILTER_RULES

if TYPE_CHECKING:
    from ..protocols import (
        ConfigManagerProtocol,
        FaultFactoryProtocol,
        StateManagerProtocol,
        LoggerProtocol,
        RemoteExecutorProtocol,
    )


class CaseConfig:
    """Case 配置类"""
    
    def __init__(self, config_dict: Dict):
        """初始化 Case 配置
        
        Args:
            config_dict: 配置字典
        """
        self.name = config_dict.get("name")
        self.description = config_dict.get("description")
        self.type = config_dict.get("type")
        self.environment = config_dict.get("environment")
        self.fault_type = config_dict.get("fault_type")
        
        # 根据 type 选择匹配字段
        if self.type == "sw":
            self.pod_match = config_dict.get("sw_match", {})
        elif self.type == "computer":
            self.pod_match = config_dict.get("computer_match", {})
        elif self.type == "cmd":
            self.pod_match = config_dict.get("cmd_match", {})
        else:
            self.pod_match = config_dict.get("pod_match", {})
        
        self.duration = config_dict.get("duration")
        self.loop_count = config_dict.get("loop_count", 1)
        self.parameters = config_dict.get("parameters", {})
        self.namespace = config_dict.get("namespace")
        self.ssh_config = config_dict.get("ssh_config")
        self.auto_clear = config_dict.get("auto_clear", False)
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """验证配置
        
        Returns:
            Tuple[bool, Optional[str]]: (是否有效，错误信息)
        """
        if not self.name:
            return False, "Case name 是必需的"
        
        if not self.type:
            return False, "Case type 是必需的"
        
        # computer 类型的 environment 不是必需的，目标信息来自 computer_match.name
        if self.type not in ["computer", "cmd"] and not self.environment:
            return False, "Environment 是必需的"
        
        if not self.fault_type:
            return False, "Fault type 是必需的"
        
        # 验证匹配规则
        if not self._validate_match():
            return False, "无效的匹配配置"
        
        return True, None
    
    def _validate_match(self) -> bool:
        """验证匹配规则"""
        if self.type == "computer":
            computer_match = self.pod_match
            return bool(computer_match.get("name"))
        
        if self.type == "sw":
            sw_match = self.pod_match
            return bool(sw_match.get("commands") or sw_match.get("command"))
        
        if self.type == "cmd":
            cmd_match = self.pod_match
            return bool(cmd_match.get("cmd"))
        
        pod_match = self.pod_match
        has_name = bool(pod_match.get("name"))
        has_labels = bool(pod_match.get("labels"))
        is_special = pod_match.get("type") == "special"
        
        return has_name or has_labels or is_special
    
    def get_effective_config(self, env_config, defaults: Dict) -> Dict:
        """获取有效配置（合并优先级）
        
        优先级：Case YAML > 环境配置 > 默认配置
        
        Args:
            env_config: 环境配置
            defaults: 默认配置
            
        Returns:
            Dict: 有效配置
        """
        effective = {}
        
        # 默认配置
        effective.update(defaults)
        
        # 环境配置
        if env_config and hasattr(env_config, 'default_namespace'):
            if env_config.default_namespace:
                effective.setdefault("namespace", env_config.default_namespace)
        
        # Case 配置覆盖
        if self.namespace:
            effective["namespace"] = self.namespace
        if self.ssh_config:
            effective["ssh_config"] = self.ssh_config
        
        return effective
    
    @classmethod
    def from_yaml(cls, yaml_file: str):
        """从 YAML 文件加载配置
        
        Args:
            yaml_file: YAML 文件路径
            
        Returns:
            CaseConfig: Case 配置对象
        """
        with open(yaml_file, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls(config_dict)


class CaseExecutor:
    """Case 执行器"""
    
    def __init__(
        self,
        config_manager: "ConfigManagerProtocol",
        fault_factory: "FaultFactoryProtocol",
        state_manager: "StateManagerProtocol",
        logger: "LoggerProtocol"
    ):
        """初始化 Case 执行器
        
        Args:
            config_manager: 配置管理器
            fault_factory: 故障注入器工厂
            state_manager: 状态管理器
            logger: 日志记录器
        """
        self.config_manager = config_manager
        self.fault_factory = fault_factory
        self.state_manager = state_manager
        self.logger = logger
        self._running_faults: Dict[str, any] = {}
    
    def execute_case(self, case_config: CaseConfig) -> bool:
        """执行 Case
        
        Args:
            case_config: Case 配置
            
        Returns:
            bool: 成功标志
        """
        try:
            self.logger.info(f"[DEBUG] ========== 开始执行 Case ==========")
            self.logger.info(f"[DEBUG] Case名称: {case_config.name}")
            self.logger.info(f"[DEBUG] Case类型: {case_config.type}")
            self.logger.info(f"[DEBUG] 故障类型: {case_config.fault_type}")
            self.logger.info(f"[DEBUG] 环境: {case_config.environment}")
            
            # 验证配置
            is_valid, error_msg = case_config.validate()
            if not is_valid:
                self.logger.error(f"无效的 Case 配置：{error_msg}")
                return False
            
            # 获取环境配置
            env_config = self.config_manager.get_environment(case_config.environment)
            defaults = self.config_manager.get_defaults()
            
            # 获取有效配置
            effective_config = case_config.get_effective_config(env_config, defaults)
            
            # 执行循环
            for i in range(case_config.loop_count):
                self.logger.info(f"[DEBUG] 执行 Case 迭代 {i+1}/{case_config.loop_count}")
                
                # 获取目标列表
                self.logger.info(f"[DEBUG] 开始获取目标列表...")
                targets = self._get_targets(case_config, effective_config)
                self.logger.info(f"[DEBUG] 找到 {len(targets) if targets else 0} 个目标")
                
                if not targets:
                    self.logger.error(f"在第 {i+1} 次迭代未找到目标")
                    return False
                
                # 获取时间间隔参数
                interval = case_config.pod_match.get("interval", 0)
                
                # 对每个目标执行故障注入
                for index, target in enumerate(targets):
                    self.logger.info(f"[DEBUG] ---------- 处理目标 {index+1}/{len(targets)} ----------")
                    self.logger.info(f"[DEBUG] 目标名称: {target.get('name')}")
                    self.logger.info(f"[DEBUG] 目标节点: {target.get('node')}")
                    
                    # 除了第一个目标外，其他目标需要等待时间间隔
                    if index > 0 and interval > 0:
                        self.logger.info(f"[DEBUG] 等待 {interval} 秒后执行下一个故障")
                        time.sleep(interval)
                    
                    # 创建故障注入器
                    self.logger.info(f"[DEBUG] 创建故障注入器...")
                    if case_config.type in ["computer", "sw", "cmd"]:
                        injector = self.fault_factory.create_injector(
                            fault_type=case_config.type,
                            logger=self.logger,
                            config_manager=self.config_manager
                        )
                    else:
                        injector = self.fault_factory.create_injector(
                            fault_type=case_config.type,
                            remote_executor=self._get_remote_executor(env_config),
                            logger=self.logger,
                            config_manager=self.config_manager
                        )
                    
                    # 注入故障
                    self.logger.info(f"[DEBUG] 准备注入故障...")
                    inject_params = {
                        "fault_type": case_config.fault_type,
                        **case_config.parameters
                    }
                    
                    # 对于 sw 类型，添加 sw_match 参数
                    if case_config.type == "sw":
                        inject_params.update(case_config.pod_match)
                    
                    # 对于 cmd 类型，添加 cmd_match 参数
                    if case_config.type == "cmd":
                        inject_params.update(case_config.pod_match)
                    
                    self.logger.info(f"[DEBUG] 注入参数: {inject_params}")
                    success = injector.inject(target, inject_params)
                    
                    if not success:
                        self.logger.error(f"[DEBUG] 在第 {i+1} 次迭代注入故障失败，目标：{target.get('name')}")
                        return False
                    
                    self.logger.info(f"[DEBUG] 故障注入成功")
                    
                    # 记录故障
                    fault_id = injector.get_fault_id()
                    self.logger.info(f"[DEBUG] 故障ID: {fault_id}")
                    self.state_manager.record_fault(
                        case_name=case_config.name,
                        fault_type=case_config.fault_type,
                        fault_id=fault_id,
                        target=target,
                        parameters=case_config.parameters
                    )
                    
                    # 保存注入器引用
                    self._running_faults[fault_id] = injector
                    
                    # 等待
                    if case_config.duration:
                        wait_time = self._parse_duration(case_config.duration)
                        self.logger.info(f"[DEBUG] 开始等待 duration: {case_config.duration} ({wait_time}秒)")
                        time.sleep(wait_time)
                        self.logger.info(f"[DEBUG] duration 等待完成")
                    
                    # 清理故障
                    self.logger.info(f"[DEBUG] 开始清理故障: {fault_id}")
                    if not injector.recover(fault_id):
                        self.logger.error(f"[DEBUG] 恢复故障失败：{fault_id}")
                        self.state_manager.mark_failed(fault_id, "恢复失败")
                        return False
                    
                    self.logger.info(f"[DEBUG] 故障清理成功: {fault_id}")
                    
                    # 标记为已恢复
                    self.state_manager.mark_recovered(fault_id)
                    
                    # 移除注入器引用
                    del self._running_faults[fault_id]
            
            # 执行 auto_clear（只有当明确设置为True时才执行）
            if case_config.auto_clear is True:
                self.logger.info(f"执行 auto_clear，清除环境 {case_config.environment} 的网络故障")
                self._execute_auto_clear(case_config, env_config)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Case 执行失败：{e}")
            return False
    
    def cleanup_case(self, case_config: CaseConfig) -> bool:
        """清理 Case（应急清理）
        
        Args:
            case_config: Case 配置
            
        Returns:
            bool: 成功标志
        """
        try:
            # 清理所有活跃故障
            active_faults = self.state_manager.get_active_faults()
            
            for fault in active_faults:
                if fault.case_name == case_config.name:
                    if fault.fault_id in self._running_faults:
                        injector = self._running_faults[fault.fault_id]
                        injector.recover(fault.fault_id)
                        del self._running_faults[fault.fault_id]
                    
                    self.state_manager.mark_recovered(fault.fault_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Case 清理失败：{e}")
            return False
    
    def _get_remote_executor(self, env_config):
        """获取远程执行器"""
        from ..utils.remote import get_ssh_pool
        pool = get_ssh_pool()
        return pool.get_connection(
            host=env_config.ip,
            port=env_config.port,
            user=env_config.user,
            passwd=env_config.passwd
        )
    
    def _get_pods_by_pattern(self, pod_manager, name_pattern: str, namespace: str) -> List[Dict]:
        """根据模式获取 Pod 列表
        
        Args:
            pod_manager: Pod 管理器
            name_pattern: 名称模式或过滤规则
            namespace: 命名空间
            
        Returns:
            List[Dict]: Pod 信息列表
        """
        matched_pods = []
        
        if name_pattern in POD_FILTER_RULES:
            method_name, filter_arg = POD_FILTER_RULES[name_pattern]
            method = getattr(pod_manager, method_name)
            pods = method(namespace, filter_arg)
            for pod_name, pod_ip in pods.items():
                matched_pods.append({"name": pod_name, "ip": pod_ip, "namespace": namespace})
        else:
            pods = pod_manager.get_pods_by_name_pattern(name_pattern, namespace)
            for pod in pods:
                pod["namespace"] = namespace
                matched_pods.append(pod)
        
        return matched_pods
    
    def _get_targets(self, case_config: CaseConfig, effective_config: Dict) -> List[Dict]:
        """获取目标信息列表
        
        Args:
            case_config: Case 配置
            effective_config: 有效配置
            
        Returns:
            List[Dict]: 目标信息列表
        """
        if case_config.type == "computer":
            computer_match = case_config.pod_match
            env_names = computer_match.get("name", [])
            if not isinstance(env_names, list):
                env_names = [env_names]
            
            targets = [{
                "name": env_names,
                "type": "computer"
            }]
            return targets
        
        if case_config.type == "cmd":
            cmd_match = case_config.pod_match
            env_name = case_config.environment
            
            if isinstance(env_name, list):
                env_names = env_name
            else:
                env_names = [env_name]
            
            targets = [{
                "name": env_names,
                "type": "cmd"
            }]
            return targets
        
        if case_config.type == "sw":
            sw_match = case_config.pod_match
            env_name = case_config.environment
            
            targets = [{
                "name": env_name,
                "type": "sw"
            }]
            return targets
        
        pod_match = case_config.pod_match
        namespace = effective_config.get("namespace")
        targets = []
        
        if pod_match.get("type") == "special":
            special_type = pod_match.get("special_type")
            role = pod_match.get("role")
            
            from ..utils.pod import PodManager
            pod_manager = PodManager(
                self._get_remote_executor(
                    self.config_manager.get_environment(case_config.environment)
                ),
                self.logger,
                self.config_manager
            )
            
            special_pod = pod_manager.get_special_pod(
                special_type, role, namespace
            )
            
            if special_pod:
                targets.append({
                    "name": special_pod["name"],
                    "ip": special_pod["ip"],
                    "namespace": namespace
                })
            
            return targets
        
        pod_name = pod_match.get("name")
        if pod_name:
            from ..utils.pod import PodManager
            pod_manager = PodManager(
                self._get_remote_executor(
                    self.config_manager.get_environment(case_config.environment)
                ),
                self.logger,
                self.config_manager
            )
            
            name_patterns = pod_name if isinstance(pod_name, list) else [pod_name]
            
            for name_pattern in name_patterns:
                matched_pods = self._get_pods_by_pattern(pod_manager, name_pattern, namespace)
                if matched_pods:
                    selected_pods = self._select_pods(matched_pods, pod_match)
                    targets.extend(selected_pods)
        
        return targets
    
    def _select_pods(self, pods: List[Dict], pod_match: Dict) -> List[Dict]:
        """选择 Pod
        
        Args:
            pods: Pod 列表
            pod_match: Pod 匹配配置
            
        Returns:
            List[Dict]: 选择的 Pod 列表
        """
        import random
        
        # 获取配置参数
        random_select = pod_match.get("random", True)  # 默认随机选择
        count = pod_match.get("count", 1)  # 默认选择 1 个
        
        # 如果没有 Pod，返回空列表
        if not pods:
            return []
        
        # 如果只需要一个 Pod
        if count == 1:
            if random_select:
                # 随机选择一个
                selected = random.choice(pods)
                self.logger.info(f"随机选择 Pod: {selected['name']}")
                return [selected]
            else:
                # 返回第一个
                return [pods[0]]
        
        # 如果需要多个 Pod
        if random_select:
            # 随机选择指定数量
            if count >= len(pods):
                self.logger.info(f"选择所有 {len(pods)} 个 Pod")
                return pods
            else:
                selected = random.sample(pods, count)
                self.logger.info(f"随机选择 {count} 个 Pod: {[p['name'] for p in selected]}")
                return selected
        else:
            # 选择前 count 个
            selected = pods[:count]
            self.logger.info(f"选择前 {count} 个 Pod: {[p['name'] for p in selected]}")
            return selected
    
    def _get_target(self, case_config: CaseConfig, effective_config: Dict) -> Dict:
        """获取目标信息（向后兼容）
        
        Args:
            case_config: Case 配置
            effective_config: 有效配置
            
        Returns:
            Dict: 目标信息
        """
        targets = self._get_targets(case_config, effective_config)
        return targets[0] if targets else {
            "name": case_config.pod_match.get("name"),
            "namespace": effective_config.get("namespace")
        }
    
    def _parse_duration(self, duration: str) -> float:
        """解析时长
        
        Args:
            duration: 时长字符串（如 "60s", "5m"）
            
        Returns:
            float: 秒数
        """
        duration = duration.lower()
        if duration.endswith('s'):
            return float(duration[:-1])
        elif duration.endswith('m'):
            return float(duration[:-1]) * 60
        elif duration.endswith('h'):
            return float(duration[:-1]) * 3600
        else:
            return float(duration)
    
    def _execute_auto_clear(self, case_config: CaseConfig, env_config):
        """执行自动清除
        
        Args:
            case_config: Case 配置
            env_config: 环境配置
        """
        try:
            # 创建远程执行器
            ssh_executor = self._get_remote_executor(env_config)
            
            # 连接到远程主机
            if not ssh_executor.connect():
                self.logger.error(f"无法连接到环境 {case_config.environment}")
                return
            
            try:
                # 获取 Pod 管理器
                from ..utils.pod import PodManager
                pod_manager = PodManager(ssh_executor, self.logger)
                
                # 获取有效配置
                defaults = self.config_manager.get_defaults()
                effective_config = case_config.get_effective_config(env_config, defaults)
                
                # 获取该节点上的 pod 列表
                namespace = effective_config.get("namespace", self.config_manager.get_namespace())
                pods = pod_manager.get_pods_by_nodename(namespace, env_config.nodename)
                
                if not pods:
                    self.logger.info(f"环境 {case_config.environment} 的节点 {env_config.nodename} 中没有找到 pod")
                else:
                    self.logger.info(f"找到 {len(pods)} 个 pod")
                    
                    # 创建网络故障清除器
                    from ..clearer.network import NetworkFaultClearerFactory
                    network_clearer = NetworkFaultClearerFactory.create_clearer("pod", ssh_executor, self.logger, self.config_manager)
                    
                    # 清除每个 pod 的网络故障
                    success_count = 0
                    failure_count = 0
                    
                    for pod_name in pods.keys():
                        target = {
                            "name": pod_name,
                            "namespace": namespace
                        }
                        parameters = {
                            "device": case_config.parameters.get("device", "eth0"),
                            "namespace": namespace
                        }
                        
                        if network_clearer.clear_fault(target, parameters):
                            success_count += 1
                        else:
                            failure_count += 1
                    
                    self.logger.info(f"环境 {case_config.environment} 网络故障清除完成：成功 {success_count}, 失败 {failure_count}")
            finally:
                # 清除完成后断开连接
                ssh_executor.disconnect()
        except Exception as e:
            self.logger.error(f"执行 auto_clear 时发生错误：{e}")


class CaseManager:
    """Case 管理器"""
    
    def __init__(self, case_executor: "CaseExecutor", logger: "LoggerProtocol"):
        """初始化 Case 管理器
        
        Args:
            case_executor: Case 执行器
            logger: 日志记录器
        """
        self.case_executor = case_executor
        self.logger = logger
    
    def load_case(self, yaml_file: str) -> Optional[CaseConfig]:
        """加载 Case YAML 文件
        
        Args:
            yaml_file: YAML 文件路径
            
        Returns:
            Optional[CaseConfig]: Case 配置对象
        """
        try:
            return CaseConfig.from_yaml(yaml_file)
        except Exception as e:
            self.logger.error(f"加载 Case 文件失败：{e}")
            return None
    
    def execute_single(self, yaml_file: str) -> bool:
        """执行单个 Case
        
        Args:
            yaml_file: YAML 文件路径
            
        Returns:
            bool: 成功标志
        """
        case_config = self.load_case(yaml_file)
        if not case_config:
            return False
        
        return self.case_executor.execute_case(case_config)
    
    def execute_batch(self, case_dir: str, pattern: str = "*.yaml") -> Dict[str, bool]:
        """批量执行 Case
        
        Args:
            case_dir: Case 目录
            pattern: 文件匹配模式
            
        Returns:
            Dict[str, bool]: {Case 文件：成功标志}
        """
        results = {}
        case_path = Path(case_dir)
        
        if not case_path.exists():
            self.logger.error(f"Case 目录不存在：{case_dir}")
            return results
        
        # 递归查找所有匹配的 YAML 文件
        yaml_files = list(case_path.rglob(pattern))
        
        self.logger.info(f"找到 {len(yaml_files)} 个 Case 文件")
        
        for yaml_file in yaml_files:
            self.logger.info(f"执行 Case: {yaml_file}")
            success = self.execute_single(str(yaml_file))
            results[str(yaml_file)] = success
        
        # 统计结果
        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed
        
        self.logger.info(f"批量执行完成：总计 {total}, 通过 {passed}, 失败 {failed}")
        
        return results
