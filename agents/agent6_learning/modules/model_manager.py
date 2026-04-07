"""
模型版本管理模块
负责模型版本控制、A/B测试支持、模型升级策略
"""
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from core.utils import setup_logging

logger = setup_logging("model_manager")


class ModelStage(Enum):
    """模型阶段"""
    EXPERIMENTAL = "experimental"  # 实验阶段
    STAGING = "staging"            # 预发布阶段
    PRODUCTION = "production"      # 生产阶段
    DEPRECATED = "deprecated"      # 废弃阶段


class ModelVersion:
    """模型版本信息"""
    
    def __init__(self, 
                 model_name: str,
                 version: str,
                 stage: ModelStage = ModelStage.EXPERIMENTAL,
                 metrics: Optional[Dict] = None,
                 created_at: Optional[str] = None,
                 metadata: Optional[Dict] = None):
        self.model_name = model_name
        self.version = version
        self.stage = stage
        self.metrics = metrics or {}
        self.created_at = created_at or datetime.now().isoformat()
        self.metadata = metadata or {}
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "stage": self.stage.value,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ModelVersion":
        return cls(
            model_name=data.get("model_name", ""),
            version=data.get("version", "v1.0"),
            stage=ModelStage(data.get("stage", "experimental")),
            metrics=data.get("metrics", {}),
            created_at=data.get("created_at"),
            metadata=data.get("metadata", {}),
        )


class ABTestGroup:
    """A/B测试分组"""
    
    def __init__(self, 
                 name: str,
                 model_version: str,
                 traffic_percentage: float = 0.5):
        self.name = name
        self.model_version = model_version
        self.traffic_percentage = traffic_percentage
        self.metrics = {
            "total_requests": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
        }
    
    def record_trade(self, pnl: float):
        """记录交易结果"""
        self.metrics["total_trades"] += 1
        if pnl > 0:
            self.metrics["winning_trades"] += 1
        self.metrics["total_pnl"] += pnl
    
    def get_win_rate(self) -> float:
        """获取胜率"""
        total = self.metrics["total_trades"]
        wins = self.metrics["winning_trades"]
        return wins / total if total > 0 else 0
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "model_version": self.model_version,
            "traffic_percentage": self.traffic_percentage,
            "metrics": self.metrics,
            "win_rate": self.get_win_rate(),
        }


class ModelVersionManager:
    """
    模型版本管理器
    
    功能：
    - 模型版本控制
    - A/B测试支持
    - 灰度发布
    - 模型回滚
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/model_versions.json"
        
        # 模型版本存储
        self.versions: Dict[str, List[ModelVersion]] = {
            "lightgbm": [],
            "informer": [],
            "ppo": [],
            "gnn": [],
        }
        
        # 当前生产版本
        self.current_versions: Dict[str, str] = {
            "lightgbm": "v1.0",
            "informer": "v1.0",
            "ppo": "v1.0",
            "gnn": "v1.0",
        }
        
        # A/B测试状态
        self.ab_tests: Dict[str, Dict] = {}  # model_name -> AB测试配置
        
        # 版本升级阈值
        self.promotion_threshold = {
            "accuracy_improvement": 0.02,  # 准确率提升2%
            "win_rate_improvement": 0.03,  # 胜率提升3%
            "pnl_improvement": 0.05,       # 盈亏提升5%
        }
        
        logger.info("Model version manager initialized")
    
    def load_current_versions(self):
        """加载当前版本配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                
                self.current_versions = config.get("current_versions", self.current_versions)
                
                # 加载版本历史
                for model_name, versions_data in config.get("versions", {}).items():
                    self.versions[model_name] = [
                        ModelVersion.from_dict(v) for v in versions_data
                    ]
                
                self.ab_tests = config.get("ab_tests", {})
                
                logger.info(f"Loaded model versions: {self.current_versions}")
        except Exception as e:
            logger.error(f"Failed to load versions: {e}")
    
    def save_versions(self):
        """保存版本配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            config = {
                "current_versions": self.current_versions,
                "versions": {
                    name: [v.to_dict() for v in versions]
                    for name, versions in self.versions.items()
                },
                "ab_tests": self.ab_tests,
                "updated_at": datetime.now().isoformat(),
            }
            
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved model versions to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save versions: {e}")
    
    def bump_version(self, model_name: str, 
                     metrics: Optional[Dict] = None) -> str:
        """
        创建新版本
        
        版本号格式：v{major}.{minor}
        - major: 重大更新
        - minor: 增量更新
        """
        current = self.current_versions.get(model_name, "v1.0")
        
        # 解析版本号
        try:
            parts = current.replace("v", "").split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            
            # 检查是否是重大更新
            if metrics and self._is_major_update(model_name, metrics):
                major += 1
                minor = 0
            else:
                minor += 1
            
            new_version = f"v{major}.{minor}"
        except:
            new_version = "v1.0"
        
        # 创建版本记录
        version_record = ModelVersion(
            model_name=model_name,
            version=new_version,
            stage=ModelStage.EXPERIMENTAL,
            metrics=metrics or {},
        )
        
        if model_name not in self.versions:
            self.versions[model_name] = []
        
        self.versions[model_name].append(version_record)
        
        logger.info(f"Created new version for {model_name}: {new_version}")
        
        return new_version
    
    def _is_major_update(self, model_name: str, metrics: Dict) -> bool:
        """检查是否是重大更新"""
        current_metrics = self._get_current_metrics(model_name)
        
        if not current_metrics:
            return False
        
        # 准确率提升超过5%
        acc_improvement = metrics.get("accuracy", 0) - current_metrics.get("accuracy", 0)
        if acc_improvement > 0.05:
            return True
        
        return False
    
    def _get_current_metrics(self, model_name: str) -> Dict:
        """获取当前版本的指标"""
        versions = self.versions.get(model_name, [])
        current_ver = self.current_versions.get(model_name, "v1.0")
        
        for v in versions:
            if v.version == current_ver:
                return v.metrics
        
        return {}
    
    def promote_version(self, model_name: str, version: str) -> bool:
        """
        提升版本到生产环境
        
        策略：
        1. 检查指标是否达标
        2. 如果是重大更新，先进行A/B测试
        3. 更新当前版本
        """
        try:
            # 查找版本记录
            version_record = None
            for v in self.versions.get(model_name, []):
                if v.version == version:
                    version_record = v
                    break
            
            if not version_record:
                logger.error(f"Version {version} not found for {model_name}")
                return False
            
            # 检查指标
            if not self._check_promotion_criteria(model_name, version_record.metrics):
                logger.warning(f"Version {version} does not meet promotion criteria")
                return False
            
            # 更新版本状态
            old_version = self.current_versions.get(model_name)
            self.current_versions[model_name] = version
            version_record.stage = ModelStage.PRODUCTION
            version_record.updated_at = datetime.now().isoformat()
            
            # 标记旧版本为废弃
            if old_version:
                for v in self.versions.get(model_name, []):
                    if v.version == old_version and v.stage == ModelStage.PRODUCTION:
                        v.stage = ModelStage.DEPRECATED
            
            logger.info(f"Promoted {model_name} from {old_version} to {version}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to promote version: {e}")
            return False
    
    def _check_promotion_criteria(self, model_name: str, metrics: Dict) -> bool:
        """检查版本提升标准"""
        current_metrics = self._get_current_metrics(model_name)
        
        if not current_metrics:
            # 首次发布
            return True
        
        # 检查各项改进
        accuracy_ok = (metrics.get("accuracy", 0) - current_metrics.get("accuracy", 0)) >= -0.01
        # 允许小幅下降，但不允许超过1%
        
        return accuracy_ok
    
    def rollback_version(self, model_name: str) -> bool:
        """
        回滚到上一个版本
        """
        try:
            versions = self.versions.get(model_name, [])
            current = self.current_versions.get(model_name)
            
            # 找到上一个生产版本
            previous = None
            for v in reversed(versions):
                if v.version != current and v.stage == ModelStage.DEPRECATED:
                    previous = v.version
                    break
            
            if not previous:
                logger.warning(f"No previous version found for {model_name}")
                return False
            
            # 执行回滚
            self.current_versions[model_name] = previous
            
            # 更新状态
            for v in versions:
                if v.version == previous:
                    v.stage = ModelStage.PRODUCTION
                elif v.version == current:
                    v.stage = ModelStage.DEPRECATED
            
            logger.info(f"Rolled back {model_name} from {current} to {previous}")
            
            return True
        
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def setup_ab_test(self, model_name: str, 
                     new_version: str,
                     traffic_split: List[float] = [0.5, 0.5]) -> Dict:
        """
        设置A/B测试
        
        Args:
            model_name: 模型名称
            new_version: 新版本
            traffic_split: 流量分配比例 [控制组, 实验组]
        """
        current_version = self.current_versions.get(model_name, "v1.0")
        
        test_config = {
            "model_name": model_name,
            "control_group": ABTestGroup(
                name="control",
                model_version=current_version,
                traffic_percentage=traffic_split[0],
            ),
            "treatment_group": ABTestGroup(
                name="treatment",
                model_version=new_version,
                traffic_percentage=traffic_split[1],
            ),
            "start_time": datetime.now().isoformat(),
            "status": "running",
        }
        
        self.ab_tests[model_name] = test_config
        
        logger.info(f"Set up A/B test for {model_name}: {current_version} vs {new_version}")
        
        return {
            "model_name": model_name,
            "control_version": current_version,
            "treatment_version": new_version,
            "traffic_split": traffic_split,
        }
    
    def get_ab_test_result(self, model_name: str) -> Optional[Dict]:
        """获取A/B测试结果"""
        test = self.ab_tests.get(model_name)
        if not test:
            return None
        
        control = test["control_group"]
        treatment = test["treatment_group"]
        
        # 计算显著性（简化实现）
        control_win_rate = control.get_win_rate()
        treatment_win_rate = treatment.get_win_rate()
        
        improvement = treatment_win_rate - control_win_rate
        
        return {
            "model_name": model_name,
            "control": control.to_dict(),
            "treatment": treatment.to_dict(),
            "improvement": improvement,
            "is_significant": abs(improvement) > 0.05,  # 5%差异认为显著
            "recommendation": "promote" if improvement > 0.03 else "keep" if improvement > -0.03 else "reject",
        }
    
    def assign_model_version(self, model_name: str, 
                            user_id: Optional[str] = None) -> str:
        """
        为请求分配模型版本
        
        如果有A/B测试，根据流量分配
        否则返回当前生产版本
        """
        test = self.ab_tests.get(model_name)
        
        if not test or test.get("status") != "running":
            return self.current_versions.get(model_name, "v1.0")
        
        # 简单的流量分配（基于user_id hash）
        import hashlib
        if user_id:
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        else:
            hash_val = random.randint(0, 10000)
        
        treatment_pct = test["treatment_group"].traffic_percentage
        
        if (hash_val % 10000) / 10000 < treatment_pct:
            return test["treatment_group"].model_version
        else:
            return test["control_group"].model_version
    
    def get_current_versions(self) -> Dict[str, str]:
        """获取当前生产版本"""
        return self.current_versions.copy()
    
    def get_version_history(self, model_name: str) -> List[Dict]:
        """获取版本历史"""
        versions = self.versions.get(model_name, [])
        return [v.to_dict() for v in versions]


import random  # 用于AB测试分配