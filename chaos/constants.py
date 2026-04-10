"""
常量定义模块
集中管理项目中使用的常量
"""

POD_FILTER_RULES = {
    "upc-talker": ("get_upc_pods", "upc-talker"),
    "upc-nontalker": ("get_upc_pods", "upc-nontalker"),
    "upc-all": ("get_upc_pods", "upc-all"),
    "etcd-leader": ("get_etcd_pods", "etcd-leader"),
    "etcd-follower": ("get_etcd_pods", "etcd-follower"),
    "etcd-all": ("get_etcd_pods", "etcd-all"),
    "ddb-master": ("get_ddb_pods", "ddb-master"),
    "ddb-slave": ("get_ddb_pods", "ddb-slave"),
    "ddb-all": ("get_ddb_pods", "ddb-all"),
    "sdb-master": ("get_sdb_pods", "sdb-master"),
    "sdb-slave": ("get_sdb_pods", "sdb-slave"),
    "sdb-all": ("get_sdb_pods", "sdb-all"),
    "rc-leader": ("get_rc_pods", "rc-leader"),
    "rc-nonleader": ("get_rc_pods", "rc-nonleader"),
    "rc-all": ("get_rc_pods", "rc-all"),
    "upu-master": ("get_upu_pods", "upu-master"),
    "upu-slave": ("get_upu_pods", "upu-slave"),
    "upu-all": ("get_upu_pods", "upu-all"),
}

DEFAULT_NAMESPACE = "ns-dupf"

VALID_SIGNALS = [1, 9, 11, 15, 18, 19]

SIGNAL_NAMES = {
    1: "SIGHUP",
    9: "SIGKILL",
    11: "SIGSEGV",
    15: "SIGTERM",
    18: "SIGCONT",
    19: "SIGSTOP",
}

SSH_DEFAULT_TIMEOUT = 10
SSH_POOL_MAX_CONNECTIONS = 10
SSH_POOL_IDLE_TIMEOUT = 300
CASE_DEFAULT_TIMEOUT = 300
DEFAULT_TIMEOUT = 300
DEFAULT_LOG_DIR = "/var/ctin/ctc-upf/var/log/service-logs"
DEFAULT_TARGET_DIR = "/home/gsta"

FAULT_TYPES = {
    "network": "Network fault injector",
    "pod": "Pod fault injector",
    "computer": "Computer/Node fault injector",
    "process": "Process fault injector",
    "sw": "Switch fault injector",
}

CASE_TYPES = ["network", "pod", "computer", "process", "sw"]

SW_SSH_TIMEOUT = 30
SW_CHANNEL_WAIT = 0.5
SW_CMD_WAIT = 1.0
SW_READ_INTERVAL = 0.1
SW_BUFFER_SIZE = 4096
