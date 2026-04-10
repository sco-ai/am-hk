"""
LightGBM主力模型 - LightGBM Model
用于实时因子评分和信号生成
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import pickle
import os


@dataclass
class LightGBMPrediction:
    """LightGBM预测结果"""
    score: float  # 0-1 综合评分
    direction: str  # "buy", "sell", "hold"
    confidence: float  # 置信度
    feature_importance: Dict[str, float]
    raw_score: float  # 原始分数 (未归一化)


class LightGBMModel:
    """
    LightGBM主力模型
    
    当前使用规则模拟, 后续接入真实训练好的模型
    """
    
    # 特征列表 (与训练时一致)
    FEATURE_NAMES = [
        # 趋势因子
        "price_momentum_5m", "price_momentum_15m", "price_momentum_1h",
        "momentum_strength", "trend_score",
        "ma_cross_5_20_distance", "ma_cross_5_20_strength",
        "macd", "macd_histogram", "macd_divergence",
        
        # 波动率因子
        "atr_pct", "atr_normalized", "atr_trend",
        "bb_bandwidth", "bb_position", "bb_squeeze",
        "volatility_current", "volatility_ratio", "volatility_regime",
        
        # 流动性因子
        "spread_pct", "spread_score", "depth_score",
        "slippage_10k", "liquidity_score",
        "funding_rate", "funding_extremity", "funding_trend",
        "depth_imbalance",
        
        # 加密货币因子
        "open_interest_usd", "oi_change_24h", "oi_trend",
        "long_short_ratio", "ls_signal",
        "sentiment_composite", "contrarian_signal",
        "liquidation_risk_score",
    ]
    
    # 特征权重 (模拟训练好的模型)
    FEATURE_WEIGHTS = {
        # 趋势权重
        "price_momentum_5m": 0.08,
        "price_momentum_15m": 0.06,
        "momentum_strength": 0.05,
        "trend_score": 0.07,
        "ma_cross_5_20_strength": 0.06,
        "macd": 0.05,
        "macd_histogram": 0.04,
        
        # 波动率权重
        "atr_normalized": 0.04,
        "bb_position": 0.03,
        "volatility_ratio": 0.04,
        
        # 流动性权重
        "spread_score": 0.05,
        "depth_score": 0.06,
        "liquidity_score": 0.05,
        "funding_rate": 0.06,
        "funding_extremity": 0.04,
        
        # 加密货币专属权重
        "oi_change_24h": 0.05,
        "long_short_ratio": 0.06,
        "sentiment_composite": 0.07,
        "contrarian_signal": 0.04,
        "liquidation_risk_score": 0.05,
    }
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化LightGBM模型
        
        Args:
            model_path: 模型文件路径, None则使用模拟模式
        """
        self.model_path = model_path
        self.model = None
        self.version = "v3.0-simulated"
        self.last_update = datetime.now()
        
        # 尝试加载真实模型
        if model_path and os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.version = "v3.0-loaded"
            except Exception as e:
                print(f"[LightGBM] 模型加载失败,使用模拟模式: {e}")
    
    def predict(self, features: Dict[str, float]) -> LightGBMPrediction:
        """
        预测评分
        
        Args:
            features: 因子字典
            
        Returns:
            LightGBMPrediction
        """
        if self.model is not None:
            return self._predict_with_model(features)
        else:
            return self._predict_simulated(features)
    
    def _predict_with_model(self, features: Dict[str, float]) -> LightGBMPrediction:
        """使用真实模型预测"""
        # 构建特征向量
        X = np.array([[features.get(f, 0) for f in self.FEATURE_NAMES]])
        
        # 预测
        raw_score = self.model.predict(X)[0]
        
        # 归一化到0-1
        score = 1 / (1 + np.exp(-raw_score))
        
        # 方向判断
        if score > 0.6:
            direction = "buy"
        elif score < 0.4:
            direction = "sell"
        else:
            direction = "hold"
        
        # 置信度
        confidence = abs(score - 0.5) * 2
        
        # 特征重要性
        importance = dict(zip(self.FEATURE_NAMES, 
                            self.model.feature_importances_ if hasattr(self.model, 'feature_importances_') 
                            else [0.0] * len(self.FEATURE_NAMES)))
        
        return LightGBMPrediction(
            score=score,
            direction=direction,
            confidence=confidence,
            feature_importance=importance,
            raw_score=raw_score
        )
    
    def _predict_simulated(self, features: Dict[str, float]) -> LightGBMPrediction:
        """模拟预测 (规则基础)"""
        score = 0.5  # 中性基准
        
        # 加权求和
        for feature, weight in self.FEATURE_WEIGHTS.items():
            value = features.get(feature, 0)
            
            # 根据特征类型处理
            if feature in ["price_momentum_5m", "price_momentum_15m", "macd", "trend_score"]:
                score += np.tanh(value / 5) * weight  # 动量类
            elif feature in ["spread_score", "depth_score", "liquidity_score"]:
                score += value * weight  # 分数类 (0-1)
            elif feature in ["funding_rate"]:
                score += (-value * 1000) * weight  # 资金费率反向
            elif feature in ["sentiment_composite"]:
                score += value * weight  # 情绪
            elif feature in ["contrarian_signal"]:
                # 反向信号处理
                if value:
                    score -= np.sign(score - 0.5) * weight * 0.5
            elif feature in ["liquidation_risk_score"]:
                # 爆仓风险处理
                score -= value * weight * 0.5
            else:
                score += np.tanh(value) * weight
        
        # 归一化
        score = max(0, min(1, score))
        
        # 方向判断
        if score > 0.65:
            direction = "buy"
        elif score < 0.35:
            direction = "sell"
        else:
            direction = "hold"
        
        # 置信度
        confidence = abs(score - 0.5) * 2
        
        # 特征重要性 (使用权重)
        importance = {k: v for k, v in self.FEATURE_WEIGHTS.items()}
        
        return LightGBMPrediction(
            score=score,
            direction=direction,
            confidence=confidence,
            feature_importance=importance,
            raw_score=(score - 0.5) * 4  # 反sigmoid近似
        )
    
    def batch_predict(self, features_list: List[Dict[str, float]]) -> List[LightGBMPrediction]:
        """批量预测"""
        return [self.predict(f) for f in features_list]
    
    def get_feature_importance(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """获取最重要的特征"""
        sorted_features = sorted(self.FEATURE_WEIGHTS.items(), 
                               key=lambda x: x[1], reverse=True)
        return sorted_features[:top_n]
    
    def update_weights(self, new_weights: Dict[str, float]):
        """更新特征权重 (在线学习)"""
        for feature, weight in new_weights.items():
            if feature in self.FEATURE_WEIGHTS:
                # 指数平滑更新
                self.FEATURE_WEIGHTS[feature] = 0.9 * self.FEATURE_WEIGHTS[feature] + 0.1 * weight
        
        self.last_update = datetime.now()
    
    def health_check(self) -> Dict[str, Any]:
        """模型健康检查"""
        return {
            "status": "healthy",
            "version": self.version,
            "model_loaded": self.model is not None,
            "last_update": self.last_update.isoformat(),
            "feature_count": len(self.FEATURE_NAMES),
        }


# 全局实例
lightgbm_model = LightGBMModel()
