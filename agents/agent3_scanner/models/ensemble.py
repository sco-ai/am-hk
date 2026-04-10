"""
模型融合集成 - Ensemble
融合LightGBM、XGBoost和RL模型的输出
"""
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketRegime(Enum):
    """市场状态"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass
class EnsemblePrediction:
    """集成预测结果"""
    final_score: float  # 0-1
    final_direction: str  # "buy", "sell", "hold"
    confidence: float
    position_size: float  # 建议仓位 (0-1)
    
    # 各模型贡献
    lightgbm_score: float
    xgboost_score: float
    xgboost_proba: Dict[str, float]
    rl_action: str
    rl_target_position: float
    
    # 融合信息
    model_weights: Dict[str, float]
    agreement_score: float  # 模型一致度
    
    # 元数据
    timestamp: datetime
    reasoning: str


class ModelEnsemble:
    """
    模型融合器
    
    动态调整各模型权重,根据市场环境选择最优融合策略
    """
    
    def __init__(self):
        self.version = "v3.0-ensemble"
        self.last_update = datetime.now()
        
        # 基础权重
        self.base_weights = {
            "lightgbm": 0.45,
            "xgboost": 0.35,
            "rl_position": 0.20,
        }
        
        # 历史表现 (用于在线学习)
        self.model_performance = {
            "lightgbm": {"correct": 0, "total": 0},
            "xgboost": {"correct": 0, "total": 0},
        }
        
        # 预测历史
        self.prediction_history: List[Dict] = []
    
    def predict(
        self,
        lightgbm_pred: Any,
        xgboost_pred: Any,
        rl_decision: Any,
        market_regime: str = "normal"
    ) -> EnsemblePrediction:
        """
        融合各模型预测
        """
        timestamp = datetime.now()
        
        # 根据市场环境调整权重
        weights = self._adjust_weights_for_regime(self.base_weights.copy(), market_regime)
        
        # 提取分数
        lgb_score = lightgbm_pred.score
        xgb_score = xgboost_pred.score
        xgb_proba = xgboost_pred.probability
        
        # 加权融合
        fused_score = (
            lgb_score * weights["lightgbm"] +
            xgb_score * weights["xgboost"]
        )
        
        # 加入RL仓位建议的调整
        rl_target = rl_decision.target_position
        if rl_decision.action.value == "increase":
            fused_score = fused_score * 0.8 + 0.2
        elif rl_decision.action.value == "decrease":
            fused_score = fused_score * 0.8
        elif rl_decision.action.value == "close":
            fused_score = 0.5
        
        fused_score = max(0, min(1, fused_score))
        
        # 确定方向
        if fused_score > 0.65:
            direction = "buy"
        elif fused_score < 0.35:
            direction = "sell"
        else:
            direction = "hold"
        
        confidence = abs(fused_score - 0.5) * 2
        
        # 模型一致度
        lgb_dir = lightgbm_pred.direction
        xgb_dir = xgboost_pred.direction
        agreement = self._calculate_agreement(lgb_dir, xgb_dir, rl_decision.action.value)
        
        # 建议仓位
        position_size = self._calculate_position_size(
            fused_score, confidence, rl_target, market_regime
        )
        
        reasoning = self._generate_reasoning(
            lgb_score, xgb_score, rl_decision, weights, agreement
        )
        
        return EnsemblePrediction(
            final_score=fused_score,
            final_direction=direction,
            confidence=confidence,
            position_size=position_size,
            lightgbm_score=lgb_score,
            xgboost_score=xgb_score,
            xgboost_proba=xgb_proba,
            rl_action=rl_decision.action.value,
            rl_target_position=rl_target,
            model_weights=weights,
            agreement_score=agreement,
            timestamp=timestamp,
            reasoning=reasoning
        )
    
    def _adjust_weights_for_regime(
        self,
        weights: Dict[str, float],
        regime: str
    ) -> Dict[str, float]:
        """根据市场状态调整权重"""
        if regime in ["trending_up", "trending_down"]:
            weights["lightgbm"] *= 1.2
            weights["xgboost"] *= 0.9
        elif regime == "ranging":
            weights["lightgbm"] *= 0.9
            weights["xgboost"] *= 1.1
        elif regime == "high_volatility":
            # 高波动时更信任RL的风险管理
            weights["lightgbm"] *= 0.8
            weights["xgboost"] *= 0.8
            weights["rl_position"] *= 1.5
        
        # 归一化
        total = sum(weights.values())
        return {k: v/total for k, v in weights.items()}
    
    def _calculate_agreement(
        self,
        lgb_dir: str,
        xgb_dir: str,
        rl_action: str
    ) -> float:
        """计算模型一致度"""
        # 标准化方向
        def normalize(d):
            d = d.lower()
            if d in ["buy", "increase"]:
                return 1
            elif d in ["sell", "decrease", "close"]:
                return -1
            else:
                return 0
        
        lgb = normalize(lgb_dir)
        xgb = normalize(xgb_dir)
        rl = normalize(rl_action)
        
        # 计算一致性
        agreements = []
        if lgb == xgb:
            agreements.append(1)
        else:
            agreements.append(0)
        
        if lgb == rl:
            agreements.append(1)
        else:
            agreements.append(0.5 if rl == 0 else 0)
        
        return np.mean(agreements)
    
    def _calculate_position_size(
        self,
        score: float,
        confidence: float,
        rl_target: float,
        regime: str
    ) -> float:
        """计算建议仓位"""
        # 基础仓位
        base_size = abs(score - 0.5) * 2  # 0-1
        
        # 置信度调整
        confidence_adjusted = base_size * (0.5 + confidence * 0.5)
        
        # RL建议调整
        rl_adjusted = (confidence_adjusted + rl_target) / 2
        
        # 市场环境调整
        if regime == "high_volatility":
            final_size = rl_adjusted * 0.6  # 降低仓位
        elif regime == "low_volatility":
            final_size = min(rl_adjusted * 1.2, 1.0)
        else:
            final_size = rl_adjusted
        
        return round(max(0, min(1, final_size)), 4)
    
    def _generate_reasoning(
        self,
        lgb_score: float,
        xgb_score: float,
        rl_decision: Any,
        weights: Dict[str, float],
        agreement: float
    ) -> str:
        """生成推理说明"""
        parts = []
        
        parts.append(f"LightGBM:{lgb_score:.2f}(w{weights['lightgbm']:.2f})")
        parts.append(f"XGBoost:{xgb_score:.2f}(w{weights['xgboost']:.2f})")
        parts.append(f"RL:{rl_decision.action.value}")
        parts.append(f"一致度:{agreement:.2f}")
        
        if agreement > 0.8:
            parts.append("模型高度一致")
        elif agreement < 0.3:
            parts.append("模型分歧较大,保守处理")
        
        return "; ".join(parts)
    
    def update_performance(self, model: str, was_correct: bool):
        """更新模型表现 (在线学习)"""
        if model in self.model_performance:
            self.model_performance[model]["total"] += 1
            if was_correct:
                self.model_performance[model]["correct"] += 1
        
        # 定期调整权重
        if self.model_performance[model]["total"] % 100 == 0:
            self._rebalance_weights()
    
    def _rebalance_weights(self):
        """基于表现重新平衡权重"""
        accuracies = {}
        for model, perf in self.model_performance.items():
            if perf["total"] > 0:
                accuracies[model] = perf["correct"] / perf["total"]
            else:
                accuracies[model] = 0.5
        
        # 基于准确率调整权重
        if len(accuracies) >= 2:
            total_acc = sum(accuracies.values())
            if total_acc > 0:
                for model in self.base_weights:
                    if model in accuracies:
                        self.base_weights[model] = accuracies[model] / total_acc
        
        self.last_update = datetime.now()
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy",
            "version": self.version,
            "weights": self.base_weights,
            "last_update": self.last_update.isoformat(),
        }


# 全局实例
ensemble = ModelEnsemble()
