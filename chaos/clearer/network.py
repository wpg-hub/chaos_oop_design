"""
网络故障清除模块
负责清除 Pod 网络延迟故障
"""

from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

from ..constants import DEFAULT_NAMESPACE


class NetworkFaultClearer(ABC):
    """网络故障清除器抽象类"""
    
    def __init__(self, remote_executor, logger):
        """初始化网络故障清除器
        
        Args:
            remote_executor: 远程执行器
            logger: 日志记录器
        """
        self.remote_executor = remote_executor
        self.logger = logger
    
    @abstractmethod
    def clear_fault(self, target: Dict, parameters: Dict) -> bool:
        """清除网络故障
        
        Args:
            target: 目标信息
            parameters: 故障参数
            
        Returns:
            bool: 成功标志
        """
        pass


class PodNetworkFaultClearer(NetworkFaultClearer):
    """Pod 网络故障清除器"""
    
    def __init__(self, remote_executor, logger, config_manager=None):
        """初始化 Pod 网络故障清除器
        
        Args:
            remote_executor: 远程执行器
            logger: 日志记录器
            config_manager: 配置管理器（用于获取默认命名空间）
        """
        super().__init__(remote_executor, logger)
        self.config_manager = config_manager
    
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
        return DEFAULT_NAMESPACE
    
    def clear_fault(self, target: Dict, parameters: Dict) -> bool:
        """清除 Pod 网络故障
        
        Args:
            target: 目标信息
                - name: Pod 名称
                - namespace: 命名空间
            parameters: 故障参数
                - device: 网络设备名称（默认: eth0）
                - namespace: Kubernetes 命名空间（可选，默认从配置文件获取）
                
        Returns:
            bool: 成功标志
        """
        try:
            pod_name = target.get("name")
            namespace = self._get_namespace(parameters.get("namespace") or target.get("namespace"))
            device = parameters.get("device", "eth0")
            
            self.logger.info(f"清除 Pod {pod_name} 的网络故障")
            self.logger.info(f"命名空间: {namespace}, 网络设备: {device}")
            
            # 获取 pause 容器 ID
            pause_container_id = self._get_pause_container_id(pod_name)
            if not pause_container_id:
                self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 ID")
                return False
            
            # 获取 pause 容器 PID
            pause_container_pid = self._get_container_pid(pause_container_id)
            if not pause_container_pid:
                self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 PID")
                return False
            
            # 在 pause 容器的命名空间中执行清除命令
            success = self._execute_clear_command(pause_container_pid, device)
            
            if success:
                self.logger.info(f"Pod {pod_name} 的网络故障清除成功")
            else:
                self.logger.error(f"Pod {pod_name} 的网络故障清除失败")
            
            return success
            
        except Exception as e:
            self.logger.error(f"清除 Pod 网络故障时发生错误：{e}")
            return False
    
    def _get_pause_container_id(self, pod_name: str) -> Optional[str]:
        """获取 Pod 对应的 pause 容器 ID
        
        Args:
            pod_name: Pod 名称
            
        Returns:
            Optional[str]: pause 容器 ID
        """
        self.logger.info(f"获取 Pod {pod_name} 的 pause 容器 ID")
        
        # 构建 docker ps 命令
        docker_cmd = f"docker ps | grep '{pod_name}' | grep k8s_POD | awk '{{print $1}}'"
        
        # 执行命令
        success, output = self.remote_executor.execute(docker_cmd)
        
        if not success or not output:
            self.logger.error(f"无法获取 Pod {pod_name} 的 pause 容器 ID")
            return None
        
        # 解析输出，提取容器 ID
        container_id = output.strip()
        self.logger.info(f"解析后的 pause 容器 ID: {container_id}")
        
        return container_id
    
    def _get_container_pid(self, container_id: str) -> Optional[str]:
        """获取容器的 PID
        
        Args:
            container_id: 容器 ID
            
        Returns:
            Optional[str]: 容器 PID
        """
        self.logger.info(f"获取容器的 PID")
        self.logger.info(f"容器 ID: {container_id}")
        
        # 构建 docker inspect 命令
        docker_cmd = f"docker inspect {container_id} | grep Pid"
        
        # 执行命令
        success, output = self.remote_executor.execute(docker_cmd)
        
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
        
        pid = parts[1].strip().strip(',').strip()
        self.logger.info(f"提取的容器 PID: {pid}")
        
        return pid
    
    def _execute_clear_command(self, pid: str, device: str) -> bool:
        """在容器的命名空间中执行清除命令
        
        Args:
            pid: 容器 PID
            device: 网络设备名称
            
        Returns:
            bool: 是否成功
        """
        # 构建一键式 nsenter 命令
        nsenter_cmd = f"sudo nsenter -n -t {pid} bash -c \"tc qdisc del dev {device} root; tc qdisc del dev {device} ingress\""
        
        # 执行命令，忽略错误（因为 "No such file or directory" 是正常情况）
        success, output = self.remote_executor.execute(nsenter_cmd, ignore_errors=True)
        
        # 如果 SSH 连接失败，返回 False
        if not success:
            return False
        
        # 检查输出中是否包含 "RTNETLINK answers: No such file or directory"
        # 这个错误表示没有 qdisc 规则需要删除，实际上命令执行是成功的
        if output and "RTNETLINK answers: No such file or directory" in output:
            self.logger.info("没有找到 qdisc 规则需要删除（正常情况）")
            return True
        
        # 其他情况都认为成功
        return True


class NetworkFaultClearerFactory:
    """网络故障清除器工厂"""
    
    @staticmethod
    def create_clearer(clearer_type: str, remote_executor, logger, config_manager=None) -> NetworkFaultClearer:
        """创建网络故障清除器
        
        Args:
            clearer_type: 清除器类型
            remote_executor: 远程执行器
            logger: 日志记录器
            config_manager: 配置管理器（用于获取默认命名空间）
            
        Returns:
            NetworkFaultClearer: 网络故障清除器实例
        """
        if clearer_type == "pod":
            return PodNetworkFaultClearer(remote_executor, logger, config_manager)
        else:
            raise ValueError(f"不支持的清除器类型：{clearer_type}")
