"""单例模式工具模块

提供线程安全的单例实现，确保__init__只执行一次。
"""

import threading
import warnings
from typing import Dict, Type, Any, Optional


class SingletonMeta(type):
    """线程安全的单例元类
    
    使用示例:
        class MyClass(metaclass=SingletonMeta):
            def __init__(self, arg1, arg2):
                self.arg1 = arg1
                self.arg2 = arg2
    
    特性:
        1. 线程安全：使用双重检查锁定
        2. __init__只执行一次：元类层面阻止重复初始化
        3. 支持参数传递：首次创建时的参数会被使用
        4. 参数忽略警告：后续调用时参数被忽略会发出警告
    """
    
    _instances: Dict[Type, Any] = {}
    _lock: threading.Lock = threading.Lock()
    _initialized: Dict[Type, bool] = {}
    _init_locks: Dict[Type, threading.Lock] = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = cls.__new__(cls)
                    cls._instances[cls] = instance
                    
                    if cls not in cls._init_locks:
                        cls._init_locks[cls] = threading.Lock()
                    
                    with cls._init_locks[cls]:
                        instance.__init__(*args, **kwargs)
                        cls._initialized[cls] = True
        else:
            if args or kwargs:
                warnings.warn(
                    f"{cls.__name__} 已初始化，参数 {args, kwargs} 被忽略。"
                    f"如需重新初始化，请调用 {cls.__name__}.reset_instance()",
                    UserWarning,
                    stacklevel=2
                )
        
        return cls._instances[cls]
    
    @classmethod
    def get_instance_count(mcs) -> int:
        """获取已创建的单例数量"""
        return len(mcs._instances)


class Singleton(metaclass=SingletonMeta):
    """单例基类
    
    使用示例:
        class MyClass(Singleton):
            def __init__(self, arg1, arg2):
                super().__init__()
                self.arg1 = arg1
                self.arg2 = arg2
    
    注意：子类无需在__init__中检查_is_initialized()，
          元类会自动处理初始化逻辑。
    """
    
    def __init__(self):
        pass
    
    @classmethod
    def _is_initialized(cls) -> bool:
        """检查当前类是否已初始化
        
        Returns:
            bool: 如果已初始化返回True
        """
        return SingletonMeta._initialized.get(cls, False)
    
    @classmethod
    def get_instance(cls, *args, **kwargs):
        """获取单例实例
        
        Args:
            *args: 位置参数（仅在首次创建时使用）
            **kwargs: 关键字参数（仅在首次创建时使用）
            
        Returns:
            单例实例
        """
        return cls(*args, **kwargs)
    
    @classmethod
    def reset_instance(cls) -> bool:
        """重置单例实例（主要用于测试）
        
        警告：此方法会删除当前实例，下次创建时将生成新实例
        
        Returns:
            bool: 是否成功重置
        """
        with SingletonMeta._lock:
            if cls in SingletonMeta._instances:
                instance = SingletonMeta._instances[cls]
                if hasattr(instance, 'cleanup') and callable(instance.cleanup):
                    try:
                        instance.cleanup()
                    except Exception as e:
                        warnings.warn(
                            f"清理 {cls.__name__} 实例时发生错误: {e}",
                            UserWarning
                        )
                
                del SingletonMeta._instances[cls]
                
            if cls in SingletonMeta._initialized:
                del SingletonMeta._initialized[cls]
                
            if cls in SingletonMeta._init_locks:
                del SingletonMeta._init_locks[cls]
            
            return True
    
    @classmethod
    def has_instance(cls) -> bool:
        """检查是否已存在实例
        
        Returns:
            bool: 如果已存在实例返回True
        """
        return cls in SingletonMeta._instances


def singleton(cls):
    """单例装饰器（非线程安全版本，用于简单场景）
    
    使用示例:
        @singleton
        class MyClass:
            pass
    
    注意：此装饰器不是线程安全的，如需线程安全请使用 SingletonMeta 或 Singleton 基类
    """
    instances: Dict[Type, Any] = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        elif args or kwargs:
            warnings.warn(
                f"{cls.__name__} 已初始化，参数被忽略",
                UserWarning,
                stacklevel=2
            )
        return instances[cls]
    
    get_instance.__name__ = cls.__name__
    get_instance.__doc__ = cls.__doc__
    get_instance.reset = lambda: instances.clear()
    
    return get_instance
