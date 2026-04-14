"""故障注入模块
提供故障注入的抽象和实现
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Union, Tuple
from datetime import datetime
import paramiko
import time
import random
import re

from ..constants import VALID_SIGNALS
from ..constants import (
    SW_SSH_TIMEOUT, SW_CHANNEL_WAIT, SW_CMD_WAIT,
    SW_READ_INTERVAL, SW_BUFFER_SIZE
)
from .registry import FaultInjectorRegistry


class FaultInjector(ABC):
    """故障注入器抽象类"""
    
    @abstractmethod
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入故障
        
        Args:
            target: 目标信息（如 Pod 信息）
            parameters: 故障参数
            
        Returns:
            bool: 成功标志
        """
        pass
    
    @abstractmethod
    def recover(self, fault_id: str) -> bool:
        """恢复故障
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        pass
    
    @abstractmethod
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID
        
        Returns:
            Optional[str]: 故障 ID
        """
        pass


@FaultInjectorRegistry.register("network")
class NetworkFaultInjector(FaultInjector):
    """网络故障注入器"""
    
    def __init__(self, remote_executor, logger, config_manager=None):
        """初始化网络故障注入器
        
        Args:
            remote_executor: 远程执行器
            logger: 日志记录器
            config_manager: 配置管理器（可选，用于获取默认网卡设备名）
        """
        self.remote_executor = remote_executor
        self.logger = logger
        self.config_manager = config_manager
        self.fault_id = None
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入网络故障"""
        fault_type = parameters.get("fault_type", "delay")
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        timestamp = int(datetime.now().timestamp())
        self.fault_id = f"{fault_type}_{pod_name}_{namespace}_{timestamp}"
        
        try:
            if fault_type == "delay":
                return self._inject_delay(target, parameters)
            elif fault_type == "loss":
                return self._inject_loss(target, parameters)
            elif fault_type == "corrupt":
                return self._inject_corrupt(target, parameters)
            elif fault_type == "duplicate":
                return self._inject_duplicate(target, parameters)
            elif fault_type == "reorder":
                return self._inject_reorder(target, parameters)
            else:
                raise ValueError(f"未知的故障类型：{fault_type}")
        except Exception as e:
            self.logger.error(f"网络故障注入失败：{e}")
            return False
    
    def _inject_delay(self, target: Dict, parameters: Dict) -> bool:
        """注入网络延迟
        
        Args:
            target: 目标 Pod 信息
            parameters: 故障参数，支持：
                - device: 网卡名，默认 eth0
                - time: 固定延迟基础时间，如 "300ms"，默认随机 100ms~1000ms
                - jitter: 随机抖动最大幅度，如 "100ms"，默认随机 0ms~100ms
                - correlation: 相关性，如 "20%"，默认随机 20%~90%
                - distribution: 分布模型，如 "paretonormal"，默认随机选择
                
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        device = self._get_device(parameters)
        delay_params = self._build_delay_params(parameters)
        
        result = self._get_pause_container_id(pod_name, namespace)
        if not result:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 ID")
            return False
        
        pause_container_id, node_executor = result
        
        pause_container_pid = self._get_container_pid(pause_container_id, node_executor)
        if not pause_container_pid:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 PID")
            return False
        
        tc_command = self._build_tc_delay_command(device, delay_params)
        command = f"nsenter -t {pause_container_pid} -n {tc_command}"
        
        self.logger.info(f"为 Pod {pod_name} 注入网络延迟")
        self.logger.info(f"延迟参数: {delay_params}")
        self.logger.info(f"tc 命令: {tc_command}")
        
        success, output = node_executor.execute(command)
        if not success:
            self.logger.error(f"网络延迟注入失败：{output}")
            return False
        
        self.logger.info(f"网络延迟注入成功")
        return True
    
    def _get_device(self, parameters: Dict) -> str:
        """获取网卡设备名
        
        优先级：参数 > config.yaml > 默认值 eth0
        
        Args:
            parameters: 参数字典
            
        Returns:
            str: 网卡设备名
        """
        device = parameters.get("device")
        if device:
            return device
        
        if self.config_manager:
            config_device = self.config_manager.config.get("device")
            if config_device:
                return config_device
        
        return "eth0"
    
    def _build_delay_params(self, parameters: Dict) -> Dict[str, str]:
        """构建延迟参数
        
        Args:
            parameters: 原始参数字典
            
        Returns:
            Dict[str, str]: 构建后的延迟参数
        """
        time_val = self._parse_time_param(parameters.get("time"))
        jitter_val = self._parse_jitter_param(parameters.get("jitter"))
        correlation_val = self._parse_correlation_param(parameters.get("correlation"))
        distribution_val = self._parse_distribution_param(parameters.get("distribution"))
        
        return {
            "time": time_val,
            "jitter": jitter_val,
            "correlation": correlation_val,
            "distribution": distribution_val
        }
    
    def _parse_time_param(self, time_param: Optional[Union[str, List[str]]]) -> str:
        """解析时间参数
        
        Args:
            time_param: 时间参数，可以是字符串、列表或 None
            
        Returns:
            str: 时间值（如 "300ms"）
        """
        if time_param is None:
            return f"{random.randint(100, 1000)}ms"
        
        if isinstance(time_param, list):
            min_val, max_val = self._parse_time_range(time_param)
            return f"{random.randint(min_val, max_val)}ms"
        
        return str(time_param)
    
    def _parse_time_range(self, time_range: List[str]) -> Tuple[int, int]:
        """解析时间范围
        
        Args:
            time_range: 时间范围列表，如 ["200ms", "800ms"]
            
        Returns:
            Tuple[int, int]: (最小值, 最大值) 单位毫秒
        """
        if len(time_range) != 2:
            self.logger.warning(f"时间范围格式不正确: {time_range}, 使用默认值")
            return (100, 1000)
        
        min_val = self._extract_time_value(time_range[0])
        max_val = self._extract_time_value(time_range[1])
        
        return (min_val, max_val)
    
    def _extract_time_value(self, time_str: str) -> int:
        """从时间字符串中提取数值
        
        Args:
            time_str: 时间字符串，如 "300ms"
            
        Returns:
            int: 时间值（毫秒）
        """
        match = re.match(r'(\d+)(ms|s)?', str(time_str))
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit == 's':
                value *= 1000
            return value
        return 100
    
    def _parse_jitter_param(self, jitter_param: Optional[Union[str, List[str]]]) -> Optional[str]:
        """解析抖动参数
        
        Args:
            jitter_param: 抖动参数，可以是字符串、列表或 None
            
        Returns:
            Optional[str]: 抖动值（如 "100ms"），None 表示不设置抖动
        """
        if jitter_param is None:
            return f"{random.randint(0, 100)}ms"
        
        if isinstance(jitter_param, list):
            min_val, max_val = self._parse_time_range(jitter_param)
            return f"{random.randint(min_val, max_val)}ms"
        
        return str(jitter_param)
    
    def _parse_correlation_param(self, correlation_param: Optional[Union[str, List[str]]]) -> Optional[str]:
        """解析相关性参数
        
        Args:
            correlation_param: 相关性参数，可以是字符串、列表或 None
            
        Returns:
            Optional[str]: 相关性值（如 "20%"），None 表示不设置相关性
        """
        if correlation_param is None:
            return f"{random.randint(20, 90)}%"
        
        if isinstance(correlation_param, list):
            min_val, max_val = self._parse_percentage_range(correlation_param)
            return f"{random.randint(min_val, max_val)}%"
        
        return str(correlation_param)
    
    def _parse_percentage_range(self, range_list: List[str]) -> Tuple[int, int]:
        """解析百分比范围
        
        Args:
            range_list: 百分比范围列表，如 ["10%", "90%"]
            
        Returns:
            Tuple[int, int]: (最小值, 最大值)
        """
        if len(range_list) != 2:
            self.logger.warning(f"百分比范围格式不正确: {range_list}, 使用默认值")
            return (20, 90)
        
        min_val = self._extract_percentage_value(range_list[0])
        max_val = self._extract_percentage_value(range_list[1])
        
        return (min_val, max_val)
    
    def _extract_percentage_value(self, percentage_str: str) -> int:
        """从百分比字符串中提取数值
        
        Args:
            percentage_str: 百分比字符串，如 "20%"
            
        Returns:
            int: 百分比值
        """
        match = re.match(r'(\d+)%?', str(percentage_str))
        if match:
            return int(match.group(1))
        return 20
    
    def _parse_distribution_param(self, distribution_param: Optional[str]) -> Optional[str]:
        """解析分布模型参数
        
        Args:
            distribution_param: 分布模型参数
            
        Returns:
            Optional[str]: 分布模型名称，None 表示不设置分布
        """
        valid_distributions = ["uniform", "normal", "pareto", "paretonormal"]
        
        if distribution_param is None:
            return random.choice(valid_distributions)
        
        if distribution_param in valid_distributions:
            return distribution_param
        
        self.logger.warning(f"无效的分布模型: {distribution_param}, 随机选择")
        return random.choice(valid_distributions)
    
    def _build_tc_delay_command(self, device: str, params: Dict[str, str]) -> str:
        """构建 tc 延迟命令
        
        Args:
            device: 网卡设备名
            params: 延迟参数字典
            
        Returns:
            str: tc 命令
        """
        time_val = params["time"]
        jitter_val = params.get("jitter")
        correlation_val = params.get("correlation")
        distribution_val = params.get("distribution")
        
        cmd_parts = [f"tc qdisc add dev {device} root netem delay {time_val}"]
        
        if jitter_val:
            cmd_parts.append(jitter_val)
            
            if correlation_val:
                cmd_parts.append(correlation_val)
                
                if distribution_val:
                    cmd_parts.append(f"distribution {distribution_val}")
        
        return " ".join(cmd_parts)
    
    def _parse_ecn_param(self, ecn_param: Optional[Union[str, bool]]) -> bool:
        """解析 ECN 参数
        
        Args:
            ecn_param: ECN 参数，可以是 true/false/random/True/False/None
            
        Returns:
            bool: ECN 标志
        """
        if ecn_param is None or ecn_param == "random":
            return random.choice([True, False])
        
        if isinstance(ecn_param, bool):
            return ecn_param
        
        if isinstance(ecn_param, str):
            if ecn_param.lower() == "true":
                return True
            elif ecn_param.lower() == "false":
                return False
            elif ecn_param.lower() == "random":
                return random.choice([True, False])
        
        return False
    
    def _build_loss_params(self, parameters: Dict) -> tuple:
        """构建丢包参数
        
        随机选择一种丢包模型并构建参数
        
        Args:
            parameters: 原始参数字典
            
        Returns:
            tuple: (模型名称, 参数字典)
        """
        model_config = parameters.get("model", {})
        
        available_models = ["random", "state", "gemodel"]
        configured_models = [m for m in available_models if m in model_config]
        
        if not configured_models:
            model_name = random.choice(available_models)
        else:
            model_name = random.choice(configured_models)
        
        model_params = model_config.get(model_name, {})
        
        if model_name == "random":
            params = self._build_loss_params_random(model_params)
        elif model_name == "state":
            params = self._build_loss_params_state(model_params)
        elif model_name == "gemodel":
            params = self._build_loss_params_gemodel(model_params)
        else:
            params = {}
        
        return model_name, params
    
    def _build_loss_params_random(self, model_params: Dict) -> Dict:
        """构建 random 模型参数
        
        Args:
            model_params: 模型参数字典
            
        Returns:
            Dict: 构建后的参数
        """
        percent = model_params.get("percent")
        if percent is None:
            percent = f"{random.randint(10, 50)}%"
        elif isinstance(percent, list):
            percent = self._parse_percent_range(percent)
        
        return {"percent": percent}
    
    def _build_loss_params_state(self, model_params: Dict) -> Dict:
        """构建 state 模型参数
        
        Args:
            model_params: 模型参数字典
            
        Returns:
            Dict: 构建后的参数
        """
        p13 = model_params.get("p13")
        if p13 is None:
            p13 = f"{random.uniform(0.01, 0.5):.2f}%"
        elif isinstance(p13, list):
            p13 = self._parse_percent_range(p13)
        
        p31 = model_params.get("p31")
        if p31 is None:
            p31 = f"{random.randint(1, 5)}%"
        elif isinstance(p31, list):
            p31 = self._parse_percent_range(p31)
        
        p23 = model_params.get("p23")
        if p23 is None:
            p23 = f"{random.randint(30, 80)}%"
        elif isinstance(p23, list):
            p23 = self._parse_percent_range(p23)
        
        p32 = model_params.get("p32")
        if p32 is None:
            p32 = f"{random.randint(10, 30)}%"
        elif isinstance(p32, list):
            p32 = self._parse_percent_range(p32)
        
        p14 = model_params.get("p14")
        if p14 is None:
            p14 = f"{random.uniform(0.01, 0.5):.2f}%"
        elif isinstance(p14, list):
            p14 = self._parse_percent_range(p14)
        
        return {
            "p13": p13,
            "p31": p31,
            "p23": p23,
            "p32": p32,
            "p14": p14
        }
    
    def _build_loss_params_gemodel(self, model_params: Dict) -> Dict:
        """构建 gemodel 模型参数
        
        Args:
            model_params: 模型参数字典
            
        Returns:
            Dict: 构建后的参数
        """
        p = model_params.get("p")
        if p is None:
            p = f"{random.randint(30, 80)}%"
        elif isinstance(p, list):
            p = self._parse_percent_range(p)
        
        pr = model_params.get("pr")
        if pr is None:
            pr = f"{random.randint(70, 90)}%"
        elif isinstance(pr, list):
            pr = self._parse_percent_range(pr)
        
        pr1_h = model_params.get("pr1-h")
        if pr1_h is None:
            pr1_h = f"{random.randint(20, 90)}%"
        elif isinstance(pr1_h, list):
            pr1_h = self._parse_percent_range(pr1_h)
        
        pr1_h1_k = model_params.get("pr1-h1-k")
        if pr1_h1_k is None:
            pr1_h1_k = f"{random.uniform(0.1, 0.5):.2f}%"
        elif isinstance(pr1_h1_k, list):
            pr1_h1_k = self._parse_percent_range(pr1_h1_k)
        
        return {
            "p": p,
            "pr": pr,
            "pr1-h": pr1_h,
            "pr1-h1-k": pr1_h1_k
        }
    
    def _parse_percent_range(self, percent_range: List[str]) -> str:
        """解析百分比范围
        
        Args:
            percent_range: 百分比范围，如 ["10%", "90%"]
            
        Returns:
            str: 随机选择的百分比值
        """
        min_val = self._parse_percent_value(percent_range[0])
        max_val = self._parse_percent_value(percent_range[1])
        
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        
        if min_val < 1:
            value = random.uniform(min_val, max_val)
            return f"{value:.2f}%"
        else:
            value = random.randint(int(min_val), int(max_val))
            return f"{value}%"
    
    def _parse_percent_value(self, percent_str: str) -> float:
        """解析百分比值
        
        Args:
            percent_str: 百分比字符串，如 "10%", "0.5%"
            
        Returns:
            float: 百分比数值
        """
        return float(percent_str.strip("%"))
    
    def _build_tc_loss_command(self, device: str, model_name: str, params: Dict, ecn: bool) -> str:
        """构建 tc 丢包命令
        
        Args:
            device: 网卡设备名
            model_name: 模型名称
            params: 丢包参数字典
            ecn: ECN 标志
            
        Returns:
            str: tc 命令
        """
        cmd_parts = [f"tc qdisc add dev {device} root netem loss {model_name}"]
        
        if model_name == "random":
            cmd_parts.append(params["percent"])
        elif model_name == "state":
            p13 = params["p13"]
            p31 = params["p31"]
            p23 = params["p23"]
            p32 = params["p32"]
            p14 = params["p14"]
            cmd_parts.extend([p13, p31, p23, p32, p14])
        elif model_name == "gemodel":
            p = params["p"]
            pr = params["pr"]
            pr1_h = params["pr1-h"]
            pr1_h1_k = params["pr1-h1-k"]
            cmd_parts.extend([p, pr, pr1_h, pr1_h1_k])
        
        if ecn:
            cmd_parts.append("ecn")
        
        return " ".join(cmd_parts)
    
    def _inject_loss(self, target: Dict, parameters: Dict) -> bool:
        """注入网络丢包
        
        Args:
            target: 目标 Pod 信息
            parameters: 故障参数，支持：
                - device: 网卡名，默认从 config.yaml 获取或 eth0
                - ecn: true/false/random，默认 random
                - model: 丢包模型配置
                    - random: 独立随机丢包模型
                        - percent: 丢包率，默认随机 10%~50%
                    - state: 状态马尔可夫模型（最高 4 态）
                        - p13, p31, p23, p32, p14: 各状态转移概率
                    - gemodel: 吉尔伯特‑埃利奥特模型
                        - p, pr, pr1-h, pr1-h1-k: 模型参数
                
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        device = self._get_device(parameters)
        ecn = self._parse_ecn_param(parameters.get("ecn"))
        model_name, loss_params = self._build_loss_params(parameters)
        
        result = self._get_pause_container_id(pod_name, namespace)
        if not result:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 ID")
            return False
        
        pause_container_id, node_executor = result
        
        pause_container_pid = self._get_container_pid(pause_container_id, node_executor)
        if not pause_container_pid:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 PID")
            return False
        
        tc_command = self._build_tc_loss_command(device, model_name, loss_params, ecn)
        command = f"nsenter -t {pause_container_pid} -n {tc_command}"
        
        self.logger.info(f"为 Pod {pod_name} 注入网络丢包")
        self.logger.info(f"丢包模型: {model_name}")
        self.logger.info(f"丢包参数: {loss_params}")
        self.logger.info(f"ECN: {ecn}")
        self.logger.info(f"tc 命令: {tc_command}")
        
        success, output = node_executor.execute(command)
        if not success:
            self.logger.error(f"网络丢包注入失败：{output}")
            return False
        
        self.logger.info(f"网络丢包注入成功")
        return True
    
    def _inject_corrupt(self, target: Dict, parameters: Dict) -> bool:
        """注入网络数据包破坏
        
        Args:
            target: 目标 Pod 信息
            parameters: 故障参数，支持：
                - device: 网卡名，默认从 config.yaml 获取或 eth0
                - percent: 被损坏的数据包所占比例，默认随机 1%~90%
                - correlation: 损坏事件之间的相关性，默认随机 1%~90%
                
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        self.logger.info(f"[DEBUG] ========== 开始注入网络数据包破坏 ==========")
        self.logger.info(f"[DEBUG] Pod名称: {pod_name}")
        self.logger.info(f"[DEBUG] 命名空间: {namespace}")
        
        device = self._get_device(parameters)
        self.logger.info(f"[DEBUG] 网卡设备: {device}")
        
        percent = self._parse_corrupt_percent_param(parameters.get("percent"))
        correlation = self._parse_corrupt_correlation_param(parameters.get("correlation"))
        self.logger.info(f"[DEBUG] 损坏比例: {percent}, 相关性: {correlation}")
        
        self.logger.info(f"[DEBUG] 获取 pause 容器 ID...")
        result = self._get_pause_container_id(pod_name, namespace)
        if not result:
            self.logger.error(f"[DEBUG] 无法获取 Pod {pod_name} 的 pause 容器 ID")
            return False
        
        pause_container_id, node_executor = result
        self.logger.info(f"[DEBUG] pause 容器 ID: {pause_container_id}")
        
        self.logger.info(f"[DEBUG] 获取 pause 容器 PID...")
        pause_container_pid = self._get_container_pid(pause_container_id, node_executor)
        if not pause_container_pid:
            self.logger.error(f"[DEBUG] 无法获取 Pod {pod_name} 的 pause 容器 PID")
            return False
        
        self.logger.info(f"[DEBUG] pause 容器 PID: {pause_container_pid}")
        
        tc_command = self._build_tc_corrupt_command(device, percent, correlation)
        command = f"nsenter -t {pause_container_pid} -n {tc_command}"
        
        self.logger.info(f"[DEBUG] 为 Pod {pod_name} 注入网络数据包破坏")
        self.logger.info(f"[DEBUG] 损坏比例: {percent}")
        self.logger.info(f"[DEBUG] 相关性: {correlation}")
        self.logger.info(f"[DEBUG] tc 命令: {tc_command}")
        self.logger.info(f"[DEBUG] 完整命令: {command}")
        
        self.logger.info(f"[DEBUG] 执行 tc 命令...")
        success, output = node_executor.execute(command)
        if not success:
            self.logger.error(f"[DEBUG] 网络数据包破坏注入失败：{output}")
            return False
        
        self.logger.info(f"[DEBUG] 网络数据包破坏注入成功")
        self.logger.info(f"[DEBUG] ========== 网络数据包破坏注入完成 ==========")
        return True
    
    def _parse_corrupt_percent_param(self, percent_param: Optional[Union[str, List[str]]]) -> str:
        """解析数据包破坏比例参数
        
        Args:
            percent_param: 比例参数，可以是字符串、列表或 None
            
        Returns:
            str: 比例值（如 "1%"）
        """
        if percent_param is None:
            return f"{random.randint(1, 90)}%"
        
        if isinstance(percent_param, list):
            return self._parse_percent_range(percent_param)
        
        return percent_param
    
    def _parse_corrupt_correlation_param(self, correlation_param: Optional[Union[str, List[str]]]) -> str:
        """解析数据包破坏相关性参数
        
        Args:
            correlation_param: 相关性参数，可以是字符串、列表或 None
            
        Returns:
            str: 相关性值（如 "25%"）
        """
        if correlation_param is None:
            return f"{random.randint(1, 90)}%"
        
        if isinstance(correlation_param, list):
            return self._parse_percent_range(correlation_param)
        
        return correlation_param
    
    def _build_tc_corrupt_command(self, device: str, percent: str, correlation: str) -> str:
        """构建 tc 数据包破坏命令
        
        Args:
            device: 网卡设备名
            percent: 损坏比例
            correlation: 相关性
            
        Returns:
            str: tc 命令
        """
        return f"tc qdisc add dev {device} root netem corrupt {percent} {correlation}"
    
    def _inject_duplicate(self, target: Dict, parameters: Dict) -> bool:
        """注入网络数据包重复
        
        Args:
            target: 目标 Pod 信息
            parameters: 故障参数，支持：
                - device: 网卡名，默认从 config.yaml 获取或 eth0
                - percent: 被复制的数据包所占比例，默认随机 0.5%~10%
                - correlation: 重复事件之间的相关性，默认随机 1%~90%
                
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        device = self._get_device(parameters)
        percent = self._parse_duplicate_percent_param(parameters.get("percent"))
        correlation = self._parse_duplicate_correlation_param(parameters.get("correlation"))
        
        result = self._get_pause_container_id(pod_name, namespace)
        if not result:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 ID")
            return False
        
        pause_container_id, node_executor = result
        
        pause_container_pid = self._get_container_pid(pause_container_id, node_executor)
        if not pause_container_pid:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 PID")
            return False
        
        tc_command = self._build_tc_duplicate_command(device, percent, correlation)
        command = f"nsenter -t {pause_container_pid} -n {tc_command}"
        
        self.logger.info(f"为 Pod {pod_name} 注入网络数据包重复")
        self.logger.info(f"重复比例: {percent}")
        self.logger.info(f"相关性: {correlation}")
        self.logger.info(f"tc 命令: {tc_command}")
        
        success, output = node_executor.execute(command)
        if not success:
            self.logger.error(f"网络数据包重复注入失败：{output}")
            return False
        
        self.logger.info(f"网络数据包重复注入成功")
        return True
    
    def _parse_duplicate_percent_param(self, percent_param: Optional[Union[str, List[str]]]) -> str:
        """解析数据包重复比例参数
        
        Args:
            percent_param: 比例参数，可以是字符串、列表或 None
            
        Returns:
            str: 比例值（如 "0.5%"）
        """
        if percent_param is None:
            value = random.uniform(0.5, 10)
            return f"{value:.1f}%"
        
        if isinstance(percent_param, list):
            return self._parse_percent_range(percent_param)
        
        return percent_param
    
    def _parse_duplicate_correlation_param(self, correlation_param: Optional[Union[str, List[str]]]) -> str:
        """解析数据包重复相关性参数
        
        Args:
            correlation_param: 相关性参数，可以是字符串、列表或 None
            
        Returns:
            str: 相关性值（如 "25%"）
        """
        if correlation_param is None:
            return f"{random.randint(1, 90)}%"
        
        if isinstance(correlation_param, list):
            return self._parse_percent_range(correlation_param)
        
        return correlation_param
    
    def _build_tc_duplicate_command(self, device: str, percent: str, correlation: str) -> str:
        """构建 tc 数据包重复命令
        
        Args:
            device: 网卡设备名
            percent: 重复比例
            correlation: 相关性
            
        Returns:
            str: tc 命令
        """
        return f"tc qdisc add dev {device} root netem duplicate {percent} {correlation}"
    
    def _inject_reorder(self, target: Dict, parameters: Dict) -> bool:
        """注入网络数据包重排序
        
        Args:
            target: 目标 Pod 信息
            parameters: 故障参数，支持：
                - device: 网卡名，默认从 config.yaml 获取或 eth0
                - percent: 立即发送（不延迟）的包所占比例，默认随机 0.5%~10%
                - correlation: 重排序事件的相关性，默认随机 1%~90%
                - gap: 指定重排序的周期性模式，默认随机 1~100
                
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        device = self._get_device(parameters)
        percent = self._parse_reorder_percent_param(parameters.get("percent"))
        correlation = self._parse_reorder_correlation_param(parameters.get("correlation"))
        gap = self._parse_reorder_gap_param(parameters.get("gap"))
        
        result = self._get_pause_container_id(pod_name, namespace)
        if not result:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 ID")
            return False
        
        pause_container_id, node_executor = result
        
        pause_container_pid = self._get_container_pid(pause_container_id, node_executor)
        if not pause_container_pid:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 PID")
            return False
        
        tc_command = self._build_tc_reorder_command(device, percent, correlation, gap)
        command = f"nsenter -t {pause_container_pid} -n {tc_command}"
        
        self.logger.info(f"为 Pod {pod_name} 注入网络数据包重排序")
        self.logger.info(f"重排序比例: {percent}")
        self.logger.info(f"相关性: {correlation}")
        self.logger.info(f"Gap: {gap}")
        self.logger.info(f"tc 命令: {tc_command}")
        
        success, output = node_executor.execute(command)
        if not success:
            self.logger.error(f"网络数据包重排序注入失败：{output}")
            return False
        
        self.logger.info(f"网络数据包重排序注入成功")
        return True
    
    def _parse_reorder_percent_param(self, percent_param: Optional[Union[str, List[str]]]) -> str:
        """解析数据包重排序比例参数
        
        Args:
            percent_param: 比例参数，可以是字符串、列表或 None
            
        Returns:
            str: 比例值（如 "0.5%"）
        """
        if percent_param is None:
            value = random.uniform(0.5, 10)
            return f"{value:.1f}%"
        
        if isinstance(percent_param, list):
            return self._parse_percent_range(percent_param)
        
        return percent_param
    
    def _parse_reorder_correlation_param(self, correlation_param: Optional[Union[str, List[str]]]) -> str:
        """解析数据包重排序相关性参数
        
        Args:
            correlation_param: 相关性参数，可以是字符串、列表或 None
            
        Returns:
            str: 相关性值（如 "25%"）
        """
        if correlation_param is None:
            return f"{random.randint(1, 90)}%"
        
        if isinstance(correlation_param, list):
            return self._parse_percent_range(correlation_param)
        
        return correlation_param
    
    def _parse_reorder_gap_param(self, gap_param: Optional[Union[int, List[int]]]) -> int:
        """解析数据包重排序 gap 参数
        
        Args:
            gap_param: gap 参数，可以是整数、列表或 None
            
        Returns:
            int: gap 值（如 5）
        """
        if gap_param is None:
            return random.randint(1, 100)
        
        if isinstance(gap_param, list):
            min_val = int(gap_param[0])
            max_val = int(gap_param[1])
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            return random.randint(min_val, max_val)
        
        return int(gap_param)
    
    def _build_tc_reorder_command(self, device: str, percent: str, correlation: str, gap: int) -> str:
        """构建 tc 数据包重排序命令
        
        Args:
            device: 网卡设备名
            percent: 重排序比例
            correlation: 相关性
            gap: 重排序周期
            
        Returns:
            str: tc 命令
        """
        return f"tc qdisc add dev {device} root netem delay 100ms reorder {percent} {correlation} gap {gap}"
    
    def _get_pause_container_id_and_executor(self, pod_name: str, namespace: str = None) -> Optional[Tuple[str, object]]:
        """获取 Pod 的 pause 容器 ID 和节点执行器
        
        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            
        Returns:
            Optional[Tuple[str, object]]: (pause 容器 ID, 节点执行器) 或 None
        """
        self.logger.info(f"获取 Pod {pod_name} 的 pause 容器 ID")
        
        # 获取 Pod 所在的节点
        from ..utils.pod import PodManager
        pod_manager = PodManager(self.remote_executor, self.logger, self.config_manager)
        node_name = pod_manager.get_pod_node(pod_name, namespace)
        
        if not node_name:
            self.logger.error(f"无法获取 Pod {pod_name} 所在的节点")
            return None
        
        self.logger.info(f"Pod {pod_name} 运行在节点 {node_name}")
        
        # 根据节点名称找到对应的 environment
        node_executor = self._get_executor_by_node(node_name)
        if not node_executor:
            self.logger.error(f"无法找到节点 {node_name} 对应的执行器")
            return None
        
        # 构建 docker ps 命令
        docker_cmd = f"docker ps | grep '{pod_name}' | grep k8s_POD | awk '{{print $1}}'"
        
        # 在正确的节点上执行命令
        success, output = node_executor.execute(docker_cmd)
        
        if not success:
            self.logger.error(f"执行 docker ps 命令失败")
            self.logger.error(f"命令输出: {output}")
            return None
        
        if not output or not output.strip():
            self.logger.error(f"未找到 Pod {pod_name} 的 pause 容器")
            self.logger.error(f"尝试查看所有容器: docker ps | grep '{pod_name}'")
            
            # 尝试查看所有相关容器
            debug_cmd = f"docker ps | grep '{pod_name}'"
            debug_success, debug_output = node_executor.execute(debug_cmd)
            if debug_success and debug_output:
                self.logger.error(f"相关容器列表:\n{debug_output}")
            else:
                self.logger.error(f"未找到任何相关容器")
            
            return None
        
        # 解析输出，提取容器 ID
        container_id = output.strip().split('\n')[0]  # 取第一行
        self.logger.info(f"解析后的 pause 容器 ID: {container_id}")
        
        return (container_id, node_executor)
    
    def _get_pause_container_id(self, pod_name: str, namespace: str = None) -> Optional[Tuple[str, object]]:
        """获取 Pod 的 pause 容器 ID 和节点执行器（向后兼容的别名）
        
        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            
        Returns:
            Optional[Tuple[str, object]]: (pause 容器 ID, 节点执行器) 或 None
        """
        return self._get_pause_container_id_and_executor(pod_name, namespace)
    
    def _get_executor_by_node(self, node_name: str):
        """根据节点名称获取对应的执行器
        
        Args:
            node_name: 节点名称
            
        Returns:
            执行器（如果找到）或 None
        """
        if not self.config_manager:
            self.logger.error("配置管理器未初始化")
            return None
        
        # 遍历所有环境，找到匹配的节点
        environments = self.config_manager.config.get("environments", {})
        
        for env_name, env_config in environments.items():
            if env_config.get("nodename") == node_name:
                self.logger.info(f"找到节点 {node_name} 对应的环境: {env_name}")
                
                # 获取该环境的执行器
                from ..utils.remote import get_ssh_pool
                pool = get_ssh_pool()
                
                executor = pool.get_connection(
                    host=env_config.get("ip"),
                    port=env_config.get("port"),
                    user=env_config.get("user"),
                    passwd=env_config.get("passwd")
                )
                
                if not executor.is_alive() and not executor.connect():
                    self.logger.error(f"无法连接到环境 {env_name}")
                    return None
                
                return executor
        
        self.logger.error(f"未找到节点 {node_name} 对应的环境配置")
        return None
    
    def _get_container_pid(self, container_id: str, node_executor=None) -> Optional[int]:
        """获取容器的 PID
        
        Args:
            container_id: 容器 ID
            node_executor: 节点执行器（可选，如果不提供则使用默认执行器）
            
        Returns:
            Optional[int]: 容器 PID
        """
        self.logger.info(f"获取容器的 PID")
        self.logger.info(f"容器 ID: {container_id}")
        
        # 构建 docker inspect 命令
        docker_cmd = f"docker inspect {container_id} | grep Pid"
        
        # 选择执行器
        executor = node_executor if node_executor else self.remote_executor
        
        # 执行命令
        success, output = executor.execute(docker_cmd)
        
        if not success or not output:
            self.logger.error("无法获取容器 PID")
            return None
        
        # 解析输出，提取 PID
        lines = output.strip().split('\n')
        
        if not lines:
            self.logger.error("命令输出为空")
            return None
        
        # 取第一行，提取 PID 值
        first_line = lines[0]
        
        parts = first_line.split(':')
        if len(parts) < 2:
            self.logger.error("输出格式不正确")
            return None
        
        pid = int(parts[1].strip().strip(',').strip())
        self.logger.info(f"提取的容器 PID: {pid}")
        
        return pid
    
    def recover(self, fault_id: str) -> bool:
        """恢复网络故障"""
        device = "eth0"  # 默认设备
        
        # 获取 Pod 名称和 namespace（从 fault_id 中提取）
        parts = fault_id.split('_')
        if len(parts) >= 3:
            pod_name = parts[1]
            namespace = parts[2]
            
            # 获取 pause 容器 ID 和节点执行器
            result = self._get_pause_container_id(pod_name, namespace)
            if result:
                pause_container_id, node_executor = result
                
                # 获取 pause 容器 PID
                pause_container_pid = self._get_container_pid(pause_container_id, node_executor)
                if pause_container_pid:
                    # 构建恢复命令（使用 nsenter 进入容器网络命名空间）
                    command = f"nsenter -t {pause_container_pid} -n tc qdisc del dev {device} root"
                    
                    self.logger.info(f"恢复网络故障：{fault_id}")
                    
                    # 执行命令
                    success, output = node_executor.execute(command, ignore_errors=True)
                    if not success:
                        # 如果命令失败，可能是因为没有设置 qdisc，这是正常的
                        self.logger.warning(f"恢复网络故障时发生警告：{output}")
                    
                    return True
        
        # 如果无法获取 Pod 信息，使用默认恢复命令
        command = f"tc qdisc del dev {device} root"
        
        self.logger.info(f"恢复网络故障（使用默认命令）：{fault_id}")
        
        # 执行命令
        success, output = self.remote_executor.execute(command, ignore_errors=True)
        if not success:
            self.logger.warning(f"恢复网络故障时发生警告：{output}")
        
        return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self.fault_id


@FaultInjectorRegistry.register("pod")
class PodFaultInjector(FaultInjector):
    """Pod 故障注入器"""
    
    def __init__(self, remote_executor, logger, config_manager=None):
        """初始化 Pod 故障注入器
        
        Args:
            remote_executor: 远程执行器
            logger: 日志记录器
            config_manager: 配置管理器（用于 stop 操作和获取默认命名空间）
        """
        self.remote_executor = remote_executor
        self.logger = logger
        self.config_manager = config_manager
        self.fault_id = None
        self._stopped_containers = []
    
    def _get_namespace(self, namespace: Optional[str] = None) -> str:
        """获取命名空间
        
        Args:
            namespace: 指定的命名空间（可选）
            
        Returns:
            str: 命名空间（优先级：参数 > 配置文件 > 默认值）
        """
        if namespace:
            return namespace
        if self.config_manager:
            return self.config_manager.get_namespace()
        from ..constants import DEFAULT_NAMESPACE
        return DEFAULT_NAMESPACE
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入 Pod 故障"""
        fault_type = parameters.get("fault_type", "kill")
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        # 生成故障 ID
        timestamp = int(datetime.now().timestamp())
        self.fault_id = f"{fault_type}_{pod_name}_{namespace}_{timestamp}"
        
        try:
            if fault_type == "delete":
                return self._delete_pod(target, parameters)
            elif fault_type == "restart":
                return self._restart_pod(target, parameters)
            elif fault_type == "stop":
                return self._stop_pod(target, parameters)
            else:
                raise ValueError(f"未知的故障类型：{fault_type}")
        except Exception as e:
            self.logger.error(f"Pod 故障注入失败：{e}")
            return False
    
    def _delete_pod(self, target: Dict, parameters: Dict) -> bool:
        """删除 Pod"""
        pod_name = target.get("name")
        namespace = target.get("namespace")
        grace_period = parameters.get("grace_period", 0)
        
        try:
            # 构建 kubectl 命令
            # kubectl不允许同时使用--force和大于0的--grace-period
            if grace_period > 0:
                command = f"kubectl delete pod {pod_name} -n {namespace} --grace-period={grace_period}"
            else:
                command = f"kubectl delete pod {pod_name} -n {namespace} --grace-period=0 --force"
            
            self.logger.info(f"删除 Pod: {pod_name} (namespace: {namespace})")
            
            # 执行命令
            success, output = self.remote_executor.execute(command)
            if success:
                self.logger.info(f"Pod {pod_name} 删除成功")
                return True
            else:
                self.logger.error(f"Pod 删除失败：{output}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除 Pod 时发生错误：{e}")
            return False
    
    def _restart_pod(self, target: Dict, parameters: Dict) -> bool:
        """重启 Pod"""
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        try:
            # 构建 kubectl 命令
            command = f"kubectl rollout restart pod {pod_name} -n {namespace}"
            
            self.logger.info(f"重启 Pod: {pod_name} (namespace: {namespace})")
            
            # 执行命令
            success, output = self.remote_executor.execute(command)
            if success:
                self.logger.info(f"Pod {pod_name} 重启成功")
                return True
            else:
                self.logger.error(f"Pod 重启失败：{output}")
                return False
                
        except Exception as e:
            self.logger.error(f"重启 Pod 时发生错误：{e}")
            return False
    
    def _stop_pod(self, target: Dict, parameters: Dict) -> bool:
        """停止 Pod 容器
        
        Args:
            target: 目标 Pod 信息
            parameters: 故障参数
            
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = self._get_namespace(target.get("namespace"))
        
        try:
            # 1. 获取 Pod 所在的节点名称
            self.logger.info(f"获取 Pod {pod_name} 所在的节点名称")
            kubectl_cmd = f"kubectl get pod {pod_name} -n {namespace} -o wide | grep '{pod_name}' | awk '{{print $7}}'"
            success, output = self.remote_executor.execute(kubectl_cmd)
            
            if not success or not output:
                self.logger.error(f"无法获取 Pod {pod_name} 所在的节点名称")
                return False
            
            node_name = output.strip()
            self.logger.info(f"Pod {pod_name} 所在的节点: {node_name}")
            
            # 2. 根据节点名称找到对应的环境配置
            target_env_config = self._find_environment_by_nodename(node_name)
            if not target_env_config:
                self.logger.error(f"无法找到节点 {node_name} 对应的环境配置")
                return False
            
            # 3. 获取容器 ID
            self.logger.info(f"获取 Pod {pod_name} 的容器 ID")
            kubectl_cmd = f"kubectl get pod {pod_name} -n {namespace} -o jsonpath='{{.status.containerStatuses[0].containerID}}'"
            success, output = target_env_config['executor'].execute(kubectl_cmd)
            
            if not success or not output:
                self.logger.error(f"无法获取 Pod {pod_name} 的容器 ID")
                return False
            
            # 解析容器 ID（格式通常为 docker://<container_id>）
            container_id = output.strip()
            if container_id.startswith("docker://"):
                container_id = container_id[9:]
            
            self.logger.info(f"容器 ID: {container_id}")
            
            # 4. 停止容器
            self.logger.info(f"停止容器 {container_id}")
            docker_cmd = f"docker stop {container_id}"
            success, output = target_env_config['executor'].execute(docker_cmd)
            
            if not success:
                self.logger.error(f"停止容器失败")
                return False
            
            # 记录已停止的容器信息，用于恢复
            self._stopped_containers.append({
                "container_id": container_id,
                "pod_name": pod_name,
                "namespace": namespace,
                "node_name": node_name,
                "env_config": target_env_config
            })
            
            self.logger.info(f"容器 {container_id} 停止成功")
            return True
                
        except Exception as e:
            self.logger.error(f"停止 Pod 容器时发生错误：{e}")
            return False
    
    def _find_environment_by_nodename(self, nodename: str) -> Optional[Dict]:
        """根据节点名称找到对应的环境配置
        
        Args:
            nodename: 节点名称
            
        Returns:
            Optional[Dict]: 环境配置（包含 executor）
        """
        if not self.config_manager:
            self.logger.error("config_manager 未设置，无法查找环境配置")
            return None
        
        # 遍历所有环境，查找 nodename 匹配的环境
        environments = self.config_manager.config.get("environments", {})
        for env_name, env_config in environments.items():
            if env_config.get("nodename") == nodename:
                self.logger.info(f"找到匹配的环境: {env_name}")
                
                from ..utils.remote import get_ssh_pool
                pool = get_ssh_pool()
                executor = pool.get_connection(
                    host=env_config["ip"],
                    port=env_config["port"],
                    user=env_config["user"],
                    passwd=env_config["passwd"]
                )
                
                return {
                    "env_name": env_name,
                    "env_config": env_config,
                    "executor": executor
                }
        
        self.logger.error(f"没有找到 nodename 为 '{nodename}' 的环境配置")
        return None
    
    def recover(self, fault_id: str) -> bool:
        """恢复 Pod 故障
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        # 对于 stop 操作，需要启动容器
        if self._stopped_containers:
            self.logger.info(f"恢复停止的容器，故障 ID: {fault_id}")
            all_success = True
            
            for container_info in self._stopped_containers:
                try:
                    container_id = container_info["container_id"]
                    pod_name = container_info["pod_name"]
                    executor = container_info["env_config"]["executor"]
                    
                    self.logger.info(f"启动容器 {container_id} (Pod: {pod_name})")
                    docker_cmd = f"docker start {container_id}"
                    success, output = executor.execute(docker_cmd)
                    
                    if not success:
                        self.logger.error(f"启动容器 {container_id} 失败")
                        all_success = False
                    else:
                        self.logger.info(f"容器 {container_id} 启动成功")
                        
                except Exception as e:
                    self.logger.error(f"启动容器时发生错误: {e}")
                    all_success = False
            
            # 清空已停止的容器列表
            self._stopped_containers = []
            return all_success
        else:
            # kill 和 restart 操作自动恢复
            self.logger.info(f"Pod 故障自动恢复：{fault_id}")
            return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self.fault_id


@FaultInjectorRegistry.register("computer")
class ComputerFaultInjector(FaultInjector):
    """物理机故障注入器"""
    
    def __init__(self, config_manager, logger):
        """初始化物理机故障注入器
        
        Args:
            config_manager: 配置管理器
            logger: 日志记录器
        """
        self.config_manager = config_manager
        self.logger = logger
        self.fault_id = None
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入物理机故障
        
        Args:
            target: 目标信息
                - name: 环境名称列表（如 ["1_ssh_remote", "2_ssh_remote"]）
            parameters: 故障参数
                - fault_type: 故障类型（reboot）
            
        Returns:
            bool: 成功标志
        """
        fault_type = parameters.get("fault_type", "reboot")
        env_names = target.get("name", [])
        
        if not isinstance(env_names, list):
            env_names = [env_names]
        
        timestamp = int(datetime.now().timestamp())
        self.fault_id = f"{fault_type}_{'_'.join(env_names)}_{timestamp}"
        
        try:
            if fault_type == "reboot":
                return self._reboot_computers(env_names)
            else:
                raise ValueError(f"未知的物理机故障类型：{fault_type}")
        except Exception as e:
            self.logger.error(f"物理机故障注入失败：{e}")
            return False
    
    def _reboot_computers(self, env_names: list) -> bool:
        """重启物理机
        
        Args:
            env_names: 环境名称列表
            
        Returns:
            bool: 成功标志
        """
        all_success = True
        
        for env_name in env_names:
            env_config = self.config_manager.get_environment(env_name)
            if not env_config:
                self.logger.error(f"环境不存在：{env_name}")
                all_success = False
                continue
            
            self.logger.info(f"正在重启物理机：{env_name} ({env_config.ip})")
            
            try:
                from chaos.utils.remote import get_ssh_pool
                
                pool = get_ssh_pool()
                ssh_executor = pool.get_connection(
                    host=env_config.ip,
                    port=env_config.port,
                    user=env_config.user,
                    passwd=env_config.passwd
                )
                
                if not ssh_executor.is_alive() and not ssh_executor.connect():
                    self.logger.error(f"无法连接到环境 {env_name}")
                    all_success = False
                    continue
                
                try:
                    success, output = ssh_executor.execute("reboot", ignore_errors=True)
                    
                    if success or self._is_reboot_success(output):
                        self.logger.info(f"物理机 {env_name} 重启命令已发送")
                    else:
                        self.logger.error(f"物理机 {env_name} 重启失败：{output}")
                        all_success = False
                        
                except Exception as e:
                    error_msg = str(e)
                    if self._is_reboot_success(error_msg):
                        self.logger.info(f"物理机 {env_name} 重启命令已发送（连接断开）")
                    else:
                        self.logger.error(f"执行重启命令时发生错误：{e}")
                        all_success = False
                    
            except Exception as e:
                error_msg = str(e)
                if self._is_reboot_success(error_msg):
                    self.logger.info(f"物理机 {env_name} 重启命令已发送（连接断开）")
                else:
                    self.logger.error(f"重启物理机 {env_name} 时发生错误：{e}")
                    all_success = False
        
        return all_success
    
    def _is_reboot_success(self, output: str) -> bool:
        """判断重启命令是否成功
        
        Args:
            output: 命令输出
            
        Returns:
            bool: 是否成功
        """
        reboot_keywords = [
            "Connection closed",
            "Connection refused", 
            "No route to host",
            "Connection timed out",
            "Software caused connection abort"
        ]
        
        return any(keyword in output for keyword in reboot_keywords)
    
    def recover(self, fault_id: str) -> bool:
        """恢复物理机故障
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        self.logger.info(f"物理机重启后自动恢复：{fault_id}")
        return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self.fault_id


@FaultInjectorRegistry.register("cmd")
class ComputerCmdFaultInjector(FaultInjector):
    """物理机命令执行注入器"""
    
    def __init__(self, config_manager, logger):
        """初始化物理机命令执行注入器
        
        Args:
            config_manager: 配置管理器
            logger: 日志记录器
        """
        self.config_manager = config_manager
        self.logger = logger
        self.fault_id = None
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """在物理机上执行命令
        
        Args:
            target: 目标信息
                - name: 环境名称列表（如 ["1_ssh_remote", "2_ssh_remote"]）
            parameters: 故障参数
                - fault_type: 故障类型（computer_cmd）
                - cmd: 命令列表（支持单个命令或命令列表）
            
        Returns:
            bool: 成功标志
        """
        fault_type = parameters.get("fault_type", "computer_cmd")
        env_names = target.get("name", [])
        cmd_list = parameters.get("cmd", [])
        
        if not isinstance(env_names, list):
            env_names = [env_names]
        
        if not isinstance(cmd_list, list):
            cmd_list = [cmd_list]
        
        timestamp = int(datetime.now().timestamp())
        self.fault_id = f"{fault_type}_{'_'.join(env_names)}_{timestamp}"
        
        try:
            return self._execute_commands_on_environments(env_names, cmd_list)
        except Exception as e:
            self.logger.error(f"命令执行失败：{e}")
            return False
    
    def _execute_commands_on_environments(self, env_names: list, cmd_list: list) -> bool:
        """在多个环境上执行命令列表
        
        Args:
            env_names: 环境名称列表
            cmd_list: 命令列表
            
        Returns:
            bool: 成功标志
        """
        all_success = True
        
        for env_name in env_names:
            env_config = self.config_manager.get_environment(env_name)
            if not env_config:
                self.logger.error(f"环境不存在：{env_name}")
                all_success = False
                continue
            
            self.logger.info(f"在环境 {env_name} ({env_config.ip}) 上执行命令")
            
            try:
                from chaos.utils.remote import get_ssh_pool
                
                pool = get_ssh_pool()
                ssh_executor = pool.get_connection(
                    host=env_config.ip,
                    port=env_config.port,
                    user=env_config.user,
                    passwd=env_config.passwd
                )
                
                if not ssh_executor.is_alive() and not ssh_executor.connect():
                    self.logger.error(f"无法连接到环境 {env_name}")
                    all_success = False
                    continue
                
                env_success = self._execute_commands(ssh_executor, cmd_list, env_name)
                if not env_success:
                    all_success = False
                    
            except Exception as e:
                self.logger.error(f"在环境 {env_name} 上执行命令时发生错误：{e}")
                all_success = False
        
        return all_success
    
    def _execute_commands(self, ssh_executor, cmd_list: list, env_name: str) -> bool:
        """执行命令列表
        
        Args:
            ssh_executor: SSH 执行器
            cmd_list: 命令列表
            env_name: 环境名称
            
        Returns:
            bool: 成功标志
        """
        all_success = True
        
        for i, cmd in enumerate(cmd_list, 1):
            self.logger.info(f"[{env_name}] 执行命令 {i}/{len(cmd_list)}: {cmd}")
            
            try:
                success, output = ssh_executor.execute(cmd)
                
                if output and output.strip():
                    self.logger.info(f"[{env_name}] 命令输出:\n{output}")
                
                if not success:
                    self.logger.error(f"[{env_name}] 命令执行失败: {cmd}")
                    self.logger.error(f"[{env_name}] 错误输出: {output}")
                    all_success = False
                else:
                    self.logger.info(f"[{env_name}] 命令执行成功: {cmd}")
                    
            except Exception as e:
                self.logger.error(f"[{env_name}] 执行命令时发生异常: {cmd}")
                self.logger.error(f"[{env_name}] 异常信息: {e}")
                all_success = False
        
        return all_success
    
    def recover(self, fault_id: str) -> bool:
        """恢复命令执行故障（命令执行完成后自动恢复）
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        self.logger.info(f"命令执行完成，自动恢复：{fault_id}")
        return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self.fault_id


@FaultInjectorRegistry.register("ipmitool")
class IpmiToolFaultInjector(FaultInjector):
    """IPMI 工具故障注入器"""
    
    def __init__(self, config_manager, logger):
        """初始化 IPMI 工具故障注入器
        
        Args:
            config_manager: 配置管理器
            logger: 日志记录器
        """
        self.config_manager = config_manager
        self.logger = logger
        self.fault_id = None
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入 IPMI 故障
        
        Args:
            target: 目标信息
                - name: BMC 名称列表（如 ["bmc_remote1", "bmc_remote2"]）
            parameters: 故障参数
                - fault_type: 故障类型（soft/off/on/reset/cycle/status/warm/cold）
            
        Returns:
            bool: 成功标志
        """
        fault_type = parameters.get("fault_type", "status")
        bmc_names = target.get("name", [])
        
        if not isinstance(bmc_names, list):
            bmc_names = [bmc_names]
        
        timestamp = int(datetime.now().timestamp())
        self.fault_id = f"ipmitool_{fault_type}_{'_'.join(bmc_names)}_{timestamp}"
        
        try:
            return self._execute_on_multiple_bmc(bmc_names, fault_type)
        except Exception as e:
            self.logger.error(f"IPMI 故障注入失败：{e}")
            return False
    
    def _execute_on_multiple_bmc(self, bmc_names: List[str], fault_type: str) -> bool:
        """并发执行多个 BMC 的命令
        
        Args:
            bmc_names: BMC 名称列表
            fault_type: 故障类型
            
        Returns:
            bool: 成功标志
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_success = True
        
        with ThreadPoolExecutor(max_workers=len(bmc_names)) as executor:
            futures = {
                executor.submit(self._execute_on_single_bmc, bmc_name, fault_type): bmc_name
                for bmc_name in bmc_names
            }
            
            for future in as_completed(futures):
                bmc_name = futures[future]
                try:
                    success = future.result()
                    if not success:
                        all_success = False
                except Exception as e:
                    self.logger.error(f"BMC {bmc_name} 执行失败：{e}")
                    all_success = False
        
        return all_success
    
    def _execute_on_single_bmc(self, bmc_name: str, fault_type: str) -> bool:
        """执行单个 BMC 的命令
        
        Args:
            bmc_name: BMC 名称
            fault_type: 故障类型
            
        Returns:
            bool: 成功标志
        """
        bmc_config = self._get_bmc_config(bmc_name)
        if not bmc_config:
            self.logger.error(f"BMC 配置不存在：{bmc_name}")
            return False
        
        command = self._build_ipmitool_command(bmc_config, fault_type)
        if not command:
            self.logger.error(f"不支持的故障类型：{fault_type}")
            return False
        
        self.logger.info(f"为 BMC {bmc_name} 执行 IPMI 命令")
        self.logger.info(f"故障类型: {fault_type}")
        self.logger.info(f"命令: {command}")
        
        success, output = self._execute_local_command(command)
        
        if not success:
            self.logger.error(f"BMC {bmc_name} 命令执行失败：{output}")
            return False
        
        self.logger.info(f"BMC {bmc_name} 命令执行成功：{output}")
        return True
    
    def _get_bmc_config(self, bmc_name: str) -> Optional[Dict]:
        """获取 BMC 配置信息
        
        Args:
            bmc_name: BMC 名称
            
        Returns:
            Optional[Dict]: BMC 配置信息
        """
        bmc_environments = self.config_manager.config.get("bmc_environments", {})
        return bmc_environments.get(bmc_name)
    
    def _build_ipmitool_command(self, bmc_config: Dict, fault_type: str) -> Optional[str]:
        """构建 ipmitool 命令
        
        Args:
            bmc_config: BMC 配置信息
            fault_type: 故障类型
            
        Returns:
            Optional[str]: ipmitool 命令
        """
        ip = bmc_config.get("ip")
        user = bmc_config.get("user")
        passwd = bmc_config.get("passwd")
        
        command_map = {
            "soft": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} chassis power soft",
            "off": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} chassis power off",
            "on": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} chassis power on",
            "reset": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} chassis power reset",
            "cycle": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} chassis power cycle",
            "status": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} chassis power status",
            "warm": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} mc reset warm",
            "cold": f"ipmitool -I lanplus -H {ip} -U {user} -P {passwd} mc reset cold",
        }
        
        return command_map.get(fault_type)
    
    def _execute_local_command(self, command: str) -> Tuple[bool, str]:
        """执行本地命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            Tuple[bool, str]: (是否成功, 输出内容)
        """
        import subprocess
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            return success, output
            
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
    
    def recover(self, fault_id: str) -> bool:
        """恢复 IPMI 故障
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        self.logger.info(f"IPMI 故障无需恢复：{fault_id}")
        return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self.fault_id


@FaultInjectorRegistry.register("process")
class ProcessFaultInjector(FaultInjector):
    """进程故障注入器"""
    
    def __init__(self, remote_executor, logger, config_manager=None):
        """初始化进程故障注入器
        
        Args:
            remote_executor: 远程执行器
            logger: 日志记录器
            config_manager: 配置管理器
        """
        self.remote_executor = remote_executor
        self.logger = logger
        self.config_manager = config_manager
        self.fault_id = None
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入进程故障
        
        Args:
            target: 目标信息
                - name: Pod 名称
                - namespace: 命名空间
            parameters: 故障参数
                - signal: 信号值（默认 15）或 "random"
                - main_process_pid: 目标进程 PID（默认 1）
            
        Returns:
            bool: 成功标志
        """
        pod_name = target.get("name")
        namespace = target.get("namespace")
        
        signal = parameters.get("signal", 15)
        pid = parameters.get("main_process_pid", 1)
        
        if signal == "random":
            import random
            signal = random.choice(VALID_SIGNALS)
            self.logger.info(f"随机选择信号: {signal}")
        
        timestamp = int(datetime.now().timestamp())
        self.fault_id = f"process_kill_{pod_name}_{namespace}_{signal}_{pid}_{timestamp}"
        
        try:
            return self._kill_process(pod_name, namespace, signal, pid)
        except Exception as e:
            self.logger.error(f"进程故障注入失败：{e}")
            return False
    
    def _kill_process(self, pod_name: str, namespace: str, signal: int, pid: int) -> bool:
        """Kill 指定 Pod 中的进程
        
        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            signal: 信号值
            pid: 进程 PID
            
        Returns:
            bool: 成功标志
        """
        try:
            kubectl_cmd = f"kubectl exec -it {pod_name} -n {namespace} -- kill -{signal} {pid}"
            
            self.logger.info(f"Kill 进程: Pod={pod_name}, Namespace={namespace}, Signal={signal}, PID={pid}")
            
            success, output = self.remote_executor.execute(kubectl_cmd)
            
            if success:
                self.logger.info(f"进程 kill 成功: Signal={signal}, PID={pid}")
                return True
            else:
                if "No such process" in output:
                    self.logger.warning(f"进程不存在: PID={pid}")
                    return True
                self.logger.error(f"进程 kill 失败: {output}")
                return False
                
        except Exception as e:
            self.logger.error(f"Kill 进程时发生错误: {e}")
            return False
    
    def recover(self, fault_id: str) -> bool:
        """恢复进程故障
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        self.logger.info(f"进程故障自动恢复（进程守护自动拉起）: {fault_id}")
        return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self.fault_id


@FaultInjectorRegistry.register("sw")
class SwitchFaultInjector(FaultInjector):
    """交换机故障注入器"""
    
    def __init__(self, config_manager, logger):
        """初始化交换机故障注入器
        
        Args:
            config_manager: 配置管理器
            logger: 日志记录器
        """
        self._config_manager = config_manager
        self._logger = logger
        self._fault_id = None
        self._execution_results = []
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入交换机故障
        
        Args:
            target: 目标信息
                - name: 环境名称（如 "sw_ssh_remote1"）
            parameters: 故障参数
                - fault_type: 故障类型（command）
                - command: 命令列表
                - loop_count: 循环次数
            
        Returns:
            bool: 成功标志
        """
        fault_type = parameters.get("fault_type", "command")
        env_name = target.get("name")
        
        if not env_name:
            self._logger.error("未指定交换机环境名称")
            return False
        
        timestamp = int(datetime.now().timestamp())
        self._fault_id = f"{fault_type}_{env_name}_{timestamp}"
        
        try:
            if fault_type == "command":
                return self._execute_commands(env_name, parameters)
            else:
                raise ValueError(f"未知的交换机故障类型：{fault_type}")
        except Exception as e:
            self._logger.error(f"交换机故障注入失败：{e}")
            return False
    
    def _read_channel_output(self, channel) -> str:
        """读取 channel 输出
        
        Args:
            channel: SSH channel
            
        Returns:
            str: 输出内容
        """
        output = ""
        while channel.recv_ready():
            try:
                output += channel.recv(SW_BUFFER_SIZE).decode('utf-8', errors='replace')
            except Exception as e:
                self._logger.warning(f"解码输出时发生错误：{e}")
                break
            time.sleep(SW_READ_INTERVAL)
        return output
    
    def _handle_password_prompt(self, channel, initial_output: str) -> None:
        """处理密码修改提示
        
        Args:
            channel: SSH channel
            initial_output: 初始输出
        """
        if "Change password" in initial_output or "修改密码" in initial_output or "[Y/N]" in initial_output:
            self._logger.info("检测到修改密码请求，输入 N 不修改")
            channel.send('N\n')
            time.sleep(SW_CHANNEL_WAIT)
            self._read_channel_output(channel)
    
    def _handle_confirmation(self, channel, output: str) -> str:
        """处理确认请求
        
        Args:
            channel: SSH channel
            output: 当前输出
            
        Returns:
            str: 处理后的输出
        """
        if "[Y/N]" in output:
            self._logger.info("检测到确认请求，输入 N 继续")
            channel.send('N\n')
            time.sleep(SW_CHANNEL_WAIT)
            output += self._read_channel_output(channel)
        return output
    
    def _connect_switch(self, env_config) -> tuple:
        """连接交换机
        
        Args:
            env_config: 环境配置
            
        Returns:
            tuple: (client, channel) 或 (None, None)
        """
        client = None
        channel = None
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                env_config.ip,
                port=env_config.port,
                username=env_config.user,
                password=env_config.passwd,
                timeout=SW_SSH_TIMEOUT
            )
            self._logger.info(f"SSH 连接成功")
            
            channel = client.invoke_shell()
            time.sleep(SW_CHANNEL_WAIT)
            
            initial_output = channel.recv(SW_BUFFER_SIZE).decode('utf-8', errors='replace')
            self._logger.debug(f"初始输出: {initial_output[:200]}")
            
            self._handle_password_prompt(channel, initial_output)
            
            return client, channel
            
        except Exception as e:
            self._logger.error(f"连接交换机失败：{e}")
            if channel:
                channel.close()
            if client:
                client.close()
            return None, None
    
    def _execute_single_command(self, channel, command: str, loop_idx: int, cmd_wait: float = SW_CMD_WAIT) -> Dict:
        """执行单个命令
        
        Args:
            channel: SSH channel
            command: 命令
            loop_idx: 循环索引
            cmd_wait: 命令执行等待时间（秒）
            
        Returns:
            Dict: 执行结果
        """
        try:
            channel.send(command + '\n')
            time.sleep(cmd_wait)
            
            output = self._read_channel_output(channel)
            output = self._handle_confirmation(channel, output)
            output = output.strip()
            
            self._logger.info(f"命令执行成功")
            if output:
                self._logger.info(f"输出结果：\n{output}")
            
            return {
                "loop": loop_idx + 1,
                "command": command,
                "success": True,
                "output": output
            }
            
        except Exception as e:
            self._logger.error(f"执行命令时发生错误：{e}")
            return {
                "loop": loop_idx + 1,
                "command": command,
                "success": False,
                "output": str(e)
            }
    
    def _parse_command_item(self, cmd_item) -> tuple:
        """解析单个命令项
        
        Args:
            cmd_item: 命令项，可以是字符串或字典
            
        Returns:
            tuple: (command, cmd_wait)
        """
        if isinstance(cmd_item, dict):
            command = cmd_item.get("cmd") or cmd_item.get("command", "")
            cmd_wait = cmd_item.get("wait", cmd_item.get("sw_command_wait", SW_CMD_WAIT))
            return command, cmd_wait
        else:
            return str(cmd_item), SW_CMD_WAIT
    
    def _execute_commands(self, env_name: str, parameters: Dict) -> bool:
        """在交换机上执行命令
        
        Args:
            env_name: 环境名称
            parameters: 故障参数
            
        Returns:
            bool: 成功标志
        """
        env_config = self._config_manager.get_sw_environment(env_name)
        if not env_config:
            self._logger.error(f"交换机环境不存在：{env_name}")
            return False
        
        commands = parameters.get("commands") or parameters.get("command", [])
        if not commands:
            self._logger.error("未指定要执行的命令")
            return False
        
        if not isinstance(commands, list):
            commands = [commands]
        
        loop_count = parameters.get("loop_count", 1)
        
        self._logger.info(f"正在连接交换机：{env_name} ({env_config.ip})")
        self._logger.info(f"命令数量：{len(commands)}")
        self._logger.info(f"循环次数：{loop_count}")
        
        client, channel = self._connect_switch(env_config)
        if not client or not channel:
            return False
        
        try:
            all_success = True
            self._execution_results = []
            
            for loop_idx in range(loop_count):
                self._logger.info(f"执行第 {loop_idx + 1}/{loop_count} 轮命令")
                
                for cmd_idx, cmd_item in enumerate(commands):
                    command, cmd_wait = self._parse_command_item(cmd_item)
                    
                    if not command:
                        self._logger.warning(f"命令 [{cmd_idx + 1}] 为空，跳过")
                        continue
                    
                    self._logger.info(f"执行命令 [{cmd_idx + 1}/{len(commands)}]: {command} (等待 {cmd_wait}s)")
                    
                    result = self._execute_single_command(channel, command, loop_idx, cmd_wait)
                    self._execution_results.append(result)
                    
                    if not result["success"]:
                        all_success = False
            
            return all_success
            
        except Exception as e:
            self._logger.error(f"交换机命令执行失败：{e}")
            return False
        finally:
            if channel:
                channel.close()
            if client:
                client.close()
    
    def recover(self, fault_id: str) -> bool:
        """恢复交换机故障
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            bool: 成功标志
        """
        self._logger.info(f"交换机命令执行完成，自动恢复：{fault_id}")
        return True
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        return self._fault_id
    
    def get_execution_results(self) -> list:
        """获取执行结果
        
        Returns:
            list: 执行结果列表
        """
        return self._execution_results


class FaultFactory:
    """故障注入器工厂
    
    兼容旧接口的工厂类，内部使用 FaultInjectorRegistry 实现。
    新增故障类型只需添加 @FaultInjectorRegistry.register 装饰器，
    无需修改此类代码。
    
    注意：此类已废弃，建议直接使用 FaultInjectorRegistry。
    """
    
    _deprecated_warning_shown = False
    
    @classmethod
    def _show_deprecation_warning(cls):
        """显示废弃警告（只显示一次）"""
        if not cls._deprecated_warning_shown:
            import warnings
            warnings.warn(
                "FaultFactory 已废弃，建议直接使用 FaultInjectorRegistry。"
                "例如：FaultInjectorRegistry.create('network', remote_executor=executor)",
                DeprecationWarning,
                stacklevel=3
            )
            cls._deprecated_warning_shown = True
    
    @classmethod
    def create_injector(cls, fault_type: str, **dependencies):
        """创建故障注入器
        
        Args:
            fault_type: 故障类型（network, pod, computer, process, sw）
            **dependencies: 依赖项（remote_executor, logger 等）
            
        Returns:
            FaultInjector: 故障注入器实例
            
        Raises:
            ValueError: 未知的故障类型
        """
        cls._show_deprecation_warning()
        return FaultInjectorRegistry.create(fault_type, **dependencies)
    
    @classmethod
    def register_injector(cls, fault_type: str, injector_class):
        """注册新的故障注入器（兼容旧接口）
        
        Args:
            fault_type: 故障类型
            injector_class: 故障注入器类
        """
        cls._show_deprecation_warning()
        FaultInjectorRegistry.register(fault_type, injector_class)
    
    @classmethod
    def get_registered_types(cls) -> list:
        """获取所有已注册的故障类型
        
        Returns:
            list: 故障类型列表
        """
        return FaultInjectorRegistry.get_registered_types()
    
    @classmethod
    def is_registered(cls, fault_type: str) -> bool:
        """检查故障类型是否已注册
        
        Args:
            fault_type: 故障类型
            
        Returns:
            bool: 是否已注册
        """
        return FaultInjectorRegistry.is_registered(fault_type)
    
    @classmethod
    def get_registry_info(cls) -> dict:
        """获取注册表信息
        
        Returns:
            dict: 注册表详细信息
        """
        return FaultInjectorRegistry.get_registry_info()
