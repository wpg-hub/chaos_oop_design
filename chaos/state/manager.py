"""
状态管理模块
负责故障状态的追踪和管理
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class FaultRecord:
    """故障记录"""
    fault_id: str
    case_name: str
    fault_type: str
    target: Dict
    parameters: Dict
    status: str  # running, recovered, failed
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None


class FaultRepository(ABC):
    """故障仓库抽象类"""
    
    @abstractmethod
    def save(self, record: FaultRecord) -> bool:
        """保存故障记录"""
        pass
    
    @abstractmethod
    def get(self, fault_id: str) -> Optional[FaultRecord]:
        """获取故障记录"""
        pass
    
    @abstractmethod
    def get_active_faults(self) -> List[FaultRecord]:
        """获取活跃的故障记录"""
        pass
    
    @abstractmethod
    def update_status(self, fault_id: str, status: str) -> bool:
        """更新故障状态"""
        pass


class FileFaultRepository(FaultRepository):
    """基于文件的故障仓库"""
    
    def __init__(self, data_file: str = "data/faults.json"):
        """初始化文件故障仓库
        
        Args:
            data_file: 数据文件路径
        """
        self.data_file = data_file
        self._ensure_directory()
    
    def _ensure_directory(self):
        """确保目录存在"""
        dir_path = os.path.dirname(self.data_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
    
    def _load_records(self) -> Dict[str, Dict]:
        """加载所有记录"""
        if not os.path.exists(self.data_file):
            return {}
        
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_records(self, records: Dict[str, Dict]) -> bool:
        """保存所有记录"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(records, f, indent=2, default=str)
            return True
        except Exception:
            return False
    
    def save(self, record: FaultRecord) -> bool:
        """保存故障记录"""
        records = self._load_records()
        records[record.fault_id] = asdict(record)
        return self._save_records(records)
    
    def get(self, fault_id: str) -> Optional[FaultRecord]:
        """获取故障记录"""
        records = self._load_records()
        record_dict = records.get(fault_id)
        if record_dict:
            return FaultRecord(**record_dict)
        return None
    
    def get_active_faults(self) -> List[FaultRecord]:
        """获取活跃的故障记录"""
        records = self._load_records()
        active_faults = []
        for record_dict in records.values():
            if record_dict.get("status") == "running":
                active_faults.append(FaultRecord(**record_dict))
        return active_faults
    
    def update_status(self, fault_id: str, status: str) -> bool:
        """更新故障状态"""
        records = self._load_records()
        if fault_id not in records:
            return False
        
        records[fault_id]["status"] = status
        if status != "running":
            records[fault_id]["end_time"] = datetime.now().isoformat()
        
        return self._save_records(records)


class StateManager:
    """状态管理器"""
    
    def __init__(self, repository: FaultRepository, logger):
        """初始化状态管理器
        
        Args:
            repository: 故障仓库
            logger: 日志记录器
        """
        self.repository = repository
        self.logger = logger
    
    def record_fault(self, case_name: str, fault_type: str, 
                     fault_id: str, target: Dict, parameters: Dict) -> bool:
        """记录故障
        
        Args:
            case_name: Case 名称
            fault_type: 故障类型
            fault_id: 故障 ID
            target: 目标信息
            parameters: 故障参数
            
        Returns:
            bool: 成功标志
        """
        record = FaultRecord(
            fault_id=fault_id,
            case_name=case_name,
            fault_type=fault_type,
            target=target,
            parameters=parameters,
            status="running",
            start_time=datetime.now()
        )
        
        success = self.repository.save(record)
        if success:
            self.logger.info(f"记录故障：{fault_id}")
        else:
            self.logger.error(f"记录故障失败：{fault_id}")
        
        return success
    
    def mark_recovered(self, fault_id: str) -> bool:
        """标记故障已恢复"""
        success = self.repository.update_status(fault_id, "recovered")
        if success:
            self.logger.info(f"标记故障已恢复：{fault_id}")
        else:
            self.logger.error(f"标记故障恢复失败：{fault_id}")
        return success
    
    def mark_failed(self, fault_id: str, error_message: str) -> bool:
        """标记故障失败"""
        # 先获取故障记录
        record = self.repository.get(fault_id)
        if not record:
            return False
        
        # 更新状态和错误信息
        record.status = "failed"
        record.error_message = error_message
        record.end_time = datetime.now()
        
        # 保存更新后的记录
        success = self.repository.save(record)
        if success:
            self.logger.info(f"标记故障失败：{fault_id}")
        else:
            self.logger.error(f"标记故障失败失败：{fault_id}")
        return success
    
    def get_active_faults(self) -> List[FaultRecord]:
        """获取活跃的故障"""
        return self.repository.get_active_faults()
    
    def get_fault_state(self, fault_id: str) -> Optional[Dict]:
        """获取故障状态
        
        Args:
            fault_id: 故障 ID
            
        Returns:
            Optional[Dict]: 故障状态字典，如果不存在则返回 None
        """
        record = self.repository.get(fault_id)
        if record:
            return {
                "fault_id": record.fault_id,
                "case_name": record.case_name,
                "fault_type": record.fault_type,
                "status": record.status,
                "start_time": record.start_time.isoformat() if record.start_time else None,
                "end_time": record.end_time.isoformat() if record.end_time else None,
                "error_message": record.error_message,
            }
        return None
    
    def clear_all(self) -> bool:
        """清除所有故障记录"""
        try:
            active_faults = self.get_active_faults()
            for fault in active_faults:
                self.repository.update_status(fault.fault_id, "recovered")
            self.logger.info(f"清除 {len(active_faults)} 个活跃故障")
            return True
        except Exception as e:
            self.logger.error(f"清除所有故障失败：{e}")
            return False
