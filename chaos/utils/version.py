"""
版本管理模块
负责版本号和备份管理
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from .logger import Logger


class VersionManager:
    """版本管理器"""
    
    def __init__(self, version_file: str = "VERSION", logger: Optional[Logger] = None):
        """初始化版本管理器
        
        Args:
            version_file: 版本文件路径
            logger: 日志记录器（可选）
        """
        self.version_file = version_file
        self.logger = logger or Logger(name="version")
        self.version = self._load_version()
    
    def _load_version(self) -> str:
        """加载版本号
        
        Returns:
            str: 版本号
        """
        try:
            with open(self.version_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            default_version = "1.0.0"
            self._safe_write_version(default_version)
            return default_version
        except Exception as e:
            self.logger.error(f"加载版本号失败：{e}")
            return "1.0.0"
    
    def _safe_write_version(self, version: str) -> bool:
        """安全写入版本号
        
        Args:
            version: 版本号
            
        Returns:
            bool: 成功标志
        """
        try:
            with open(self.version_file, 'w') as f:
                f.write(version)
            return True
        except PermissionError:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(version)
                    tmp_path = tmp.name
                
                subprocess.run(
                    ['sudo', 'mv', tmp_path, self.version_file],
                    check=True,
                    capture_output=True
                )
                current_user = os.environ.get('USER', 'root')
                subprocess.run(
                    ['sudo', 'chown', f'{current_user}:{current_user}', self.version_file],
                    capture_output=True
                )
                return True
            except Exception as e:
                self.logger.error(f"使用 sudo 写入版本号失败：{e}")
                return False
    
    def get_version(self) -> str:
        """获取当前版本号
        
        Returns:
            str: 当前版本号
        """
        return self.version
    
    def increment_version(self) -> str:
        """增加版本号
        
        Returns:
            str: 新的版本号
        """
        parts = self.version.split('.')
        if len(parts) >= 3:
            major, minor, patch = parts
            try:
                new_patch = int(patch) + 1
                new_version = f"{major}.{minor}.{new_patch}"
            except ValueError:
                new_version = f"{major}.{minor}.1"
        else:
            new_version = "1.0.1"
        
        self.version = new_version
        self._safe_write_version(new_version)
        
        return new_version
    
    def backup_project(self, backup_dir: str = "backups") -> Tuple[bool, str]:
        """备份项目
        
        Args:
            backup_dir: 备份目录
            
        Returns:
            Tuple[bool, str]: (成功标志，备份文件路径)
        """
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"chaos_{self.version}_{timestamp}.tar.gz"
            backup_file_path = backup_path / backup_file
            
            project_dir = Path(__file__).parent.parent.parent
            
            subprocess.run(
                ['tar', '-czf', str(backup_file_path),
                 f'--exclude={str(backup_path)}',
                 '--exclude=.git',
                 '-C', str(project_dir), '.'],
                check=True,
                capture_output=True
            )
            
            return True, str(backup_file_path)
            
        except Exception as e:
            self.logger.error(f"备份项目失败：{e}")
            return False, ""
