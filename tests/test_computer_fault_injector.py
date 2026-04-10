"""
物理机故障注入器单元测试
测试 reboot 操作
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import MagicMock, patch
from chaos.fault.base import ComputerFaultInjector, FaultFactory
from chaos.config import ConfigManager, EnvironmentConfig


class TestComputerFaultInjector(unittest.TestCase):
    """ComputerFaultInjector 测试类"""
    
    def setUp(self):
        """测试初始化"""
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_logger = MagicMock()
        self.injector = ComputerFaultInjector(
            config_manager=self.mock_config_manager,
            logger=self.mock_logger
        )
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_reboot_single_env(self, mock_get_ssh_pool):
        """测试 reboot 操作（单个环境）"""
        # Mock 环境配置
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        # Mock SSH 连接池
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "reboot"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertIsNotNone(self.injector.fault_id)
        self.assertIn("reboot", self.injector.fault_id)
        mock_ssh_instance.execute.assert_called_once_with("reboot", ignore_errors=True)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_reboot_multiple_envs(self, mock_get_ssh_pool):
        """测试 reboot 操作（多个环境）"""
        # Mock 环境配置
        env_config1 = MagicMock(spec=EnvironmentConfig)
        env_config1.ip = "10.230.246.167"
        env_config1.port = 50163
        env_config1.user = "root"
        env_config1.passwd = "Gsta@123"
        
        env_config2 = MagicMock(spec=EnvironmentConfig)
        env_config2.ip = "10.230.246.168"
        env_config2.port = 50163
        env_config2.user = "root"
        env_config2.passwd = "Gsta@123"
        
        def get_env_side_effect(name):
            if name == "1_ssh_remote":
                return env_config1
            elif name == "2_ssh_remote":
                return env_config2
            return None
        
        self.mock_config_manager.get_environment.side_effect = get_env_side_effect
        
        # Mock SSH 连接池
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote", "2_ssh_remote"]
        }
        parameters = {
            "fault_type": "reboot"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertEqual(mock_ssh_instance.execute.call_count, 2)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_reboot_connection_closed(self, mock_get_ssh_pool):
        """测试 reboot 操作（连接关闭视为成功）"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        # Mock SSH 连接池
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (False, "Connection closed by remote host")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "reboot"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
    
    def test_inject_env_not_found(self):
        """测试环境不存在的情况"""
        self.mock_config_manager.get_environment.return_value = None
        
        target = {
            "name": ["non_existent_env"]
        }
        parameters = {
            "fault_type": "reboot"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    def test_inject_connection_failed(self):
        """测试连接失败的情况"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        with patch('chaos.utils.remote.SSHExecutor') as mock_ssh_class:
            mock_ssh_instance = MagicMock()
            mock_ssh_class.return_value = mock_ssh_instance
            mock_ssh_instance.connect.return_value = False
            
            target = {
                "name": ["1_ssh_remote"]
            }
            parameters = {
                "fault_type": "reboot"
            }
            
            result = self.injector.inject(target, parameters)
            
            self.assertFalse(result)
    
    def test_inject_unknown_fault_type(self):
        """测试未知的故障类型"""
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "unknown"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    def test_recover(self):
        """测试恢复操作"""
        result = self.injector.recover("reboot_1_ssh_remote_123456")
        
        self.assertTrue(result)
    
    def test_get_fault_id(self):
        """测试获取故障 ID"""
        self.assertIsNone(self.injector.get_fault_id())
        
        self.injector.fault_id = "test_fault_id"
        self.assertEqual(self.injector.get_fault_id(), "test_fault_id")
    
    def test_is_reboot_success(self):
        """测试判断重启是否成功"""
        self.assertTrue(self.injector._is_reboot_success("Connection closed by remote host"))
        self.assertTrue(self.injector._is_reboot_success("Connection refused"))
        self.assertTrue(self.injector._is_reboot_success("No route to host"))
        self.assertTrue(self.injector._is_reboot_success("Connection timed out"))
        self.assertFalse(self.injector._is_reboot_success("Permission denied"))


class TestFaultFactoryComputer(unittest.TestCase):
    """FaultFactory computer 类型测试"""
    
    def test_create_computer_injector(self):
        """测试创建 computer 类型的注入器"""
        mock_config_manager = MagicMock()
        mock_logger = MagicMock()
        
        injector = FaultFactory.create_injector(
            fault_type="computer",
            config_manager=mock_config_manager,
            logger=mock_logger
        )
        
        self.assertIsInstance(injector, ComputerFaultInjector)
    
    def test_register_computer_injector(self):
        """测试 computer 注入器已注册"""
        self.assertTrue(FaultFactory.is_registered("computer"))


if __name__ == '__main__':
    unittest.main()
