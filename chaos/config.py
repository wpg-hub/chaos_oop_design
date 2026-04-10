"""
配置管理模块
负责加载、验证和访问配置信息
"""

import yaml
from typing import Dict, List, Optional
from pathlib import Path


class EnvironmentConfig:
    """环境配置类"""
    
    def __init__(self, name: str, config: Dict):
        """初始化环境配置
        
        Args:
            name: 环境名称
            config: 环境配置字典
        """
        self.name = name
        self.config = config
        self.type = config.get("type", "ssh")
        self.ip = config.get("ip")
        self.port = config.get("port", 22)
        self.user = config.get("user")
        self.passwd = config.get("passwd")
        self.nodename = config.get("nodename")
        self.key_file = config.get("key_file")
        self.default_namespace = config.get("default_namespace")
    
    def get(self, key: str, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def __repr__(self):
        return f"EnvironmentConfig(name={self.name}, type={self.type}, ip={self.ip})"


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.yaml"):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = {}
        self.environments: Dict[str, EnvironmentConfig] = {}
        self.sw_environments: Dict[str, EnvironmentConfig] = {}
        self.defaults: Dict = {}
        self.upu_filters: List[str] = []
        self.upu_filters_slave: List[str] = []
        
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在：{self.config_file}")
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # 加载环境配置
        environments = self.config.get("environments", {})
        for name, env_config in environments.items():
            self.environments[name] = EnvironmentConfig(name, env_config)
        
        # 加载交换机环境配置
        sw_environments = self.config.get("sw_environments", {})
        for name, env_config in sw_environments.items():
            self.sw_environments[name] = EnvironmentConfig(name, env_config)
        
        # 加载默认配置
        self.defaults = self.config.get("defaults", {})
        
        # 加载 UPU 过滤列表
        self.upu_filters = self.config.get("UPU_POD_FILTERS", [])
        self.upu_filters_slave = self.config.get("UPU_POD_FILTERS_SLAVE", [])
    
    def get_environment(self, env_name: str) -> Optional[EnvironmentConfig]:
        """获取环境配置
        
        Args:
            env_name: 环境名称
            
        Returns:
            EnvironmentConfig: 环境配置对象
        """
        return self.environments.get(env_name)
    
    def get_all_environments(self) -> List[EnvironmentConfig]:
        """获取所有环境配置
        
        Returns:
            List[EnvironmentConfig]: 环境配置列表
        """
        return list(self.environments.values())
    
    def get_sw_environment(self, env_name: str) -> Optional[EnvironmentConfig]:
        """获取交换机环境配置
        
        Args:
            env_name: 交换机环境名称
            
        Returns:
            EnvironmentConfig: 环境配置对象
        """
        return self.sw_environments.get(env_name)
    
    def get_defaults(self) -> Dict:
        """获取默认配置
        
        Returns:
            Dict: 默认配置
        """
        return self.defaults
    
    def get_namespace(self) -> str:
        """获取默认命名空间
        
        Returns:
            str: 默认命名空间（默认值：ns-dupf）
        """
        return self.defaults.get("namespace", "ns-dupf")
    
    def get_upu_filters(self) -> List[str]:
        """获取 UPU 过滤列表
        
        Returns:
            List[str]: UPU Pod 名称列表
        """
        return self.upu_filters
    
    def get_upu_filters_slave(self) -> List[str]:
        """获取 UPU Slave 过滤列表
        
        Returns:
            List[str]: UPU Slave Pod 名称列表
        """
        return self.upu_filters_slave
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """验证配置
        
        Returns:
            Tuple[bool, Optional[str]]: (是否有效，错误信息)
        """
        # 检查必需的环境配置
        if not self.environments:
            return False, "没有配置任何环境"
        
        # 验证每个环境配置
        for name, env in self.environments.items():
            if not env.ip:
                return False, f"环境 {name} 缺少必需的 ip 配置"
        
        return True, None
