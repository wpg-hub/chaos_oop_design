"""协议一致性测试

验证实现类是否符合协议定义的接口。
"""

import unittest
from unittest.mock import MagicMock

from chaos.protocols import (
    ConfigManagerProtocol,
    FaultInjectorProtocol,
    FaultFactoryProtocol,
    StateManagerProtocol,
    RemoteExecutorProtocol,
    LoggerProtocol,
)
from chaos.config import ConfigManager
from chaos.fault.base import FaultFactory, NetworkFaultInjector, PodFaultInjector
from chaos.fault.registry import FaultInjectorRegistry
from chaos.state.manager import StateManager
from chaos.utils.remote import SSHExecutor, SSHConnectionPool


class TestProtocolCompliance(unittest.TestCase):
    """协议一致性测试"""
    
    def test_config_manager_protocol_compliance(self):
        """测试 ConfigManager 是否符合 ConfigManagerProtocol"""
        config_manager = ConfigManager.__new__(ConfigManager)
        config_manager.config = {}
        
        self.assertIsInstance(config_manager, ConfigManagerProtocol)
    
    def test_state_manager_protocol_compliance(self):
        """测试 StateManager 是否符合 StateManagerProtocol"""
        mock_repository = MagicMock()
        mock_logger = MagicMock()
        state_manager = StateManager(repository=mock_repository, logger=mock_logger)
        
        self.assertIsInstance(state_manager, StateManagerProtocol)
    
    def test_ssh_executor_protocol_compliance(self):
        """测试 SSHExecutor 是否符合 RemoteExecutorProtocol"""
        executor = SSHExecutor(host="192.168.1.1", user="root", passwd="test")
        
        self.assertIsInstance(executor, RemoteExecutorProtocol)
        
        self.assertTrue(hasattr(executor, 'host'))
        self.assertTrue(hasattr(executor, 'port'))
        self.assertTrue(hasattr(executor, 'user'))
        self.assertTrue(callable(getattr(executor, 'execute', None)))
        self.assertTrue(callable(getattr(executor, 'connect', None)))
        self.assertTrue(callable(getattr(executor, 'disconnect', None)))
        self.assertTrue(callable(getattr(executor, 'is_alive', None)))
        self.assertTrue(callable(getattr(executor, 'reconnect', None)))
    
    def test_fault_factory_protocol_compliance(self):
        """测试 FaultFactory 是否符合 FaultFactoryProtocol"""
        self.assertTrue(hasattr(FaultFactory, 'create_injector'))
        self.assertTrue(callable(getattr(FaultFactory, 'create_injector', None)))
        self.assertTrue(hasattr(FaultFactory, 'get_registered_types'))
        self.assertTrue(callable(getattr(FaultFactory, 'get_registered_types', None)))
    
    def test_fault_injector_protocol_compliance(self):
        """测试故障注入器是否符合 FaultInjectorProtocol"""
        mock_executor = MagicMock()
        mock_logger = MagicMock()
        
        network_injector = NetworkFaultInjector(mock_executor, mock_logger)
        self.assertIsInstance(network_injector, FaultInjectorProtocol)
        
        pod_injector = PodFaultInjector(mock_executor, mock_logger)
        self.assertIsInstance(pod_injector, FaultInjectorProtocol)
    
    def test_logger_protocol_compliance(self):
        """测试 Logger 是否符合 LoggerProtocol"""
        import logging
        logger = logging.getLogger('test')
        
        self.assertIsInstance(logger, LoggerProtocol)


class TestSSHConnectionPoolProtocolCompliance(unittest.TestCase):
    """SSH 连接池协议一致性测试"""
    
    def test_pool_singleton_behavior(self):
        """测试连接池单例行为"""
        from chaos.utils.singleton import SingletonMeta
        
        self.assertEqual(type(SSHConnectionPool), SingletonMeta)
    
    def test_pool_has_required_methods(self):
        """测试连接池具有必要的方法"""
        required_methods = [
            'get_connection',
            'close_connection',
            'close_all',
            'cleanup_idle',
            'health_check',
            'get_pool_status',
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(SSHConnectionPool, method),
                f"SSHConnectionPool 缺少方法: {method}"
            )


class TestFaultInjectorRegistryProtocolCompliance(unittest.TestCase):
    """故障注入器注册表协议一致性测试"""
    
    def test_registry_has_required_methods(self):
        """测试注册表具有必要的方法"""
        required_methods = [
            'register',
            'create',
            'get_registered_types',
            'is_registered',
            'unregister',
            'clear',
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(FaultInjectorRegistry, method),
                f"FaultInjectorRegistry 缺少方法: {method}"
            )
    
    def test_registry_type_validation(self):
        """测试注册表类型验证"""
        class InvalidInjector:
            pass
        
        with self.assertRaises(TypeError):
            FaultInjectorRegistry.register("invalid", InvalidInjector)


if __name__ == '__main__':
    unittest.main()
