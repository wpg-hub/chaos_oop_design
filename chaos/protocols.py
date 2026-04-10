"""协议定义模块

定义项目中使用的抽象接口，用于类型提示和依赖注入。
此模块不依赖其他业务模块，避免循环导入。
"""

from typing import Dict, List, Optional, Protocol, Tuple, Any, runtime_checkable


# ========== 配置管理协议 ==========

@runtime_checkable
class ConfigManagerProtocol(Protocol):
    """配置管理器协议"""
    
    def get_environment(self, name: str) -> Optional[Dict[str, Any]]:
        """获取环境配置"""
        ...
    
    def get_defaults(self) -> Dict[str, Any]:
        """获取默认配置"""
        ...
    
    def get_namespace(self) -> str:
        """获取默认命名空间"""
        ...
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置"""
        ...


@runtime_checkable
class EnvironmentConfigProtocol(Protocol):
    """环境配置协议"""
    
    ip: str
    port: int
    user: str
    passwd: str
    nodename: Optional[str]
    default_namespace: Optional[str]


# ========== 故障注入协议 ==========

@runtime_checkable
class FaultInjectorProtocol(Protocol):
    """故障注入器协议"""
    
    def inject(self, target: Dict, parameters: Dict) -> bool:
        """注入故障"""
        ...
    
    def recover(self, fault_id: str) -> bool:
        """恢复故障"""
        ...
    
    def get_fault_id(self) -> Optional[str]:
        """获取故障 ID"""
        ...


@runtime_checkable
class FaultFactoryProtocol(Protocol):
    """故障工厂协议"""
    
    def create_injector(self, fault_type: str, **dependencies) -> FaultInjectorProtocol:
        """创建故障注入器"""
        ...
    
    def get_registered_types(self) -> List[str]:
        """获取已注册的故障类型列表"""
        ...


# ========== 状态管理协议 ==========

@runtime_checkable
class StateManagerProtocol(Protocol):
    """状态管理器协议"""
    
    def record_fault(
        self,
        case_name: str,
        fault_type: str,
        fault_id: str,
        target: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> None:
        """记录故障"""
        ...
    
    def mark_recovered(self, fault_id: str) -> None:
        """标记故障已恢复"""
        ...
    
    def mark_failed(self, fault_id: str, error_message: str) -> None:
        """标记故障失败"""
        ...
    
    def get_fault_state(self, fault_id: str) -> Optional[Dict[str, Any]]:
        """获取故障状态"""
        ...
    
    def get_active_faults(self) -> List[Any]:
        """获取活跃故障列表"""
        ...


# ========== 工具类协议 ==========

@runtime_checkable
class RemoteExecutorProtocol(Protocol):
    """远程执行器协议"""
    
    @property
    def host(self) -> str:
        """主机地址"""
        ...
    
    @property
    def port(self) -> int:
        """端口"""
        ...
    
    @property
    def user(self) -> str:
        """用户名"""
        ...
    
    def execute(self, command: str, ignore_errors: bool = False, timeout: int = 120) -> Tuple[bool, str]:
        """执行命令"""
        ...
    
    def connect(self) -> bool:
        """建立连接"""
        ...
    
    def disconnect(self) -> None:
        """断开连接"""
        ...
    
    def is_alive(self) -> bool:
        """检查连接是否存活"""
        ...
    
    def reconnect(self) -> bool:
        """重新连接"""
        ...


@runtime_checkable
class LoggerProtocol(Protocol):
    """日志记录器协议"""
    
    def info(self, message: str) -> None:
        """记录信息日志"""
        ...
    
    def error(self, message: str) -> None:
        """记录错误日志"""
        ...
    
    def warning(self, message: str) -> None:
        """记录警告日志"""
        ...
    
    def debug(self, message: str) -> None:
        """记录调试日志"""
        ...
