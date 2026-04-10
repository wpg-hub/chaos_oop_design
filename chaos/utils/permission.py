"""
权限管理模块
提供统一的权限处理功能，支持 sudo 操作
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class PermissionManager:
    """权限管理器"""
    
    @staticmethod
    def check_sudo_available() -> bool:
        """检查是否有 sudo 权限"""
        try:
            result = subprocess.run(
                ['sudo', '-n', 'true'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def check_write_permission(path: str) -> bool:
        """检查路径写入权限"""
        path = Path(path)
        
        # 如果路径不存在，检查父目录
        if not path.exists():
            path = path.parent
        
        return os.access(path, os.W_OK)
    
    @staticmethod
    def ensure_directory(path: str, use_sudo: bool = True) -> Tuple[bool, Optional[str]]:
        """确保目录存在
        
        Args:
            path: 目录路径
            use_sudo: 是否使用 sudo
            
        Returns:
            Tuple[bool, Optional[str]]: (成功标志，错误信息)
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True, None
        except PermissionError:
            if use_sudo:
                try:
                    subprocess.run(
                        ['sudo', 'mkdir', '-p', path],
                        check=True,
                        capture_output=True
                    )
                    # 设置所有者为当前用户
                    current_user = os.environ.get('USER', 'root')
                    subprocess.run(
                        ['sudo', 'chown', f'{current_user}:{current_user}', path],
                        capture_output=True
                    )
                    return True, None
                except subprocess.CalledProcessError as e:
                    return False, f"使用 sudo 创建目录失败：{e}"
            return False, f"无权限创建目录：{path}"
    
    @staticmethod
    def safe_write_file(path: str, content: str, use_sudo: bool = True) -> Tuple[bool, Optional[str]]:
        """安全写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
            use_sudo: 是否使用 sudo
            
        Returns:
            Tuple[bool, Optional[str]]: (成功标志，错误信息)
        """
        path = Path(path)
        
        # 确保目录存在
        success, error = PermissionManager.ensure_directory(
            str(path.parent),
            use_sudo
        )
        if not success:
            return False, error
        
        # 尝试直接写入
        try:
            with open(path, 'w') as f:
                f.write(content)
            return True, None
        except PermissionError:
            if use_sudo:
                # 使用临时文件 + sudo 移动
                try:
                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(
                        mode='w',
                        delete=False,
                        suffix='.tmp'
                    ) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name
                    
                    # 使用 sudo 移动到目标位置
                    subprocess.run(
                        ['sudo', 'mv', tmp_path, str(path)],
                        check=True,
                        capture_output=True
                    )
                    
                    # 设置所有者
                    current_user = os.environ.get('USER', 'root')
                    subprocess.run(
                        ['sudo', 'chown', f'{current_user}:{current_user}', str(path)],
                        capture_output=True
                    )
                    
                    return True, None
                except subprocess.CalledProcessError as e:
                    # 清理临时文件
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    return False, f"使用 sudo 写入文件失败：{e}"
            
            return False, f"无权限写入文件：{path}"
    
    @staticmethod
    def safe_read_file(path: str) -> Tuple[Optional[str], Optional[str]]:
        """安全读取文件
        
        Args:
            path: 文件路径
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (文件内容，错误信息)
        """
        try:
            with open(path, 'r') as f:
                return f.read(), None
        except PermissionError:
            # 尝试使用 sudo 读取
            try:
                result = subprocess.run(
                    ['sudo', 'cat', path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout, None
            except subprocess.CalledProcessError:
                return None, f"无权限读取文件：{path}"
        except FileNotFoundError:
            return None, f"文件不存在：{path}"
    
    @staticmethod
    def set_file_owner(path: str, owner: str = None) -> Tuple[bool, Optional[str]]:
        """设置文件所有者
        
        Args:
            path: 文件路径
            owner: 所有者（默认当前用户）
            
        Returns:
            Tuple[bool, Optional[str]]: (成功标志，错误信息)
        """
        if owner is None:
            owner = os.environ.get('USER', 'root')
        
        try:
            subprocess.run(
                ['sudo', 'chown', f'{owner}:{owner}', path],
                check=True,
                capture_output=True
            )
            return True, None
        except subprocess.CalledProcessError as e:
            return False, f"设置文件所有者失败：{e}"
    
    @staticmethod
    def set_file_permission(path: str, mode: int) -> Tuple[bool, Optional[str]]:
        """设置文件权限
        
        Args:
            path: 文件路径
            mode: 权限模式（如 0o755）
            
        Returns:
            Tuple[bool, Optional[str]]: (成功标志，错误信息)
        """
        try:
            subprocess.run(
                ['sudo', 'chmod', oct(mode), path],
                check=True,
                capture_output=True
            )
            return True, None
        except subprocess.CalledProcessError as e:
            return False, f"设置文件权限失败：{e}"
