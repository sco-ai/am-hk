"""
XGBoost备选模型 - XGBoost Model
用于模型对比和集成
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import pickle
import os


@dataclass
class XGBoostPrediction:
    """XGBoost预测结果"""
    score: float
    direction: str
    confidence: float
    probability: Dict[str, float]  # 各类别概率
    feature_importance: Dict[str, float]


class XGBoostModel:
    """
    XGBoost备选模型
    
    三分类模型: Buy / Hold / Sell
    """
    
    FEATURE_NAMES = [
        "price_momentum_5m", "price_momentum_15m", "price_momentum_1h",
        "momentum_strength", "trend_score",
        "ma_cross_5_20_distance", "ma_cross_5_20_strength",
        "macd", "macd_histogram", "macd_divergence",
        "atr_pct", "atr_normalized", 
        "bb_bandwidth", "bb_position", 
        "volatility_current", "volatility_ratio",
        "spread_pct", "spread_score", "depth_score",
        "slippage_10k", "liquidity_score",
        "funding_rate", "funding_extremity",
        "open_interest_usd", "oi_change_24h",
        "long_short_ratio", 
        "sentiment_composite", "contrarian_signal",
        "liquidation_risk_score",
    ]
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.version = "v3.0-simulated"
        self.last_update = datetime.now()
        
        # 尝试加载模型
        if model_path and os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.version = "v3.0-loaded"
            except Exception as e:
                print(f"[XGBoost] 模型加载失败,使用模拟模式: {e}")
    
    def predict(self, features: Dict[str, float]) -> XGBoostPrediction:
        """预测"""
        if self.model is not None:
            return self._predict_with_model(features)
        else:
            return self._predict_simulated(features)
    
    def _predict_with_model(self, features: Dict[str, float]) -> XGBoostPrediction:
        """使用真实模型预测"""
        X = np.array([[features.get(f, 0) for f in self.FEATURE_NAMES]])
        
        # 预测概率
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(X)[0]
        else:
            proba = [0.33, 0.34, 0.33]
        
        # 类别映射
        classes = ["sell", "hold", "buy"]
        probabilities = {c: p for c, p in zip(classes, proba)}
        
        # 最高概率类别
        pred_idx = np.argmax(proba)
        direction = classes[pred_idx]
        confidence = proba[pred_idx]
        
        # 转换为0-1分数
        score = probabilities["buy"] * 0.75 + probabilities["hold"] * 0.5 + probabilities["sell"] * 0.25
        
        # 特征重要性
        importance = {}
        if hasattr(self.model, 'feature_importances_'):
            importance = dict(zip(self.FEATURE_NAMES, self.model.feature_importances_))
        
        return XGBoostPrediction(
            score=score,
            direction=direction,
            confidence=confidence,
            probability=probabilities,
            feature_importance=importance
        )
    
    def _predict_simulated(self, features: Dict[str, float]) -> XGBoostPrediction:
        """模拟预测"""
        # 使用与LightGBM类似的逻辑,但添加一些差异
        buy_score = 0.33
        hold_score = 0.34
        sell_score = 0.33
        
        # 动量因子
        mom_5m = features.get("price_momentum_5m", 0)
        mom_15m = features.get("price_momentum_15m", 0)
        if mom_5m > 2 and mom_15m > 1:
            buy_score += 0.15
            sell_score -= 0.1
        elif mom_5m < -2 and mom_15m < -1:
            sell_score += 0.15
            buy_score -= 0.1
        
        # 趋势因子
        trend = features.get("trend_score", 0)
        if trend > 0.5:
            buy_score += 0.1
        elif trend < -0.5:
            sell_score += 0.1
        
        # 情绪因子
        sentiment = features.get("sentiment_composite", 0)
        if sentiment > 0.5:
            buy_score += 0.08
        elif sentiment < -0.5:
            sell_score += 0.08
        
        # 资金费率 (反向)
        funding = features.get("funding_rate", 0)
        if funding > 0.001:
            sell_score += 0.05  # 高费率暗示多头过多
        elif funding < -0.001:
            buy_score += 0.05
        
        # 爆仓风险 (反向)
        liq_risk = features.get("liquidation_risk_score", 0)
        if liq_risk > 0.6:
            hold_score += 0.1  # 风险高时倾向于观望
        
        # 归一化
        total = buy_score + hold_score + sell_score
        buy_score /= total
        hold_score /= total
        sell_score /= total
        
        probabilities = {
            "buy": buy_score,
            "hold": hold_score,
            "sell": sell_score
        }
        
        # 确定方向
        direction = max(probabilities, key=probabilities.get)
        confidence = probabilities[direction]
        
        # 综合分数
        score = buy_score * 0.75 + hold_score * 0.5 + sell_score * 0.25
        
        return XGBoostPrediction(
            score=score,
            direction=direction,
            confidence=confidence,
            probability=probabilities,
            feature_importance={}
        )
    
    def batch_predict(self, features_list: List[Dict[str, float]]) -> List[XGBoostPrediction]:
        """批量预测"""
        return [self.predict(f) for f in features_list]
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy",
            "version": self.version,
            "model_loaded": self.model is not None,
            "last_update": self.last_update.isoformat(),
        }


# 全局实例
xgboost_model = XGBoostModel()
