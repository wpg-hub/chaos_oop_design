"""NetworkFaultInjector 数据包重复注入功能测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from chaos.fault.base import NetworkFaultInjector


class TestNetworkFaultInjectorDuplicate(unittest.TestCase):
    """测试 NetworkFaultInjector 的数据包重复注入功能"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_remote_executor = Mock()
        self.mock_logger = Mock()
        self.injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger
        )
    
    def test_parse_duplicate_percent_param_with_string(self):
        """测试解析重复比例参数 - 字符串"""
        result = self.injector._parse_duplicate_percent_param("0.5%")
        self.assertEqual(result, "0.5%")
    
    def test_parse_duplicate_percent_param_with_list(self):
        """测试解析重复比例参数 - 列表"""
        result = self.injector._parse_duplicate_percent_param(["0.5%", "10%"])
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 0.5)
        self.assertLessEqual(percent_value, 10)
    
    def test_parse_duplicate_percent_param_with_none(self):
        """测试解析重复比例参数 - None（随机生成）"""
        result = self.injector._parse_duplicate_percent_param(None)
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 0.5)
        self.assertLessEqual(percent_value, 10)
    
    def test_parse_duplicate_correlation_param_with_string(self):
        """测试解析相关性参数 - 字符串"""
        result = self.injector._parse_duplicate_correlation_param("25%")
        self.assertEqual(result, "25%")
    
    def test_parse_duplicate_correlation_param_with_list(self):
        """测试解析相关性参数 - 列表"""
        result = self.injector._parse_duplicate_correlation_param(["10%", "90%"])
        self.assertIn("%", result)
        correlation_value = float(result.replace("%", ""))
        self.assertGreaterEqual(correlation_value, 10)
        self.assertLessEqual(correlation_value, 90)
    
    def test_parse_duplicate_correlation_param_with_none(self):
        """测试解析相关性参数 - None（随机生成）"""
        result = self.injector._parse_duplicate_correlation_param(None)
        self.assertIn("%", result)
        correlation_value = float(result.replace("%", ""))
        self.assertGreaterEqual(correlation_value, 1)
        self.assertLessEqual(correlation_value, 90)
    
    def test_build_tc_duplicate_command(self):
        """测试构建 tc 数据包重复命令"""
        result = self.injector._build_tc_duplicate_command("eth0", "0.3%", "50%")
        
        expected = "tc qdisc add dev eth0 root netem duplicate 0.3% 50%"
        self.assertEqual(result, expected)
    
    def test_build_tc_duplicate_command_with_different_device(self):
        """测试构建 tc 数据包重复命令 - 不同网卡"""
        result = self.injector._build_tc_duplicate_command("eth1", "1%", "30%")
        
        expected = "tc qdisc add dev eth1 root netem duplicate 1% 30%"
        self.assertEqual(result, expected)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_duplicate_success(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重复 - 成功"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (True, "")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "duplicate",
            "percent": "0.3%",
            "correlation": "50%"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        mock_get_container_id.assert_called_once()
        mock_get_pid.assert_called_once()
        self.mock_remote_executor.execute.assert_called_once()
        
        call_args = self.mock_remote_executor.execute.call_args
        command = call_args[0][0]
        self.assertIn("nsenter", command)
        self.assertIn("tc qdisc add", command)
        self.assertIn("duplicate 0.3% 50%", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_duplicate_with_random_params(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重复 - 随机参数"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (True, "")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "duplicate"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        
        call_args = self.mock_remote_executor.execute.call_args
        command = call_args[0][0]
        self.assertIn("duplicate", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    def test_inject_duplicate_no_container_id(self, mock_get_container_id):
        """测试注入数据包重复 - 无法获取容器 ID"""
        mock_get_container_id.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "duplicate"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_duplicate_no_pid(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重复 - 无法获取 PID"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "duplicate"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_duplicate_execution_failure(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重复 - 执行失败"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (False, "Error")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "duplicate",
            "percent": "0.5%",
            "correlation": "25%"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
