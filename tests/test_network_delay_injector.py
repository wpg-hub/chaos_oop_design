"""NetworkFaultInjector 延迟注入功能测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from chaos.fault.base import NetworkFaultInjector


class TestNetworkFaultInjectorDelay(unittest.TestCase):
    """测试 NetworkFaultInjector 的延迟注入功能"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_remote_executor = Mock()
        self.mock_logger = Mock()
        self.injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger
        )
    
    def test_parse_time_param_with_string(self):
        """测试解析时间参数 - 字符串"""
        result = self.injector._parse_time_param("300ms")
        self.assertEqual(result, "300ms")
    
    def test_parse_time_param_with_list(self):
        """测试解析时间参数 - 列表"""
        result = self.injector._parse_time_param(["200ms", "800ms"])
        self.assertIn("ms", result)
        time_value = int(result.replace("ms", ""))
        self.assertGreaterEqual(time_value, 200)
        self.assertLessEqual(time_value, 800)
    
    def test_parse_time_param_with_none(self):
        """测试解析时间参数 - None（随机生成）"""
        result = self.injector._parse_time_param(None)
        self.assertIn("ms", result)
        time_value = int(result.replace("ms", ""))
        self.assertGreaterEqual(time_value, 100)
        self.assertLessEqual(time_value, 1000)
    
    def test_parse_jitter_param_with_string(self):
        """测试解析抖动参数 - 字符串"""
        result = self.injector._parse_jitter_param("100ms")
        self.assertEqual(result, "100ms")
    
    def test_parse_jitter_param_with_list(self):
        """测试解析抖动参数 - 列表"""
        result = self.injector._parse_jitter_param(["20ms", "100ms"])
        self.assertIn("ms", result)
        jitter_value = int(result.replace("ms", ""))
        self.assertGreaterEqual(jitter_value, 20)
        self.assertLessEqual(jitter_value, 100)
    
    def test_parse_jitter_param_with_none(self):
        """测试解析抖动参数 - None（随机生成）"""
        result = self.injector._parse_jitter_param(None)
        self.assertIn("ms", result)
        jitter_value = int(result.replace("ms", ""))
        self.assertGreaterEqual(jitter_value, 0)
        self.assertLessEqual(jitter_value, 100)
    
    def test_parse_correlation_param_with_string(self):
        """测试解析相关性参数 - 字符串"""
        result = self.injector._parse_correlation_param("20%")
        self.assertEqual(result, "20%")
    
    def test_parse_correlation_param_with_list(self):
        """测试解析相关性参数 - 列表"""
        result = self.injector._parse_correlation_param(["10%", "90%"])
        self.assertIn("%", result)
        corr_value = int(result.replace("%", ""))
        self.assertGreaterEqual(corr_value, 10)
        self.assertLessEqual(corr_value, 90)
    
    def test_parse_correlation_param_with_none(self):
        """测试解析相关性参数 - None（随机生成）"""
        result = self.injector._parse_correlation_param(None)
        self.assertIn("%", result)
        corr_value = int(result.replace("%", ""))
        self.assertGreaterEqual(corr_value, 20)
        self.assertLessEqual(corr_value, 90)
    
    def test_parse_distribution_param_valid(self):
        """测试解析分布参数 - 有效值"""
        valid_distributions = ["uniform", "normal", "pareto", "paretonormal"]
        for dist in valid_distributions:
            result = self.injector._parse_distribution_param(dist)
            self.assertEqual(result, dist)
    
    def test_parse_distribution_param_invalid(self):
        """测试解析分布参数 - 无效值（随机选择）"""
        result = self.injector._parse_distribution_param("invalid")
        self.assertIn(result, ["uniform", "normal", "pareto", "paretonormal"])
    
    def test_parse_distribution_param_none(self):
        """测试解析分布参数 - None（随机选择）"""
        result = self.injector._parse_distribution_param(None)
        self.assertIn(result, ["uniform", "normal", "pareto", "paretonormal"])
    
    def test_extract_time_value_ms(self):
        """测试提取时间值 - 毫秒"""
        result = self.injector._extract_time_value("300ms")
        self.assertEqual(result, 300)
    
    def test_extract_time_value_s(self):
        """测试提取时间值 - 秒"""
        result = self.injector._extract_time_value("2s")
        self.assertEqual(result, 2000)
    
    def test_extract_time_value_no_unit(self):
        """测试提取时间值 - 无单位"""
        result = self.injector._extract_time_value("500")
        self.assertEqual(result, 500)
    
    def test_extract_percentage_value(self):
        """测试提取百分比值"""
        result = self.injector._extract_percentage_value("20%")
        self.assertEqual(result, 20)
    
    def test_extract_percentage_value_no_symbol(self):
        """测试提取百分比值 - 无符号"""
        result = self.injector._extract_percentage_value("30")
        self.assertEqual(result, 30)
    
    def test_build_tc_delay_command_basic(self):
        """测试构建 tc 命令 - 基本延迟"""
        params = {
            "time": "300ms",
            "jitter": None,
            "correlation": None,
            "distribution": None
        }
        result = self.injector._build_tc_delay_command("eth0", params)
        self.assertEqual(result, "tc qdisc add dev eth0 root netem delay 300ms")
    
    def test_build_tc_delay_command_with_jitter(self):
        """测试构建 tc 命令 - 带抖动"""
        params = {
            "time": "300ms",
            "jitter": "100ms",
            "correlation": None,
            "distribution": None
        }
        result = self.injector._build_tc_delay_command("eth0", params)
        self.assertEqual(result, "tc qdisc add dev eth0 root netem delay 300ms 100ms")
    
    def test_build_tc_delay_command_with_jitter_and_correlation(self):
        """测试构建 tc 命令 - 带抖动和相关性"""
        params = {
            "time": "300ms",
            "jitter": "100ms",
            "correlation": "20%",
            "distribution": None
        }
        result = self.injector._build_tc_delay_command("eth0", params)
        self.assertEqual(result, "tc qdisc add dev eth0 root netem delay 300ms 100ms 20%")
    
    def test_build_tc_delay_command_full(self):
        """测试构建 tc 命令 - 完整参数"""
        params = {
            "time": "300ms",
            "jitter": "100ms",
            "correlation": "20%",
            "distribution": "paretonormal"
        }
        result = self.injector._build_tc_delay_command("eth0", params)
        expected = "tc qdisc add dev eth0 root netem delay 300ms 100ms 20% distribution paretonormal"
        self.assertEqual(result, expected)
    
    def test_build_delay_params_full(self):
        """测试构建延迟参数 - 完整参数"""
        parameters = {
            "time": "300ms",
            "jitter": "100ms",
            "correlation": "20%",
            "distribution": "paretonormal"
        }
        result = self.injector._build_delay_params(parameters)
        
        self.assertEqual(result["time"], "300ms")
        self.assertEqual(result["jitter"], "100ms")
        self.assertEqual(result["correlation"], "20%")
        self.assertEqual(result["distribution"], "paretonormal")
    
    def test_build_delay_params_random(self):
        """测试构建延迟参数 - 随机参数"""
        parameters = {}
        result = self.injector._build_delay_params(parameters)
        
        self.assertIn("ms", result["time"])
        self.assertIn("ms", result["jitter"])
        self.assertIn("%", result["correlation"])
        self.assertIn(result["distribution"], ["uniform", "normal", "pareto", "paretonormal"])
    
    def test_get_device_from_parameters(self):
        """测试获取网卡设备 - 从参数"""
        parameters = {"device": "eth1"}
        result = self.injector._get_device(parameters)
        self.assertEqual(result, "eth1")
    
    def test_get_device_default(self):
        """测试获取网卡设备 - 默认值"""
        parameters = {}
        result = self.injector._get_device(parameters)
        self.assertEqual(result, "eth0")
    
    def test_get_device_from_config_manager(self):
        """测试获取网卡设备 - 从 config_manager"""
        mock_config_manager = Mock()
        mock_config_manager.config = {"device": "ens33"}
        
        injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger,
            mock_config_manager
        )
        
        parameters = {}
        result = injector._get_device(parameters)
        self.assertEqual(result, "ens33")
    
    def test_get_device_priority(self):
        """测试获取网卡设备 - 参数优先级高于 config_manager"""
        mock_config_manager = Mock()
        mock_config_manager.config = {"device": "ens33"}
        
        injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger,
            mock_config_manager
        )
        
        parameters = {"device": "eth1"}
        result = injector._get_device(parameters)
        self.assertEqual(result, "eth1")
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_delay_success(self, mock_get_pid, mock_get_container_id):
        """测试注入延迟 - 成功"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (True, "")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = 12345
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "delay",
            "time": "300ms",
            "jitter": "100ms",
            "correlation": "20%",
            "distribution": "paretonormal"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertIsNotNone(self.injector.get_fault_id())
        mock_get_container_id.assert_called_once_with("test-pod", "default")
        mock_get_pid.assert_called_once_with("container123", mock_node_executor)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    def test_inject_delay_no_container(self, mock_get_container_id):
        """测试注入延迟 - 无法获取容器 ID"""
        mock_get_container_id.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "delay",
            "time": "300ms"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_delay_no_pid(self, mock_get_pid, mock_get_container_id):
        """测试注入延迟 - 无法获取 PID"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (True, "")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "delay",
            "time": "300ms"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_delay_execution_failed(self, mock_get_pid, mock_get_container_id):
        """测试注入延迟 - 命令执行失败"""
        mock_node_executor = MagicMock()
        mock_node_executor.execute.return_value = (False, "Error")
        mock_get_container_id.return_value = ("container123", mock_node_executor)
        mock_get_pid.return_value = 12345
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "delay",
            "time": "300ms"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
