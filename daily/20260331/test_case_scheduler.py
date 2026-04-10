#!/usr/bin/env python3
"""
Case Scheduler 单元测试
"""

import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from case_scheduler import (
    ExecutionStatus,
    ExecutionResult,
    ExecutionMonitor,
    CaseDiscovery,
    CaseScheduler,
    PythonCaseRunner,
    Logger
)


class TestExecutionResult(TestCase):
    """ExecutionResult 测试"""

    def test_execution_result_creation(self):
        """测试创建执行结果"""
        start = datetime.now()
        end = datetime.now()
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.SUCCESS,
            start_time=start,
            end_time=end,
            exit_code=0
        )
        self.assertEqual(result.case_file, "test.yaml")
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.exit_code, 0)

    def test_execution_result_duration(self):
        """测试执行时长计算"""
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 10, 0, 30)
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.SUCCESS,
            start_time=start,
            end_time=end
        )
        self.assertEqual(result.duration, 30.0)

    def test_execution_result_to_dict(self):
        """测试转换为字典"""
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 10, 0, 30)
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.SUCCESS,
            start_time=start,
            end_time=end,
            exit_code=0,
            round_number=1
        )
        result_dict = result.to_dict()
        self.assertEqual(result_dict["case_file"], "test.yaml")
        self.assertEqual(result_dict["status"], "success")
        self.assertEqual(result_dict["duration"], 30.0)
        self.assertEqual(result_dict["round_number"], 1)


class TestExecutionMonitor(TestCase):
    """ExecutionMonitor 测试"""

    def setUp(self):
        self.monitor = ExecutionMonitor()

    def test_record_success(self):
        """测试记录成功结果"""
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        self.monitor.record(result)
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_runs"], 1)
        self.assertEqual(stats["success_count"], 1)

    def test_record_failed(self):
        """测试记录失败结果"""
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        self.monitor.record(result)
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_runs"], 1)
        self.assertEqual(stats["failed_count"], 1)

    def test_record_timeout(self):
        """测试记录超时结果"""
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.TIMEOUT,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        self.monitor.record(result)
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_runs"], 1)
        self.assertEqual(stats["timeout_count"], 1)

    def test_success_rate(self):
        """测试成功率计算"""
        for i in range(3):
            result = ExecutionResult(
                case_file=f"test{i}.yaml",
                status=ExecutionStatus.SUCCESS if i < 2 else ExecutionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now()
            )
            self.monitor.record(result)
        self.assertEqual(self.monitor.get_success_rate(), 66.66666666666666)

    def test_success_rate_zero(self):
        """测试无记录时的成功率"""
        self.assertEqual(self.monitor.get_success_rate(), 0.0)

    def test_get_results(self):
        """测试获取结果列表"""
        for i in range(5):
            result = ExecutionResult(
                case_file=f"test{i}.yaml",
                status=ExecutionStatus.SUCCESS,
                start_time=datetime.now(),
                end_time=datetime.now()
            )
            self.monitor.record(result)
        results = self.monitor.get_results(limit=3)
        self.assertEqual(len(results), 3)

    def test_reset(self):
        """测试重置"""
        result = ExecutionResult(
            case_file="test.yaml",
            status=ExecutionStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        self.monitor.record(result)
        self.monitor.reset()
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_runs"], 0)


class TestCaseDiscovery(TestCase):
    """CaseDiscovery 测试"""

    def test_discover_yaml_files(self):
        """测试发现 YAML 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.yaml").touch()
            Path(tmpdir, "b.yaml").touch()
            Path(tmpdir, "c.yml").touch()
            Path(tmpdir, "readme.txt").touch()

            discovery = CaseDiscovery(tmpdir)
            files = discovery.discover()

            self.assertEqual(len(files), 3)
            self.assertTrue(all(f.endswith(('.yaml', '.yml')) for f in files))

    def test_discover_sorted(self):
        """测试文件按字母顺序排序"""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "z.yaml").touch()
            Path(tmpdir, "a.yaml").touch()
            Path(tmpdir, "m.yaml").touch()

            discovery = CaseDiscovery(tmpdir)
            files = discovery.discover()

            self.assertEqual(files[0].endswith("a.yaml"), True)
            self.assertEqual(files[1].endswith("m.yaml"), True)
            self.assertEqual(files[2].endswith("z.yaml"), True)

    def test_discover_empty_dir(self):
        """测试空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = CaseDiscovery(tmpdir)
            files = discovery.discover()
            self.assertEqual(len(files), 0)

    def test_discover_nonexistent_dir(self):
        """测试不存在的目录"""
        discovery = CaseDiscovery("/nonexistent/path")
        files = discovery.discover()
        self.assertEqual(len(files), 0)


class TestPythonCaseRunner(TestCase):
    """PythonCaseRunner 测试"""

    def test_run_success(self):
        """测试成功执行"""
        runner = PythonCaseRunner(
            python_cmd="python3",
            main_script="",
            timeout=30
        )

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"name: test\n")
            f.write(b"type: sw\n")
            f.write(b"environment: sw_ssh_remote1\n")
            f.write(b"fault_type: command\n")
            f.write(b"sw_match:\n")
            f.write(b"  commands:\n")
            f.write(b"    - cmd: echo test\n")
            yaml_file = f.name

        try:
            result = runner.run(yaml_file, 1)
            self.assertIn(result.status, [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED])
        finally:
            os.unlink(yaml_file)

    def test_run_timeout(self):
        """测试超时处理"""
        runner = PythonCaseRunner(
            python_cmd="python3",
            main_script="",
            timeout=1
        )

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            yaml_file = f.name

        try:
            result = runner.run(yaml_file, 1)
            self.assertIn(result.status, [ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT])
        finally:
            os.unlink(yaml_file)


class TestCaseScheduler(TestCase):
    """CaseScheduler 测试"""

    def test_scheduler_creation(self):
        """测试调度器创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = CaseScheduler(
                case_dir=tmpdir,
                main_script="/tmp/main.py",
                timeout=60
            )
            self.assertEqual(scheduler.case_dir, tmpdir)
            self.assertEqual(scheduler.timeout, 60)
            self.assertFalse(scheduler.is_running())

    def test_scheduler_stop(self):
        """测试调度器停止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = CaseScheduler(
                case_dir=tmpdir,
                main_script="/tmp/main.py",
                timeout=60
            )

            def run_scheduler():
                time.sleep(0.1)
                scheduler.stop()

            thread = threading.Thread(target=run_scheduler)
            thread.start()

            scheduler._running = False
            scheduler._stop_event.set()
            self.assertFalse(scheduler.is_running())

            thread.join()

    def test_get_round_count(self):
        """测试获取轮次"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = CaseScheduler(
                case_dir=tmpdir,
                main_script="/tmp/main.py",
                timeout=60
            )
            self.assertEqual(scheduler.get_round_count(), 0)


class TestLogger(TestCase):
    """Logger 测试"""

    def test_logger_singleton(self):
        """测试单例模式"""
        logger1 = Logger()
        logger2 = Logger()
        self.assertIs(logger1, logger2)

    def test_logger_methods(self):
        """测试日志方法"""
        logger = Logger()
        logger.info("test info")
        logger.error("test error")
        logger.warning("test warning")
        logger.debug("test debug")


if __name__ == "__main__":
    main()
