"""
日志收集器模块
提供远程日志收集和打包功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import os
import re


class LogCollector(ABC):
    """日志收集器抽象类"""
    
    @abstractmethod
    def collect_logs(self, date: str, log_base_dir: str) -> bool:
        """收集日志
        
        Args:
            date: 日期（格式：YYYY-MM-DD）
            log_base_dir: 日志基础目录
            
        Returns:
            bool: 成功标志
        """
        pass
    
    @abstractmethod
    def get_collected_files(self) -> List[str]:
        """获取已收集的文件列表
        
        Returns:
            List[str]: 文件路径列表
        """
        pass


class NodeLogCollector(LogCollector):
    """单节点日志收集器"""
    
    def __init__(self, ssh_executor, logger, node_name: str):
        """初始化节点日志收集器
        
        Args:
            ssh_executor: SSH 执行器
            logger: 日志记录器
            node_name: 节点名称
        """
        self.ssh_executor = ssh_executor
        self.logger = logger
        self.node_name = node_name
        self.collected_files = []
        self.temp_dir = "/tmp/log_collect"
    
    def collect_logs(self, date: str, log_base_dir: str) -> bool:
        """收集指定日期的日志
        
        Args:
            date: 日期（格式：YYYY-MM-DD）
            log_base_dir: 日志基础目录
            
        Returns:
            bool: 成功标志
        """
        try:
            self.logger.info(f"[{self.node_name}] 开始收集日志，日期：{date}")
            
            # 验证日期格式
            if not self._validate_date(date):
                self.logger.error(f"[{self.node_name}] 无效的日期格式：{date}")
                return False
            
            # 创建临时目录
            if not self._create_temp_dir():
                return False
            
            # 获取所有子目录
            sub_dirs = self._get_sub_directories(log_base_dir)
            if not sub_dirs:
                self.logger.warning(f"[{self.node_name}] 未找到子目录：{log_base_dir}")
                return True
            
            self.logger.info(f"[{self.node_name}] 找到 {len(sub_dirs)} 个子目录")
            
            # 处理每个子目录
            for sub_dir in sub_dirs:
                if not self._process_sub_directory(sub_dir, date, log_base_dir):
                    self.logger.warning(f"[{self.node_name}] 处理子目录失败：{sub_dir}")
            
            # 汇总打包
            if not self._create_node_archive(date):
                return False
            
            self.logger.info(f"[{self.node_name}] 日志收集完成")
            return True
            
        except Exception as e:
            self.logger.error(f"[{self.node_name}] 日志收集失败：{e}")
            return False
    
    def _validate_date(self, date: str) -> bool:
        """验证日期格式
        
        Args:
            date: 日期字符串
            
        Returns:
            bool: 是否有效
        """
        try:
            datetime.strptime(date, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def _create_temp_dir(self) -> bool:
        """创建临时目录
        
        Returns:
            bool: 成功标志
        """
        cmd = f"mkdir -p {self.temp_dir}/{self.node_name}"
        success, output = self.ssh_executor.execute(cmd)
        return success
    
    def _get_sub_directories(self, base_dir: str) -> List[str]:
        """获取所有子目录（递归）
        
        Args:
            base_dir: 基础目录
            
        Returns:
            List[str]: 子目录列表
        """
        cmd = f"find {base_dir} -type d"
        success, output = self.ssh_executor.execute(cmd)
        
        if not success:
            return []
        
        all_dirs = [d.strip() for d in output.strip().split('\n') if d.strip()]
        all_dirs = [d for d in all_dirs if d != base_dir]
        
        return all_dirs
    
    def _process_sub_directory(self, sub_dir: str, date: str, log_base_dir: str) -> bool:
        """处理子目录
        
        Args:
            sub_dir: 子目录路径
            date: 日期
            log_base_dir: 日志基础目录
            
        Returns:
            bool: 成功标志
        """
        try:
            relative_path = os.path.relpath(sub_dir, log_base_dir)
            archive_name = relative_path.replace('/', '_').replace('\\', '_')
            
            self.logger.info(f"[{self.node_name}] 处理子目录：{relative_path}")
            
            log_files = self._find_log_files(sub_dir, date)
            
            if not log_files:
                self.logger.debug(f"[{self.node_name}] 未找到日期 {date} 的日志文件：{sub_dir}")
                return True
            
            self.logger.info(f"[{self.node_name}] 找到 {len(log_files)} 个日志文件")
            
            archive_filename = f"{archive_name}_{date}.tar.gz"
            archive_path = f"{self.temp_dir}/{self.node_name}/{archive_filename}"
            
            cmd = f"cd {sub_dir} && tar -czf {archive_path} {' '.join([os.path.basename(f) for f in log_files])}"
            
            success, output = self.ssh_executor.execute(cmd)
            
            if success:
                self.collected_files.append(archive_path)
                self.logger.info(f"[{self.node_name}] 已打包：{archive_filename}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"[{self.node_name}] 处理子目录失败：{e}")
            return False
    
    def _find_log_files(self, directory: str, date: str) -> List[str]:
        """查找指定日期的日志文件（仅当前目录，不递归）
        
        支持两种过滤方式：
        1. 按文件名包含日期过滤（如 *2026-03-26*）
        2. 按文件修改时间过滤（如 2026-03-26 当天修改的文件）
        
        Args:
            directory: 目录路径
            date: 日期（格式：YYYY-MM-DD）
            
        Returns:
            List[str]: 日志文件列表
        """
        files = []
        
        cmd = f"find {directory} -maxdepth 1 -type f -name '*{date}*' 2>/dev/null"
        success, output = self.ssh_executor.execute(cmd, ignore_errors=True)
        
        if success:
            files = [f.strip() for f in output.strip().split('\n') if f.strip()]
        
        if not files:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
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
                
                date_str = f"{year}-{month:02d}-{day:02d}"
                next_date_str = f"{next_year}-{next_month:02d}-{next_day:02d}"
                
                cmd = f"find {directory} -maxdepth 1 -type f -newermt '{date_str}' ! -newermt '{next_date_str}' 2>/dev/null"
                success, output = self.ssh_executor.execute(cmd, ignore_errors=True)
                
                if success:
                    files = [f.strip() for f in output.strip().split('\n') if f.strip()]
                    
            except Exception as e:
                self.logger.warning(f"[{self.node_name}] 解析日期失败：{e}")
        
        return files
    
    def _create_node_archive(self, date: str) -> bool:
        """创建节点归档文件
        
        Args:
            date: 日期
            
        Returns:
            bool: 成功标志
        """
        try:
            archive_name = f"{self.node_name}.tar"
            archive_path = f"{self.temp_dir}/{archive_name}"
            node_temp_dir = f"{self.temp_dir}/{self.node_name}"
            
            # 打包所有子目录的压缩包
            cmd = f"cd {self.temp_dir} && tar -cf {archive_path} -C {self.temp_dir} {self.node_name}"
            success, output = self.ssh_executor.execute(cmd)
            
            if success:
                self.logger.info(f"[{self.node_name}] 已创建节点归档：{archive_name}")
                # 清理子目录压缩包
                self._cleanup_temp_files(node_temp_dir)
            
            return success
            
        except Exception as e:
            self.logger.error(f"[{self.node_name}] 创建节点归档失败：{e}")
            return False
    
    def _cleanup_temp_files(self, directory: str):
        """清理临时文件
        
        Args:
            directory: 目录路径
        """
        cmd = f"rm -rf {directory}"
        self.ssh_executor.execute(cmd, ignore_errors=True)
        self.logger.info(f"[{self.node_name}] 已清理临时文件")
    
    def get_collected_files(self) -> List[str]:
        """获取已收集的文件列表
        
        Returns:
            List[str]: 文件路径列表
        """
        return self.collected_files
    
    def get_node_archive_path(self) -> str:
        """获取节点归档文件路径
        
        Returns:
            str: 归档文件路径
        """
        return f"{self.temp_dir}/{self.node_name}.tar"


class MultiNodeLogCollector:
    """多节点日志收集器"""
    
    def __init__(self, config_manager, logger):
        """初始化多节点日志收集器
        
        Args:
            config_manager: 配置管理器
            logger: 日志记录器
        """
        self.config_manager = config_manager
        self.logger = logger
        self.node_collectors = []
    
    def collect_all_logs(self, date: str, log_base_dir: str, 
                         target_dir: str = "/home/gsta") -> bool:
        """收集所有节点的日志
        
        Args:
            date: 日期
            log_base_dir: 日志基础目录
            target_dir: 目标目录
            
        Returns:
            bool: 成功标志
        """
        try:
            self.logger.info(f"开始收集所有节点日志，日期：{date}")
            
            # 获取所有环境
            environments = self.config_manager.get_all_environments()
            if not environments:
                self.logger.error("未找到任何环境配置")
                return False
            
            self.logger.info(f"找到 {len(environments)} 个节点")
            
            # 收集每个节点的日志
            collected_archives = []
            
            for env in environments:
                archive_path = self._collect_single_node(env, date, log_base_dir)
                if archive_path:
                    collected_archives.append((env.name, archive_path))
            
            if not collected_archives:
                self.logger.error("没有收集到任何日志")
                return False
            
            # 汇总到第一个节点
            if not self._aggregate_to_first_node(collected_archives, date, target_dir):
                return False
            
            self.logger.info("所有节点日志收集完成")
            return True
            
        except Exception as e:
            self.logger.error(f"收集所有节点日志失败：{e}")
            return False
    
    def _collect_single_node(self, env_config, date: str, 
                             log_base_dir: str) -> Optional[str]:
        """收集单个节点的日志
        
        Args:
            env_config: 环境配置
            date: 日期
            log_base_dir: 日志基础目录
            
        Returns:
            Optional[str]: 归档文件路径
        """
        from chaos.utils.remote import get_ssh_pool
        
        self.logger.info(f"正在收集节点 {env_config.name} 的日志")
        
        pool = get_ssh_pool()
        ssh_executor = pool.get_connection(
            host=env_config.ip,
            port=env_config.port,
            user=env_config.user,
            passwd=env_config.passwd
        )
        
        if not ssh_executor.is_alive() and not ssh_executor.connect():
            self.logger.error(f"无法连接到节点 {env_config.name}")
            return None
        
        try:
            # 创建节点日志收集器
            collector = NodeLogCollector(
                ssh_executor=ssh_executor,
                logger=self.logger,
                node_name=env_config.name
            )
            
            # 收集日志
            if collector.collect_logs(date, log_base_dir):
                return collector.get_node_archive_path()
            
            return None
            
        except Exception as e:
            self.logger.error(f"收集节点 {env_config.name} 日志时发生错误：{e}")
            return None
    
    def _aggregate_to_first_node(self, archives: List[Tuple[str, str]], 
                                  date: str, target_dir: str) -> bool:
        """汇总到第一个节点
        
        Args:
            archives: 归档文件列表 [(节点名, 文件路径), ...]
            date: 日期
            target_dir: 目标目录
            
        Returns:
            bool: 成功标志
        """
        try:
            if not archives:
                return False
            
            first_node_name, first_archive = archives[0]
            first_env = self.config_manager.get_environment(first_node_name)
            
            if not first_env:
                self.logger.error(f"找不到第一个节点配置：{first_node_name}")
                return False
            
            self.logger.info(f"汇总日志到节点 {first_node_name}")
            
            from chaos.utils.remote import get_ssh_pool
            
            pool = get_ssh_pool()
            ssh_executor = pool.get_connection(
                host=first_env.ip,
                port=first_env.port,
                user=first_env.user,
                passwd=first_env.passwd
            )
            
            if not ssh_executor.is_alive() and not ssh_executor.connect():
                self.logger.error(f"无法连接到节点 {first_node_name}")
                return False
            
            try:
                # 创建目标目录
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_archive = f"{date}_{timestamp}.tar"
                final_path = f"{target_dir}/{final_archive}"
                
                cmd = f"mkdir -p {target_dir}"
                ssh_executor.execute(cmd)
                
                # 创建临时收集目录
                collect_dir = f"{target_dir}/log_collect_{timestamp}"
                cmd = f"mkdir -p {collect_dir}"
                ssh_executor.execute(cmd)
                
                # 移动第一个节点的归档到收集目录
                node_tar_name = os.path.basename(first_archive)
                cmd = f"cp {first_archive} {collect_dir}/{node_tar_name}"
                ssh_executor.execute(cmd)
                
                # 从其他节点传输文件到第一个节点
                for node_name, archive_path in archives[1:]:
                    self._transfer_file(node_name, archive_path, 
                                        first_env, collect_dir, ssh_executor)
                
                # 创建最终归档
                cmd = f"cd {target_dir} && tar -cf {final_path} -C {target_dir} log_collect_{timestamp}"
                success, output = ssh_executor.execute(cmd)
                
                if success:
                    self.logger.info(f"已创建最终归档：{final_path}")
                    # 清理临时目录
                    cmd = f"rm -rf {collect_dir}"
                    ssh_executor.execute(cmd, ignore_errors=True)
                    # 清理第一个节点的临时归档
                    cmd = f"rm -f {first_archive}"
                    ssh_executor.execute(cmd, ignore_errors=True)
                
                return success
                
            except Exception as e:
                self.logger.error(f"创建最终归档时发生错误：{e}")
                return False
                
        except Exception as e:
            self.logger.error(f"汇总日志失败：{e}")
            return False
    
    def _transfer_file(self, source_node: str, source_file: str,
                       target_env, target_dir: str, target_ssh):
        """从第一个节点主动拉取其他节点的文件
        
        Args:
            source_node: 源节点名称
            source_file: 源文件路径
            target_env: 目标环境配置（第一个节点）
            target_dir: 目标目录
            target_ssh: 目标 SSH 执行器
        """
        try:
            source_env = self.config_manager.get_environment(source_node)
            if not source_env:
                self.logger.warning(f"找不到源节点配置：{source_node}")
                return
            
            self.logger.info(f"从 {source_node} 拉取文件到第一个节点")
            
            source_path = f"{source_env.user}@{source_env.ip}:{source_file}"
            
            scp_cmd = (
                f"sshpass -p '{source_env.passwd}' "
                f"scp -o StrictHostKeyChecking=no "
                f"-P {source_env.port} "
                f"{source_path} {target_dir}/"
            )
            
            success, output = target_ssh.execute(scp_cmd, ignore_errors=True)
            
            if success:
                self.logger.info(f"文件拉取成功：{source_file}")
            else:
                self.logger.warning(f"文件拉取失败：{output}")
                
        except Exception as e:
            self.logger.error(f"拉取文件失败：{e}")
