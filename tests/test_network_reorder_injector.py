"""NetworkFaultInjector 数据包重排序注入功能测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from chaos.fault.base import NetworkFaultInjector


class TestNetworkFaultInjectorReorder(unittest.TestCase):
    """测试 NetworkFaultInjector 的数据包重排序注入功能"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_remote_executor = Mock()
        self.mock_logger = Mock()
        self.injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger
        )
    
    def test_parse_reorder_percent_param_with_string(self):
        """测试解析重排序比例参数 - 字符串"""
        result = self.injector._parse_reorder_percent_param("0.5%")
        self.assertEqual(result, "0.5%")
    
    def test_parse_reorder_percent_param_with_list(self):
        """测试解析重排序比例参数 - 列表"""
        result = self.injector._parse_reorder_percent_param(["0.5%", "10%"])
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 0.5)
        self.assertLessEqual(percent_value, 10)
    
    def test_parse_reorder_percent_param_with_none(self):
        """测试解析重排序比例参数 - None（随机生成）"""
        result = self.injector._parse_reorder_percent_param(None)
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 0.5)
        self.assertLessEqual(percent_value, 10)
    
    def test_parse_reorder_correlation_param_with_string(self):
        """测试解析相关性参数 - 字符串"""
        result = self.injector._parse_reorder_correlation_param("25%")
        self.assertEqual(result, "25%")
    
    def test_parse_reorder_correlation_param_with_list(self):
        """测试解析相关性参数 - 列表"""
        result = self.injector._parse_reorder_correlation_param(["10%", "90%"])
        self.assertIn("%", result)
        correlation_value = float(result.replace("%", ""))
        self.assertGreaterEqual(correlation_value, 10)
        self.assertLessEqual(correlation_value, 90)
    
    def test_parse_reorder_correlation_param_with_none(self):
        """测试解析相关性参数 - None（随机生成）"""
        result = self.injector._parse_reorder_correlation_param(None)
        self.assertIn("%", result)
        correlation_value = float(result.replace("%", ""))
        self.assertGreaterEqual(correlation_value, 1)
        self.assertLessEqual(correlation_value, 90)
    
    def test_parse_reorder_gap_param_with_int(self):
        """测试解析 gap 参数 - 整数"""
        result = self.injector._parse_reorder_gap_param(5)
        self.assertEqual(result, 5)
    
    def test_parse_reorder_gap_param_with_list(self):
        """测试解析 gap 参数 - 列表"""
        result = self.injector._parse_reorder_gap_param([1, 100])
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
        self.assertLessEqual(result, 100)
    
    def test_parse_reorder_gap_param_with_none(self):
        """测试解析 gap 参数 - None（随机生成）"""
        result = self.injector._parse_reorder_gap_param(None)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
        self.assertLessEqual(result, 100)
    
    def test_build_tc_reorder_command(self):
        """测试构建 tc 数据包重排序命令"""
        result = self.injector._build_tc_reorder_command("eth0", "20%", "50%", 5)
        
        expected = "tc qdisc add dev eth0 root netem delay 100ms reorder 20% 50% gap 5"
        self.assertEqual(result, expected)
    
    def test_build_tc_reorder_command_with_different_device(self):
        """测试构建 tc 数据包重排序命令 - 不同网卡"""
        result = self.injector._build_tc_reorder_command("eth1", "1%", "30%", 3)
        
        expected = "tc qdisc add dev eth1 root netem delay 100ms reorder 1% 30% gap 3"
        self.assertEqual(result, expected)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_reorder_success(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重排序 - 成功"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (True, "")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "reorder",
            "percent": "20%",
            "correlation": "50%",
            "gap": 5
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
        self.assertIn("delay 100ms reorder 20% 50% gap 5", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_reorder_with_random_params(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重排序 - 随机参数"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (True, "")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "reorder"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        
        call_args = self.mock_remote_executor.execute.call_args
        command = call_args[0][0]
        self.assertIn("reorder", command)
        self.assertIn("gap", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    def test_inject_reorder_no_container_id(self, mock_get_container_id):
        """测试注入数据包重排序 - 无法获取容器 ID"""
        mock_get_container_id.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "reorder"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_reorder_no_pid(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重排序 - 无法获取 PID"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "reorder"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_reorder_execution_failure(self, mock_get_pid, mock_get_container_id):
        """测试注入数据包重排序 - 执行失败"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (False, "Error")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "reorder",
            "percent": "0.5%",
            "correlation": "25%",
            "gap": 5
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
