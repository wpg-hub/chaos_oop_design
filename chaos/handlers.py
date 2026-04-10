"""
命令处理模块
提供各命令的处理逻辑
"""

from typing import Dict, List, Optional
from .config import ConfigManager
from .utils.logger import Logger
from .utils.remote import SSHExecutor, get_ssh_pool
from .utils.pod import PodManager


class PodActionHandler:
    """Pod 操作处理器"""
    
    def __init__(self, config_manager: ConfigManager, logger: Logger):
        self._config_manager = config_manager
        self._logger = logger
        self._pool = get_ssh_pool()
    
    def execute_list(self, pod_manager: PodManager, namespace: str) -> bool:
        pods = pod_manager.get_pods(namespace)
        self._logger.info(f"环境中的 Pod 数量：{len(pods)}")
        for pod_name, pod_ip in pods.items():
            print(f"{pod_name} - {pod_ip}")
        return bool(pods)
    
    def execute_ddb(self, pod_manager: PodManager, namespace: str) -> bool:
        ddb_pods = pod_manager.get_ddb_pods(namespace)
        self._logger.info(f"环境中的 DDB Pod：")
        for pod_name, pod_ip in ddb_pods.items():
            print(f"{pod_name} - {pod_ip}")
        
        masters = pod_manager.get_ddb_master(namespace)
        if masters:
            self._logger.info("DDB Masters:")
            for master in masters:
                self._logger.info(f"  {master.get('name')} - {master.get('ip')}")
        
        slaves = pod_manager.get_ddb_slaves(namespace)
        if slaves:
            self._logger.info("DDB Slaves:")
            for slave in slaves:
                self._logger.info(f"  {slave.get('name')} - {slave.get('ip')}")
        return True
    
    def execute_sdb(self, pod_manager: PodManager, namespace: str) -> bool:
        sdb_pods = pod_manager.get_sdb_pods(namespace)
        self._logger.info(f"环境中的 SDB Pod：")
        for pod_name, pod_ip in sdb_pods.items():
            print(f"{pod_name} - {pod_ip}")
        
        master = pod_manager.get_sdb_master(namespace)
        if master:
            self._logger.info(f"SDB Master: {master.get('name')} - {master.get('ip')}")
        
        slaves = pod_manager.get_sdb_slaves(namespace)
        if slaves:
            self._logger.info("SDB Slaves:")
            for slave in slaves:
                self._logger.info(f"  {slave.get('name')} - {slave.get('ip')}")
        return True
    
    def execute_etcd(self, pod_manager: PodManager, namespace: str) -> bool:
        etcd_pods = pod_manager.get_etcd_pods(namespace)
        self._logger.info(f"环境中的 etcd Pod：")
        for pod_name, pod_ip in etcd_pods.items():
            print(f"{pod_name} - {pod_ip}")
        
        leader = pod_manager.get_etcd_leader(namespace)
        if leader:
            self._logger.info(f"etcd Leader: {leader.get('name')} - {leader.get('ip')}")
        
        followers = pod_manager.get_etcd_followers(namespace)
        if followers:
            self._logger.info("etcd Followers:")
            for follower in followers:
                self._logger.info(f"  {follower.get('name')} - {follower.get('ip')}")
        return True
    
    def execute_upc(self, pod_manager: PodManager, namespace: str) -> bool:
        upc_pods = pod_manager.get_upc_pods(namespace)
        self._logger.info(f"环境中的 UPC Pod：")
        for pod_name, pod_ip in upc_pods.items():
            print(f"{pod_name} - {pod_ip}")
        
        talker = pod_manager.get_upc_talker(namespace)
        if talker:
            self._logger.info(f"UPC Talker: {talker.get('name')} - {talker.get('ip')}")
        return True
    
    def execute_upu(self, pod_manager: PodManager, namespace: str) -> bool:
        upu_pods = pod_manager.get_upu_pods(namespace)
        self._logger.info(f"环境中的 UPU Pod：")
        for pod_name, pod_ip in upu_pods.items():
            print(f"{pod_name} - {pod_ip}")
        return True
    
    def execute_rc(self, pod_manager: PodManager, namespace: str) -> bool:
        rc_pods = pod_manager.get_rc_pods(namespace)
        self._logger.info(f"环境中的 RC Pod：")
        for pod_name, pod_ip in rc_pods.items():
            print(f"{pod_name} - {pod_ip}")
        
        leader_name = pod_manager.get_rc_leader(namespace)
        if leader_name:
            self._logger.info(f"RC Leader: {leader_name}")
        
        non_leader_names = pod_manager.get_rc_non_leaders(namespace)
        if non_leader_names:
            self._logger.info("RC Non-Leaders:")
            for non_leader_name in non_leader_names:
                self._logger.info(f"  {non_leader_name}")
        return True
    
    def get_handler(self, action: str):
        handlers = {
            "list": self.execute_list,
            "ddb": self.execute_ddb,
            "sdb": self.execute_sdb,
            "etcd": self.execute_etcd,
            "upc": self.execute_upc,
            "upu": self.execute_upu,
            "rc": self.execute_rc,
        }
        return handlers.get(action)
    
    def get_ssh_executor(self, env) -> SSHExecutor:
        return self._pool.get_connection_from_env(env)


class ClearActionHandler:
    """清除操作处理器"""
    
    def __init__(self, config_manager: ConfigManager, logger: Logger):
        self._config_manager = config_manager
        self._logger = logger
        self._pool = get_ssh_pool()
    
    def clear_network_faults(self, env, device: str, namespace: str) -> Dict[str, int]:
        ssh_executor = self._pool.get_connection_from_env(env)
        
        if not ssh_executor.is_alive() and not ssh_executor.connect():
            self._logger.error(f"无法连接到环境 {env.name}")
            return {"success": 0, "failure": 0, "connected": False}
        
        try:
            pod_manager = PodManager(ssh_executor, self._logger, self._config_manager)
            pods = pod_manager.get_pods_by_nodename(namespace, env.nodename)
            
            if not pods:
                self._logger.info(f"环境 {env.name} 的节点 {env.nodename} 中没有找到 pod")
                return {"success": 0, "failure": 0, "connected": True}
            
            self._logger.info(f"找到 {len(pods)} 个 pod")
            
            from .clearer.network import NetworkFaultClearerFactory
            network_clearer = NetworkFaultClearerFactory.create_clearer(
                "pod", ssh_executor, self._logger, self._config_manager
            )
            
            success_count = 0
            failure_count = 0
            
            for pod_name in pods.keys():
                target = {"name": pod_name, "namespace": namespace}
                parameters = {"device": device, "namespace": namespace}
                
                if network_clearer.clear_fault(target, parameters):
                    success_count += 1
                else:
                    failure_count += 1
            
            return {"success": success_count, "failure": failure_count, "connected": True}
        except Exception as e:
            self._logger.error(f"清除网络故障时发生错误：{e}")
            return {"success": 0, "failure": 0, "connected": True}


class LogActionHandler:
    """日志操作处理器"""
    
    def __init__(self, config_manager: ConfigManager, logger: Logger):
        self._config_manager = config_manager
        self._logger = logger
    
    def collect_logs(self, date: str, log_dir: str, target_dir: str) -> bool:
        from .utils.log_collector import MultiNodeLogCollector
        
        collector = MultiNodeLogCollector(self._config_manager, self._logger)
        
        self._logger.info(f"开始收集日志，日期：{date}")
        self._logger.info(f"日志目录：{log_dir}")
        self._logger.info(f"目标目录：{target_dir}")
        
        return collector.collect_all_logs(
            date=date,
            log_base_dir=log_dir,
            target_dir=target_dir
        )
