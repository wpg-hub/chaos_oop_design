"""故障注入器注册表模块

提供故障注入器的注册和创建功能，支持装饰器注册和自定义工厂函数。
使用注册机制替代if-else判断，符合开闭原则。
"""

from typing import Dict, Type, Callable, Any, Optional, List, Set
import inspect


REQUIRED_INJECTOR_METHODS: Set[str] = {'inject', 'recover', 'get_fault_id'}


class FaultInjectorRegistry:
    """故障注入器注册表
    
    使用示例:
        # 方式1: 使用装饰器注册
        @FaultInjectorRegistry.register("network")
        class NetworkFaultInjector(FaultInjector):
            pass
        
        # 方式2: 函数调用注册
        FaultInjectorRegistry.register("pod", PodFaultInjector)
        
        # 方式3: 注册带自定义工厂的注入器
        def create_computer_injector(**deps):
            return ComputerFaultInjector(**deps)
        
        FaultInjectorRegistry.register("computer", ComputerFaultInjector, factory=create_computer_injector)
        
        # 创建注入器实例
        injector = FaultInjectorRegistry.create("network", remote_executor=executor, logger=logger)
    """
    
    _registry: Dict[str, Type] = {}
    _factories: Dict[str, Callable[..., Any]] = {}
    _validate_on_register: bool = True
    
    @classmethod
    def set_validation(cls, enabled: bool) -> None:
        """设置是否在注册时进行类型验证
        
        Args:
            enabled: 是否启用验证
        """
        cls._validate_on_register = enabled
    
    @classmethod
    def _validate_injector_class(cls, injector_cls: Type, fault_type: str) -> None:
        """验证注入器类是否实现了必要的方法
        
        Args:
            injector_cls: 注入器类
            fault_type: 故障类型
            
        Raises:
            TypeError: 如果注入器类缺少必要的方法
        """
        if not cls._validate_on_register:
            return
        
        missing_methods: List[str] = []
        
        for method_name in REQUIRED_INJECTOR_METHODS:
            if not hasattr(injector_cls, method_name):
                missing_methods.append(method_name)
            else:
                method = getattr(injector_cls, method_name)
                if not callable(method):
                    missing_methods.append(method_name)
        
        if missing_methods:
            raise TypeError(
                f"故障注入器 '{injector_cls.__name__}' 缺少必要的方法: {missing_methods}。"
                f"故障类型 '{fault_type}' 注册失败。"
            )
    
    @classmethod
    def _validate_factory(cls, factory: Callable[..., Any], fault_type: str) -> None:
        """验证工厂函数签名
        
        Args:
            factory: 工厂函数
            fault_type: 故障类型
            
        Raises:
            TypeError: 如果工厂函数签名不正确
        """
        if not cls._validate_on_register:
            return
        
        sig = inspect.signature(factory)
        params = list(sig.parameters.keys())
        
        if not any(p in params for p in ['dependencies', 'deps', 'kwargs']) and \
           not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            pass
    
    @classmethod
    def register(cls, fault_type: str, injector_class: Type = None, 
                 factory: Callable[..., Any] = None,
                 skip_validation: bool = False):
        """注册故障注入器
        
        Args:
            fault_type: 故障类型标识符
            injector_class: 故障注入器类（可选，用于装饰器模式）
            factory: 自定义工厂函数（可选）
            skip_validation: 是否跳过类型验证（默认 False）
            
        Returns:
            如果用作装饰器，返回装饰器函数；否则返回None
            
        Raises:
            TypeError: 如果注入器类未实现必要的方法
            ValueError: 如果故障类型已注册
        """
        if fault_type in cls._registry:
            import warnings
            warnings.warn(
                f"故障类型 '{fault_type}' 已注册，将被覆盖。"
                f"原注入器: {cls._registry[fault_type].__name__}",
                UserWarning
            )
        
        original_validation = cls._validate_on_register
        if skip_validation:
            cls._validate_on_register = False
        
        def decorator(injector_cls: Type) -> Type:
            cls._validate_injector_class(injector_cls, fault_type)
            
            cls._registry[fault_type] = injector_cls
            if factory:
                cls._validate_factory(factory, fault_type)
                cls._factories[fault_type] = factory
            
            return injector_cls
        
        try:
            if injector_class is None:
                return decorator
            else:
                cls._validate_injector_class(injector_class, fault_type)
                cls._registry[fault_type] = injector_class
                if factory:
                    cls._validate_factory(factory, fault_type)
                    cls._factories[fault_type] = factory
        finally:
            cls._validate_on_register = original_validation
    
    @classmethod
    def create(cls, fault_type: str, **dependencies) -> Any:
        """创建故障注入器实例
        
        Args:
            fault_type: 故障类型
            **dependencies: 依赖项（remote_executor, logger, config_manager等）
            
        Returns:
            故障注入器实例
            
        Raises:
            ValueError: 如果故障类型未注册
        """
        if fault_type not in cls._registry:
            registered_types = list(cls._registry.keys())
            if registered_types:
                available = ", ".join(sorted(registered_types))
                raise ValueError(
                    f"未知的故障类型: '{fault_type}'。\n"
                    f"可用的故障类型: [{available}]"
                )
            else:
                raise ValueError(
                    f"未知的故障类型: '{fault_type}'。\n"
                    f"当前没有注册任何故障类型。请先使用 @FaultInjectorRegistry.register() 注册注入器。"
                )
        
        if fault_type in cls._factories:
            try:
                return cls._factories[fault_type](**dependencies)
            except Exception as e:
                raise RuntimeError(
                    f"创建故障注入器失败 (类型: '{fault_type}')。\n"
                    f"工厂函数执行错误: {e}"
                ) from e
        
        injector_class = cls._registry[fault_type]
        try:
            return injector_class(**dependencies)
        except TypeError as e:
            sig = inspect.signature(injector_class.__init__)
            expected_params = list(sig.parameters.keys())[1:]
            provided_params = list(dependencies.keys())
            missing = set(expected_params) - set(provided_params)
            
            raise TypeError(
                f"创建故障注入器失败 (类型: '{fault_type}', 类: '{injector_class.__name__}')。\n"
                f"构造函数参数不匹配: {e}\n"
                f"期望参数: {expected_params}\n"
                f"提供参数: {provided_params}\n"
                f"缺失参数: {list(missing)}"
            ) from e
    
    @classmethod
    def get_registered_types(cls) -> List[str]:
        """获取所有已注册的类型"""
        return list(cls._registry.keys())
    
    @classmethod
    def is_registered(cls, fault_type: str) -> bool:
        """检查类型是否已注册"""
        return fault_type in cls._registry
    
    @classmethod
    def get_injector_class(cls, fault_type: str) -> Optional[Type]:
        """获取注入器类（不实例化）
        
        Args:
            fault_type: 故障类型
            
        Returns:
            注入器类，如果未注册则返回 None
        """
        return cls._registry.get(fault_type)
    
    @classmethod
    def unregister(cls, fault_type: str) -> bool:
        """注销故障类型（主要用于测试）
        
        Args:
            fault_type: 故障类型
            
        Returns:
            bool: 是否成功注销
        """
        if fault_type in cls._registry:
            del cls._registry[fault_type]
            if fault_type in cls._factories:
                del cls._factories[fault_type]
            return True
        return False
    
    @classmethod
    def clear(cls) -> None:
        """清空所有注册（主要用于测试）"""
        cls._registry.clear()
        cls._factories.clear()
    
    @classmethod
    def get_registry_info(cls) -> Dict[str, Any]:
        """获取注册表信息（用于调试）
        
        Returns:
            包含注册表详细信息的字典
        """
        return {
            "registered_types": cls.get_registered_types(),
            "type_count": len(cls._registry),
            "custom_factories": list(cls._factories.keys()),
            "validation_enabled": cls._validate_on_register,
        }
