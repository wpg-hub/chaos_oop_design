#!/usr/bin/env python3
"""SSH模块优化单元测试

测试覆盖：
1. ConnectionStats - 连接统计
2. CircuitBreaker - 熔断器
3. SSHExecutor - SSH执行器增强功能
4. SSHConnectionPool - 连接池增强功能
"""

import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chaos.utils.remote import (
    CircuitState,
    ConnectionStats,
    CircuitBreaker,
    SSHExecutor,
    SSHConnectionPool,
    get_ssh_pool,
)
from chaos.utils.singleton import SingletonMeta


class TestConnectionStats:
    """ConnectionStats 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        stats = ConnectionStats()
        assert stats.total_connections == 0
        assert stats.successful_connections == 0
        assert stats.failed_connections == 0
        assert stats.total_commands == 0
        assert stats.avg_connect_time == 0.0
        assert stats.avg_command_time == 0.0
    
    def test_record_connect_success(self):
        """测试记录成功连接"""
        stats = ConnectionStats()
        stats.record_connect(True, 1.5)
        
        assert stats.total_connections == 1
        assert stats.successful_connections == 1
        assert stats.failed_connections == 0
        assert stats.last_connect_time == 1.5
        assert stats.min_connect_time == 1.5
        assert stats.max_connect_time == 1.5
    
    def test_record_connect_failure(self):
        """测试记录失败连接"""
        stats = ConnectionStats()
        stats.record_connect(False, 2.0)
        
        assert stats.total_connections == 1
        assert stats.successful_connections == 0
        assert stats.failed_connections == 1
        assert stats.last_connect_time == 2.0
    
    def test_record_connect_multiple(self):
        """测试记录多次连接"""
        stats = ConnectionStats()
        stats.record_connect(True, 1.0)
        stats.record_connect(True, 2.0)
        stats.record_connect(False, 3.0)
        
        assert stats.total_connections == 3
        assert stats.successful_connections == 2
        assert stats.failed_connections == 1
        assert stats.min_connect_time == 1.0
        assert stats.max_connect_time == 3.0
        assert stats.avg_connect_time == 2.0
    
    def test_record_command_success(self):
        """测试记录成功命令"""
        stats = ConnectionStats()
        stats.record_command(True, 0.5)
        
        assert stats.total_commands == 1
        assert stats.successful_commands == 1
        assert stats.failed_commands == 0
        assert stats.last_command_time == 0.5
    
    def test_record_command_failure(self):
        """测试记录失败命令"""
        stats = ConnectionStats()
        stats.record_command(False, 1.0)
        
        assert stats.total_commands == 1
        assert stats.successful_commands == 0
        assert stats.failed_commands == 1
    
    def test_success_rate(self):
        """测试成功率计算"""
        stats = ConnectionStats()
        assert stats.connection_success_rate == 0.0
        assert stats.command_success_rate == 0.0
        
        stats.record_connect(True, 1.0)
        stats.record_connect(True, 1.0)
        stats.record_connect(False, 1.0)
        
        assert stats.connection_success_rate == pytest.approx(2/3, 0.01)
    
    def test_to_dict(self):
        """测试转换为字典"""
        stats = ConnectionStats()
        stats.record_connect(True, 1.5)
        stats.record_command(True, 0.5)
        
        result = stats.to_dict()
        
        assert isinstance(result, dict)
        assert result["total_connections"] == 1
        assert result["successful_connections"] == 1
        assert result["avg_connect_time"] == 1.5
        assert result["connection_success_rate"] == 1.0


class TestCircuitBreaker:
    """CircuitBreaker 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        
        assert cb.state == CircuitState.CLOSED
        status = cb.get_status()
        assert status["failure_threshold"] == 5
        assert status["recovery_timeout"] == 30
    
    def test_closed_state_allows_execution(self):
        """测试CLOSED状态允许执行"""
        cb = CircuitBreaker()
        assert cb.can_execute() is True
    
    def test_failure_threshold_opens_circuit(self):
        """测试失败阈值触发熔断"""
        cb = CircuitBreaker(failure_threshold=3)
        
        assert cb.can_execute() is True
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
    
    def test_open_state_blocks_execution(self):
        """测试OPEN状态阻止执行"""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
    
    def test_success_resets_failure_count(self):
        """测试成功重置失败计数"""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        
        status = cb.get_status()
        assert status["failure_count"] == 0
        assert cb.state == CircuitState.CLOSED
    
    def test_recovery_timeout_transitions_to_half_open(self):
        """测试恢复超时转换到HALF_OPEN状态"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        
        time.sleep(1.1)
        
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute() is True
    
    def test_half_open_success_closes_circuit(self):
        """测试HALF_OPEN状态成功后关闭熔断器"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        cb.record_failure()
        time.sleep(1.1)
        
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        
        assert cb.state == CircuitState.CLOSED
    
    def test_half_open_failure_reopens_circuit(self):
        """测试HALF_OPEN状态失败后重新打开熔断器"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        cb.record_failure()
        time.sleep(1.1)
        
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        
        assert cb.state == CircuitState.OPEN
    
    def test_reset(self):
        """测试重置熔断器"""
        cb = CircuitBreaker(failure_threshold=1)
        
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        status = cb.get_status()
        assert status["failure_count"] == 0
    
    def test_get_status(self):
        """测试获取状态"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        
        status = cb.get_status()
        
        assert status["state"] == "closed"
        assert status["failure_count"] == 1
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout"] == 60
        assert status["last_failure_time"] is not None


class TestSSHExecutor:
    """SSHExecutor 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        executor = SSHExecutor(
            host="192.168.1.1",
            port=22,
            user="root",
            passwd="password"
        )
        
        assert executor.host == "192.168.1.1"
        assert executor.port == 22
        assert executor.user == "root"
        assert executor.error_count == 0
        assert executor.last_error is None
    
    def test_init_with_circuit_breaker(self):
        """测试带熔断器初始化"""
        executor = SSHExecutor(
            host="192.168.1.1",
            enable_circuit_breaker=True,
            circuit_breaker_config={
                "failure_threshold": 5,
                "recovery_timeout": 30
            }
        )
        
        assert executor.circuit_breaker is not None
        status = executor.circuit_breaker.get_status()
        assert status["failure_threshold"] == 5
        assert status["recovery_timeout"] == 30
    
    def test_init_without_circuit_breaker(self):
        """测试不启用熔断器初始化"""
        executor = SSHExecutor(
            host="192.168.1.1",
            enable_circuit_breaker=False
        )
        
        assert executor.circuit_breaker is None
    
    def test_stats_tracking(self):
        """测试统计追踪"""
        executor = SSHExecutor(host="192.168.1.1", passwd="test")
        
        assert executor.stats.total_connections == 0
        
        with patch.object(executor, '_check_port_reachable', return_value=(True, "")):
            with patch('paramiko.SSHClient') as mock_ssh:
                mock_client = MagicMock()
                mock_ssh.return_value = mock_client
                mock_transport = MagicMock()
                mock_transport.is_active.return_value = True
                mock_client.get_transport.return_value = mock_transport
                
                executor.connect()
        
        assert executor.stats.total_connections == 1
        assert executor.stats.successful_connections == 1
    
    def test_check_port_reachable_success(self):
        """测试端口可达性检查成功"""
        executor = SSHExecutor(host="127.0.0.1", port=22, connect_timeout=1)
        
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock
            
            reachable, error = executor._check_port_reachable()
            
            assert reachable is True
            assert error == ""
    
    def test_check_port_reachable_failure(self):
        """测试端口可达性检查失败"""
        executor = SSHExecutor(host="192.168.1.1", port=22, connect_timeout=1)
        
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 111
            mock_socket.return_value = mock_sock
            
            reachable, error = executor._check_port_reachable()
            
            assert reachable is False
            assert "不可达" in error
    
    def test_check_port_reachable_timeout(self):
        """测试端口可达性检查超时"""
        executor = SSHExecutor(host="192.168.1.1", port=22, connect_timeout=1)
        
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.side_effect = TimeoutError()
            mock_socket.return_value = mock_sock
            
            reachable, error = executor._check_port_reachable()
            
            assert reachable is False
    
    def test_get_status(self):
        """测试获取状态"""
        executor = SSHExecutor(host="192.168.1.1", port=2222, user="test")
        
        status = executor.get_status()
        
        assert status["host"] == "192.168.1.1"
        assert status["port"] == 2222
        assert status["user"] == "test"
        assert status["connected"] is False
        assert status["alive"] is False
        assert "stats" in status
    
    def test_get_status_with_circuit_breaker(self):
        """测试获取带熔断器的状态"""
        executor = SSHExecutor(
            host="192.168.1.1",
            enable_circuit_breaker=True
        )
        
        status = executor.get_status()
        
        assert "circuit_breaker" in status
        assert status["circuit_breaker"]["state"] == "closed"
    
    def test_disconnect(self):
        """测试断开连接"""
        executor = SSHExecutor(host="192.168.1.1", passwd="test")
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = MagicMock()
            mock_ssh.return_value = mock_client
            mock_transport = MagicMock()
            mock_transport.is_active.return_value = True
            mock_client.get_transport.return_value = mock_transport
            
            with patch.object(executor, '_check_port_reachable', return_value=(True, "")):
                executor.connect()
            
            executor.disconnect()
            
            assert executor._connected is False
            mock_client.close.assert_called_once()


class TestSSHConnectionPool:
    """SSHConnectionPool 单元测试"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        SingletonMeta._instances.pop(SSHConnectionPool, None)
        SingletonMeta._initialized.pop(SSHConnectionPool, None)
    
    def test_init(self):
        """测试初始化"""
        pool = SSHConnectionPool(
            max_connections=5,
            idle_timeout=60,
            enable_health_check=False
        )
        
        assert pool.connection_count == 0
    
    def test_make_key(self):
        """测试生成连接键"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        key = pool._make_key("192.168.1.1", 22, "root")
        
        assert key == "root@192.168.1.1:22"
    
    def test_get_pool_status(self):
        """测试获取连接池状态"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        status = pool.get_pool_status()
        
        assert status["total_connections"] == 0
        assert status["alive_connections"] == 0
        assert status["health_check_enabled"] is False
    
    def test_close_all(self):
        """测试关闭所有连接"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        pool.close_all()
        
        assert pool.connection_count == 0
    
    def test_cleanup_idle(self):
        """测试清理空闲连接"""
        pool = SSHConnectionPool(idle_timeout=1, enable_health_check=False)
        
        cleaned = pool.cleanup_idle()
        
        assert cleaned == 0
    
    def test_warmup_empty(self):
        """测试空预热"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        results = pool.warmup([])
        
        assert results == {}
    
    def test_warmup_with_configs(self):
        """测试带配置的预热"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        with patch.object(pool, 'get_connection') as mock_get:
            mock_get.return_value = MagicMock()
            
            configs = [
                {"host": "192.168.1.1", "port": 22, "user": "root", "passwd": "pass"}
            ]
            
            results = pool.warmup(configs)
            
            assert "root@192.168.1.1:22" in results
            assert results["root@192.168.1.1:22"] is True
    
    def test_warmup_with_failure(self):
        """测试预热失败"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        with patch.object(pool, 'get_connection') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            
            configs = [
                {"host": "192.168.1.1", "port": 22, "user": "root", "passwd": "pass"}
            ]
            
            results = pool.warmup(configs)
            
            assert "root@192.168.1.1:22" in results
            assert results["root@192.168.1.1:22"] is False
    
    def test_health_check(self):
        """测试健康检查"""
        pool = SSHConnectionPool(enable_health_check=False)
        
        results = pool.health_check()
        
        assert results["total_connections"] == 0
        assert results["alive_connections"] == 0
        assert results["dead_connections"] == 0
        assert results["cleaned_connections"] == 0


class TestGetSSHPool:
    """get_ssh_pool 单元测试"""
    
    def test_returns_singleton(self):
        """测试返回单例"""
        pool1 = get_ssh_pool()
        pool2 = get_ssh_pool()
        
        assert pool1 is pool2


class TestThreadSafety:
    """线程安全测试"""
    
    def test_circuit_breaker_thread_safety(self):
        """测试熔断器线程安全"""
        cb = CircuitBreaker(failure_threshold=100)
        success_count = [0]
        lock = threading.Lock()
        
        def record_success():
            for _ in range(100):
                cb.record_success()
                with lock:
                    success_count[0] += 1
        
        threads = [threading.Thread(target=record_success) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert success_count[0] == 1000
        assert cb.state == CircuitState.CLOSED
    
    def test_connection_stats_thread_safety(self):
        """测试连接统计线程安全"""
        stats = ConnectionStats()
        
        def record_connect():
            for _ in range(100):
                stats.record_connect(True, 0.1)
        
        threads = [threading.Thread(target=record_connect) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert stats.total_connections == 1000
        assert stats.successful_connections == 1000


class TestEdgeCases:
    """边界情况测试"""
    
    def test_circuit_breaker_zero_threshold(self):
        """测试熔断器零阈值"""
        cb = CircuitBreaker(failure_threshold=0)
        
        assert cb.can_execute() is True
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
    
    def test_connection_stats_zero_division(self):
        """测试连接统计零除"""
        stats = ConnectionStats()
        
        assert stats.avg_connect_time == 0.0
        assert stats.avg_command_time == 0.0
        assert stats.connection_success_rate == 0.0
        assert stats.command_success_rate == 0.0
    
    def test_ssh_executor_no_credentials(self):
        """测试SSH执行器无凭据"""
        executor = SSHExecutor(host="192.168.1.1")
        
        with patch.object(executor, '_check_port_reachable', return_value=(True, "")):
            result = executor.connect()
            
            assert result is False
            assert "未提供认证凭据" in executor.last_error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
