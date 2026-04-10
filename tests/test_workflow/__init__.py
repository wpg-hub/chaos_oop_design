"""
工作流模块单元测试
"""

import os
import tempfile
from datetime import datetime
from unittest import TestCase

import yaml

from chaos.workflow.definition import (
    CaseDefinition,
    ExecutionMode,
    HybridWorkflow,
    ParallelWorkflow,
    SerialWorkflow,
    Task,
    TaskGroup,
    TaskStatus,
    TimingConfig,
)
from chaos.workflow.monitor import TaskResult, WorkflowMonitor, WorkflowResult
from chaos.workflow.parser import WorkflowParser, WorkflowParseError


class TestTimingConfig(TestCase):
    """TimingConfig 测试"""

    def test_default_values(self):
        """测试默认值"""
        timing = TimingConfig()
        self.assertEqual(timing.start_delay, 0.0)
        self.assertEqual(timing.node_interval, 0.0)
        self.assertEqual(timing.task_timeout, 600.0)
        self.assertEqual(timing.global_timeout, 3600.0)
        self.assertEqual(timing.branch_start_delay, 0.0)

    def test_custom_values(self):
        """测试自定义值"""
        timing = TimingConfig(
            start_delay=10.0,
            node_interval=5.0,
            task_timeout=300.0,
            global_timeout=1800.0,
            branch_start_delay=3.0
        )
        self.assertEqual(timing.start_delay, 10.0)
        self.assertEqual(timing.node_interval, 5.0)
        self.assertEqual(timing.task_timeout, 300.0)
        self.assertEqual(timing.global_timeout, 1800.0)
        self.assertEqual(timing.branch_start_delay, 3.0)

    def test_merge(self):
        """测试合并配置"""
        base = TimingConfig(start_delay=10.0, task_timeout=600.0)
        override = TimingConfig(start_delay=20.0)
        merged = base.merge(override)
        
        self.assertEqual(merged.start_delay, 20.0)
        self.assertEqual(merged.task_timeout, 600.0)

    def test_to_dict(self):
        """测试转换为字典"""
        timing = TimingConfig(start_delay=5.0)
        data = timing.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data["start_delay"], 5.0)

    def test_from_dict(self):
        """测试从字典创建"""
        data = {"start_delay": 15.0, "task_timeout": 500.0}
        timing = TimingConfig.from_dict(data)
        
        self.assertEqual(timing.start_delay, 15.0)
        self.assertEqual(timing.task_timeout, 500.0)


class TestCaseDefinition(TestCase):
    """CaseDefinition 测试"""

    def setUp(self):
        self.case = CaseDefinition(
            name="test_case",
            type="sw",
            fault_type="command",
            sw_match={"commands": [{"cmd": "test"}]}
        )

    def test_creation(self):
        """测试创建"""
        self.assertEqual(self.case.name, "test_case")
        self.assertEqual(self.case.type, "sw")
        self.assertEqual(self.case.fault_type, "command")

    def test_validate_success(self):
        """测试验证成功"""
        valid, error = self.case.validate()
        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_validate_missing_name(self):
        """测试缺少名称"""
        case = CaseDefinition(name="", type="sw", fault_type="command")
        valid, error = case.validate()
        self.assertFalse(valid)
        self.assertIn("name", error)

    def test_validate_missing_type(self):
        """测试缺少类型"""
        case = CaseDefinition(name="test", type="", fault_type="command")
        valid, error = case.validate()
        self.assertFalse(valid)
        self.assertIn("type", error)

    def test_validate_no_match(self):
        """测试缺少匹配配置"""
        case = CaseDefinition(name="test", type="sw", fault_type="command")
        valid, error = case.validate()
        self.assertFalse(valid)
        self.assertIn("match", error)

    def test_validate_multiple_match(self):
        """测试多个匹配配置"""
        case = CaseDefinition(
            name="test",
            type="sw",
            fault_type="command",
            sw_match={"commands": []},
            pod_match={"name": "test"}
        )
        valid, error = case.validate()
        self.assertFalse(valid)
        self.assertIn("Only one", error)

    def test_to_case_dict(self):
        """测试转换为 Case 字典"""
        case_dict = self.case.to_case_dict()
        
        self.assertEqual(case_dict["name"], "test_case")
        self.assertEqual(case_dict["type"], "sw")
        self.assertIn("sw_match", case_dict)


class TestTask(TestCase):
    """Task 测试"""

    def setUp(self):
        self.case = CaseDefinition(
            name="test_case",
            type="sw",
            fault_type="command",
            sw_match={"commands": [{"cmd": "test"}]}
        )
        self.task = Task(
            id="task_1",
            name="Test Task",
            case=self.case
        )

    def test_creation(self):
        """测试创建"""
        self.assertEqual(self.task.id, "task_1")
        self.assertEqual(self.task.name, "Test Task")
        self.assertEqual(self.task.case, self.case)

    def test_validate_success(self):
        """测试验证成功"""
        valid, error = self.task.validate()
        self.assertTrue(valid)

    def test_validate_missing_id(self):
        """测试缺少 ID"""
        task = Task(id="", name="Test", case=self.case)
        valid, error = task.validate()
        self.assertFalse(valid)
        self.assertIn("id", error)

    def test_validate_invalid_retry(self):
        """测试无效重试次数"""
        task = Task(id="test", name="Test", case=self.case, retry_count=-1)
        valid, error = task.validate()
        self.assertFalse(valid)
        self.assertIn("Retry count", error)


class TestTaskGroup(TestCase):
    """TaskGroup 测试"""

    def setUp(self):
        self.case = CaseDefinition(
            name="test_case",
            type="sw",
            fault_type="command",
            sw_match={"commands": [{"cmd": "test"}]}
        )
        self.task1 = Task(id="task_1", name="Task 1", case=self.case)
        self.task2 = Task(id="task_2", name="Task 2", case=self.case)

    def test_creation(self):
        """测试创建"""
        group = TaskGroup(
            id="group_1",
            name="Test Group",
            tasks=[self.task1, self.task2]
        )
        
        self.assertEqual(group.id, "group_1")
        self.assertEqual(len(group.tasks), 2)

    def test_add_task(self):
        """测试添加任务"""
        group = TaskGroup(id="group_1", name="Test Group")
        group.add_task(self.task1)
        
        self.assertEqual(len(group.tasks), 1)
        self.assertEqual(self.task1.group, "group_1")

    def test_get_task(self):
        """测试获取任务"""
        group = TaskGroup(
            id="group_1",
            name="Test Group",
            tasks=[self.task1, self.task2]
        )
        
        task = group.get_task("task_1")
        self.assertEqual(task, self.task1)
        
        task = group.get_task("nonexistent")
        self.assertIsNone(task)

    def test_validate_success(self):
        """测试验证成功"""
        group = TaskGroup(
            id="group_1",
            name="Test Group",
            tasks=[self.task1]
        )
        valid, error = group.validate()
        self.assertTrue(valid)

    def test_validate_empty_tasks(self):
        """测试空任务列表"""
        group = TaskGroup(id="group_1", name="Test Group")
        valid, error = group.validate()
        self.assertFalse(valid)
        self.assertIn("no tasks", error)


class TestSerialWorkflow(TestCase):
    """SerialWorkflow 测试"""

    def setUp(self):
        self.case = CaseDefinition(
            name="test_case",
            type="sw",
            fault_type="command",
            sw_match={"commands": [{"cmd": "test"}]}
        )
        self.task1 = Task(id="task_1", name="Task 1", case=self.case)
        self.task2 = Task(id="task_2", name="Task 2", case=self.case)

    def test_creation(self):
        """测试创建"""
        workflow = SerialWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        self.assertEqual(workflow.execution_mode, ExecutionMode.SERIAL)

    def test_get_execution_order(self):
        """测试执行顺序"""
        workflow = SerialWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        workflow.tasks = [self.task1, self.task2]
        
        order = workflow.get_execution_order()
        self.assertEqual(len(order), 2)
        self.assertEqual(len(order[0]), 1)
        self.assertEqual(order[0][0], self.task1)

    def test_validate_empty_tasks(self):
        """测试空任务列表"""
        workflow = SerialWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        valid, error = workflow.validate()
        self.assertFalse(valid)


class TestParallelWorkflow(TestCase):
    """ParallelWorkflow 测试"""

    def setUp(self):
        self.case = CaseDefinition(
            name="test_case",
            type="sw",
            fault_type="command",
            sw_match={"commands": [{"cmd": "test"}]}
        )
        self.task1 = Task(id="task_1", name="Task 1", case=self.case)
        self.task2 = Task(id="task_2", name="Task 2", case=self.case)

    def test_creation(self):
        """测试创建"""
        workflow = ParallelWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        self.assertEqual(workflow.execution_mode, ExecutionMode.PARALLEL)

    def test_get_execution_order(self):
        """测试执行顺序"""
        workflow = ParallelWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        workflow.tasks = [self.task1, self.task2]
        
        order = workflow.get_execution_order()
        self.assertEqual(len(order), 1)
        self.assertEqual(len(order[0]), 2)


class TestHybridWorkflow(TestCase):
    """HybridWorkflow 测试"""

    def setUp(self):
        self.case = CaseDefinition(
            name="test_case",
            type="sw",
            fault_type="command",
            sw_match={"commands": [{"cmd": "test"}]}
        )
        self.task1 = Task(id="task_1", name="Task 1", case=self.case)
        self.task2 = Task(id="task_2", name="Task 2", case=self.case)
        self.group = TaskGroup(
            id="group_1",
            name="Group 1",
            tasks=[self.task1, self.task2],
            execution_mode=ExecutionMode.SERIAL
        )

    def test_creation(self):
        """测试创建"""
        workflow = HybridWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        self.assertEqual(workflow.execution_mode, ExecutionMode.HYBRID)

    def test_get_execution_order(self):
        """测试执行顺序"""
        workflow = HybridWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        workflow.groups = [self.group]
        
        order = workflow.get_execution_order()
        self.assertEqual(len(order), 2)

    def test_validate_empty_groups(self):
        """测试空分组列表"""
        workflow = HybridWorkflow(
            workflow_id="wf_1",
            name="Test Workflow",
            timing=TimingConfig()
        )
        valid, error = workflow.validate()
        self.assertFalse(valid)


class TestWorkflowMonitor(TestCase):
    """WorkflowMonitor 测试"""

    def setUp(self):
        self.monitor = WorkflowMonitor()
        self.result1 = TaskResult(
            task_id="task_1",
            task_name="Task 1",
            status=TaskStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=1.0
        )
        self.result2 = TaskResult(
            task_id="task_2",
            task_name="Task 2",
            status=TaskStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=2.0,
            error_message="Test error"
        )

    def test_record(self):
        """测试记录结果"""
        self.monitor.record(self.result1)
        self.monitor.record(self.result2)
        
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_count"], 2)
        self.assertEqual(stats["success_count"], 1)
        self.assertEqual(stats["failed_count"], 1)

    def test_get_results(self):
        """测试获取结果"""
        self.monitor.record(self.result1)
        self.monitor.record(self.result2)
        
        results = self.monitor.get_results()
        self.assertEqual(len(results), 2)

    def test_get_success_rate(self):
        """测试成功率计算"""
        self.monitor.record(self.result1)
        self.monitor.record(self.result2)
        
        rate = self.monitor.get_success_rate()
        self.assertEqual(rate, 50.0)

    def test_reset(self):
        """测试重置"""
        self.monitor.record(self.result1)
        self.monitor.reset()
        
        stats = self.monitor.get_stats()
        self.assertEqual(stats["total_count"], 0)


class TestWorkflowResult(TestCase):
    """WorkflowResult 测试"""

    def test_get_success_rate(self):
        """测试成功率计算"""
        result = WorkflowResult(
            workflow_id="wf_1",
            workflow_name="Test",
            status=TaskStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
            task_results=[
                TaskResult(
                    task_id="t1",
                    task_name="T1",
                    status=TaskStatus.SUCCESS,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    duration=1.0
                ),
                TaskResult(
                    task_id="t2",
                    task_name="T2",
                    status=TaskStatus.FAILED,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    duration=1.0
                )
            ]
        )
        
        self.assertEqual(result.get_success_rate(), 50.0)

    def test_generate_report(self):
        """测试生成报告"""
        result = WorkflowResult(
            workflow_id="wf_1",
            workflow_name="Test Workflow",
            status=TaskStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
            total_duration=10.0,
            task_results=[]
        )
        
        report = result.generate_report()
        self.assertIn("wf_1", report)
        self.assertIn("Test Workflow", report)


class TestWorkflowParser(TestCase):
    """WorkflowParser 测试"""

    def setUp(self):
        self.parser = WorkflowParser()
        self.valid_serial_workflow = {
            "workflow": {
                "id": "test_serial",
                "name": "Test Serial Workflow",
                "execution_mode": "serial",
                "timing": {
                    "start_delay": 5,
                    "node_interval": 10
                },
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Task 1",
                        "case": {
                            "name": "case_1",
                            "type": "sw",
                            "fault_type": "command",
                            "sw_match": {
                                "commands": [{"cmd": "test"}]
                            }
                        }
                    }
                ]
            }
        }

    def test_parse_serial_workflow(self):
        """测试解析串行工作流"""
        workflow = self.parser.parse_from_dict(self.valid_serial_workflow)
        
        self.assertEqual(workflow.id, "test_serial")
        self.assertEqual(workflow.execution_mode, ExecutionMode.SERIAL)
        self.assertEqual(len(workflow.tasks), 1)

    def test_parse_parallel_workflow(self):
        """测试解析并行工作流"""
        data = {
            "workflow": {
                "id": "test_parallel",
                "name": "Test Parallel Workflow",
                "execution_mode": "parallel",
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Task 1",
                        "case": {
                            "name": "case_1",
                            "type": "sw",
                            "fault_type": "command",
                            "sw_match": {"commands": [{"cmd": "test"}]}
                        }
                    },
                    {
                        "id": "task_2",
                        "name": "Task 2",
                        "case": {
                            "name": "case_2",
                            "type": "pod",
                            "fault_type": "delete",
                            "pod_match": {"name": "test-pod", "namespace": "default"}
                        }
                    }
                ]
            }
        }
        
        workflow = self.parser.parse_from_dict(data)
        
        self.assertEqual(workflow.execution_mode, ExecutionMode.PARALLEL)
        self.assertEqual(len(workflow.tasks), 2)

    def test_parse_hybrid_workflow(self):
        """测试解析混合工作流"""
        data = {
            "workflow": {
                "id": "test_hybrid",
                "name": "Test Hybrid Workflow",
                "execution_mode": "hybrid",
                "groups": [
                    {
                        "id": "group_1",
                        "name": "Group 1",
                        "execution_mode": "serial",
                        "tasks": [
                            {
                                "id": "task_1",
                                "name": "Task 1",
                                "case": {
                                    "name": "case_1",
                                    "type": "sw",
                                    "fault_type": "command",
                                    "sw_match": {"commands": [{"cmd": "test"}]}
                                }
                            }
                        ]
                    }
                ]
            }
        }
        
        workflow = self.parser.parse_from_dict(data)
        
        self.assertEqual(workflow.execution_mode, ExecutionMode.HYBRID)
        self.assertEqual(len(workflow.groups), 1)

    def test_parse_missing_workflow_section(self):
        """测试缺少 workflow 节"""
        with self.assertRaises(WorkflowParseError):
            self.parser.parse_from_dict({})

    def test_parse_missing_id(self):
        """测试缺少 ID"""
        data = {"workflow": {"name": "Test"}}
        with self.assertRaises(WorkflowParseError):
            self.parser.parse_from_dict(data)

    def test_parse_invalid_mode(self):
        """测试无效执行模式"""
        data = {
            "workflow": {
                "id": "test",
                "name": "Test",
                "execution_mode": "invalid"
            }
        }
        with self.assertRaises(WorkflowParseError):
            self.parser.parse_from_dict(data)

    def test_parse_yaml_file(self):
        """测试解析 YAML 文件"""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.yaml',
            delete=False
        ) as f:
            yaml.dump(self.valid_serial_workflow, f)
            temp_path = f.name
        
        try:
            workflow = self.parser.parse(temp_path)
            self.assertEqual(workflow.id, "test_serial")
        finally:
            os.unlink(temp_path)

    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        with self.assertRaises(WorkflowParseError):
            self.parser.parse("/nonexistent/path.yaml")

    def test_validate_yaml_file(self):
        """测试验证 YAML 文件"""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.yaml',
            delete=False
        ) as f:
            yaml.dump(self.valid_serial_workflow, f)
            temp_path = f.name
        
        try:
            valid, error = self.parser.validate_yaml_file(temp_path)
            self.assertTrue(valid)
        finally:
            os.unlink(temp_path)
