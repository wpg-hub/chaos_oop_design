"""
工作流执行器
负责执行工作流，管理并发和时序控制
"""

import os
import signal
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from chaos.config import ConfigManager
from chaos.fault.base import FaultFactory
from chaos.state.manager import StateManager
from chaos.utils.logger import Logger
from chaos.workflow.definition import (
    ExecutionMode,
    Task,
    TaskStatus,
    TimingConfig,
    WorkflowDefinition,
)
from chaos.workflow.monitor import TaskResult, WorkflowMonitor, WorkflowResult


class TaskExecutor:
    """任务执行器
    
    负责执行单个任务，创建临时 Case 文件并调用现有 CaseManager。
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        fault_factory: FaultFactory,
        state_manager: StateManager,
        logger: Logger
    ):
        self.config_manager = config_manager
        self.fault_factory = fault_factory
        self.state_manager = state_manager
        self.logger = logger
    
    def execute(self, task: Task, timeout: float) -> TaskResult:
        """执行任务
        
        Args:
            task: 任务对象
            timeout: 超时时间（秒）
            
        Returns:
            TaskResult: 执行结果
        """
        start_time = datetime.now()
        self.logger.info(f"开始执行任务: {task.name} ({task.id})")
        
        effective_timeout = self._calculate_effective_timeout(task, timeout)
        if effective_timeout != timeout:
            self.logger.info(
                f"任务超时时间已调整: {timeout}s -> {effective_timeout}s "
                f"(包含 duration: {task.case.duration})"
            )
        
        temp_file = None
        retry_count = 0
        
        try:
            temp_file = self._create_temp_case_file(task.case)
            
            while True:
                try:
                    success = self._execute_with_timeout(temp_file, effective_timeout)
                    
                    end_time = datetime.now()
                    status = TaskStatus.SUCCESS if success else TaskStatus.FAILED
                    
                    if status == TaskStatus.SUCCESS:
                        self.logger.info(
                            f"任务执行成功: {task.name} "
                            f"(耗时: {(end_time - start_time).total_seconds():.2f}s)"
                        )
                    else:
                        self.logger.error(f"任务执行失败: {task.name}")
                        
                        if retry_count < task.retry_count:
                            retry_count += 1
                            self.logger.info(
                                f"任务 {task.name} 将在 {task.retry_interval}s 后重试 "
                                f"({retry_count}/{task.retry_count})"
                            )
                            time.sleep(task.retry_interval)
                            continue
                    
                    return TaskResult(
                        task_id=task.id,
                        task_name=task.name,
                        status=status,
                        start_time=start_time,
                        end_time=end_time,
                        duration=(end_time - start_time).total_seconds(),
                        group_id=task.group,
                        retry_count=retry_count
                    )
                    
                except TimeoutError:
                    end_time = datetime.now()
                    self.logger.error(f"任务执行超时: {task.name} (超时: {effective_timeout}s)")
                    
                    return TaskResult(
                        task_id=task.id,
                        task_name=task.name,
                        status=TaskStatus.TIMEOUT,
                        start_time=start_time,
                        end_time=end_time,
                        duration=(end_time - start_time).total_seconds(),
                        error_message=f"Task timeout after {effective_timeout}s",
                        group_id=task.group,
                        retry_count=retry_count
                    )
                    
        except Exception as e:
            end_time = datetime.now()
            self.logger.error(f"任务执行异常: {task.name} - {str(e)}")
            
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                duration=(end_time - start_time).total_seconds(),
                error_message=str(e),
                group_id=task.group,
                retry_count=retry_count
            )
            
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
    
    def _calculate_effective_timeout(self, task: Task, timeout: float) -> float:
        """计算有效的超时时间
        
        自动包含 duration 时间，确保 duration 等待不会被 task_timeout 打断
        
        Args:
            task: 任务对象
            timeout: 原始超时时间（秒）
            
        Returns:
            float: 有效的超时时间（秒）
        """
        if not task.case.duration:
            return timeout
        
        duration_seconds = self._parse_duration(task.case.duration)
        
        execution_overhead = 60
        
        effective_timeout = duration_seconds + execution_overhead
        
        return max(timeout, effective_timeout)
    
    def _parse_duration(self, duration: str) -> float:
        """解析时长字符串
        
        Args:
            duration: 时长字符串（如 "60s", "5m", "2h"）
            
        Returns:
            float: 秒数
        """
        if not duration:
            return 0.0
        
        duration = duration.lower().strip()
        
        try:
            if duration.endswith('s'):
                return float(duration[:-1])
            elif duration.endswith('m'):
                return float(duration[:-1]) * 60
            elif duration.endswith('h'):
                return float(duration[:-1]) * 3600
            else:
                return float(duration)
        except (ValueError, AttributeError):
            self.logger.warning(f"无法解析 duration: {duration}，使用默认值 0")
            return 0.0
    
    def _create_temp_case_file(self, case: Any) -> str:
        """创建临时 Case 文件
        
        Args:
            case: Case 定义对象
            
        Returns:
            临时文件路径
        """
        fd, temp_path = tempfile.mkstemp(
            suffix='.yaml',
            prefix='workflow_case_',
            dir='/tmp'
        )
        
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            yaml.dump(
                case.to_case_dict(),
                f,
                allow_unicode=True,
                default_flow_style=False
            )
        
        self.logger.debug(f"创建临时 Case 文件: {temp_path}")
        return temp_path
    
    def _execute_with_timeout(self, case_file: str, timeout: float) -> bool:
        """带超时的执行
        
        Args:
            case_file: Case 文件路径
            timeout: 超时时间（秒）
            
        Returns:
            是否成功
            
        Raises:
            TimeoutError: 执行超时
        """
        from chaos.case.base import CaseManager, CaseExecutor
        
        case_executor = CaseExecutor(
            self.config_manager,
            self.fault_factory,
            self.state_manager,
            self.logger
        )
        case_manager = CaseManager(case_executor, self.logger)
        
        result = [False]
        exception = [None]
        
        def run_case():
            try:
                result[0] = case_manager.execute_single(case_file)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=run_case)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Case execution timeout after {timeout}s")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]


class WorkflowExecutor:
    """工作流执行器
    
    负责执行整个工作流，管理并发和时序控制。
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        fault_factory: FaultFactory,
        state_manager: StateManager,
        logger: Logger,
        max_workers: int = 10
    ):
        self.config_manager = config_manager
        self.fault_factory = fault_factory
        self.state_manager = state_manager
        self.logger = logger
        self.max_workers = max_workers
        
        self.task_executor = TaskExecutor(
            config_manager, fault_factory, state_manager, logger
        )
        self.monitor = WorkflowMonitor()
        self._stop_event = threading.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}，准备停止工作流...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def execute(self, workflow: WorkflowDefinition) -> WorkflowResult:
        """执行工作流
        
        Args:
            workflow: 工作流定义对象
            
        Returns:
            WorkflowResult: 执行结果
        """
        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info(f"开始执行工作流: {workflow.name}")
        self.logger.info(f"工作流 ID: {workflow.id}")
        self.logger.info(f"执行模式: {workflow.execution_mode.value}")
        self.logger.info("=" * 60)
        
        valid, error = workflow.validate()
        if not valid:
            end_time = datetime.now()
            return WorkflowResult(
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                status=TaskStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                error_message=f"Workflow validation failed: {error}"
            )
        
        self.monitor.reset()
        
        if workflow.timing.start_delay > 0:
            self.logger.info(f"启动延迟 {workflow.timing.start_delay}s")
            self._sleep_with_stop_check(workflow.timing.start_delay)
        
        if self._stop_event.is_set():
            end_time = datetime.now()
            return WorkflowResult(
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                status=TaskStatus.SKIPPED,
                start_time=start_time,
                end_time=end_time,
                error_message="Workflow stopped by user"
            )
        
        execution_order = workflow.get_execution_order()
        self.logger.info(f"执行计划: 共 {len(execution_order)} 层")
        
        for layer_index, layer in enumerate(execution_order):
            if self._stop_event.is_set():
                break
            
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"执行第 {layer_index + 1}/{len(execution_order)} 层，共 {len(layer)} 个任务")
            self.logger.info("=" * 60)
            
            if len(layer) == 1:
                self._execute_serial_layer(layer, workflow.timing)
            else:
                self._execute_parallel_layer(layer, workflow.timing)
            
            if layer_index < len(execution_order) - 1:
                interval = workflow.timing.node_interval
                if interval > 0:
                    self.logger.info(f"层间等待 {interval}s")
                    self._sleep_with_stop_check(interval)
        
        end_time = datetime.now()
        stats = self.monitor.get_stats()
        
        overall_status = TaskStatus.SUCCESS
        if stats["failed_count"] > 0 or stats["timeout_count"] > 0:
            overall_status = TaskStatus.FAILED
        
        result = WorkflowResult(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status=overall_status,
            start_time=start_time,
            end_time=end_time,
            total_duration=(end_time - start_time).total_seconds(),
            task_results=self.monitor.get_results(),
            stats=stats
        )
        
        self.logger.info("\n" + result.generate_report())
        
        return result
    
    def _execute_serial_layer(self, layer: List[Task], timing: TimingConfig) -> None:
        """执行串行层
        
        Args:
            layer: 任务列表
            timing: 时间配置
        """
        for i, task in enumerate(layer):
            if self._stop_event.is_set():
                break
            
            result = self.task_executor.execute(task, timing.task_timeout)
            self.monitor.record(result)
            
            if timing.node_interval > 0 and i < len(layer) - 1:
                self.logger.info(f"节点间等待 {timing.node_interval}s")
                self._sleep_with_stop_check(timing.node_interval)
    
    def _execute_parallel_layer(self, layer: List[Task], timing: TimingConfig) -> None:
        """执行并行层
        
        Args:
            layer: 任务列表
            timing: 时间配置
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            for i, task in enumerate(layer):
                if self._stop_event.is_set():
                    break
                
                if timing.branch_start_delay > 0 and i > 0:
                    self.logger.debug(f"分支启动延迟 {timing.branch_start_delay}s")
                    self._sleep_with_stop_check(timing.branch_start_delay)
                
                if self._stop_event.is_set():
                    break
                
                future = executor.submit(
                    self.task_executor.execute,
                    task,
                    timing.task_timeout
                )
                futures.append(future)
            
            for future in as_completed(futures):
                if self._stop_event.is_set():
                    break
                try:
                    result = future.result()
                    self.monitor.record(result)
                except Exception as e:
                    self.logger.error(f"并行任务执行异常: {e}")
    
    def _sleep_with_stop_check(self, seconds: float) -> None:
        """带停止检查的睡眠
        
        Args:
            seconds: 睡眠时间（秒）
        """
        interval = 0.1
        elapsed = 0.0
        while elapsed < seconds and not self._stop_event.is_set():
            time.sleep(min(interval, seconds - elapsed))
            elapsed += interval
    
    def stop(self) -> None:
        """停止执行"""
        self._stop_event.set()
        self.logger.info("工作流执行已请求停止")
    
    def is_stopped(self) -> bool:
        """检查是否已停止"""
        return self._stop_event.is_set()
    
    def get_monitor(self) -> WorkflowMonitor:
        """获取监控器"""
        return self.monitor
