"""
Pod 管理模块
负责获取和管理 Kubernetes Pod 信息，特别是特殊 Pod（DDB、SDB、etcd、UPC、UPU）
"""

import json
import base64
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..constants import DEFAULT_NAMESPACE


class PodManager:
    """Pod 管理器"""
    
    def __init__(self, remote_executor, logger, config_manager=None):
        """初始化 Pod 管理器
        
        Args:
            remote_executor: 远程执行器
            logger: 日志记录器
            config_manager: 配置管理器（用于获取 UPU 过滤列表和默认命名空间）
        """
        self.remote_executor = remote_executor
        self.logger = logger
        self.config_manager = config_manager
    
    def _get_namespace(self, namespace: Optional[str] = None) -> str:
        """获取命名空间
        
        Args:
            namespace: 指定的命名空间（可选）
            
        Returns:
            str: 命名空间（优先级：参数 > 配置文件 > 默认值）
        """
        if namespace:
            return namespace
        if self.config_manager:
            return self.config_manager.get_namespace()
        return DEFAULT_NAMESPACE
    
    def get_pods(self, namespace: str = None, labels: Optional[Dict] = None) -> Dict[str, str]:
        """获取 Pod 列表
        
        Args:
            namespace: 命名空间（可选，默认从配置文件获取）
            labels: 标签过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 Pod 列表，namespace: {namespace}")
        
        # 构建 kubectl 命令
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide'
        
        if labels:
            label_str = ','.join([f"{k}={v}" for k, v in labels.items()])
            kubectl_cmd += f' -l {label_str}'
        
        # 执行命令
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 Pod 列表失败")
            return {}
        
        # 解析输出
        pod_ip_map = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6 and not line.startswith('NAME'):
                pod_name = parts[0]
                pod_ip = parts[5]
                pod_ip_map[pod_name] = pod_ip
        
        self.logger.info(f"找到 {len(pod_ip_map)} 个 Pod")
        return pod_ip_map
    
    def get_pods_by_nodename(self, namespace: str = None, nodename: str = None) -> Dict[str, str]:
        """根据节点名称获取 Pod 列表
        
        Args:
            namespace: 命名空间（可选，默认从配置文件获取）
            nodename: 节点名称（可选）
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 Pod 列表，namespace: {namespace}, nodename: {nodename}")
        
        # 构建 kubectl 命令
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide'
        
        if nodename:
            kubectl_cmd += f' | grep {nodename}'
        
        # 执行命令
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 Pod 列表失败")
            return {}
        
        # 解析输出
        pod_ip_map = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6 and not line.startswith('NAME'):
                pod_name = parts[0]
                pod_ip = parts[5]
                pod_ip_map[pod_name] = pod_ip
        
        self.logger.info(f"找到 {len(pod_ip_map)} 个 Pod")
        return pod_ip_map
    
    def get_pod_node(self, pod_name: str, namespace: str = None) -> Optional[str]:
        """获取 Pod 所在的节点名称
        
        Args:
            pod_name: Pod 名称
            namespace: 命名空间（可选，默认从配置文件获取）
            
        Returns:
            Optional[str]: 节点名称
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 Pod {pod_name} 所在的节点，namespace: {namespace}")
        
        # 构建 kubectl 命令
        kubectl_cmd = f'kubectl get pod {pod_name} -n {namespace} -o wide'
        
        # 执行命令
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error(f"获取 Pod {pod_name} 信息失败")
            return None
        
        # 解析输出
        lines = output.strip().split('\n')
        if len(lines) < 2:
            self.logger.error(f"Pod {pod_name} 不存在")
            return None
        
        # 跳过标题行，解析 Pod 信息
        parts = lines[1].split()
        if len(parts) >= 7:
            node_name = parts[6]
            self.logger.info(f"Pod {pod_name} 运行在节点 {node_name}")
            return node_name
        
        self.logger.error(f"无法解析 Pod {pod_name} 的节点信息")
        return None
    
    def get_db_service_ip(self, namespace: str = None, port: int = 8082, 
                         service_name: Optional[str] = None) -> Optional[str]:
        """获取 DB Service IP
        
        Args:
            namespace: 命名空间（可选，默认从配置文件获取）
            port: 服务端口
            service_name: 服务名称
            
        Returns:
            Optional[str]: Service IP
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 DB Service IP，namespace: {namespace}，端口: {port}")
        
        if service_name:
            kubectl_cmd = f'kubectl get svc {service_name} -n {namespace} -o jsonpath="{{.spec.clusterIP}}"'
        else:
            kubectl_cmd = f'kubectl get svc -n {namespace} | grep {port} | grep -v hl | awk "{{print $4}}"'
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 Service IP 失败")
            return None
        
        service_ip = output.strip().split('\n')[0]
        
        if not service_ip or service_ip == "<none>":
            self.logger.error("未找到有效的 Service IP")
            return None
        
        self.logger.info(f"找到 Service IP: {service_ip}")
        return service_ip
    
    def get_ddb_pods(self, namespace: str = None, filter_type: str = None) -> Dict[str, str]:
        """获取 DDB Pod 列表
        
        Args:
            namespace: 命名空间
            filter_type: 过滤类型（ddb-master、ddb-slave、ddb-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        return self._get_db_pods("ddb", namespace, filter_type)
    
    def get_sdb_pods(self, namespace: str = None, filter_type: str = None) -> Dict[str, str]:
        """获取 SDB Pod 列表
        
        Args:
            namespace: 命名空间
            filter_type: 过滤类型（sdb-master、sdb-slave、sdb-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        return self._get_db_pods("sdb", namespace, filter_type)
    
    def _get_db_pods(self, db_type: str, namespace: str, filter_type: str = None) -> Dict[str, str]:
        """获取 DB Pod 列表（内部方法）
        
        Args:
            db_type: 数据库类型 (ddb/sdb)
            namespace: 命名空间
            filter_type: 过滤类型（ddb-master、ddb-slave、ddb-all、sdb-master、sdb-slave、sdb-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 {db_type.upper()} Pod 列表，namespace: {namespace}, filter_type: {filter_type}")
        
        # 如果有过滤类型，使用相应的过滤逻辑
        if filter_type:
            if db_type == "ddb":
                if filter_type == "ddb-master":
                    # 只返回 master Pod
                    masters = self.get_ddb_master(namespace)
                    return {master["name"]: master["ip"] for master in masters}
                elif filter_type == "ddb-slave":
                    # 只返回 slave Pod
                    slaves = self.get_ddb_slaves(namespace)
                    return {slave["name"]: slave["ip"] for slave in slaves}
                elif filter_type == "ddb-all":
                    # 返回所有 ddb Pod
                    pass  # 继续执行下面的默认逻辑
            elif db_type == "sdb":
                if filter_type == "sdb-master":
                    # 只返回 master Pod
                    master = self.get_sdb_master(namespace)
                    if master:
                        return {master["name"]: master["ip"]}
                    return {}
                elif filter_type == "sdb-slave":
                    # 只返回 slave Pod
                    slaves = self.get_sdb_slaves(namespace)
                    return {slave["name"]: slave["ip"] for slave in slaves}
                elif filter_type == "sdb-all":
                    # 返回所有 sdb Pod
                    pass  # 继续执行下面的默认逻辑
        
        # 默认：返回所有 DB Pod
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide | grep {db_type} | grep -v sentinel'
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error(f"获取 {db_type.upper()} Pod 列表失败")
            return {}
        
        pod_ip_map = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6:
                pod_name = parts[0]
                pod_ip = parts[5]
                pod_ip_map[pod_name] = pod_ip
        
        self.logger.info(f"找到 {len(pod_ip_map)} 个 {db_type.upper()} Pod（过滤类型：{filter_type or '默认'}）")
        return pod_ip_map
    
    def get_ddb_master(self, namespace: str = None, 
                      service_name: str = "dupf-db-operator-svc") -> List[Dict[str, str]]:
        """获取 DDB Master Pod 列表
        
        Args:
            namespace: 命名空间
            service_name: DDB Service 名称
            
        Returns:
            List[Dict[str, str]]: Master Pod 列表
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 DDB Master Pod 列表，namespace: {namespace}")
        
        # 获取 Service IP
        service_ip = self.get_db_service_ip(namespace, 8082, service_name)
        if not service_ip:
            self.logger.error("获取 DDB Service IP 失败")
            return []
        
        # 获取所有 DDB Pod
        pods = self.get_ddb_pods(namespace)
        if not pods:
            self.logger.error("获取 DDB Pod 列表失败")
            return []
        
        # 检查每个 Pod 的角色，找到所有 master
        masters = []
        for pod_name, pod_ip in pods.items():
            role = self._check_ddb_role(service_ip, pod_name, pod_ip)
            if role == "master":
                masters.append({"name": pod_name, "ip": pod_ip})
        
        self.logger.info(f"找到 {len(masters)} 个 DDB Master")
        return masters
    
    def get_ddb_slaves(self, namespace: str = None, 
                       service_name: str = "dupf-db-operator-svc") -> List[Dict[str, str]]:
        """获取 DDB Slave Pod 列表
        
        Args:
            namespace: 命名空间
            service_name: DDB Service 名称
            
        Returns:
            List[Dict[str, str]]: Slave Pod 列表
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 DDB Slave Pod 列表，namespace: {namespace}")
        
        # 获取 Service IP
        service_ip = self.get_db_service_ip(namespace, 8082, service_name)
        if not service_ip:
            self.logger.error("获取 DDB Service IP 失败")
            return []
        
        # 获取所有 DDB Pod
        pods = self.get_ddb_pods(namespace)
        if not pods:
            self.logger.error("获取 DDB Pod 列表失败")
            return []
        
        # 检查每个 Pod 的角色，找到所有 slave
        slaves = []
        for pod_name, pod_ip in pods.items():
            role = self._check_ddb_role(service_ip, pod_name, pod_ip)
            if role == "slave":
                slaves.append({"name": pod_name, "ip": pod_ip})
        
        self.logger.info(f"找到 {len(slaves)} 个 DDB Slave")
        return slaves
    
    def _check_ddb_role(self, service_ip: str, pod_name: str, pod_ip: str) -> str:
        """检查 DDB Pod 角色
        
        Args:
            service_ip: DDB Service IP
            pod_name: Pod 名称
            pod_ip: Pod IP
            
        Returns:
            str: 角色 (master/slave/unknown)
        """
        curl_cmd = f"curl -X GET 'http://{service_ip}:8082/api/ddb/node/info?type=role&fields=role&node={pod_name}' 2>&1"
        
        success, output = self.remote_executor.execute(curl_cmd)
        
        if not success or not output:
            return "unknown"
        
        # 尝试解析 JSON
        try:
            # 提取 JSON 部分
            json_start = output.find('[')
            json_end = output.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = output[json_start:json_end]
                data = json.loads(json_str)
                
                # 查找匹配的节点
                for node_info in data:
                    if 'addr' in node_info:
                        node_ip = node_info['addr'].split(':')[0]
                        if node_ip == pod_ip:
                            return node_info.get('role', 'unknown')
        except Exception as e:
            self.logger.error(f"解析 DDB 角色失败: {e}")
        
        # 降级到字符串匹配
        if '"role":"master"' in output or '"role": "master"' in output:
            return "master"
        elif '"role":"slave"' in output or '"role": "slave"' in output:
            return "slave"
        else:
            return "unknown"
    
    def get_sdb_master(self, namespace: str = None) -> Optional[Dict[str, str]]:
        """获取 SDB Master Pod
        
        Args:
            namespace: 命名空间
            
        Returns:
            Optional[Dict[str, str]]: Master Pod 信息
        """
        namespace = self._get_namespace(namespace)
        pods = self.get_sdb_pods(namespace)
        if not pods:
            return None
        
        # 检查每个 Pod 的角色
        for pod_name, pod_ip in pods.items():
            role = self._check_sdb_role(pod_name, namespace)
            if role == "master":
                return {"name": pod_name, "ip": pod_ip}
        
        return None
    
    def get_sdb_slaves(self, namespace: str = None) -> List[Dict[str, str]]:
        """获取 SDB Slave Pod 列表
        
        Args:
            namespace: 命名空间
            
        Returns:
            List[Dict[str, str]]: Slave Pod 列表
        """
        namespace = self._get_namespace(namespace)
        pods = self.get_sdb_pods(namespace)
        if not pods:
            return []
        
        # 检查每个 Pod 的角色
        slaves = []
        for pod_name, pod_ip in pods.items():
            role = self._check_sdb_role(pod_name, namespace)
            if role == "slave":
                slaves.append({"name": pod_name, "ip": pod_ip})
        
        return slaves
    
    def _check_sdb_role(self, pod_name: str, namespace: str) -> str:
        """检查 SDB Pod 角色
        
        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            
        Returns:
            str: 角色 (master/slave/unknown)
        """
        # 获取 SDB 密码
        secret_cmd = f'kubectl get secret dupf-sdb-default-user-secret -n {namespace} -o jsonpath="{{.data.password}}"'
        success, password_b64 = self.remote_executor.execute(secret_cmd)
        
        if not success or not password_b64:
            self.logger.error("获取 SDB 密码失败")
            return "unknown"
        
        try:
            password = base64.b64decode(password_b64.strip()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"解码 SDB 密码失败: {e}")
            return "unknown"
        
        # 使用 redis-cli 获取角色信息
        redis_cmd = f"kubectl exec -i {pod_name} -n {namespace} -- redis-cli -p 17369 -a '{password}' info replication 2>&1"
        success, output = self.remote_executor.execute(redis_cmd)
        
        if not success or not output:
            return "unknown"
        
        # 解析角色信息
        for line in output.split('\n'):
            if line.startswith('role:'):
                return line.split(':')[1].strip()
        
        return "unknown"
    
    def get_etcd_pods(self, namespace: str = None, filter_type: str = None) -> Dict[str, str]:
        """获取 etcd Pod 列表
        
        Args:
            namespace: 命名空间
            filter_type: 过滤类型（etcd-leader、etcd-follower、etcd-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 etcd Pod 列表，namespace: {namespace}, filter_type: {filter_type}")
        
        # 如果有过滤类型，使用相应的过滤逻辑
        if filter_type:
            if filter_type == "etcd-leader":
                # 只返回 leader Pod
                leader = self.get_etcd_leader(namespace)
                if leader:
                    return {leader["name"]: leader["ip"]}
                return {}
            elif filter_type == "etcd-follower":
                # 只返回 follower Pod
                followers = self.get_etcd_followers(namespace)
                return {follower["name"]: follower["ip"] for follower in followers}
            elif filter_type == "etcd-all":
                # 返回所有 etcd Pod
                pass  # 继续执行下面的默认逻辑
        
        # 默认：返回所有 etcd Pod
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide | grep etcd'
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 etcd Pod 列表失败")
            return {}
        
        pod_ip_map = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6:
                pod_name = parts[0]
                pod_ip = parts[5]
                pod_ip_map[pod_name] = pod_ip
        
        self.logger.info(f"找到 {len(pod_ip_map)} 个 etcd Pod（过滤类型：{filter_type or '默认'}）")
        return pod_ip_map
    
    def get_etcd_leader(self, namespace: str = None) -> Optional[Dict[str, str]]:
        """获取 etcd Leader Pod
        
        Args:
            namespace: 命名空间
            
        Returns:
            Optional[Dict[str, str]]: Leader Pod 信息
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 etcd Leader Pod，namespace: {namespace}")
        
        # 获取 registry-center 服务的 IP 地址
        get_ip_command = "kubectl get svc -A | grep registry-center | grep -v headless | awk '{print $4}'"
        success, ip_output = self.remote_executor.execute(get_ip_command)
        
        if not success or not ip_output:
            self.logger.error("获取 registry-center IP 失败")
            return None
        
        registry_center_ip = ip_output.strip()
        
        if not registry_center_ip:
            self.logger.error("registry-center IP 为空")
            return None
        
        self.logger.info(f"获取到 registry-center IP: {registry_center_ip}")
        
        # 获取 etcd leader
        leader_command = f"curl -X GET http://{registry_center_ip}:8158/api/paas/v1/maintenance/db/health | jq '.Endpoints[] | select(.Leader == 1) | .Endpoint'"
        success, leader_output = self.remote_executor.execute(leader_command)
        
        if not success or not leader_output:
            self.logger.error("获取 etcd leader 失败")
            return None
        
        leader_endpoint = leader_output.strip()
        
        if not leader_endpoint:
            self.logger.error("etcd leader endpoint 为空")
            return None
        
        # 从 "dupf-etcd-1.dupf-etcd-headless:2379" 中提取 "dupf-etcd-1"
        leader_pod_name = leader_endpoint.replace('"', '').split('.')[0]
        
        # 获取 leader pod 的 IP
        pods = self.get_etcd_pods(namespace)
        leader_pod_ip = pods.get(leader_pod_name)
        
        if leader_pod_name and leader_pod_ip:
            self.logger.info(f"找到 etcd Leader: {leader_pod_name} - {leader_pod_ip}")
            return {"name": leader_pod_name, "ip": leader_pod_ip}
        
        return None
    
    def get_etcd_followers(self, namespace: str = None) -> List[Dict[str, str]]:
        """获取 etcd Follower Pod 列表
        
        Args:
            namespace: 命名空间
            
        Returns:
            List[Dict[str, str]]: Follower Pod 信息列表
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 etcd Follower Pod 列表，namespace: {namespace}")
        
        # 获取 registry-center 服务的 IP 地址
        get_ip_command = "kubectl get svc -A | grep registry-center | grep -v headless | awk '{print $4}'"
        success, ip_output = self.remote_executor.execute(get_ip_command)
        
        if not success or not ip_output:
            self.logger.error("获取 registry-center IP 失败")
            return []
        
        registry_center_ip = ip_output.strip()
        
        if not registry_center_ip:
            self.logger.error("registry-center IP 为空")
            return []
        
        self.logger.info(f"获取到 registry-center IP: {registry_center_ip}")
        
        # 获取 etcd followers
        follower_command = f"curl -X GET http://{registry_center_ip}:8158/api/paas/v1/maintenance/db/health | jq '.Endpoints[] | select(.Leader == 0) | .Endpoint'"
        success, follower_output = self.remote_executor.execute(follower_command)
        
        if not success or not follower_output:
            self.logger.error("获取 etcd followers 失败")
            return []
        
        follower_endpoints = [follower.strip() for follower in follower_output.strip().split('\n') if follower.strip()]
        
        # 提取 follower pod 名称和 IP
        pods = self.get_etcd_pods(namespace)
        follower_pods = []
        
        for endpoint in follower_endpoints:
            if endpoint:
                # 从 "dupf-etcd-0.dupf-etcd-headless:2379" 中提取 "dupf-etcd-0"
                pod_name = endpoint.replace('"', '').split('.')[0]
                pod_ip = pods.get(pod_name)
                
                if pod_name and pod_ip:
                    follower_pods.append({"name": pod_name, "ip": pod_ip})
        
        self.logger.info(f"找到 {len(follower_pods)} 个 etcd Follower")
        return follower_pods
    
    def _check_upc_talker(self, pod_ip: str) -> bool:
        """检查指定 IP 的 Pod 是否为 talker 角色
        
        Args:
            pod_ip: Pod 的 IP 地址
            
        Returns:
            bool: 是否为 talker 角色
        """
        curl_cmd = f"curl -X GET -m 5 http://{pod_ip}:3333/show/rsc_info 2>&1"
        
        try:
            success, output = self.remote_executor.execute(curl_cmd)
            if success and output:
                return "talker role" in output
        except Exception as e:
            self.logger.debug(f"检查 {pod_ip} 是否为 talker 时出错: {e}")
        
        return False
    
    def get_upc_pods(self, namespace: str = None, filter_type: str = None) -> Dict[str, str]:
        """获取 UPC Pod 列表
        
        Args:
            namespace: 命名空间
            filter_type: 过滤类型（upc-talker、upc-nontalker、upc-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 UPC Pod 列表，namespace: {namespace}, filter_type: {filter_type}")
        
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide | grep upc'
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 UPC Pod 列表失败")
            return {}
        
        all_pods = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6:
                pod_name = parts[0]
                pod_ip = parts[5]
                if 'upc-' in pod_name:
                    all_pods[pod_name] = pod_ip
        
        pod_ip_map = {}
        
        if filter_type == "upc-talker":
            talker_pods = {}
            
            for pod_name, pod_ip in all_pods.items():
                if 'upc-lb' in pod_name:
                    continue
                elif self._check_upc_talker(pod_ip):
                    talker_pods[pod_name] = pod_ip
            
            pod_ip_map = talker_pods
            
        elif filter_type == "upc-nontalker":
            nontalker_pods = {}
            
            for pod_name, pod_ip in all_pods.items():
                if 'upc-lb' in pod_name:
                    continue
                elif not self._check_upc_talker(pod_ip):
                    nontalker_pods[pod_name] = pod_ip
            
            pod_ip_map = nontalker_pods
            
        elif filter_type == "upc-all":
            pod_ip_map = all_pods
            
        else:
            for pod_name, pod_ip in all_pods.items():
                if 'upc-lb' not in pod_name:
                    pod_ip_map[pod_name] = pod_ip
        
        return pod_ip_map
    
    def get_upc_talker(self, namespace: str = None) -> Optional[Dict[str, str]]:
        """获取 UPC Talker Pod
        
        Args:
            namespace: 命名空间
            
        Returns:
            Optional[Dict[str, str]]: Talker Pod 信息
        """
        namespace = self._get_namespace(namespace)
        pods = self.get_upc_pods(namespace, filter_type="upc-talker")
        if pods:
            pod_name, pod_ip = next(iter(pods.items()))
            return {"name": pod_name, "ip": pod_ip}
        return None
    
    def get_upu_pods(self, namespace: str = None, filter_type: str = None) -> Dict[str, str]:
        """获取 UPU Pod 列表
        
        Args:
            namespace: 命名空间
            filter_type: 过滤类型（upu-master、upu-slave、upu-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 UPU Pod 列表，namespace: {namespace}, filter_type: {filter_type}")
        
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide | grep upu'
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 UPU Pod 列表失败")
            return {}
        
        # 获取配置中的 UPU 过滤列表
        upu_master_filters = []
        upu_slave_filters = []
        
        if self.config_manager:
            config = self.config_manager.config if hasattr(self.config_manager, 'config') else {}
            upu_master_filters = config.get("UPU_POD_FILTERS", [])
            upu_slave_filters = config.get("UPU_POD_FILTERS_SLAVE", [])
        
        pod_ip_map = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6:
                pod_name = parts[0]
                pod_ip = parts[5]
                
                # 根据过滤类型进行过滤
                if filter_type:
                    if filter_type == "upu-master":
                        # 只返回 master Pod（根据配置中的 UPU_POD_FILTERS 过滤）
                        if upu_master_filters:
                            for master_filter in upu_master_filters:
                                if master_filter in pod_name:
                                    pod_ip_map[pod_name] = pod_ip
                                    break
                        else:
                            # 如果没有配置过滤列表，返回所有 UPU Pod
                            pod_ip_map[pod_name] = pod_ip
                    elif filter_type == "upu-slave":
                        # 只返回 slave Pod（根据配置中的 UPU_POD_FILTERS_SLAVE 过滤）
                        if upu_slave_filters:
                            for slave_filter in upu_slave_filters:
                                if slave_filter in pod_name:
                                    pod_ip_map[pod_name] = pod_ip
                                    break
                        else:
                            # 如果没有配置过滤列表，返回空
                            self.logger.warning("未配置 UPU_POD_FILTERS_SLAVE，无法过滤 slave Pod")
                    elif filter_type == "upu-all":
                        # 返回所有 UPU Pod（包括 master 和 slave）
                        pod_ip_map[pod_name] = pod_ip
                else:
                    # 默认：返回所有 UPU Pod
                    pod_ip_map[pod_name] = pod_ip
        
        self.logger.info(f"找到 {len(pod_ip_map)} 个 UPU Pod（过滤类型：{filter_type or '默认（全部）'}）")
        return pod_ip_map
    
    def _get_rc_service_ip(self, namespace: str = None) -> Optional[str]:
        """获取 RC Service IP 地址
        
        Args:
            namespace: 命名空间
            
        Returns:
            Optional[str]: RC Service IP 地址
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 RC Service IP，namespace: {namespace}")
        
        kubectl_cmd = f'kubectl get svc -n {namespace} | grep registry-center | grep -v headless | grep -v NAME | awk \'{{print $3}}\''
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 RC Service IP 失败")
            return None
        
        # 清理输出，只保留 IP 地址
        service_ip = output.strip()
        # 移除可能的空行和多余信息
        lines = [line for line in service_ip.split('\n') if line.strip()]
        if lines:
            service_ip = lines[0].strip()
        
        if not service_ip or service_ip == "<none>":
            self.logger.error("获取 RC Service IP 失败：IP 为空")
            return None
            
        self.logger.info(f"找到 RC Service IP: {service_ip}")
        return service_ip
    
    def _get_rc_cluster_info(self, service_ip: str) -> Optional[dict]:
        """获取 RC 集群信息
        
        Args:
            service_ip: RC Service IP 地址
            
        Returns:
            Optional[dict]: RC 集群信息
        """
        self.logger.info(f"获取 RC 集群信息，service_ip: {service_ip}")
        
        curl_cmd = f"curl -X GET http://{service_ip}:8158/api/paas/v1/maintenance/rc/cluster -H 'Content-Type: application/json' -k 2>&1"
        
        success, output = self.remote_executor.execute(curl_cmd)
        
        if not success or not output:
            self.logger.error("获取 RC 集群信息失败")
            return None
        
        # 清理输出，移除可能的错误信息
        output = output.strip()
        
        # 尝试提取 JSON 部分
        try:
            data = json.loads(output)
            rc_cluster_info = data.get("rc_cluster_info", {})
            return rc_cluster_info
        except json.JSONDecodeError as e:
            self.logger.error(f"解析 RC 集群信息 JSON 失败: {e}")
            self.logger.error(f"原始输出: {output[:500]}")
            
            # 尝试从输出中提取 JSON
            try:
                json_start = output.find('{')
                json_end = output.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    data = json.loads(json_str)
                    rc_cluster_info = data.get("rc_cluster_info", {})
                    return rc_cluster_info
            except Exception as e2:
                self.logger.error(f"尝试提取 JSON 也失败: {e2}")
            
            return None
    
    def _extract_rc_leader_name(self, rc_cluster_info: dict) -> Optional[str]:
        """从 RC 集群信息中提取 leader 名称
        
        Args:
            rc_cluster_info: RC 集群信息
            
        Returns:
            Optional[str]: Leader Pod 名称
        """
        if not rc_cluster_info:
            return None
            
        # 检查是否有 leader 字段
        if "leader" in rc_cluster_info:
            leader = rc_cluster_info["leader"]
            if isinstance(leader, dict):
                if "pod" in leader:
                    return leader["pod"]
                elif "pod_name" in leader:
                    return leader["pod_name"]
        
        # 检查是否有 nodes 字段
        if "nodes" in rc_cluster_info:
            for node in rc_cluster_info["nodes"]:
                if isinstance(node, dict) and node.get("role") == "Leader":
                    if "pod" in node:
                        return node["pod"]
                    elif "pod_name" in node:
                        return node["pod_name"]
        
        # 检查是否有 rc_info 字段
        if "rc_info" in rc_cluster_info:
            for item in rc_cluster_info["rc_info"]:
                if isinstance(item, dict) and item.get("role") == "Leader":
                    if "pod" in item:
                        return item["pod"]
                    elif "pod_name" in item:
                        return item["pod_name"]
        
        return None
    
    def _extract_rc_non_leader_names(self, rc_cluster_info: dict) -> List[str]:
        """从 RC 集群信息中提取 non-leader 名称
        
        Args:
            rc_cluster_info: RC 集群信息
            
        Returns:
            List[str]: Non-leader Pod 名称列表
        """
        if not rc_cluster_info:
            return []
            
        non_leader_names = []
        
        # 检查是否有 nodes 字段
        if "nodes" in rc_cluster_info:
            for node in rc_cluster_info["nodes"]:
                if isinstance(node, dict) and node.get("role") != "Leader":
                    if "pod" in node:
                        non_leader_names.append(node["pod"])
                    elif "pod_name" in node:
                        non_leader_names.append(node["pod_name"])
        
        # 检查是否有 rc_info 字段
        if "rc_info" in rc_cluster_info:
            for item in rc_cluster_info["rc_info"]:
                if isinstance(item, dict) and item.get("role") != "Leader":
                    if "pod" in item:
                        non_leader_names.append(item["pod"])
                    elif "pod_name" in item:
                        non_leader_names.append(item["pod_name"])
        
        return non_leader_names
    
    def get_rc_pods(self, namespace: str = None, filter_type: str = None) -> Dict[str, str]:
        """获取 RC Pod 列表
        
        Args:
            namespace: 命名空间
            filter_type: 过滤类型（rc-leader、rc-nonleader、rc-all），默认 None 表示不过滤
            
        Returns:
            Dict[str, str]: Pod 名称到 IP 的映射
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 RC Pod 列表，namespace: {namespace}, filter_type: {filter_type}")
        
        # 获取所有 RC Pod（Registry Center）
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide | grep registry-center'
        
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 RC Pod 列表失败")
            return {}
        
        pod_ip_map = {}
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6:
                pod_name = parts[0]
                pod_ip = parts[5]
                pod_ip_map[pod_name] = pod_ip
        
        # 如果有过滤类型，进行过滤
        if filter_type:
            if filter_type == "rc-leader":
                # 只返回 leader Pod
                leader_name = self.get_rc_leader(namespace)
                if leader_name and leader_name in pod_ip_map:
                    return {leader_name: pod_ip_map[leader_name]}
                return {}
            elif filter_type == "rc-nonleader":
                # 只返回 non-leader Pod
                non_leader_names = self.get_rc_non_leaders(namespace)
                return {name: pod_ip_map[name] for name in non_leader_names if name in pod_ip_map}
            elif filter_type == "rc-all":
                # 返回所有 RC Pod
                pass
        
        self.logger.info(f"找到 {len(pod_ip_map)} 个 RC Pod（过滤类型：{filter_type or '默认'}）")
        return pod_ip_map
    
    def get_rc_leader(self, namespace: str = None) -> Optional[str]:
        """获取 RC Leader Pod 名称
        
        Args:
            namespace: 命名空间
            
        Returns:
            Optional[str]: Leader Pod 名称
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 RC Leader Pod，namespace: {namespace}")
        
        # 获取 RC Service IP
        service_ip = self._get_rc_service_ip(namespace)
        if not service_ip:
            self.logger.error("获取 RC Service IP 失败")
            return None
        
        # 获取 RC 集群信息
        rc_cluster_info = self._get_rc_cluster_info(service_ip)
        if not rc_cluster_info:
            self.logger.error("获取 RC 集群信息失败")
            return None
        
        # 提取 leader 名称
        leader_name = self._extract_rc_leader_name(rc_cluster_info)
        if leader_name:
            self.logger.info(f"找到 RC Leader: {leader_name}")
        else:
            self.logger.warning("未找到 RC Leader")
        
        return leader_name
    
    def get_rc_non_leaders(self, namespace: str = None) -> List[str]:
        """获取 RC Non-Leader Pod 名称列表
        
        Args:
            namespace: 命名空间
            
        Returns:
            List[str]: Non-Leader Pod 名称列表
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"获取 RC Non-Leader Pod 列表，namespace: {namespace}")
        
        # 获取 RC Service IP
        service_ip = self._get_rc_service_ip(namespace)
        if not service_ip:
            self.logger.error("获取 RC Service IP 失败")
            return []
        
        # 获取 RC 集群信息
        rc_cluster_info = self._get_rc_cluster_info(service_ip)
        if not rc_cluster_info:
            self.logger.error("获取 RC 集群信息失败")
            return []
        
        # 提取 non-leader 名称
        non_leader_names = self._extract_rc_non_leader_names(rc_cluster_info)
        self.logger.info(f"找到 {len(non_leader_names)} 个 RC Non-Leader")
        
        return non_leader_names
    
    def get_special_pod(self, pod_type: str, role: str, namespace: str = None) -> Optional[Dict[str, str]]:
        """获取特殊 Pod
        
        Args:
            pod_type: Pod 类型 (ddb/sdb/etcd/upc/upu)
            role: 角色 (master/slave/leader/talker/non-talker)
            namespace: 命名空间
            
        Returns:
            Optional[Dict[str, str]]: Pod 信息
        """
        namespace = self._get_namespace(namespace)
        if pod_type == "ddb":
            if role == "master":
                return self.get_ddb_master(namespace)
            elif role == "slave":
                slaves = self.get_ddb_slaves(namespace)
                return slaves[0] if slaves else None
        elif pod_type == "sdb":
            if role == "master":
                return self.get_sdb_master(namespace)
            elif role == "slave":
                slaves = self.get_sdb_slaves(namespace)
                return slaves[0] if slaves else None
        elif pod_type == "etcd":
            if role == "leader":
                return self.get_etcd_leader(namespace)
        elif pod_type == "upc":
            if role == "talker":
                return self.get_upc_talker(namespace)
        
        return None
    
    def get_pod_by_name_pattern(self, name_pattern: str, namespace: str = None) -> Optional[Dict[str, str]]:
        """根据名称匹配规则获取 Pod
        
        Args:
            name_pattern: Pod 名称匹配规则（支持通配符）
            namespace: 命名空间
            
        Returns:
            Optional[Dict[str, str]]: Pod 信息
        """
        namespace = self._get_namespace(namespace)
        pods = self.get_pods_by_name_pattern(name_pattern, namespace)
        return pods[0] if pods else None
    
    def get_pods_by_name_pattern(self, name_pattern: str, namespace: str = None) -> List[Dict[str, str]]:
        """根据名称匹配规则获取所有匹配的 Pod
        
        Args:
            name_pattern: Pod 名称匹配规则（支持通配符）
            namespace: 命名空间
            
        Returns:
            List[Dict[str, str]]: Pod 信息列表
        """
        namespace = self._get_namespace(namespace)
        self.logger.info(f"根据名称匹配规则获取 Pod，pattern: {name_pattern}, namespace: {namespace}")
        
        # 构建 kubectl 命令
        kubectl_cmd = f'kubectl get pod -n {namespace} -o wide'
        
        # 执行命令
        success, output = self.remote_executor.execute(kubectl_cmd)
        
        if not success or not output:
            self.logger.error("获取 Pod 列表失败")
            return []
        
        # 解析输出并匹配
        import fnmatch
        matched_pods = []
        
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 6 and not line.startswith('NAME'):
                pod_name = parts[0]
                pod_ip = parts[5]
                
                # 方法1：使用 fnmatch 进行通配符匹配
                if fnmatch.fnmatch(pod_name, name_pattern):
                    self.logger.info(f"找到匹配的 Pod: {pod_name}")
                    matched_pods.append({"name": pod_name, "ip": pod_ip})
                    continue
                
                # 方法2：如果是精确匹配但没找到，尝试匹配前缀（处理 deployment 后缀）
                # 例如：dupf-upu-dupf01-1-688fc66ddb-bpd5h 应该匹配 dupf-upu-dupf01-1
                pod_name_parts = pod_name.split('-')
                if len(pod_name_parts) > 2:
                    # 尝试移除最后两个部分（deployment 后缀）
                    potential_match = '-'.join(pod_name_parts[0:-2])
                    if name_pattern == potential_match:
                        self.logger.info(f"找到前缀匹配的 Pod: {pod_name}")
                        matched_pods.append({"name": pod_name, "ip": pod_ip})
                        continue
                    
                    # 尝试移除最后三个部分（更复杂的 deployment 后缀）
                    if len(pod_name_parts) > 3:
                        potential_match = '-'.join(pod_name_parts[0:-3])
                        if name_pattern == potential_match:
                            self.logger.info(f"找到前缀匹配的 Pod: {pod_name}")
                            matched_pods.append({"name": pod_name, "ip": pod_ip})
                            continue
                
                # 方法3：尝试匹配中间部分
                if name_pattern in pod_name:
                    self.logger.info(f"找到包含匹配的 Pod: {pod_name}")
                    matched_pods.append({"name": pod_name, "ip": pod_ip})
                    continue
        
        if not matched_pods:
            self.logger.warning(f"未找到匹配 {name_pattern} 的 Pod")
        else:
            self.logger.info(f"找到 {len(matched_pods)} 个匹配的 Pod")
        
        return matched_pods
