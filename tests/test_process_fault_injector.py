#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process 故障注入器单元测试
测试进程 kill 操作
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chaos.fault.base import ProcessFaultInjector, FaultFactory
from chaos.constants import VALID_SIGNALS


class TestProcessFaultInjector(unittest.TestCase):
    """ProcessFaultInjector 单元测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_executor = Mock()
        self.mock_logger = Mock()
        self.mock_config_manager = Mock()
        
        self.injector = ProcessFaultInjector(
            remote_executor=self.mock_executor,
            logger=self.mock_logger,
            config_manager=self.mock_config_manager
        )
    
    def test_inject_with_default_signal(self):
        """测试使用默认信号（15）kill 进程"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {}
        
        self.mock_executor.execute.return_value = (True, "")
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()
        
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("kill -15 1", call_args)
        self.assertIn("test-pod", call_args)
        self.assertIn("ns-dupf", call_args)
    
    def test_inject_with_custom_signal(self):
        """测试使用自定义信号 kill 进程"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "signal": 9,
            "main_process_pid": 1234
        }
        
        self.mock_executor.execute.return_value = (True, "")
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("kill -9 1234", call_args)
    
    def test_inject_with_random_signal(self):
        """测试使用随机信号 kill 进程"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "signal": "random",
            "main_process_pid": 1
        }
        
        self.mock_executor.execute.return_value = (True, "")
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
        
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("kill -", call_args)
    
    def test_inject_process_not_exist(self):
        """测试进程不存在的情况"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "signal": 15,
            "main_process_pid": 9999
        }
        
        self.mock_executor.execute.return_value = (False, "No such process")
        
        result = self.injector.inject(target, parameters)
        
        self.assertTrue(result)
    
    def test_inject_failure(self):
        """测试 kill 失败的情况"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "signal": 15,
            "main_process_pid": 1
        }
        
        self.mock_executor.execute.return_value = (False, "Operation not permitted")
        
        result = self.injector.inject(target, parameters)
        
        self.assertFalse(result)
    
    def test_get_fault_id(self):
        """测试获取故障 ID"""
        target = {
            "name": "test-pod",
            "namespace": "ns-dupf"
        }
        parameters = {
            "signal": 15,
            "main_process_pid": 1
        }
        
        self.mock_executor.execute.return_value = (True, "")
        self.injector.inject(target, parameters)
        
        fault_id = self.injector.get_fault_id()
        
        self.assertIsNotNone(fault_id)
        self.assertIn("process_kill", fault_id)
        self.assertIn("test-pod", fault_id)
        self.assertIn("ns-dupf", fault_id)
    
    def test_recover(self):
        """测试恢复操作"""
        result = self.injector.recover("test_fault_id")
        
        self.assertTrue(result)
        self.mock_logger.info.assert_called()


class TestFaultFactoryForProcess(unittest.TestCase):
    """FaultFactory 对 process 类型的支持测试"""
    
    def test_create_process_injector(self):
        """测试创建 process 故障注入器"""
        mock_executor = Mock()
        mock_logger = Mock()
        mock_config_manager = Mock()
        
        injector = FaultFactory.create_injector(
            "process",
            remote_executor=mock_executor,
            logger=mock_logger,
            config_manager=mock_config_manager
        )
        
        self.assertIsInstance(injector, ProcessFaultInjector)
    
    def test_process_injector_registered(self):
        """测试 process 注入器已注册"""
        from chaos.fault.registry import FaultInjectorRegistry
        self.assertTrue(FaultFactory.is_registered("process"))
        self.assertEqual(FaultInjectorRegistry.get_injector_class("process"), ProcessFaultInjector)


class TestSignalValues(unittest.TestCase):
    """信号值测试"""
    
    def test_valid_signals(self):
        """测试有效信号值"""
        valid_signals = [1, 9, 11, 15, 18, 19]
        
        for signal in valid_signals:
            self.assertIn(signal, VALID_SIGNALS)
    
    def test_signal_list(self):
        """测试信号列表"""
        self.assertEqual(VALID_SIGNALS, [1, 9, 11, 15, 18, 19])
        self.assertEqual(len(VALID_SIGNALS), 6)


if __name__ == '__main__':
    unittest.main()
