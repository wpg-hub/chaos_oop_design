"""
物理机命令执行注入器单元测试
测试命令执行操作
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import MagicMock, patch
from chaos.fault.base import ComputerCmdFaultInjector, FaultFactory
from chaos.config import ConfigManager, EnvironmentConfig


class TestComputerCmdFaultInjector(unittest.TestCase):
    """ComputerCmdFaultInjector 测试类"""
    
    def setUp(self):
        """测试初始化"""
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_logger = MagicMock()
        self.injector = ComputerCmdFaultInjector(
            config_manager=self.mock_config_manager,
            logger=self.mock_logger
        )
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_single_command_single_env(self, mock_get_ssh_pool):
        """测试单个命令执行（单个环境）"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "command output")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["ls -la"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertIsNotNone(self.injector.fault_id)
        self.assertIn("computer_cmd", self.injector.fault_id)
        mock_ssh_instance.execute.assert_called_once_with("ls -la")
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_multiple_commands_single_env(self, mock_get_ssh_pool):
        """测试多个命令执行（单个环境）"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "output")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["ls -la", "pwd", "whoami"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertEqual(mock_ssh_instance.execute.call_count, 3)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_commands_multiple_envs(self, mock_get_ssh_pool):
        """测试命令执行（多个环境）"""
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
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "output")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote", "2_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["ls -la"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertEqual(mock_ssh_instance.execute.call_count, 2)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_command_with_output(self, mock_get_ssh_pool):
        """测试命令执行并回显输出"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "total 0\ndrwxr-xr-x 2 root root 6 Apr 10 18:00 .")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["ls -la"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.mock_logger.info.assert_called()
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_command_failure(self, mock_get_ssh_pool):
        """测试命令执行失败"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (False, "command not found")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["invalid_command"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    def test_inject_env_not_exist(self):
        """测试环境不存在"""
        self.mock_config_manager.get_environment.return_value = None
        
        target = {
            "name": ["non_existent_env"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["ls -la"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_connection_failure(self, mock_get_ssh_pool):
        """测试连接失败"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = False
        mock_ssh_instance.connect.return_value = False
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": ["ls -la"]
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    def test_recover(self):
        """测试恢复操作"""
        result = self.injector.recover("computer_cmd_test_123")
        
        self.assertTrue(result)
    
    def test_get_fault_id(self):
        """测试获取故障 ID"""
        self.assertIsNone(self.injector.get_fault_id())
        
        self.injector.fault_id = "computer_cmd_test_123"
        self.assertEqual(self.injector.get_fault_id(), "computer_cmd_test_123")
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_single_cmd_string(self, mock_get_ssh_pool):
        """测试单个命令字符串（非列表）"""
        env_config = MagicMock(spec=EnvironmentConfig)
        env_config.ip = "10.230.246.167"
        env_config.port = 50163
        env_config.user = "root"
        env_config.passwd = "Gsta@123"
        
        self.mock_config_manager.get_environment.return_value = env_config
        
        mock_pool = MagicMock()
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.is_alive.return_value = True
        mock_ssh_instance.execute.return_value = (True, "output")
        mock_pool.get_connection.return_value = mock_ssh_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        target = {
            "name": ["1_ssh_remote"]
        }
        parameters = {
            "fault_type": "computer_cmd",
            "cmd": "ls -la"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        mock_ssh_instance.execute.assert_called_once_with("ls -la")


class TestFaultFactoryForComputerCmd(unittest.TestCase):
    """FaultFactory 测试类（computer_cmd）"""
    
    def test_create_computer_cmd_injector(self):
        """测试创建 computer_cmd 注入器"""
        mock_config_manager = MagicMock(spec=ConfigManager)
        mock_logger = MagicMock()
        
        injector = FaultFactory.create_injector(
            fault_type="cmd",
            config_manager=mock_config_manager,
            logger=mock_logger
        )
        
        self.assertIsInstance(injector, ComputerCmdFaultInjector)
    
    def test_computer_cmd_injector_registered(self):
        """测试 computer_cmd 注入器已注册"""
        from chaos.fault.base import FaultInjectorRegistry
        
        self.assertIn("cmd", FaultInjectorRegistry._registry)
        self.assertEqual(FaultInjectorRegistry._registry["cmd"], ComputerCmdFaultInjector)


if __name__ == '__main__':
    unittest.main()
