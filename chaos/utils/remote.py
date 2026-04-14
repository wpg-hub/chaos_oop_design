"""远程执行模块
提供 SSH 远程执行功能和连接池管理
"""

import paramiko
import threading
import time
import logging
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
        self._client = None
        self._connected = False
        self._last_used = None
        self._error_count = 0
        self._last_error = None
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
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
    
    def execute(self, command: str, ignore_errors: bool = False, timeout: int = 120, 
                max_retries: int = 3, retry_delay: float = 2.0) -> Tuple[bool, str]:
        """执行远程命令（带重试机制）
        
        Args:
            command: 要执行的命令
            ignore_errors: 是否忽略错误，默认 False
            timeout: 超时时间（秒），默认 120
            max_retries: 最大重试次数，默认 3
            retry_delay: 重试延迟（秒），默认 2.0
            
        Returns:
            Tuple[bool, str]: (成功标志，输出/错误信息)
        """
        last_error = None
        
        for attempt in range(max_retries):
            with self._lock:
                # 检查连接状态
                if not self._connected or not self.is_alive():
                    # 尝试重连
                    if not self.connect():
                        last_error = f"无法建立 SSH 连接: {self._last_error or '未知错误'}"
                        if attempt < max_retries - 1:
                            self.logger.warning(f"连接失败，{retry_delay}秒后重试 (尝试 {attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            continue
                        else:
                            return False, last_error
                
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
                    last_error = f"执行失败：{str(e)}"
                    
                    if attempt < max_retries - 1:
                        self.logger.warning(f"命令执行失败，{retry_delay}秒后重试 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                        time.sleep(retry_delay)
                        # 尝试重连
                        self.connect()
                    else:
                        return False, last_error
        
        return False, last_error or "未知错误"
    
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
        self.logger = logging.getLogger(__name__)
    
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
        """获取或创建连接（优化版，避免在锁内执行耗时操作）
        
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
        
        # 第一步：在锁内快速检查连接状态
        with self._pool_lock:
            if key in self._connections:
                executor = self._connections[key]
                if executor.is_alive():
                    self.logger.debug(f"复用现有连接: {key}")
                    return executor
                # 连接不可用，标记需要重连
                self.logger.info(f"连接 {key} 不可用，需要重连")
                need_reconnect = True
            else:
                need_reconnect = False
                # 检查是否需要清理旧连接
                if len(self._connections) >= self._max_connections:
                    self.logger.info(f"连接池已满 ({len(self._connections)}/{self._max_connections})，清理最旧连接")
                    self._cleanup_oldest()
        
        # 第二步：在锁外执行重连或创建新连接
        if need_reconnect:
            # 重连现有连接（在锁外执行，避免阻塞其他线程）
            self.logger.info(f"尝试重连: {key}")
            if executor.reconnect():
                self.logger.info(f"重连成功: {key}")
                return executor
            else:
                # 重连失败，从连接池移除
                self.logger.warning(f"重连失败: {key}，从连接池移除")
                with self._pool_lock:
                    if key in self._connections:
                        del self._connections[key]
                # 创建新连接
                return self._create_new_connection(key, host, port, user, passwd, key_file)
        else:
            # 创建新连接
            return self._create_new_connection(key, host, port, user, passwd, key_file)
    
    def _create_new_connection(self, key: str, host: str, port: int, 
                               user: str, passwd: str, key_file: str) -> SSHExecutor:
        """创建新连接（在锁外执行）
        
        Args:
            key: 连接键
            host: 主机 IP
            port: SSH 端口
            user: 用户名
            passwd: 密码
            key_file: 密钥文件路径
            
        Returns:
            SSHExecutor: SSH 执行器实例
            
        Raises:
            Exception: 连接失败时抛出异常
        """
        self.logger.info(f"创建新连接: {key}")
        executor = SSHExecutor(
            host=host,
            port=port,
            user=user,
            passwd=passwd,
            key_file=key_file
        )
        
        if executor.connect():
            with self._pool_lock:
                # 再次检查，防止并发创建
                if key not in self._connections:
                    self._connections[key] = executor
                    self.logger.info(f"新连接创建成功: {key}，当前连接池大小: {len(self._connections)}")
                else:
                    # 其他线程已经创建了连接，使用现有的
                    self.logger.info(f"其他线程已创建连接: {key}，使用现有连接")
                    executor.disconnect()
                    return self._connections[key]
            return executor
        else:
            self.logger.error(f"连接失败: {key}")
            raise Exception(f"无法连接到 {key}")
    
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
