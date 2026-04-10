"""
工作流监控器
负责监控执行状态和生成报告
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from chaos.workflow.definition import TaskStatus


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    task_name: str
    status: TaskStatus
    start_time: datetime
    end_time: datetime
    duration: float
    error_message: str = ""
    output: str = ""
    group_id: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration": self.duration,
            "error_message": self.error_message,
            "output": self.output,
            "group_id": self.group_id,
            "retry_count": self.retry_count
        }


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_id: str
    workflow_name: str
    status: TaskStatus
    start_time: datetime
    end_time: datetime
    total_duration: float = 0.0
    task_results: List[TaskResult] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    error_message: str = ""
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if not self.task_results:
            return 0.0
        success_count = sum(1 for r in self.task_results if r.status == TaskStatus.SUCCESS)
        return success_count / len(self.task_results) * 100
    
    def generate_report(self) -> str:
        """生成执行报告"""
        lines = [
            "=" * 80,
            "Workflow Execution Report".center(80),
            "=" * 80,
            f"Workflow ID    : {self.workflow_id}",
            f"Workflow Name  : {self.workflow_name}",
            f"Status         : {self.status.value.upper()}",
            f"Start Time     : {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"End Time       : {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Duration : {self.total_duration:.2f}s",
            f"Success Rate   : {self.get_success_rate():.2f}%",
        ]
        
        if self.error_message:
            lines.append(f"Error Message  : {self.error_message}")
        
        lines.extend([
            "=" * 80,
            "",
            "Task Results:",
            "-" * 80,
        ])
        
        current_group = None
        for result in self.task_results:
            if result.group_id and result.group_id != current_group:
                current_group = result.group_id
                lines.append(f"\n  Group: {current_group}")
            
            status_str = f"[{result.status.value.upper():8}]"
            group_info = f"Group: {result.group_id}" if result.group_id else "Group: N/A"
            lines.append(
                f"  {status_str} {result.task_name:30} "
                f"Duration: {result.duration:6.2f}s  {group_info}"
            )
            if result.error_message:
                lines.append(f"           Error: {result.error_message}")
            if result.retry_count > 0:
                lines.append(f"           Retries: {result.retry_count}")
        
        lines.extend([
            "",
            "=" * 80,
            "Summary Statistics",
            "=" * 80,
            f"Total Tasks    : {len(self.task_results)}",
            f"Success        : {self.stats.get('success_count', 0)}",
            f"Failed         : {self.stats.get('failed_count', 0)}",
            f"Timeout        : {self.stats.get('timeout_count', 0)}",
            f"Skipped        : {self.stats.get('skipped_count', 0)}",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_duration": self.total_duration,
            "task_results": [r.to_dict() for r in self.task_results],
            "stats": self.stats,
            "error_message": self.error_message,
            "success_rate": self.get_success_rate()
        }


class WorkflowMonitor:
    """工作流监控器
    
    线程安全的执行状态监控器，记录任务执行结果并计算统计数据。
    """
    
    def __init__(self):
        self._results: List[TaskResult] = []
        self._lock = threading.Lock()
        self._stats = {
            "total_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "timeout_count": 0,
            "skipped_count": 0
        }
    
    def record(self, result: TaskResult) -> None:
        """记录执行结果
        
        Args:
            result: 任务执行结果
        """
        with self._lock:
            self._results.append(result)
            self._stats["total_count"] += 1
            
            if result.status == TaskStatus.SUCCESS:
                self._stats["success_count"] += 1
            elif result.status == TaskStatus.FAILED:
                self._stats["failed_count"] += 1
            elif result.status == TaskStatus.TIMEOUT:
                self._stats["timeout_count"] += 1
            else:
                self._stats["skipped_count"] += 1
    
    def get_results(self, limit: Optional[int] = None) -> List[TaskResult]:
        """获取执行结果列表
        
        Args:
            limit: 返回结果数量限制
            
        Returns:
            任务执行结果列表
        """
        with self._lock:
            if limit:
                return self._results[-limit:]
            return self._results.copy()
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计数据
        
        Returns:
            统计数据字典
        """
        with self._lock:
            return self._stats.copy()
    
    def get_success_rate(self) -> float:
        """获取成功率
        
        Returns:
            成功率百分比
        """
        with self._lock:
            if self._stats["total_count"] == 0:
                return 0.0
            return self._stats["success_count"] / self._stats["total_count"] * 100
    
    def reset(self) -> None:
        """重置监控器"""
        with self._lock:
            self._results.clear()
            for key in self._stats:
                self._stats[key] = 0
    
    def get_group_results(self, group_id: str) -> List[TaskResult]:
        """获取指定分组的结果
        
        Args:
            group_id: 分组ID
            
        Returns:
            该分组的任务执行结果列表
        """
        with self._lock:
            return [r for r in self._results if r.group_id == group_id]
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取指定任务的结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务执行结果，不存在则返回 None
        """
        with self._lock:
            for result in self._results:
                if result.task_id == task_id:
                    return result
            return None
