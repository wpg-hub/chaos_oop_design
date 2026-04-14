#!/usr/bin/env python3
"""
Chaos 命令行入口
提供统一的命令行接口
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from chaos.config import ConfigManager
from chaos.utils.logger import Logger
from chaos.utils.version import VersionManager
from chaos.fault.base import FaultFactory
from chaos.state.manager import StateManager, FileFaultRepository
from chaos.case.base import CaseConfig, CaseExecutor, CaseManager
from chaos.handlers import PodActionHandler, ClearActionHandler, LogActionHandler
from chaos.constants import DEFAULT_TIMEOUT
from chaos.utils.remote import get_ssh_pool
from chaos.workflow import WorkflowParser, WorkflowExecutor


def main():
    parser = argparse.ArgumentParser(description="Chaos: Chaos engineering toolkit")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    case_parser = subparsers.add_parser("case", help="Run case")
    case_parser.add_argument("--name", help="Case name or YAML file path")
    case_parser.add_argument("--dir", help="Directory to run all cases recursively")
    case_parser.add_argument("--env", default="all", help="Environment to run")
    case_parser.add_argument("--namespace", help="Namespace to use")
    case_parser.add_argument("--cleanup", action="store_true", help="Cleanup after case")
    case_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Execution timeout in seconds")
    
    clear_parser = subparsers.add_parser("clear", help="Clear chaos effects")
    clear_parser.add_argument("--env", default="all", help="Environment to clear")
    clear_parser.add_argument("--type", default="all", choices=["all", "network", "pod"], help="Type of effects to clear")
    clear_parser.add_argument("--device", default="eth0", help="Network device to clear")
    clear_parser.add_argument("--namespace", help="Namespace to use")
    
    pod_parser = subparsers.add_parser("pod", help="Manage pods")
    pod_parser.add_argument("--action", required=True, 
                          choices=["list", "ddb", "sdb", "etcd", "upc", "upu", "rc"],
                          help="Pod action")
    pod_parser.add_argument("--namespace", default=None, help="Namespace (default: from config.yaml)")
    pod_parser.add_argument("--env", default="all", help="Environment")
    
    version_parser = subparsers.add_parser("version", help="Manage version")
    version_parser.add_argument("--action", required=True, 
                              choices=["show", "iterate"], 
                              help="Version action")
    version_parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    
    state_parser = subparsers.add_parser("state", help="Manage fault state")
    state_parser.add_argument("--action", required=True, 
                            choices=["list", "clear"], 
                            help="State action")
    state_parser.add_argument("--format", default="table", 
                            choices=["table", "json"], 
                            help="Output format")
    state_parser.add_argument("--fault-id", help="Specific fault ID to operate on")
    
    log_parser = subparsers.add_parser("log", help="Collect logs from nodes")
    log_parser.add_argument("--date", required=True, help="Date to collect logs (format: YYYY-MM-DD)")
    log_parser.add_argument("--log-dir", default="/var/ctin/ctc-upf/var/log/service-logs", 
                          help="Log base directory")
    log_parser.add_argument("--target-dir", default="/home/gsta", 
                          help="Target directory for final archive")
    
    workflow_parser = subparsers.add_parser("workflow", help="Run workflow")
    
    # 创建互斥组，--file 和 --dir 不能同时使用
    workflow_group = workflow_parser.add_mutually_exclusive_group(required=True)
    workflow_group.add_argument("--file", help="Workflow YAML file path")
    workflow_group.add_argument("--dir", help="Directory containing workflow YAML files (recursive)")
    
    workflow_parser.add_argument("--dry-run", action="store_true", help="Dry run mode (validate only)")
    workflow_parser.add_argument("--max-workers", type=int, default=10, help="Max parallel workers")
    
    args = parser.parse_args()
    
    logger = Logger(name="chaos")
    
    if args.command == "case":
        handle_case_command(args, logger)
    elif args.command == "clear":
        handle_clear_command(args, logger)
    elif args.command == "pod":
        handle_pod_command(args, logger)
    elif args.command == "version":
        handle_version_command(args, logger)
    elif args.command == "state":
        handle_state_command(args, logger)
    elif args.command == "log":
        handle_log_command(args, logger)
    elif args.command == "workflow":
        handle_workflow_command(args, logger)


def handle_case_command(args, logger):
    config_manager = ConfigManager()
    fault_factory = FaultFactory()
    state_manager = StateManager(FileFaultRepository(), logger)
    case_executor = CaseExecutor(config_manager, fault_factory, state_manager, logger)
    case_manager = CaseManager(case_executor, logger)
    
    if args.name:
        logger.info(f"执行单个 Case: {args.name}")
        success = case_manager.execute_single(args.name)
        sys.exit(0 if success else 1)
    elif args.dir:
        logger.info(f"批量执行 Case 目录：{args.dir}")
        results = case_manager.execute_batch(args.dir)
        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed
        logger.info(f"执行完成：总计 {total}, 通过 {passed}, 失败 {failed}")
        sys.exit(0 if failed == 0 else 1)
    else:
        logger.error("必须指定 --name 或 --dir 参数")
        sys.exit(1)


def handle_clear_command(args, logger):
    logger.info(f"清除故障：env={args.env}, type={args.type}")
    
    try:
        config_manager = ConfigManager()
        default_namespace = config_manager.get_namespace()
        namespace = args.namespace if args.namespace else default_namespace
        device = args.device
        
        if args.env == "all":
            environments = config_manager.get_all_environments()
        else:
            env = config_manager.get_environment(args.env)
            if not env:
                logger.error(f"环境不存在：{args.env}")
                return
            environments = [env]
        
        clear_handler = ClearActionHandler(config_manager, logger)
        
        for env in environments:
            logger.info(f"清除环境 {env.name} 的故障")
            
            if args.type in ["all", "network"]:
                logger.info(f"清除环境 {env.name} 的网络故障")
                logger.info(f"网络设备: {device}, 命名空间: {namespace}")
                logger.info(f"节点名称: {env.nodename}")
                
                result = clear_handler.clear_network_faults(env, device, namespace)
                
                if result["connected"]:
                    logger.info(f"环境 {env.name} 网络故障清除完成：成功 {result['success']}, 失败 {result['failure']}")
        
        state_manager = StateManager(FileFaultRepository(), logger)
        state_manager.clear_all()
        
        logger.info("清除完成")
        
    except Exception as e:
        logger.error(f"清除故障时发生错误：{e}")


def handle_pod_command(args, logger):
    try:
        config_manager = ConfigManager()
        default_namespace = config_manager.get_namespace()
        namespace = args.namespace if args.namespace else default_namespace
        
        logger.info(f"Pod 操作：action={args.action}, namespace={namespace}")
        
        if args.env == "all":
            environments = config_manager.get_all_environments()
        else:
            env = config_manager.get_environment(args.env)
            if not env:
                logger.error(f"环境不存在：{args.env}")
                return
            environments = [env]
        
        pod_handler = PodActionHandler(config_manager, logger)
        action_func = pod_handler.get_handler(args.action)
        
        if not action_func:
            logger.error(f"不支持的操作：{args.action}")
            return
        
        pool = get_ssh_pool()
        
        if args.env == "all":
            last_error = None
            
            for env in environments:
                logger.info(f"尝试从环境 {env.name} 获取信息")
                
                ssh_executor = pool.get_connection_from_env(env)
                
                if not ssh_executor.is_alive() and not ssh_executor.connect():
                    logger.warning(f"无法连接到环境 {env.name}")
                    last_error = f"无法连接到环境 {env.name}"
                    continue
                
                try:
                    from chaos.utils.pod import PodManager
                    pod_manager = PodManager(ssh_executor, logger, config_manager)
                    success = action_func(pod_manager, namespace)
                    
                    if success:
                        logger.info(f"从环境 {env.name} 成功获取信息")
                        return
                    else:
                        logger.warning(f"环境 {env.name} 中没有找到信息")
                        last_error = f"环境 {env.name} 中没有找到信息"
                except Exception as e:
                    logger.warning(f"环境 {env.name} 操作失败：{e}")
                    last_error = str(e)
            
            if last_error:
                logger.error(f"无法从任何环境获取信息：{last_error}")
        else:
            env = environments[0]
            logger.info(f"处理环境：{env.name}")
            
            ssh_executor = pool.get_connection_from_env(env)
            
            if not ssh_executor.is_alive() and not ssh_executor.connect():
                logger.error(f"无法连接到环境 {env.name}")
                return
            
            try:
                from chaos.utils.pod import PodManager
                pod_manager = PodManager(ssh_executor, logger, config_manager)
                action_func(pod_manager, namespace)
            except Exception as e:
                logger.error(f"Pod 操作失败：{e}")
                    
    except Exception as e:
        logger.error(f"Pod 操作失败：{e}")


def handle_version_command(args, logger):
    version_manager = VersionManager()
    
    if args.action == "show":
        print(version_manager.get_version())
    elif args.action == "iterate":
        new_version, backup_path = version_manager.iterate_version(args.backup_dir)
        logger.info(f"版本已更新到：{new_version}")
        logger.info(f"备份已创建：{backup_path}")


def handle_state_command(args, logger):
    state_manager = StateManager(FileFaultRepository(), logger)
    
    if args.action == "list":
        faults = state_manager.get_active_faults()
        display_faults(faults, args.format)
    elif args.action == "clear":
        if args.fault_id:
            state_manager.mark_recovered(args.fault_id)
            logger.info(f"故障已清除：{args.fault_id}")
        else:
            state_manager.clear_all()
            logger.info("所有故障已清除")


def display_faults(faults, format):
    if format == "json":
        import json
        from dataclasses import asdict
        print(json.dumps([asdict(f) for f in faults], indent=2, default=str))
    else:
        if not faults:
            print("没有活跃的故障")
            return
        
        print(f"{'Fault ID':<40} {'Case':<20} {'Type':<10} {'Status':<10} {'Start Time'}")
        print("-" * 100)
        for fault in faults:
            print(f"{fault.fault_id:<40} {fault.case_name:<20} "
                  f"{fault.fault_type:<10} {fault.status:<10} "
                  f"{fault.start_time.strftime('%Y-%m-%d %H:%M:%S')}")


def handle_log_command(args, logger):
    config_manager = ConfigManager()
    log_handler = LogActionHandler(config_manager, logger)
    
    success = log_handler.collect_logs(
        date=args.date,
        log_dir=args.log_dir,
        target_dir=args.target_dir
    )
    
    if success:
        logger.info("日志收集完成")
        sys.exit(0)
    else:
        logger.error("日志收集失败")
        sys.exit(1)


def handle_workflow_command(args, logger):
    from chaos.workflow.parser import WorkflowParseError
    from pathlib import Path
    from datetime import datetime
    
    try:
        # 批量执行模式
        if args.dir:
            handle_workflow_batch(args, logger)
        # 单文件执行模式
        elif args.file:
            handle_workflow_single(args, logger)
            
    except WorkflowParseError as e:
        logger.error(f"工作流解析错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"工作流执行错误: {e}")
        sys.exit(1)


def handle_workflow_single(args, logger):
    """执行单个workflow文件
    
    Args:
        args: 命令行参数
        logger: 日志器
    """
    parser = WorkflowParser(logger)
    
    if args.dry_run:
        valid, error = parser.validate_yaml_file(args.file)
        if valid:
            logger.info(f"工作流配置验证通过: {args.file}")
            sys.exit(0)
        else:
            logger.error(f"工作流配置验证失败: {error}")
            sys.exit(1)
    
    workflow = parser.parse(args.file)
    
    config_manager = ConfigManager()
    fault_factory = FaultFactory()
    state_manager = StateManager(FileFaultRepository(), logger)
    
    executor = WorkflowExecutor(
        config_manager,
        fault_factory,
        state_manager,
        logger,
        max_workers=args.max_workers
    )
    
    result = executor.execute(workflow)
    
    sys.exit(0 if result.status.value == "success" else 1)


def handle_workflow_batch(args, logger):
    """批量执行目录下的workflow文件
    
    Args:
        args: 命令行参数
        logger: 日志器
    """
    from pathlib import Path
    from datetime import datetime
    
    # 查找所有YAML文件
    yaml_files = []
    dir_path = Path(args.dir)
    
    if not dir_path.exists():
        logger.error(f"目录不存在: {args.dir}")
        sys.exit(1)
    
    if not dir_path.is_dir():
        logger.error(f"路径不是目录: {args.dir}")
        sys.exit(1)
    
    # 递归查找所有.yaml和.yml文件
    for pattern in ["*.yaml", "*.yml"]:
        yaml_files.extend(dir_path.rglob(pattern))
    
    # 按文件名排序
    yaml_files = sorted(yaml_files, key=lambda x: str(x))
    
    if not yaml_files:
        logger.warning(f"目录中没有找到YAML文件: {args.dir}")
        sys.exit(0)
    
    logger.info(f"找到 {len(yaml_files)} 个workflow文件")
    
    # 批量执行结果
    batch_results = []
    
    # 创建执行器
    config_manager = ConfigManager()
    fault_factory = FaultFactory()
    state_manager = StateManager(FileFaultRepository(), logger)
    workflow_parser = WorkflowParser(logger)
    
    executor = WorkflowExecutor(
        config_manager,
        fault_factory,
        state_manager,
        logger,
        max_workers=args.max_workers
    )
    
    # 串行执行每个workflow
    for yaml_file in yaml_files:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"执行workflow: {yaml_file}")
        logger.info(f"{'=' * 80}")
        
        try:
            workflow = workflow_parser.parse(str(yaml_file))
            start_time = datetime.now()
            result = executor.execute(workflow)
            end_time = datetime.now()
            
            batch_results.append({
                "file": str(yaml_file),
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "status": result.status.value,
                "duration": (end_time - start_time).total_seconds(),
                "error": None
            })
            
        except Exception as e:
            end_time = datetime.now()
            logger.error(f"Workflow执行失败: {yaml_file}, 错误: {e}")
            
            batch_results.append({
                "file": str(yaml_file),
                "workflow_id": "N/A",
                "workflow_name": "N/A",
                "status": "failed",
                "duration": (end_time - start_time).total_seconds(),
                "error": str(e)
            })
    
    # 生成批量执行报告
    generate_batch_report(batch_results, logger)
    
    # 根据是否有失败的workflow决定退出码
    failed_count = sum(1 for r in batch_results if r["status"] != "success")
    sys.exit(1 if failed_count > 0 else 0)


def generate_batch_report(batch_results, logger):
    """生成批量执行报告
    
    Args:
        batch_results: 批量执行结果列表
        logger: 日志器
    """
    total = len(batch_results)
    success_count = sum(1 for r in batch_results if r["status"] == "success")
    failed_count = total - success_count
    
    # 打印汇总报告
    print("\n" + "=" * 80)
    print("                    Workflow Batch Execution Report                    ")
    print("=" * 80)
    print(f"Total Workflows : {total}")
    print(f"Success        : {success_count}")
    print(f"Failed         : {failed_count}")
    print("=" * 80)
    
    # 打印详细结果表格
    print("\nWorkflow Execution Details:")
    print("-" * 80)
    print(f"{'ID':<30} {'Name':<25} {'Status':<10} {'Duration':<10}")
    print("-" * 80)
    
    for result in batch_results:
        print(f"{result['workflow_id']:<30} "
              f"{result['workflow_name'][:25]:<25} "
              f"{result['status'].upper():<10} "
              f"{result['duration']:.1f}s")
    
    print("=" * 80)
    
    # 打印失败的workflow详情
    if failed_count > 0:
        print("\nFailed Workflows:")
        print("-" * 80)
        
        failed_index = 1
        for result in batch_results:
            if result["status"] != "success":
                print(f"{failed_index}. {result['workflow_id']} - {result['workflow_name']}")
                print(f"   File: {result['file']}")
                if result['error']:
                    print(f"   Error: {result['error']}")
                print()
                failed_index += 1
        
        print("=" * 80)


if __name__ == "__main__":
    main()
