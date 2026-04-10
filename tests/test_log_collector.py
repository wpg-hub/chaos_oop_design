#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志收集器单元测试
测试日志过滤和文件聚合功能
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chaos.utils.log_collector import NodeLogCollector, MultiNodeLogCollector


class TestNodeLogCollector(unittest.TestCase):
    """NodeLogCollector 单元测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_ssh_executor = Mock()
        self.mock_logger = Mock()
        self.node_name = "test_node"
        
        self.collector = NodeLogCollector(
            ssh_executor=self.mock_ssh_executor,
            logger=self.mock_logger,
            node_name=self.node_name
        )
    
    def test_validate_date_valid(self):
        """测试有效的日期格式"""
        self.assertTrue(self.collector._validate_date("2026-03-26"))
        self.assertTrue(self.collector._validate_date("2026-01-01"))
        self.assertTrue(self.collector._validate_date("2026-12-31"))
    
    def test_validate_date_invalid(self):
        """测试无效的日期格式"""
        self.assertFalse(self.collector._validate_date("2026-13-01"))
        self.assertFalse(self.collector._validate_date("2026-03-32"))
        self.assertFalse(self.collector._validate_date("2026/03/26"))
        self.assertFalse(self.collector._validate_date("invalid"))
    
    def test_find_log_files_by_filename(self):
        """测试按文件名查找日志文件"""
        self.mock_ssh_executor.execute.return_value = (
            True, 
            "/var/log/app-2026-03-26.log\n/var/log/service-2026-03-26.log"
        )
        
        files = self.collector._find_log_files("/var/log", "2026-03-26")
        
        self.assertEqual(len(files), 2)
        self.assertIn("/var/log/app-2026-03-26.log", files)
        self.assertIn("/var/log/service-2026-03-26.log", files)
    
    def test_find_log_files_by_mtime(self):
        """测试按修改时间查找日志文件"""
        self.mock_ssh_executor.execute.side_effect = [
            (True, ""),
            (True, "/var/log/app.log\n/var/log/service.log")
        ]
        
        files = self.collector._find_log_files("/var/log", "2026-03-26")
        
        self.assertEqual(len(files), 2)
        self.assertIn("/var/log/app.log", files)
        self.assertIn("/var/log/service.log", files)
    
    def test_find_log_files_empty(self):
        """测试没有找到日志文件"""
        self.mock_ssh_executor.execute.return_value = (True, "")
        
        files = self.collector._find_log_files("/var/log", "2026-03-26")
        
        self.assertEqual(len(files), 0)
    
    def test_get_sub_directories(self):
        """测试获取子目录"""
        self.mock_ssh_executor.execute.return_value = (
            True,
            "/var/log/sub1\n/var/log/sub2\n/var/log/sub1/nested"
        )
        
        dirs = self.collector._get_sub_directories("/var/log")
        
        self.assertEqual(len(dirs), 3)
        self.assertIn("/var/log/sub1", dirs)
        self.assertIn("/var/log/sub2", dirs)
        self.assertIn("/var/log/sub1/nested", dirs)


class TestMultiNodeLogCollector(unittest.TestCase):
    """MultiNodeLogCollector 单元测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_config_manager = Mock()
        self.mock_logger = Mock()
        
        self.mock_config_manager.get_all_environments.return_value = [
            Mock(name="1_ssh_remote", ip="10.230.246.167", port=50163, user="root", passwd="pass1"),
            Mock(name="2_ssh_remote", ip="10.230.246.168", port=50163, user="root", passwd="pass2"),
        ]
        self.mock_config_manager.get_environment.return_value = Mock(
            name="1_ssh_remote", ip="10.230.246.167", port=50163, user="root", passwd="pass1"
        )
        
        self.collector = MultiNodeLogCollector(
            config_manager=self.mock_config_manager,
            logger=self.mock_logger
        )
    
    def test_collect_all_logs_no_environments(self):
        """测试没有环境配置的情况"""
        self.mock_config_manager.get_all_environments.return_value = []
        
        result = self.collector.collect_all_logs("2026-03-26", "/var/log")
        
        self.assertFalse(result)
    
    @patch('chaos.utils.remote.SSHExecutor')
    def test_collect_single_node_success(self, mock_ssh_class):
        """测试单节点收集成功"""
        mock_ssh = Mock()
        mock_ssh.connect.return_value = True
        mock_ssh.execute.return_value = (True, "")
        mock_ssh_class.return_value = mock_ssh
        
        env_config = Mock(
            name="test_node",
            ip="10.230.246.167",
            port=50163,
            user="root",
            passwd="password"
        )
        
        with patch.object(NodeLogCollector, 'collect_logs', return_value=True):
            with patch.object(NodeLogCollector, 'get_node_archive_path', return_value="/tmp/test_node.tar"):
                result = self.collector._collect_single_node(env_config, "2026-03-26", "/var/log")
                
                self.assertIsNotNone(result)
    
    def test_transfer_file_missing_source(self):
        """测试源节点配置缺失"""
        self.mock_config_manager.get_environment.return_value = None
        
        mock_target_ssh = Mock()
        
        self.collector._transfer_file(
            "missing_node",
            "/tmp/test.tar",
            Mock(),
            "/home/gsta",
            mock_target_ssh
        )
        
        self.mock_logger.warning.assert_called()


class TestDateCalculation(unittest.TestCase):
    """日期计算单元测试"""
    
    def test_next_day_calculation(self):
        """测试下一天计算"""
        from datetime import datetime
        
        test_cases = [
            ("2026-03-26", "2026-03-27"),
            ("2026-01-31", "2026-02-01"),
            ("2026-02-28", "2026-03-01"),
            ("2026-12-31", "2027-01-01"),
            ("2024-02-28", "2024-02-29"),
            ("2024-02-29", "2024-03-01"),
        ]
        
        for date_str, expected_next in test_cases:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            year = date_obj.year
            month = date_obj.month
            day = date_obj.day
            
            if day < 28:
                next_year, next_month, next_day = year, month, day + 1
            elif month in [1, 3, 5, 7, 8, 10, 12] and day == 31:
                if month == 12:
                    next_year, next_month, next_day = year + 1, 1, 1
                else:
                    next_year, next_month, next_day = year, month + 1, 1
            elif month in [4, 6, 9, 11] and day == 30:
                next_year, next_month, next_day = year, month + 1, 1
            elif month == 2:
                is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                if is_leap and day == 29:
                    next_year, next_month, next_day = year, 3, 1
                elif not is_leap and day == 28:
                    next_year, next_month, next_day = year, 3, 1
                else:
                    next_year, next_month, next_day = year, month, day + 1
            else:
                next_year, next_month, next_day = year, month, day + 1
            
            calculated = f"{next_year}-{next_month:02d}-{next_day:02d}"
            self.assertEqual(calculated, expected_next, f"Failed for {date_str}")


if __name__ == '__main__':
    unittest.main()
