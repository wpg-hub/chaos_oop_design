"""
工作流解析器
负责解析 YAML 配置文件，构建工作流对象
"""

import os
from typing import Any, Dict, List, Optional

import yaml

from chaos.utils.logger import Logger
from chaos.workflow.definition import (
    CaseDefinition,
    ExecutionMode,
    SerialWorkflow,
    ParallelWorkflow,
    HybridWorkflow,
    Task,
    TaskGroup,
    TimingConfig,
    WorkflowDefinition,
)


class WorkflowParseError(Exception):
    """工作流解析错误"""
    pass


class WorkflowParser:
    """工作流解析器
    
    负责解析 YAML 配置文件，构建工作流对象。
    支持串行、并行、混合三种执行模式。
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger(name="workflow")
    
    def parse(self, yaml_file: str) -> WorkflowDefinition:
        """解析 YAML 文件
        
        Args:
            yaml_file: YAML 文件路径
            
        Returns:
            WorkflowDefinition: 工作流对象
            
        Raises:
            WorkflowParseError: 解析错误
        """
        if not os.path.exists(yaml_file):
            raise WorkflowParseError(f"YAML file not found: {yaml_file}")
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"YAML parse error: {e}")
        
        if not data:
            raise WorkflowParseError("Empty YAML file")
        
        return self.parse_from_dict(data)
    
    def parse_from_dict(self, data: Dict[str, Any]) -> WorkflowDefinition:
        """从字典解析
        
        Args:
            data: 配置字典
            
        Returns:
            WorkflowDefinition: 工作流对象
            
        Raises:
            WorkflowParseError: 解析错误
        """
        workflow_data = data.get("workflow")
        if not workflow_data:
            raise WorkflowParseError("Missing 'workflow' section")
        
        workflow_id = workflow_data.get("id", "")
        if not workflow_id:
            raise WorkflowParseError("Workflow id is required")
        
        name = workflow_data.get("name", "")
        if not name:
            raise WorkflowParseError("Workflow name is required")
        
        mode_str = workflow_data.get("execution_mode", "serial")
        try:
            execution_mode = ExecutionMode(mode_str)
        except ValueError:
            raise WorkflowParseError(f"Invalid execution_mode: {mode_str}")
        
        timing = self._parse_timing(workflow_data.get("timing", {}))
        
        auto_clear = workflow_data.get("auto_clear", False)
        
        if execution_mode == ExecutionMode.SERIAL:
            workflow = SerialWorkflow(workflow_id, name, timing, auto_clear)
        elif execution_mode == ExecutionMode.PARALLEL:
            workflow = ParallelWorkflow(workflow_id, name, timing, auto_clear)
        else:
            workflow = HybridWorkflow(workflow_id, name, timing, auto_clear)
        
        workflow.description = workflow_data.get("description", "")
        
        if execution_mode in [ExecutionMode.SERIAL, ExecutionMode.PARALLEL]:
            tasks_data = workflow_data.get("tasks", [])
            if not tasks_data:
                raise WorkflowParseError(f"{execution_mode.value} workflow requires 'tasks' section")
            workflow.tasks = self._parse_tasks(tasks_data, timing, auto_clear)
        else:
            groups_data = workflow_data.get("groups", [])
            if not groups_data:
                raise WorkflowParseError("Hybrid workflow requires 'groups' section")
            workflow.groups = self._parse_groups(groups_data, timing, auto_clear)
            
            final_tasks_data = workflow_data.get("final_tasks", [])
            workflow.final_tasks = self._parse_tasks(final_tasks_data, timing, auto_clear)
        
        valid, error = workflow.validate()
        if not valid:
            raise WorkflowParseError(f"Workflow validation failed: {error}")
        
        self.logger.info(f"Successfully parsed workflow: {workflow_id}")
        return workflow
    
    def _parse_timing(self, data: Dict[str, Any]) -> TimingConfig:
        """解析时间配置
        
        Args:
            data: 时间配置字典
            
        Returns:
            TimingConfig: 时间配置对象
        """
        return TimingConfig(
            start_delay=float(data.get("start_delay", 0.0)),
            node_interval=float(data.get("node_interval", 0.0)),
            task_timeout=float(data.get("task_timeout", 600.0)),
            global_timeout=float(data.get("global_timeout", 3600.0)),
            branch_start_delay=float(data.get("branch_start_delay", 0.0))
        )
    
    def _parse_tasks(
        self,
        data_list: List[Dict[str, Any]],
        parent_timing: TimingConfig,
        workflow_auto_clear: bool = False
    ) -> List[Task]:
        """解析任务列表
        
        Args:
            data_list: 任务配置列表
            parent_timing: 父级时间配置
            workflow_auto_clear: workflow级别的auto_clear配置
            
        Returns:
            任务对象列表
        """
        tasks = []
        for data in data_list:
            task_timing = self._parse_timing(data.get("timing", {}))
            merged_timing = parent_timing.merge(task_timing)
            
            case_data = data.get("case")
            if not case_data:
                raise WorkflowParseError(f"Task {data.get('id', 'unknown')} missing 'case' section")
            
            task = Task(
                id=data.get("id", ""),
                name=data.get("name", ""),
                case=self._parse_case(case_data, workflow_auto_clear),
                timing=merged_timing,
                dependencies=data.get("dependencies", []),
                retry_count=data.get("retry_count", 0),
                retry_interval=float(data.get("retry_interval", 5.0))
            )
            tasks.append(task)
        return tasks
    
    def _parse_groups(
        self,
        data_list: List[Dict[str, Any]],
        parent_timing: TimingConfig,
        workflow_auto_clear: bool = False
    ) -> List[TaskGroup]:
        """解析分组列表
        
        Args:
            data_list: 分组配置列表
            parent_timing: 父级时间配置
            workflow_auto_clear: workflow级别的auto_clear配置
            
        Returns:
            分组对象列表
        """
        groups = []
        for data in data_list:
            group_timing = self._parse_timing(data.get("timing", {}))
            merged_timing = parent_timing.merge(group_timing)
            
            mode_str = data.get("execution_mode", "serial")
            try:
                execution_mode = ExecutionMode(mode_str)
            except ValueError:
                raise WorkflowParseError(f"Invalid group execution_mode: {mode_str}")
            
            group = TaskGroup(
                id=data.get("id", ""),
                name=data.get("name", ""),
                execution_mode=execution_mode,
                timing=merged_timing,
                start_delay=float(data.get("start_delay", 0.0))
            )
            
            tasks_data = data.get("tasks", [])
            for task_data in tasks_data:
                task_timing = self._parse_timing(task_data.get("timing", {}))
                task_merged_timing = merged_timing.merge(task_timing)
                
                case_data = task_data.get("case")
                if not case_data:
                    raise WorkflowParseError(
                        f"Task {task_data.get('id', 'unknown')} in group {group.id} missing 'case' section"
                    )
                
                task = Task(
                    id=task_data.get("id", ""),
                    name=task_data.get("name", ""),
                    case=self._parse_case(case_data, workflow_auto_clear),
                    timing=task_merged_timing,
                    dependencies=task_data.get("dependencies", []),
                    group=group.id,
                    retry_count=task_data.get("retry_count", 0),
                    retry_interval=float(task_data.get("retry_interval", 5.0))
                )
                group.tasks.append(task)
            
            groups.append(group)
        return groups
    
    def _parse_case(self, data: Dict[str, Any], workflow_auto_clear: bool = False) -> CaseDefinition:
        """解析 Case 定义
        
        Args:
            data: Case 配置字典
            workflow_auto_clear: workflow级别的auto_clear配置（不继承到case）
            
        Returns:
            CaseDefinition: Case 定义对象
        """
        # case的auto_clear不继承workflow的配置
        # 只有当case明确指定auto_clear时才使用
        case_auto_clear = data.get("auto_clear")
        
        return CaseDefinition(
            name=data.get("name", ""),
            type=data.get("type", ""),
            fault_type=data.get("fault_type", ""),
            environment=data.get("environment", ""),
            description=data.get("description", ""),
            duration=data.get("duration", ""),
            loop_count=data.get("loop_count", 1),
            namespace=data.get("namespace", ""),
            auto_clear=case_auto_clear,
            parameters=data.get("parameters", {}),
            sw_match=data.get("sw_match"),
            pod_match=data.get("pod_match"),
            computer_match=data.get("computer_match")
        )
    
    def validate_yaml_file(self, yaml_file: str) -> tuple[bool, str]:
        """验证 YAML 文件
        
        Args:
            yaml_file: YAML 文件路径
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            workflow = self.parse(yaml_file)
            valid, error = workflow.validate()
            return valid, error
        except WorkflowParseError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"
