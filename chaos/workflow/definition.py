"""
工作流数据结构定义
定义工作流相关的枚举、数据类和抽象类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class ExecutionMode(Enum):
    """执行模式枚举"""
    SERIAL = "serial"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class TimingConfig:
    """时间配置
    
    用于控制任务执行的时间行为，支持多层级继承覆盖。
    继承优先级：Task > TaskGroup > Workflow
    """
    start_delay: float = 0.0
    node_interval: float = 0.0
    task_timeout: float = 600.0
    global_timeout: float = 3600.0
    branch_start_delay: float = 0.0
    
    def merge(self, other: 'TimingConfig') -> 'TimingConfig':
        """合并配置，other 优先级更高
        
        Args:
            other: 优先级更高的配置
            
        Returns:
            合并后的新配置对象
        """
        return TimingConfig(
            start_delay=other.start_delay if other.start_delay != 0.0 else self.start_delay,
            node_interval=other.node_interval if other.node_interval != 0.0 else self.node_interval,
            task_timeout=other.task_timeout if other.task_timeout != 600.0 else self.task_timeout,
            global_timeout=other.global_timeout if other.global_timeout != 3600.0 else self.global_timeout,
            branch_start_delay=other.branch_start_delay if other.branch_start_delay != 0.0 else self.branch_start_delay
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start_delay": self.start_delay,
            "node_interval": self.node_interval,
            "task_timeout": self.task_timeout,
            "global_timeout": self.global_timeout,
            "branch_start_delay": self.branch_start_delay
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimingConfig':
        """从字典创建"""
        return cls(
            start_delay=data.get("start_delay", 0.0),
            node_interval=data.get("node_interval", 0.0),
            task_timeout=data.get("task_timeout", 600.0),
            global_timeout=data.get("global_timeout", 3600.0),
            branch_start_delay=data.get("branch_start_delay", 0.0)
        )


@dataclass
class CaseDefinition:
    """Case 定义（嵌入式）
    
    将 Case 配置直接嵌入工作流定义中，无需引用外部文件。
    """
    name: str
    type: str
    fault_type: str
    environment: str = ""
    description: str = ""
    duration: str = ""
    loop_count: int = 1
    namespace: str = ""
    auto_clear: Optional[bool] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    sw_match: Optional[Dict[str, Any]] = None
    pod_match: Optional[Dict[str, Any]] = None
    computer_match: Optional[Dict[str, Any]] = None
    
    def to_case_dict(self) -> Dict[str, Any]:
        """转换为 Case 字典格式
        
        生成符合现有 CaseManager 期望的字典结构。
        """
        result = {
            "name": self.name,
            "type": self.type,
            "fault_type": self.fault_type,
            "environment": self.environment,
            "description": self.description,
            "duration": self.duration,
            "loop_count": self.loop_count,
            "namespace": self.namespace,
            "auto_clear": self.auto_clear,
            "parameters": self.parameters
        }
        
        if self.sw_match:
            result["sw_match"] = self.sw_match
        if self.pod_match:
            result["pod_match"] = self.pod_match
        if self.computer_match:
            result["computer_match"] = self.computer_match
            
        return result
    
    def validate(self) -> Tuple[bool, str]:
        """验证 Case 配置有效性"""
        if not self.name:
            return False, "Case name is required"
        if not self.type:
            return False, "Case type is required"
        if not self.fault_type:
            return False, "Case fault_type is required"
        
        match_count = sum([
            self.sw_match is not None,
            self.pod_match is not None,
            self.computer_match is not None
        ])
        if match_count == 0:
            return False, "At least one match config is required"
        if match_count > 1:
            return False, "Only one match config is allowed"
            
        return True, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "name": self.name,
            "type": self.type,
            "fault_type": self.fault_type,
            "environment": self.environment,
            "description": self.description,
            "duration": self.duration,
            "loop_count": self.loop_count,
            "namespace": self.namespace,
            "auto_clear": self.auto_clear,
            "parameters": self.parameters
        }
        if self.sw_match:
            result["sw_match"] = self.sw_match
        if self.pod_match:
            result["pod_match"] = self.pod_match
        if self.computer_match:
            result["computer_match"] = self.computer_match
        return result


@dataclass
class Task:
    """任务节点
    
    工作流中的最小执行单元，包含一个嵌入式 Case 定义。
    """
    id: str
    name: str
    case: CaseDefinition
    timing: TimingConfig = field(default_factory=TimingConfig)
    dependencies: List[str] = field(default_factory=list)
    group: Optional[str] = None
    retry_count: int = 0
    retry_interval: float = 5.0
    
    def validate(self) -> Tuple[bool, str]:
        """验证任务配置"""
        if not self.id:
            return False, "Task id is required"
        if not self.name:
            return False, "Task name is required"
        if not self.case:
            return False, "Task case is required"
            
        case_valid, case_error = self.case.validate()
        if not case_valid:
            return False, f"Task case invalid: {case_error}"
            
        if self.retry_count < 0:
            return False, "Retry count must be non-negative"
        if self.retry_interval < 0:
            return False, "Retry interval must be non-negative"
            
        return True, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "case": self.case.to_dict(),
            "timing": self.timing.to_dict(),
            "dependencies": self.dependencies,
            "group": self.group,
            "retry_count": self.retry_count,
            "retry_interval": self.retry_interval
        }


@dataclass
class TaskGroup:
    """任务分组
    
    用于混合模式，将多个任务组织成一个执行单元。
    组内可配置串行或并行执行。
    """
    id: str
    name: str
    tasks: List[Task] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.SERIAL
    timing: TimingConfig = field(default_factory=TimingConfig)
    start_delay: float = 0.0
    
    def add_task(self, task: Task) -> None:
        """添加任务到分组"""
        task.group = self.id
        self.tasks.append(task)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def validate(self) -> Tuple[bool, str]:
        """验证分组配置"""
        if not self.id:
            return False, "Group id is required"
        if not self.name:
            return False, "Group name is required"
        if not self.tasks:
            return False, f"Group {self.id} has no tasks"
        
        task_ids = set()
        for task in self.tasks:
            if task.id in task_ids:
                return False, f"Duplicate task id: {task.id}"
            task_ids.add(task.id)
            
            valid, error = task.validate()
            if not valid:
                return False, f"Task {task.id} invalid: {error}"
                
        return True, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
            "execution_mode": self.execution_mode.value,
            "timing": self.timing.to_dict(),
            "start_delay": self.start_delay
        }


class WorkflowDefinition(ABC):
    """工作流定义抽象类
    
    定义工作流的基本结构和行为，由子类实现具体执行逻辑。
    """
    
    def __init__(
        self,
        workflow_id: str,
        name: str,
        execution_mode: ExecutionMode,
        timing: TimingConfig,
        auto_clear: bool = False
    ):
        self.id = workflow_id
        self.name = name
        self.description = ""
        self.execution_mode = execution_mode
        self.timing = timing
        self.auto_clear = auto_clear
        self.tasks: List[Task] = []
        self.groups: List[TaskGroup] = []
        self.final_tasks: List[Task] = []
    
    def validate(self) -> Tuple[bool, str]:
        """验证工作流配置"""
        if not self.id:
            return False, "Workflow id is required"
        if not self.name:
            return False, "Workflow name is required"
        
        return self._do_validate()
    
    @abstractmethod
    def _do_validate(self) -> Tuple[bool, str]:
        """子类实现具体验证逻辑"""
        pass
    
    def get_execution_order(self) -> List[List[Task]]:
        """获取执行顺序
        
        Returns:
            二维列表，每层可并行执行
            例如: [[A], [B], [C]] 表示串行
                  [[A, B, C]] 表示并行
                  [[A1, A2], [B1, B2]] 表示混合
        """
        return self._do_get_execution_order()
    
    @abstractmethod
    def _do_get_execution_order(self) -> List[List[Task]]:
        """子类实现具体执行顺序"""
        pass
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务（扁平化）"""
        all_tasks = []
        all_tasks.extend(self.tasks)
        for group in self.groups:
            all_tasks.extend(group.tasks)
        all_tasks.extend(self.final_tasks)
        return all_tasks
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "execution_mode": self.execution_mode.value,
            "timing": self.timing.to_dict(),
            "auto_clear": self.auto_clear,
            "tasks": [t.to_dict() for t in self.tasks],
            "groups": [g.to_dict() for g in self.groups],
            "final_tasks": [t.to_dict() for t in self.final_tasks]
        }


class SerialWorkflow(WorkflowDefinition):
    """串行工作流"""
    
    def __init__(self, workflow_id: str, name: str, timing: TimingConfig, auto_clear: bool = False):
        super().__init__(workflow_id, name, ExecutionMode.SERIAL, timing, auto_clear)
    
    def _do_validate(self) -> Tuple[bool, str]:
        if not self.tasks:
            return False, "Serial workflow requires at least one task"
        
        task_ids = set()
        for task in self.tasks:
            if task.id in task_ids:
                return False, f"Duplicate task id: {task.id}"
            task_ids.add(task.id)
            
            valid, error = task.validate()
            if not valid:
                return False, f"Task {task.id} invalid: {error}"
        
        return True, ""
    
    def _do_get_execution_order(self) -> List[List[Task]]:
        return [[task] for task in self.tasks]


class ParallelWorkflow(WorkflowDefinition):
    """并行工作流"""
    
    def __init__(self, workflow_id: str, name: str, timing: TimingConfig, auto_clear: bool = False):
        super().__init__(workflow_id, name, ExecutionMode.PARALLEL, timing, auto_clear)
    
    def _do_validate(self) -> Tuple[bool, str]:
        if not self.tasks:
            return False, "Parallel workflow requires at least one task"
        
        task_ids = set()
        for task in self.tasks:
            if task.id in task_ids:
                return False, f"Duplicate task id: {task.id}"
            task_ids.add(task.id)
            
            valid, error = task.validate()
            if not valid:
                return False, f"Task {task.id} invalid: {error}"
        
        return True, ""
    
    def _do_get_execution_order(self) -> List[List[Task]]:
        return [self.tasks]


class HybridWorkflow(WorkflowDefinition):
    """混合工作流"""
    
    def __init__(self, workflow_id: str, name: str, timing: TimingConfig, auto_clear: bool = False):
        super().__init__(workflow_id, name, ExecutionMode.HYBRID, timing, auto_clear)
    
    def _do_validate(self) -> Tuple[bool, str]:
        if not self.groups:
            return False, "Hybrid workflow requires at least one group"
        
        group_ids = set()
        all_task_ids = set()
        
        for group in self.groups:
            if group.id in group_ids:
                return False, f"Duplicate group id: {group.id}"
            group_ids.add(group.id)
            
            valid, error = group.validate()
            if not valid:
                return False, f"Group {group.id} invalid: {error}"
            
            for task in group.tasks:
                if task.id in all_task_ids:
                    return False, f"Duplicate task id across groups: {task.id}"
                all_task_ids.add(task.id)
        
        for task in self.final_tasks:
            if task.id in all_task_ids:
                return False, f"Duplicate task id in final_tasks: {task.id}"
            all_task_ids.add(task.id)
            
            valid, error = task.validate()
            if not valid:
                return False, f"Final task {task.id} invalid: {error}"
        
        return True, ""
    
    def _do_get_execution_order(self) -> List[List[Task]]:
        result = []
        
        for group in self.groups:
            if group.execution_mode == ExecutionMode.SERIAL:
                for task in group.tasks:
                    result.append([task])
            else:
                result.append(group.tasks)
        
        for task in self.final_tasks:
            result.append([task])
        
        return result
