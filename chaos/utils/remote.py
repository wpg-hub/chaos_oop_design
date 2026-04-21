"""远程执行模块
提供 SSH 远程执行功能和连接池管理

优化功能：
1. 连接超时双重保护（socket + paramiko）
2. 熔断机制（Circuit Breaker）
3. 后台健康检查线程
4. 心跳保活机制
5. 连接耗时监控
6. 连接池预热功能
"""

import socket
import paramiko
import threading
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from enum import Enum

from ..constants import SSH_DEFAULT_TIMEOUT
from .singleton import SingletonMeta


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ConnectionStats:
    """连接统计信息"""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_commands: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    total_connect_time: float = 0.0
    total_command_time: float = 0.0
    last_connect_time: Optional[float] = None
    last_command_time: Optional[float] = None
    min_connect_time: Optional[float] = None
    max_connect_time: Optional[float] = None
    
    def record_connect(self, success: bool, duration: float):
        """记录连接统计"""
        self.total_connections += 1
        if success:
            self.successful_connections += 1
        else:
            self.failed_connections += 1
        self.total_connect_time += duration
        self.last_connect_time = duration
        if self.min_connect_time is None or duration < self.min_connect_time:
            self.min_connect_time = duration
        if self.max_connect_time is None or duration > self.max_connect_time:
            self.max_connect_time = duration
    
    def record_command(self, success: bool, duration: float):
        """记录命令统计"""
        self.total_commands += 1
        if success:
            self.successful_commands += 1
        else:
            self.failed_commands += 1
        self.total_command_time += duration
        self.last_command_time = duration
    
    @property
    def avg_connect_time(self) -> float:
        """平均连接耗时"""
        if self.total_connections == 0:
            return 0.0
        return self.total_connect_time / self.total_connections
    
    @property
    def avg_command_time(self) -> float:
        """平均命令耗时"""
        if self.total_commands == 0:
            return 0.0
        return self.total_command_time / self.total_commands
    
    @property
    def connection_success_rate(self) -> float:
        """连接成功率"""
        if self.total_connections == 0:
            return 0.0
        return self.successful_connections / self.total_connections
    
    @property
    def command_success_rate(self) -> float:
        """命令成功率"""
        if self.total_commands == 0:
            return 0.0
        return self.successful_commands / self.total_commands
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_connections": self.total_connections,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "total_commands": self.total_commands,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands,
            "avg_connect_time": round(self.avg_connect_time, 3),
            "avg_command_time": round(self.avg_command_time, 3),
            "min_connect_time": round(self.min_connect_time, 3) if self.min_connect_time else None,
            "max_connect_time": round(self.max_connect_time, 3) if self.max_connect_time else None,
            "connection_success_rate": round(self.connection_success_rate, 3),
            "command_success_rate": round(self.command_success_rate, 3),
        }


class CircuitBreaker:
    """熔断器
    
    实现熔断模式，防止对故障服务的持续请求。
    
    状态转换：
    CLOSED -> OPEN: 连续失败次数达到阈值
    OPEN -> HALF_OPEN: 熔断时间到期
    HALF_OPEN -> CLOSED: 尝试成功
    HALF_OPEN -> OPEN: 尝试失败
    """
    
    def __init__(self, failure_threshold: int = 3, 
                 recovery_timeout: int = 60,
                 half_open_max_calls: int = 1):
        """初始化熔断器
        
        Args:
            failure_threshold: 失败次数阈值，达到后熔断
            recovery_timeout: 熔断恢复超时时间（秒）
            half_open_max_calls: 半开状态最大尝试次数
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        with self._lock:
            self._check_state_transition()
            return self._state
    
    def _check_state_transition(self):
        """检查状态转换（在锁内调用）"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self.logger.info("熔断器状态转换: OPEN -> HALF_OPEN")
    
    def can_execute(self) -> bool:
        """检查是否可以执行
        
        Returns:
            bool: 是否可以执行
        """
        with self._lock:
            self._check_state_transition()
            
            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.OPEN:
                return False
            else:  # HALF_OPEN
                if self._half_open_calls < self._half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
    
    def record_success(self):
        """记录成功"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                self.logger.info("熔断器状态转换: HALF_OPEN -> CLOSED")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
    
    def record_failure(self):
        """记录失败"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                self.logger.warning("熔断器状态转换: HALF_OPEN -> OPEN")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                    self.logger.warning(
                        f"熔断器状态转换: CLOSED -> OPEN "
                        f"(失败次数: {self._failure_count}/{self._failure_threshold})"
                    )
    
    def reset(self):
        """重置熔断器"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
    
    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        with self._lock:
            self._check_state_transition()
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            }


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
    """SSH 远程执行器（增强版）
    
    新增功能：
    - 双重超时保护（socket + paramiko）
    - 熔断机制
    - 心跳保活
    - 连接耗时监控
    """
    
    DEFAULT_KEEPALIVE_INTERVAL = 30
    DEFAULT_KEEPALIVE_COUNT = 3
    
    def __init__(self, host: str, port: int = 22, 
                 user: str = "root", passwd: str = None,
                 key_file: str = None,
                 connect_timeout: int = SSH_DEFAULT_TIMEOUT,
                 enable_circuit_breaker: bool = True,
                 circuit_breaker_config: Dict[str, Any] = None,
                 keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL):
        """初始化 SSH 执行器
        
        Args:
            host: 主机 IP
            port: SSH 端口
            user: 用户名
            passwd: 密码
            key_file: 密钥文件路径
            connect_timeout: 连接超时时间（秒）
            enable_circuit_breaker: 是否启用熔断器
            circuit_breaker_config: 熔断器配置
            keepalive_interval: 心跳间隔（秒）
        """
        self._host = host
        self._port = port
        self._user = user
        self._passwd = passwd
        self._key_file = key_file
        self._connect_timeout = connect_timeout
        self._keepalive_interval = keepalive_interval
        self._client = None
        self._connected = False
        self._last_used = None
        self._error_count = 0
        self._last_error = None
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        self._stats = ConnectionStats()
        
        if enable_circuit_breaker:
            cb_config = circuit_breaker_config or {}
            self._circuit_breaker = CircuitBreaker(**cb_config)
        else:
            self._circuit_breaker = None
        
        self._keepalive_thread = None
        self._keepalive_stop_event = threading.Event()
    
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
    
    @property
    def stats(self) -> ConnectionStats:
        """获取连接统计信息"""
        return self._stats
    
    @property
    def circuit_breaker(self) -> Optional[CircuitBreaker]:
        """获取熔断器"""
        return self._circuit_breaker
    
    def _check_port_reachable(self) -> Tuple[bool, str]:
        """检查端口可达性（双重超时保护第一步）
        
        Returns:
            Tuple[bool, str]: (成功标志，错误信息)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._connect_timeout)
            result = sock.connect_ex((self._host, self._port))
            sock.close()
            
            if result != 0:
                return False, f"端口 {self._port} 不可达 (错误码: {result})"
            return True, ""
        except socket.timeout:
            return False, f"连接超时: {self._host}:{self._port}"
        except socket.error as e:
            return False, f"Socket错误: {str(e)}"
    
    def connect(self) -> bool:
        """建立 SSH 连接（带双重超时保护和耗时监控）"""
        with self._lock:
            if self._connected and self.is_alive():
                return True
            
            if self._circuit_breaker and not self._circuit_breaker.can_execute():
                self.logger.warning(f"熔断器开启，跳过连接: {self._host}:{self._port}")
                return False
            
            start_time = time.time()
            
            try:
                reachable, error_msg = self._check_port_reachable()
                if not reachable:
                    self._handle_connect_failure(start_time, error_msg)
                    return False
                
                self._client = paramiko.SSHClient()
                self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    "hostname": self._host,
                    "port": self._port,
                    "username": self._user,
                    "timeout": self._connect_timeout,
                    "banner_timeout": self._connect_timeout,
                }
                
                if self._key_file:
                    connect_params["key_filename"] = self._key_file
                elif self._passwd:
                    connect_params["password"] = self._passwd
                else:
                    self._handle_connect_failure(start_time, "未提供认证凭据")
                    return False
                
                self._client.connect(**connect_params)
                
                transport = self._client.get_transport()
                if transport:
                    transport.set_keepalive(self._keepalive_interval)
                
                self._connected = True
                self._last_used = datetime.now()
                self._error_count = 0
                self._last_error = None
                
                duration = time.time() - start_time
                self._stats.record_connect(True, duration)
                
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()
                
                self.logger.info(
                    f"SSH连接建立成功: {self._host}:{self._port}, "
                    f"耗时: {duration:.2f}s"
                )
                
                if duration > 5:
                    self.logger.warning(
                        f"连接耗时过长: {self._host}:{self._port}, "
                        f"耗时: {duration:.2f}s"
                    )
                
                self._start_keepalive()
                
                return True
                
            except Exception as e:
                error_msg = f"SSH连接失败: {str(e)}"
                self._handle_connect_failure(start_time, error_msg)
                return False
    
    def _handle_connect_failure(self, start_time: float, error_msg: str):
        """处理连接失败"""
        duration = time.time() - start_time
        self._stats.record_connect(False, duration)
        
        self._connected = False
        self._last_error = error_msg
        self._error_count += 1
        
        if self._circuit_breaker:
            self._circuit_breaker.record_failure()
        
        self.logger.error(
            f"SSH连接失败: {self._host}:{self._port}, "
            f"耗时: {duration:.2f}s, 错误: {error_msg}"
        )
    
    def disconnect(self):
        """断开 SSH 连接"""
        with self._lock:
            self._stop_keepalive_thread()
            
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
    
    def _start_keepalive(self):
        """启动心跳保活线程"""
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            return
        
        self._keepalive_stop_event.clear()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop,
            daemon=True
        )
        self._keepalive_thread.start()
    
    def _stop_keepalive_thread(self):
        """停止心跳保活线程"""
        if self._keepalive_thread:
            self._keepalive_stop_event.set()
            self._keepalive_thread.join(timeout=2)
            self._keepalive_thread = None
    
    def _keepalive_loop(self):
        """心跳保活循环"""
        while not self._keepalive_stop_event.is_set():
            try:
                if self._connected and self._client:
                    transport = self._client.get_transport()
                    if transport and transport.is_active():
                        transport.send_ignore()
                        self.logger.debug(f"心跳保活: {self._host}:{self._port}")
            except Exception as e:
                self.logger.warning(f"心跳保活失败: {self._host}:{self._port}, 错误: {e}")
                self._connected = False
                break
            
            self._keepalive_stop_event.wait(self._keepalive_interval)
    
    def execute(self, command: str, ignore_errors: bool = False, timeout: int = 120, 
                max_retries: int = 3, retry_delay: float = 2.0) -> Tuple[bool, str]:
        """执行远程命令（带重试机制和耗时监控）
        
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
                if not self._connected or not self.is_alive():
                    if not self.connect():
                        last_error = f"无法建立 SSH 连接: {self._last_error or '未知错误'}"
                        if attempt < max_retries - 1:
                            self.logger.warning(
                                f"连接失败，{retry_delay}秒后重试 "
                                f"(尝试 {attempt + 1}/{max_retries})"
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            return False, last_error
                
                start_time = time.time()
                
                try:
                    stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
                    
                    output = stdout.read().decode('utf-8')
                    error = stderr.read().decode('utf-8')
                    exit_status = stdout.channel.recv_exit_status()
                    
                    self._last_used = datetime.now()
                    duration = time.time() - start_time
                    self._stats.record_command(True, duration)
                    
                    if exit_status == 0 or ignore_errors:
                        return True, output + error
                    else:
                        return False, error
                        
                except Exception as e:
                    self._connected = False
                    self._last_error = str(e)
                    self._error_count += 1
                    
                    duration = time.time() - start_time
                    self._stats.record_command(False, duration)
                    
                    last_error = f"执行失败：{str(e)}"
                    
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            f"命令执行失败，{retry_delay}秒后重试 "
                            f"(尝试 {attempt + 1}/{max_retries}): {str(e)}"
                        )
                        time.sleep(retry_delay)
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
        status = {
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "connected": self._connected,
            "alive": self.is_alive() if self._connected else False,
            "last_used": self._last_used.isoformat() if self._last_used else None,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "stats": self._stats.to_dict(),
        }
        
        if self._circuit_breaker:
            status["circuit_breaker"] = self._circuit_breaker.get_status()
        
        return status


class SSHConnectionPool(metaclass=SingletonMeta):
    """SSH 连接池（增强版）
    
    新增功能：
    - 后台健康检查线程
    - 连接池预热
    - 统计信息汇总
    """
    
    def __init__(self, max_connections: int = 10, 
                 idle_timeout: int = 300,
                 health_check_interval: int = 60,
                 enable_health_check: bool = True):
        """初始化连接池
        
        Args:
            max_connections: 最大连接数
            idle_timeout: 空闲超时时间（秒）
            health_check_interval: 健康检查间隔（秒）
            enable_health_check: 是否启用后台健康检查
        """
        self._connections: Dict[str, SSHExecutor] = {}
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout
        self._pool_lock = threading.Lock()
        self._health_check_interval = health_check_interval
        self._last_health_check = datetime.now()
        self.logger = logging.getLogger(__name__)
        
        self._health_check_thread = None
        self._stop_health_check = threading.Event()
        self._enable_health_check = enable_health_check
        
        self._pool_stats = ConnectionStats()
        
        if enable_health_check:
            self._start_health_check_thread()
    
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
    
    def _start_health_check_thread(self):
        """启动后台健康检查线程"""
        if self._health_check_thread and self._health_check_thread.is_alive():
            return
        
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self._health_check_thread.start()
        self.logger.info("后台健康检查线程已启动")
    
    def _stop_health_check_thread(self):
        """停止后台健康检查线程"""
        if self._health_check_thread:
            self._stop_health_check.set()
            self._health_check_thread.join(timeout=5)
            self._health_check_thread = None
            self.logger.info("后台健康检查线程已停止")
    
    def _health_check_loop(self):
        """健康检查循环"""
        while not self._stop_health_check.is_set():
            try:
                self.health_check()
            except Exception as e:
                self.logger.error(f"健康检查异常: {e}")
            
            self._stop_health_check.wait(self._health_check_interval)
    
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
        
        with self._pool_lock:
            if key in self._connections:
                executor = self._connections[key]
                if executor.is_alive():
                    self.logger.debug(f"复用现有连接: {key}")
                    return executor
                self.logger.info(f"连接 {key} 不可用，需要重连")
                need_reconnect = True
            else:
                need_reconnect = False
                if len(self._connections) >= self._max_connections:
                    self.logger.info(
                        f"连接池已满 ({len(self._connections)}/{self._max_connections})，"
                        f"清理最旧连接"
                    )
                    self._cleanup_oldest()
        
        if need_reconnect:
            self.logger.info(f"尝试重连: {key}")
            if executor.reconnect():
                self.logger.info(f"重连成功: {key}")
                return executor
            else:
                self.logger.warning(f"重连失败: {key}，从连接池移除")
                with self._pool_lock:
                    if key in self._connections:
                        del self._connections[key]
                return self._create_new_connection(key, host, port, user, passwd, key_file)
        else:
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
                if key not in self._connections:
                    self._connections[key] = executor
                    self.logger.info(
                        f"新连接创建成功: {key}，"
                        f"当前连接池大小: {len(self._connections)}"
                    )
                else:
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
    
    def warmup(self, env_configs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """预热连接池
        
        Args:
            env_configs: 环境配置列表，每个配置包含:
                - host: 主机IP
                - port: SSH端口
                - user: 用户名
                - passwd: 密码
                - key_file: 密钥文件路径（可选）
                
        Returns:
            Dict[str, bool]: 预热结果，key为连接键，value为是否成功
        """
        self.logger.info(f"开始预热连接池，共 {len(env_configs)} 个环境")
        results = {}
        
        for config in env_configs:
            key = self._make_key(
                config.get("host"),
                config.get("port", 22),
                config.get("user", "root")
            )
            try:
                self.get_connection(**config)
                results[key] = True
                self.logger.info(f"预热成功: {key}")
            except Exception as e:
                results[key] = False
                self.logger.warning(f"预热失败: {key}, 错误: {e}")
        
        success_count = sum(1 for v in results.values() if v)
        self.logger.info(
            f"预热完成: 成功 {success_count}/{len(env_configs)}"
        )
        return results
    
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
        self._stop_health_check_thread()
        
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
                if executor.last_used:
                    idle_seconds = (now - executor.last_used).total_seconds()
                    if idle_seconds > self._idle_timeout:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._connections[key].disconnect()
                del self._connections[key]
                cleaned += 1
                self.logger.info(f"清理空闲连接: {key}")
        
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
                self.logger.info(f"健康检查清理无效连接: {key}")
        
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
            total_stats = ConnectionStats()
            
            for key, executor in self._connections.items():
                status = executor.get_status()
                connections_info.append(status)
                if status["alive"]:
                    alive_count += 1
                
                stats = executor.stats
                total_stats.total_connections += stats.total_connections
                total_stats.successful_connections += stats.successful_connections
                total_stats.failed_connections += stats.failed_connections
                total_stats.total_commands += stats.total_commands
                total_stats.successful_commands += stats.successful_commands
                total_stats.failed_commands += stats.failed_commands
                total_stats.total_connect_time += stats.total_connect_time
                total_stats.total_command_time += stats.total_command_time
            
            return {
                "max_connections": self._max_connections,
                "idle_timeout": self._idle_timeout,
                "total_connections": len(self._connections),
                "alive_connections": alive_count,
                "dead_connections": len(self._connections) - alive_count,
                "last_health_check": self._last_health_check.isoformat(),
                "health_check_enabled": self._enable_health_check,
                "connections": connections_info,
                "total_stats": total_stats.to_dict(),
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
