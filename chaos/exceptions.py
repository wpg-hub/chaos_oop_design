"""
异常类模块
定义混沌工程相关的异常类
"""


class ChaosException(Exception):
    """混沌工程基础异常"""
    pass


class ConfigException(ChaosException):
    """配置异常"""
    pass


class ExecutionException(ChaosException):
    """执行异常"""
    pass


class FaultStateException(ChaosException):
    """故障状态异常"""
    pass


class FaultInjectionException(ExecutionException):
    """故障注入异常"""
    pass


class RecoveryException(ExecutionException):
    """恢复异常"""
    pass


class ResourceConflictException(ExecutionException):
    """资源冲突异常"""
    pass


class TimeoutException(ExecutionException):
    """超时异常"""
    pass
