"""
日志工具模块
提供统一的日志管理功能
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""
    
    def format(self, record):
        """格式化日志记录为 JSON
        
        Args:
            record: 日志记录
            
        Returns:
            str: JSON 格式的日志字符串
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class Logger:
    """日志记录器"""
    
    def __init__(self, name: str = "chaos", 
                 log_file: Optional[str] = None,
                 level: int = logging.INFO,
                 use_json: bool = False):
        """初始化日志记录器
        
        Args:
            name: 日志名称
            log_file: 日志文件路径（None 则只输出到控制台）
            level: 日志级别
            use_json: 是否使用 JSON 格式
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 避免重复添加 handler
        if self.logger.handlers:
            return
        
        # 创建控制台 handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        if use_json:
            console_formatter = JSONFormatter()
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 创建文件 handler
        if log_file:
            try:
                # 确保日志目录存在
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(level)
                file_handler.setFormatter(console_formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                self.logger.warning(f"无法创建日志文件 {log_file}: {e}")
    
    def debug(self, msg: str):
        """记录 debug 日志"""
        self.logger.debug(msg)
    
    def info(self, msg: str):
        """记录 info 日志"""
        self.logger.info(msg)
    
    def warning(self, msg: str):
        """记录 warning 日志"""
        self.logger.warning(msg)
    
    def error(self, msg: str):
        """记录 error 日志"""
        self.logger.error(msg)
    
    def critical(self, msg: str):
        """记录 critical 日志"""
        self.logger.critical(msg)
    
    def exception(self, msg: str):
        """记录异常日志"""
        self.logger.exception(msg)
