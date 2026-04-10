"""NetworkFaultInjector 丢包注入功能测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from chaos.fault.base import NetworkFaultInjector


class TestNetworkFaultInjectorLoss(unittest.TestCase):
    """测试 NetworkFaultInjector 的丢包注入功能"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_remote_executor = Mock()
        self.mock_logger = Mock()
        self.injector = NetworkFaultInjector(
            self.mock_remote_executor,
            self.mock_logger
        )
    
    def test_parse_ecn_param_with_true(self):
        """测试解析 ECN 参数 - true"""
        result = self.injector._parse_ecn_param("true")
        self.assertTrue(result)
    
    def test_parse_ecn_param_with_false(self):
        """测试解析 ECN 参数 - false"""
        result = self.injector._parse_ecn_param("false")
        self.assertFalse(result)
    
    def test_parse_ecn_param_with_random(self):
        """测试解析 ECN 参数 - random"""
        result = self.injector._parse_ecn_param("random")
        self.assertIn(result, [True, False])
    
    def test_parse_ecn_param_with_none(self):
        """测试解析 ECN 参数 - None（随机生成）"""
        result = self.injector._parse_ecn_param(None)
        self.assertIn(result, [True, False])
    
    def test_parse_ecn_param_with_bool(self):
        """测试解析 ECN 参数 - 布尔值"""
        self.assertTrue(self.injector._parse_ecn_param(True))
        self.assertFalse(self.injector._parse_ecn_param(False))
    
    def test_build_loss_params_random_model(self):
        """测试构建丢包参数 - random 模型"""
        parameters = {
            "model": {
                "random": {
                    "percent": "20%"
                }
            }
        }
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertEqual(model_name, "random")
        self.assertEqual(params["percent"], "20%")
    
    def test_build_loss_params_random_model_default(self):
        """测试构建丢包参数 - random 模型（默认值）"""
        parameters = {
            "model": {
                "random": {}
            }
        }
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertEqual(model_name, "random")
        self.assertIn("%", params["percent"])
        percent_value = float(params["percent"].replace("%", ""))
        self.assertGreaterEqual(percent_value, 10)
        self.assertLessEqual(percent_value, 50)
    
    def test_build_loss_params_state_model(self):
        """测试构建丢包参数 - state 模型"""
        parameters = {
            "model": {
                "state": {
                    "p13": "0.1%",
                    "p31": "1%",
                    "p23": "30%",
                    "p32": "20%",
                    "p14": "0.1%"
                }
            }
        }
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertEqual(model_name, "state")
        self.assertEqual(params["p13"], "0.1%")
        self.assertEqual(params["p31"], "1%")
        self.assertEqual(params["p23"], "30%")
        self.assertEqual(params["p32"], "20%")
        self.assertEqual(params["p14"], "0.1%")
    
    def test_build_loss_params_state_model_default(self):
        """测试构建丢包参数 - state 模型（默认值）"""
        parameters = {
            "model": {
                "state": {}
            }
        }
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertEqual(model_name, "state")
        self.assertIn("%", params["p13"])
        self.assertIn("%", params["p31"])
        self.assertIn("%", params["p23"])
        self.assertIn("%", params["p32"])
        self.assertIn("%", params["p14"])
    
    def test_build_loss_params_gemodel_model(self):
        """测试构建丢包参数 - gemodel 模型"""
        parameters = {
            "model": {
                "gemodel": {
                    "p": "30%",
                    "pr": "70%",
                    "pr1-h": "20%",
                    "pr1-h1-k": "0.1%"
                }
            }
        }
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertEqual(model_name, "gemodel")
        self.assertEqual(params["p"], "30%")
        self.assertEqual(params["pr"], "70%")
        self.assertEqual(params["pr1-h"], "20%")
        self.assertEqual(params["pr1-h1-k"], "0.1%")
    
    def test_build_loss_params_gemodel_model_default(self):
        """测试构建丢包参数 - gemodel 模型（默认值）"""
        parameters = {
            "model": {
                "gemodel": {}
            }
        }
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertEqual(model_name, "gemodel")
        self.assertIn("%", params["p"])
        self.assertIn("%", params["pr"])
        self.assertIn("%", params["pr1-h"])
        self.assertIn("%", params["pr1-h1-k"])
    
    def test_build_loss_params_no_model(self):
        """测试构建丢包参数 - 未指定模型（随机选择）"""
        parameters = {}
        model_name, params = self.injector._build_loss_params(parameters)
        
        self.assertIn(model_name, ["random", "state", "gemodel"])
        self.assertIsInstance(params, dict)
    
    def test_build_loss_params_multiple_models(self):
        """测试构建丢包参数 - 多个模型（随机选择）"""
        parameters = {
            "model": {
                "random": {"percent": "10%"},
                "gemodel": {"p": "30%"}
            }
        }
        
        results = set()
        for _ in range(20):
            model_name, params = self.injector._build_loss_params(parameters)
            results.add(model_name)
        
        self.assertTrue(len(results) > 1)
    
    def test_parse_percent_range(self):
        """测试解析百分比范围"""
        result = self.injector._parse_percent_range(["10%", "50%"])
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 10)
        self.assertLessEqual(percent_value, 50)
    
    def test_parse_percent_range_with_float(self):
        """测试解析百分比范围 - 小数值"""
        result = self.injector._parse_percent_range(["0.1%", "0.5%"])
        self.assertIn("%", result)
        percent_value = float(result.replace("%", ""))
        self.assertGreaterEqual(percent_value, 0.1)
        self.assertLessEqual(percent_value, 0.5)
    
    def test_parse_percent_value(self):
        """测试解析百分比值"""
        self.assertEqual(self.injector._parse_percent_value("10%"), 10.0)
        self.assertEqual(self.injector._parse_percent_value("0.5%"), 0.5)
        self.assertEqual(self.injector._parse_percent_value("100%"), 100.0)
    
    def test_build_tc_loss_command_random_without_ecn(self):
        """测试构建 tc 丢包命令 - random 模型，无 ECN"""
        params = {"percent": "10%"}
        result = self.injector._build_tc_loss_command("eth0", "random", params, False)
        
        self.assertEqual(result, "tc qdisc add dev eth0 root netem loss random 10%")
    
    def test_build_tc_loss_command_random_with_ecn(self):
        """测试构建 tc 丢包命令 - random 模型，有 ECN"""
        params = {"percent": "10%"}
        result = self.injector._build_tc_loss_command("eth0", "random", params, True)
        
        self.assertEqual(result, "tc qdisc add dev eth0 root netem loss random 10% ecn")
    
    def test_build_tc_loss_command_state_without_ecn(self):
        """测试构建 tc 丢包命令 - state 模型，无 ECN"""
        params = {
            "p13": "0.1%",
            "p31": "1%",
            "p23": "30%",
            "p32": "20%",
            "p14": "0.1%"
        }
        result = self.injector._build_tc_loss_command("eth0", "state", params, False)
        
        expected = "tc qdisc add dev eth0 root netem loss state 0.1% 1% 30% 20% 0.1%"
        self.assertEqual(result, expected)
    
    def test_build_tc_loss_command_state_with_ecn(self):
        """测试构建 tc 丢包命令 - state 模型，有 ECN"""
        params = {
            "p13": "0.1%",
            "p31": "1%",
            "p23": "30%",
            "p32": "20%",
            "p14": "0.1%"
        }
        result = self.injector._build_tc_loss_command("eth0", "state", params, True)
        
        expected = "tc qdisc add dev eth0 root netem loss state 0.1% 1% 30% 20% 0.1% ecn"
        self.assertEqual(result, expected)
    
    def test_build_tc_loss_command_gemodel_without_ecn(self):
        """测试构建 tc 丢包命令 - gemodel 模型，无 ECN"""
        params = {
            "p": "30%",
            "pr": "70%",
            "pr1-h": "20%",
            "pr1-h1-k": "0.1%"
        }
        result = self.injector._build_tc_loss_command("eth0", "gemodel", params, False)
        
        expected = "tc qdisc add dev eth0 root netem loss gemodel 30% 70% 20% 0.1%"
        self.assertEqual(result, expected)
    
    def test_build_tc_loss_command_gemodel_with_ecn(self):
        """测试构建 tc 丢包命令 - gemodel 模型，有 ECN"""
        params = {
            "p": "30%",
            "pr": "70%",
            "pr1-h": "20%",
            "pr1-h1-k": "0.1%"
        }
        result = self.injector._build_tc_loss_command("eth0", "gemodel", params, True)
        
        expected = "tc qdisc add dev eth0 root netem loss gemodel 30% 70% 20% 0.1% ecn"
        self.assertEqual(result, expected)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_loss_success(self, mock_get_pid, mock_get_container_id):
        """测试注入丢包 - 成功"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = 12345
        self.mock_remote_executor.execute.return_value = (True, "")
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "loss",
            "ecn": "true",
            "model": {
                "random": {
                    "percent": "10%"
                }
            }
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
        self.assertIn("loss random 10%", command)
        self.assertIn("ecn", command)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    def test_inject_loss_no_container_id(self, mock_get_container_id):
        """测试注入丢包 - 无法获取容器 ID"""
        mock_get_container_id.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "loss"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    @patch.object(NetworkFaultInjector, '_get_pause_container_id')
    @patch.object(NetworkFaultInjector, '_get_container_pid')
    def test_inject_loss_no_pid(self, mock_get_pid, mock_get_container_id):
        """测试注入丢包 - 无法获取 PID"""
        mock_get_container_id.return_value = "container123"
        mock_get_pid.return_value = None
        
        target = {
            "name": "test-pod",
            "namespace": "default"
        }
        parameters = {
            "fault_type": "loss"
        }
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
