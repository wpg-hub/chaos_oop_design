#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pod 故障注入器单元测试
测试 delete、restart 和 stop 操作
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chaos.fault.base import PodFaultInjector, FaultFactory


class TestPodFaultInjector(unittest.TestCase):
    """PodFaultInjector 单元测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_executor = Mock()
        self.mock_logger = Mock()
        self.mock_config_manager = Mock()
        self.mock_config_manager.config = {
            "environments": {
                "1_ssh_remote": {
                    "ip": "10.230.246.167",
                    "port": 50163,
                    "user": "root",
                    "passwd": "Gsta@123",
                    "nodename": "dupf01"
                }
            }
        }
        
        self.injector = PodFaultInjector(
            remote_executor=self.mock_executor,
            logger=self.mock_logger,
            config_manager=self.mock_config_manager
        )
    
    def test_delete_pod_with_grace_period(self):
        """测试 delete 操作（带 grace_period）"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "grace_period": 30
        }
        
        # Mock 执行器返回成功
        self.mock_executor.execute.return_value = (True, "pod deleted")
        
        result = self.injector._delete_pod(target, parameters)
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()
        
        # 验证命令格式
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("kubectl delete pod test-pod", call_args)
        self.assertIn("--grace-period=30", call_args)
        self.assertNotIn("--force", call_args)
    
    def test_delete_pod_without_grace_period(self):
        """测试 delete 操作（无 grace_period，强制删除）"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "grace_period": 0
        }
        
        # Mock 执行器返回成功
        self.mock_executor.execute.return_value = (True, "pod deleted")
        
        result = self.injector._delete_pod(target, parameters)
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()
        
        # 验证命令格式
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("kubectl delete pod test-pod", call_args)
        self.assertIn("--grace-period=0", call_args)
        self.assertIn("--force", call_args)
    
    def test_restart_pod(self):
        """测试 restart 操作"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {}
        
        # Mock 执行器返回成功
        self.mock_executor.execute.return_value = (True, "pod restarted")
        
        result = self.injector._restart_pod(target, parameters)
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()
        
        # 验证命令格式
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("kubectl rollout restart pod test-pod", call_args)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_stop_pod(self, mock_get_ssh_pool):
        """测试 stop 操作"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {}
        
        # Mock 执行器返回 - 获取节点名称（awk 提取后的结果）
        self.mock_executor.execute.return_value = (True, "dupf01")
        
        # Mock SSH连接池
        mock_pool = Mock()
        mock_executor_instance = Mock()
        mock_executor_instance.execute.side_effect = [
            (True, "docker://container123"),  # 获取容器 ID
            (True, "container123")  # 停止容器
        ]
        mock_pool.get_connection.return_value = mock_executor_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        result = self.injector._stop_pod(target, parameters)
        
        self.assertTrue(result)
        
        # 验证记录了停止的容器信息
        self.assertEqual(len(self.injector._stopped_containers), 1)
        self.assertEqual(self.injector._stopped_containers[0]["container_id"], "container123")
    
    def test_recover_with_stopped_containers(self):
        """测试恢复操作（有停止的容器）"""
        # 添加一个停止的容器记录
        mock_executor = Mock()
        mock_executor.execute.return_value = (True, "container started")
        
        self.injector._stopped_containers = [{
            "container_id": "container123",
            "pod_name": "test-pod",
            "namespace": "ns-dupf",
            "node_name": "dupf01",
            "env_config": {
                "executor": mock_executor
            }
        }]
        
        result = self.injector.recover("stop_test-pod_ns-dupf_123456")
        
        self.assertTrue(result)
        mock_executor.execute.assert_called_once()
        
        # 验证命令格式
        call_args = mock_executor.execute.call_args[0][0]
        self.assertIn("docker start container123", call_args)
        
        # 验证清空了停止的容器列表
        self.assertEqual(len(self.injector._stopped_containers), 0)
    
    def test_recover_without_stopped_containers(self):
        """测试恢复操作（无停止的容器）"""
        result = self.injector.recover("delete_test-pod_ns-dupf_123456")
        
        self.assertTrue(result)
    
    def test_inject_delete(self):
        """测试 inject 方法（delete 操作）"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "fault_type": "delete",
            "grace_period": 30
        }
        
        # Mock 执行器返回成功
        self.mock_executor.execute.return_value = (True, "pod deleted")
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertIsNotNone(self.injector.fault_id)
        self.assertIn("delete", self.injector.fault_id)
    
    def test_inject_restart(self):
        """测试 inject 方法（restart 操作）"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "fault_type": "restart"
        }
        
        # Mock 执行器返回成功
        self.mock_executor.execute.return_value = (True, "pod restarted")
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertIsNotNone(self.injector.fault_id)
        self.assertIn("restart", self.injector.fault_id)
    
    @patch('chaos.utils.remote.get_ssh_pool')
    def test_inject_stop(self, mock_get_ssh_pool):
        """测试 inject 方法（stop 操作）"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "fault_type": "stop"
        }
        
        # Mock 执行器返回 - 获取节点名称（awk 提取后的结果）
        self.mock_executor.execute.return_value = (True, "dupf01")
        
        # Mock SSH连接池
        mock_pool = Mock()
        mock_executor_instance = Mock()
        mock_executor_instance.execute.side_effect = [
            (True, "docker://container123"),
            (True, "container123")
        ]
        mock_pool.get_connection.return_value = mock_executor_instance
        mock_get_ssh_pool.return_value = mock_pool
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.assertIsNotNone(self.injector.fault_id)
        self.assertIn("stop", self.injector.fault_id)
    
    def test_inject_unknown_fault_type(self):
        """测试 inject 方法（未知故障类型）"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "fault_type": "unknown"
        }
        
        result = self.injector.inject(target, parameters)
        
        # 未知的故障类型应该返回 False
        self.assertFalse(result)


class TestFaultFactory(unittest.TestCase):
    """FaultFactory 单元测试"""
    
    def test_create_pod_injector(self):
        """测试创建 Pod 故障注入器"""
        mock_executor = Mock()
        mock_logger = Mock()
        mock_config_manager = Mock()
        
        injector = FaultFactory.create_injector(
            fault_type="pod",
            remote_executor=mock_executor,
            logger=mock_logger,
            config_manager=mock_config_manager
        )
        
        self.assertIsInstance(injector, PodFaultInjector)
        self.assertEqual(injector.remote_executor, mock_executor)
        self.assertEqual(injector.logger, mock_logger)
        self.assertEqual(injector.config_manager, mock_config_manager)
    
    def test_create_unknown_injector(self):
        """测试创建未知类型的注入器"""
        with self.assertRaises(ValueError) as context:
            FaultFactory.create_injector(fault_type="unknown")
        
        self.assertIn("未知的故障类型", str(context.exception))


if __name__ == '__main__':
    unittest.main()
