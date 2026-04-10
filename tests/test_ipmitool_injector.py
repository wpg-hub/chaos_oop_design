"""IpmiToolFaultInjector 功能测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from chaos.fault.base import IpmiToolFaultInjector


class TestIpmiToolFaultInjector(unittest.TestCase):
    """测试 IpmiToolFaultInjector 的功能"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_config_manager = Mock()
        self.mock_config_manager.config = {
            "bmc_environments": {
                "bmc_remote1": {
                    "ip": "192.168.1.100",
                    "user": "admin",
                    "passwd": "password1"
                },
                "bmc_remote2": {
                    "ip": "192.168.1.101",
                    "user": "admin",
                    "passwd": "password2"
                }
            }
        }
        self.mock_logger = Mock()
        self.injector = IpmiToolFaultInjector(
            self.mock_config_manager,
            self.mock_logger
        )
    
    def test_get_bmc_config_success(self):
        """测试获取 BMC 配置 - 成功"""
        result = self.injector._get_bmc_config("bmc_remote1")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.100")
        self.assertEqual(result["user"], "admin")
        self.assertEqual(result["passwd"], "password1")
    
    def test_get_bmc_config_not_found(self):
        """测试获取 BMC 配置 - 不存在"""
        result = self.injector._get_bmc_config("bmc_remote_not_exist")
        
        self.assertIsNone(result)
    
    def test_build_ipmitool_command_soft(self):
        """测试构建 ipmitool 命令 - soft"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "soft")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power soft"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_off(self):
        """测试构建 ipmitool 命令 - off"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "off")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power off"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_on(self):
        """测试构建 ipmitool 命令 - on"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "on")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power on"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_reset(self):
        """测试构建 ipmitool 命令 - reset"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "reset")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power reset"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_cycle(self):
        """测试构建 ipmitool 命令 - cycle"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "cycle")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power cycle"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_status(self):
        """测试构建 ipmitool 命令 - status"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "status")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password chassis power status"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_warm(self):
        """测试构建 ipmitool 命令 - warm"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "warm")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password mc reset warm"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_cold(self):
        """测试构建 ipmitool 命令 - cold"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "cold")
        
        expected = "ipmitool -I lanplus -H 192.168.1.100 -U admin -P password mc reset cold"
        self.assertEqual(result, expected)
    
    def test_build_ipmitool_command_unknown(self):
        """测试构建 ipmitool 命令 - 未知类型"""
        bmc_config = {
            "ip": "192.168.1.100",
            "user": "admin",
            "passwd": "password"
        }
        
        result = self.injector._build_ipmitool_command(bmc_config, "unknown")
        
        self.assertIsNone(result)
    
    @patch('subprocess.run')
    def test_execute_local_command_success(self, mock_run):
        """测试执行本地命令 - 成功"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Chassis Power is on"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        success, output = self.injector._execute_local_command("echo test")
        
        self.assertTrue(success)
        self.assertEqual(output, "Chassis Power is on")
    
    @patch('subprocess.run')
    def test_execute_local_command_failure(self, mock_run):
        """测试执行本地命令 - 失败"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Unable to establish LAN session"
        mock_run.return_value = mock_result
        
        success, output = self.injector._execute_local_command("ipmitool test")
        
        self.assertFalse(success)
        self.assertIn("Error", output)
    
    @patch('subprocess.run')
    def test_execute_local_command_timeout(self, mock_run):
        """测试执行本地命令 - 超时"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=30)
        
        success, output = self.injector._execute_local_command("sleep 60")
        
        self.assertFalse(success)
        self.assertEqual(output, "命令执行超时")
    
    @patch.object(IpmiToolFaultInjector, '_execute_local_command')
    def test_execute_on_single_bmc_success(self, mock_execute):
        """测试执行单个 BMC 命令 - 成功"""
        mock_execute.return_value = (True, "Chassis Power is on")
        
        result = self.injector._execute_on_single_bmc("bmc_remote1", "status")
        
        self.assertTrue(result)
        mock_execute.assert_called_once()
    
    @patch.object(IpmiToolFaultInjector, '_execute_local_command')
    def test_execute_on_single_bmc_failure(self, mock_execute):
        """测试执行单个 BMC 命令 - 失败"""
        mock_execute.return_value = (False, "Error: Unable to establish LAN session")
        
        result = self.injector._execute_on_single_bmc("bmc_remote1", "status")
        
        self.assertFalse(result)
    
    def test_execute_on_single_bmc_config_not_found(self):
        """测试执行单个 BMC 命令 - 配置不存在"""
        result = self.injector._execute_on_single_bmc("bmc_not_exist", "status")
        
        self.assertFalse(result)
    
    @patch.object(IpmiToolFaultInjector, '_execute_on_single_bmc')
    def test_execute_on_multiple_bmc_all_success(self, mock_execute):
        """测试并发执行多个 BMC 命令 - 全部成功"""
        mock_execute.return_value = True
        
        result = self.injector._execute_on_multiple_bmc(
            ["bmc_remote1", "bmc_remote2"],
            "status"
        )
        
        self.assertTrue(result)
        self.assertEqual(mock_execute.call_count, 2)
    
    @patch.object(IpmiToolFaultInjector, '_execute_on_single_bmc')
    def test_execute_on_multiple_bmc_partial_failure(self, mock_execute):
        """测试并发执行多个 BMC 命令 - 部分失败"""
        mock_execute.side_effect = [True, False]
        
        result = self.injector._execute_on_multiple_bmc(
            ["bmc_remote1", "bmc_remote2"],
            "status"
        )
        
        self.assertFalse(result)
        self.assertEqual(mock_execute.call_count, 2)
    
    @patch.object(IpmiToolFaultInjector, '_execute_on_multiple_bmc')
    def test_inject_success(self, mock_execute):
        """测试注入故障 - 成功"""
        mock_execute.return_value = True
        
        target = {
            "name": ["bmc_remote1", "bmc_remote2"]
        }
        parameters = {
            "fault_type": "status"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        mock_execute.assert_called_once_with(["bmc_remote1", "bmc_remote2"], "status")
    
    @patch.object(IpmiToolFaultInjector, '_execute_on_multiple_bmc')
    def test_inject_with_single_bmc(self, mock_execute):
        """测试注入故障 - 单个 BMC"""
        mock_execute.return_value = True
        
        target = {
            "name": "bmc_remote1"
        }
        parameters = {
            "fault_type": "status"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        mock_execute.assert_called_once_with(["bmc_remote1"], "status")
    
    @patch.object(IpmiToolFaultInjector, '_execute_on_multiple_bmc')
    def test_inject_with_default_fault_type(self, mock_execute):
        """测试注入故障 - 默认 fault_type"""
        mock_execute.return_value = True
        
        target = {
            "name": ["bmc_remote1"]
        }
        parameters = {}
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        mock_execute.assert_called_once_with(["bmc_remote1"], "status")
    
    def test_recover(self):
        """测试恢复故障"""
        result = self.injector.recover("test_fault_id")
        
        self.assertTrue(result)
    
    def test_get_fault_id(self):
        """测试获取故障 ID"""
        self.assertIsNone(self.injector.get_fault_id())
        
        self.injector.fault_id = "test_fault_id"
        self.assertEqual(self.injector.get_fault_id(), "test_fault_id")


if __name__ == '__main__':
    unittest.main()
