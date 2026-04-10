"""NetworkFaultInjector 数据包破坏注入功能测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from chaos.fault.base import NetworkFaultInjector


class TestNetworkFaultInjectorCorrupt(unittest.TestCase):
    """测试 NetworkFaultInjector 的数据包破坏注入功能"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_remote_executor = Mock()
        self.mock_logger = Mock()
        self.injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger
        )
    
    def test_parse_corrupt_percent_param_with_string(self):
        """测试解析损坏比例参数 - 字符串"""
        result = self.injector._parse_corrupt_percent_param("1%")
        self.assertEqual(result, "1%")
    
    def test_parse_corrupt_percent_param_with_list(self):
        """测试解析损坏比例参数 - 列表"""
        result = self.injector._parse_corrupt_percent_param(["10%", "90%"])
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 10)
        self.assertLessEqual(percent_value, 90)
    
    def test_parse_corrupt_percent_param_with_none(self):
        """测试解析损坏比例参数 - None（随机生成）"""
        result = self.injector._parse_corrupt_percent_param(None)
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 1)
        self.assertLessEqual(percent_value, 90)
    
    def test_parse_corrupt_correlation_param_with_string(self):
        """测试解析相关性参数 - 字符串"""
        result = self.injector._parse_corrupt_correlation_param("25%")
        self.assertEqual(result, "25%")
    
    def test_parse_corrupt_correlation_param_with_list(self):
        """测试解析相关性参数 - 列表"""
        result = self.injector._parse_corrupt_correlation_param(["10%", "90%"])
        self.assertIn("%", result)
        correlation_value = float(result.replace("%", ""))
        self.assertGreaterEqual(correlation_value, 10)
        self.assertLessEqual(correlation_value, 90)
    
    def test_parse_corrupt_correlation_param_with_none(self):
        """测试解析相关性参数 - None（随机生成）"""
        result = self.injector._parse_corrupt_correlation_param(None)
        self.assertIn("%", result)
        correlation_value = float(result.replace("%", ""))
        self.assertGreaterEqual(correlation_value, 1)
        self.assertLessEqual(correlation_value, 90)
    
    def test_build_tc_corrupt_command(self):
        """测试构建 tc 数据包破坏命令"""
        result = self.injector._build_tc_corrupt_command("eth0", "0.5%", "25%")
        
        expected = "tc qdisc add dev eth0 root netem corrupt 0.5% 25%"
        self.assertEqual(result, expected)
    
    def test_build_tc_corrupt_command_with_different_device(self):
        """测试构建 tc 数据包破坏命令 - 不同网卡"""
        result = self.injector._build_tc_corrupt_command("eth1", "2%", "30%")
        
        expected = "tc qdisc add dev eth1 root netem corrupt 2% 30%"
        self.assertEqual(result, expected)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_corrupt_success(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包破坏 - 成功"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (True, "")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = 12345        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "corrupt",
            "percent": "0.5%",
            "correlation": "25%"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        mock_get_container_id.assert_called_once()
        mock_get_pid.assert_called_once()
        mock_node_executor.execute.assert_called_once()
        
        call_args = mock_node_executor.execute.call_args
        command = call_args[0][0]
        self.assertIn("nsenter", command)
        self.assertIn("tc qdisc add", command)
        self.assertIn("corrupt 0.5% 25%", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_corrupt_with_random_params(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包破坏 - 随机参数"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (True, "")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = 12345        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "corrupt"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        
        call_args = mock_node_executor.execute.call_args
        command = call_args[0][0]
        self.assertIn("corrupt", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    def test_inject_corrupt_no_container_id(self, mock_get_container_id):
        """测试注入数据包破坏 - 无法获取容器 ID"""
        mock_get_container_id.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "corrupt"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_corrupt_no_pid(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包破坏 - 无法获取 PID"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (True, "")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "corrupt"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_corrupt_execution_failure(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包破坏 - 执行失败"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (False, "Error")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = 12345        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "corrupt",
            "percent": "1%",
            "correlation": "25%"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
