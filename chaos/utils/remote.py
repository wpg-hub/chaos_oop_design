"""远程执行模块
提供 SSH 远程执行功能和连接池管理
"""

import paramiko
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any

from ..constants import SSH_DEFAULT_TIMEOUT
from .singleton import SingletonMeta


class RemoteExecutor(ABC):
    """远程执行器抽象类"""
    
    @abstractmethod
    def execute(self, command: str, ignore_errors: bool = False, timeout: int = 120) -> Tuple[bool, str]:
        """执行命令
        
        Args:
            command: 要执行的命令
            ignore_errors: 是否忽略错误，默认 False
            timeout: 超时时间（秒）
            
        Returns:
            Tuple[bool, str]: (成功标志，输出/错误信息)
        """
        pass
    
    @abstractmethod
    def connect(self) -> bool:
        """建立连接
        
        Returns:
            bool: 成功标志
        """
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    def is_alive(self) -> bool:
        """检查连接是否存活
        
        Returns:
            bool: 连接是否存活
        """
        pass


class SSHExecutor(RemoteExecutor):
    """SSH 远程执行器"""
    
    def __init__(self, host: str, port: int = 22, 
                 user: str = "root", passwd: str = None,
                 key_file: str = None,
                 connect_timeout: int = SSH_DEFAULT_TIMEOUT):
        """初始化 SSH 执行器
        
        Args:
            host: 主机 IP
            port: SSH 端口
            user: 用户名
            passwd: 密码
            key_file: 密钥文件路径
            connect_timeout: 连接超时时间（秒）
        """
        self._host = host
        self._port = port
        self._user = user
        self._passwd = passwd
        self._key_file = key_file
        self._connect_timeout = connect_timeout
        self._connected = False
        self._client = None
        self._last_used = datetime.now()
        self._lock = threading.Lock()
        self._error_count = 0
        self._last_error: Optional[str] = None
    
    @property
    def host(self) -> str:
        return self._host
    
    @property
    def port(self) -> int:
        return self._port
    
    @property
    def user(self) -> str:
        return self._user
    
    @property
    def last_used(self) -> datetime:
        return self._last_used
    
    @property
    def error_count(self) -> int:
        return self._error_count
    
    @property
    def last_error(self) -> Optional[str]:
        return self._last_error
    
    def connect(self) -> bool:
        """建立 SSH 连接"""
        with self._lock:
            if self._connected and self.is_alive():
                return True
            
            try:
                self._client = paramiko.SSHClient()
                self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                if self._key_file:
                    self._client.connect(
                        hostname=self._host,
                        port=self._port,
                        username=self._user,
                        key_filename=self._key_file,
                        timeout=self._connect_timeout
                    )
                elif self._passwd:
                    self._client.connect(
                        hostname=self._host,
                        port=self._port,
                        username=self._user,
                        password=self._passwd,
                        timeout=self._connect_timeout
                    )
                else:
                    return False
                
                self._connected = True
                self._last_used = datetime.now()
                self._error_count = 0
                self._last_error = None
                return True
            except Exception as e:
                self._connected = False
                self._last_error = str(e)
                self._error_count += 1
                return False
    
    def disconnect(self):
        """断开 SSH 连接"""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            self._connected = False
    
    def is_alive(self) -> bool:
        """检查连接是否存活"""
        if not self._connected or not self._client:
            return False
        
        try:
            transport = self._client.get_transport()
            if transport is None:
                return False
            return transport.is_active()
        except Exception:
            return False
    
    def reconnect(self) -> bool:
        """重新连接
        
        Returns:
            bool: 重连成功标志
        """
        self.disconnect()
        return self.connect()
    
    def execute(self, command: str, ignore_errors: bool = False, timeout: int = 120) -> Tuple[bool, str]:
        """执行远程命令
        
        Args:
            command: 要执行的命令
            ignore_errors: 是否忽略错误，默认 False
            timeout: 超时时间（秒），默认 120
            
        Returns:
            Tuple[bool, str]: (成功标志，输出/错误信息)
        """
        with self._lock:
            if not self._connected or not self.is_alive():
                if not self.connect():
                    return False, f"无法建立 SSH 连接: {self._last_error or '未知错误'}"
            
            try:
                stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
                
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                exit_status = stdout.channel.recv_exit_status()
                
                self._last_used = datetime.now()
                
                if exit_status == 0 or ignore_errors:
                    return True, output + error
                else:
                    return False, error
                    
            except Exception as e:
                self._connected = False
                self._last_error = str(e)
                self._error_count += 1
                return False, f"执行失败：{str(e)}"
    
    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """上传文件到远程主机
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            Tuple[bool, str]: (成功标志，输出/错误信息)
        """
        with self._lock:
            if not self._connected or not self.is_alive():
                if not self.connect():
                    return False, f"无法建立 SSH 连接: {self._last_error or '未知错误'}"
            
            try:
                sftp = self._client.open_sftp()
                sftp.put(local_path, remote_path)
                sftp.close()
                self._last_used = datetime.now()
                return True, "文件上传成功"
            except Exception as e:
                self._last_error = str(e)
                self._error_count += 1
                return False, f"文件上传失败：{str(e)}"
    
    def download_file(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """从远程主机下载文件
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            Tuple[bool, str]: (成功标志，输出/错误信息)
        """
        with self._lock:
            if not self._connected or not self.is_alive():
                if not self.connect():
                    return False, f"无法建立 SSH 连接: {self._last_error or '未知错误'}"
            
            try:
                sftp = self._client.open_sftp()
                sftp.get(remote_path, local_path)
                sftp.close()
                self._last_used = datetime.now()
                return True, "文件下载成功"
            except Exception as e:
                self._last_error = str(e)
                self._error_count += 1
                return False, f"文件下载失败：{str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """获取连接器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "connected": self._connected,
            "alive": self.is_alive() if self._connected else False,
            "last_used": self._last_used.isoformat() if self._last_used else None,
            "error_count": self._error_count,
            "last_error": self._last_error,
        }


class SSHConnectionPool(metaclass=SingletonMeta):
    """SSH 连接池（单例模式）
    
    提供连接复用、自动重连、空闲连接清理功能。
    使用 SingletonMeta 元类确保线程安全和单次初始化。
    
    使用示例:
        pool = SSHConnectionPool(max_connections=10, idle_timeout=300)
        executor = pool.get_connection(host="192.168.1.1", user="root")
    
    注意:
        构造函数的参数只在首次创建实例时生效，后续获取实例将忽略参数。
        元类会自动处理单例逻辑，无需手动检查初始化状态。
    """
    
    def __init__(self, max_connections: int = 10, idle_timeout: int = 300):
        self._connections: Dict[str, SSHExecutor] = {}
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout
        self._pool_lock = threading.Lock()
        self._health_check_interval = 60
        self._last_health_check = datetime.now()
    
    def _make_key(self, host: str, port: int, user: str) -> str:
        """生成连接键
        
        Args:
            host: 主机 IP
            port: SSH 端口
            user: 用户名
            
        Returns:
            str: 连接键
        """
        return f"{user}@{host}:{port}"
    
    def get_connection(self, host: str, port: int = 22, 
                       user: str = "root", passwd: str = None,
                       key_file: str = None) -> SSHExecutor:
        """获取或创建连接
        
        Args:
            host: 主机 IP
            port: SSH 端口
            user: 用户名
            passwd: 密码
            key_file: 密钥文件路径
            
        Returns:
            SSHExecutor: SSH 执行器实例
        """
        key = self._make_key(host, port, user)
        
        with self._pool_lock:
            if key in self._connections:
                executor = self._connections[key]
                if executor.is_alive():
                    return executor
                else:
                    executor.reconnect()
                    return executor
            
            if len(self._connections) >= self._max_connections:
                self._cleanup_oldest()
            
            executor = SSHExecutor(
                host=host,
                port=port,
                user=user,
                passwd=passwd,
                key_file=key_file
            )
            executor.connect()
            self._connections[key] = executor
            return executor
    
    def get_connection_from_env(self, env_config) -> SSHExecutor:
        """从环境配置获取连接
        
        Args:
            env_config: EnvironmentConfig 对象
            
        Returns:
            SSHExecutor: SSH 执行器实例
        """
        return self.get_connection(
            host=env_config.ip,
            port=env_config.port,
            user=env_config.user,
            passwd=env_config.passwd,
            key_file=env_config.key_file
        )
    
    def close_connection(self, host: str, port: int = 22, user: str = "root"):
        """关闭指定连接
        
        Args:
            host: 主机 IP
            port: SSH 端口
            user: 用户名
        """
        key = self._make_key(host, port, user)
        
        with self._pool_lock:
            if key in self._connections:
                self._connections[key].disconnect()
                del self._connections[key]
    
    def close_all(self):
        """关闭所有连接"""
        with self._pool_lock:
            for executor in self._connections.values():
                executor.disconnect()
            self._connections.clear()
    
    def _cleanup_oldest(self):
        """清理最旧的连接"""
        if not self._connections:
            return
        
        oldest_key = min(
            self._connections.keys(),
            key=lambda k: self._connections[k].last_used
        )
        self._connections[oldest_key].disconnect()
        del self._connections[oldest_key]
    
    def cleanup_idle(self) -> int:
        """清理空闲超时的连接
        
        Returns:
            int: 清理的连接数量
        """
        now = datetime.now()
        cleaned = 0
        
        with self._pool_lock:
            keys_to_remove = []
            for key, executor in self._connections.items():
                idle_seconds = (now - executor.last_used).total_seconds()
                if idle_seconds > self._idle_timeout:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._connections[key].disconnect()
                del self._connections[key]
                cleaned += 1
        
        return cleaned
    
    def health_check(self) -> Dict[str, Any]:
        """执行健康检查
        
        检查所有连接的状态，清理无效连接。
        
        Returns:
            Dict: 健康检查结果
        """
        now = datetime.now()
        results = {
            "total_connections": 0,
            "alive_connections": 0,
            "dead_connections": 0,
            "cleaned_connections": 0,
            "connection_details": [],
        }
        
        with self._pool_lock:
            results["total_connections"] = len(self._connections)
            
            keys_to_remove = []
            for key, executor in self._connections.items():
                status = executor.get_status()
                results["connection_details"].append(status)
                
                if executor.is_alive():
                    results["alive_connections"] += 1
                else:
                    results["dead_connections"] += 1
                    if executor.error_count > 3:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._connections[key].disconnect()
                del self._connections[key]
                results["cleaned_connections"] += 1
        
        self._last_health_check = now
        return results
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态
        
        Returns:
            Dict: 连接池状态信息
        """
        with self._pool_lock:
            connections_info = []
            alive_count = 0
            
            for key, executor in self._connections.items():
                status = executor.get_status()
                connections_info.append(status)
                if status["alive"]:
                    alive_count += 1
            
            return {
                "max_connections": self._max_connections,
                "idle_timeout": self._idle_timeout,
                "total_connections": len(self._connections),
                "alive_connections": alive_count,
                "dead_connections": len(self._connections) - alive_count,
                "last_health_check": self._last_health_check.isoformat(),
                "connections": connections_info,
            }
    
    @property
    def connection_count(self) -> int:
        """当前连接数"""
        return len(self._connections)
    
    def cleanup(self):
        """清理资源（用于 reset_instance 时自动调用）"""
        self.close_all()


def get_ssh_pool() -> SSHConnectionPool:
    """获取 SSH 连接池单例
    
    Returns:
        SSHConnectionPool: 连接池实例
    """
    return SSHConnectionPool()
