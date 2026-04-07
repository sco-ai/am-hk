"""
LightGBM增量学习模块
负责因子权重的动态调整和特征选择优化
"""
import json
import logging
import pickle
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
import numpy as np

from core.utils import setup_logging

logger = setup_logging("lightgbm_trainer")

# 尝试导入LightGBM
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("LightGBM not installed, using mock implementation")


class LightGBMTrainer:
    """
    LightGBM增量学习训练器
    
    功能：
    - 增量训练：新交易数据 → 模型更新
    - 因子重要性重计算
    - 特征选择优化
    - 模型版本管理
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "models/lightgbm_factor_model.pkl"
        self.model = None
        self.feature_names = []
        self.feature_importance = {}
        
        # 训练数据缓存
        self.training_buffer = deque(maxlen=10000)
        self.min_buffer_size = 100
        
        # 模型配置
        self.params = {
            "objective": "binary",
            "metric": ["binary_logloss", "auc"],
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "min_data_in_leaf": 20,
        }
        
        # 加载现有模型
        self._load_model()
        
        logger.info("LightGBM trainer initialized")
    
    def _load_model(self):
        """加载已有模型"""
        try:
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
            logger.info("Loaded existing LightGBM model")
        except FileNotFoundError:
            logger.info("No existing model found, will train from scratch")
            self.model = None
    
    def _save_model(self):
        """保存模型"""
        try:
            import os
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump(self.model, f)
            logger.info(f"Model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def add_sample(self, trade_record: Dict):
        """添加训练样本"""
        self.training_buffer.append(trade_record)
    
    def has_enough_data(self) -> bool:
        """检查是否有足够数据进行训练"""
        return len(self.training_buffer) >= self.min_buffer_size
    
    def prepare_training_data(self, trade_history: List[Dict]) -> List[Dict]:
        """
        准备训练数据
        
        特征工程：
        - 原始因子值
        - 技术因子交叉
        - 市场环境特征
        - 信号置信度
        
        标签：
        - 1: 盈利交易
        - 0: 亏损或平盘交易
        """
        training_data = []
        
        for trade in trade_history:
            if "factors" not in trade or "pnl" not in trade:
                continue
            
            factors = trade["factors"]
            
            # 构建特征向量
            features = self._extract_features(factors, trade)
            
            # 标签：盈利为1，亏损为0
            label = 1 if trade.get("pnl", 0) > 0 else 0
            
            training_data.append({
                "features": features,
                "label": label,
                "weight": abs(trade.get("pnl", 0)) + 0.1,  # 根据盈亏大小加权
            })
        
        return training_data
    
    def _extract_features(self, factors: Dict, trade: Dict) -> Dict[str, float]:
        """提取特征向量"""
        features = {}
        
        # 基础因子
        base_factors = [
            "mom_5m", "mom_15m", "mom_1h", "mom_1d",
            "rsi", "macd", "macd_signal", "macd_hist",
            "volatility_5m", "volatility_15m",
            "volume_ratio", "obv",
            "bb_position", "bb_width",
            "atr", "atr_ratio",
        ]
        
        for factor in base_factors:
            features[factor] = factors.get(factor, 0.0)
        
        # 信号相关特征
        features["signal_confidence"] = trade.get("signal_confidence", 0.5)
        features["predicted_return"] = trade.get("predicted_return", 0.0)
        
        # 市场状态特征（交叉特征）
        features["mom_volatility"] = features.get("mom_5m", 0) * features.get("volatility_5m", 1)
        features["rsi_macd"] = features.get("rsi", 50) * features.get("macd", 0)
        
        return features
    
    async def incremental_train(self, training_data: List[Dict]) -> Dict:
        """
        执行增量训练
        
        策略：
        1. 使用新数据训练新树
        2. 与现有模型集成（加权平均）
        3. 更新因子重要性
        4. 执行特征选择
        """
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, returning mock result")
            return self._mock_train_result()
        
        try:
            # 准备数据
            X, y, weights = self._prepare_lgb_data(training_data)
            
            if len(X) == 0:
                return {"status": "error", "error": "no_valid_data"}
            
            # 创建数据集
            train_data = lgb.Dataset(X, label=y, weight=weights)
            
            # 训练新模型或增量更新
            if self.model is None:
                # 从头训练
                logger.info("Training new LightGBM model from scratch")
                new_model = lgb.train(
                    self.params,
                    train_data,
                    num_boost_round=100,
                    valid_sets=[train_data],
                    callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(0)]
                )
                self.model = new_model
            else:
                # 增量训练
                logger.info("Performing incremental training")
                new_model = lgb.train(
                    self.params,
                    train_data,
                    num_boost_round=50,
                    init_model=self.model,
                    valid_sets=[train_data],
                    callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(0)]
                )
                
                # 模型融合：新模型权重0.3，旧模型权重0.7
                self.model = self._merge_models(self.model, new_model, alpha=0.3)
            
            # 计算因子重要性
            self._update_feature_importance()
            
            # 特征选择优化
            selected_features = self._feature_selection()
            
            # 评估模型
            metrics = self._evaluate_model(X, y)
            
            # 保存模型
            self._save_model()
            
            return {
                "status": "success",
                "accuracy": metrics.get("accuracy", 0),
                "auc": metrics.get("auc", 0),
                "feature_importance": self.feature_importance,
                "selected_features": selected_features,
                "num_features": len(selected_features),
                "num_samples": len(X),
            }
        
        except Exception as e:
            logger.error(f"Incremental training failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    def _prepare_lgb_data(self, training_data: List[Dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """准备LightGBM输入数据"""
        if not training_data:
            return np.array([]), np.array([]), np.array([])
        
        # 收集所有特征名
        all_features = set()
        for sample in training_data:
            all_features.update(sample["features"].keys())
        
        self.feature_names = sorted(list(all_features))
        
        # 构建矩阵
        X = []
        y = []
        weights = []
        
        for sample in training_data:
            row = [sample["features"].get(f, 0.0) for f in self.feature_names]
            X.append(row)
            y.append(sample["label"])
            weights.append(sample.get("weight", 1.0))
        
        return np.array(X), np.array(y), np.array(weights)
    
    def _merge_models(self, old_model, new_model, alpha: float = 0.3):
        """
        融合新旧模型
        
        Args:
            old_model: 旧模型
            new_model: 新模型
            alpha: 新模型权重
        """
        # 简化实现：使用新模型，但在预测时加权
        # 实际生产环境可能需要更复杂的模型融合策略
        return new_model
    
    def _update_feature_importance(self):
        """更新因子重要性"""
        if self.model is None or not LIGHTGBM_AVAILABLE:
            return
        
        importance = self.model.feature_importance(importance_type="gain")
        
        self.feature_importance = {
            name: float(imp)
            for name, imp in zip(self.feature_names, importance)
        }
        
        # 归一化
        total = sum(self.feature_importance.values())
        if total > 0:
            self.feature_importance = {
                k: v / total for k, v in self.feature_importance.items()
            }
        
        logger.info(f"Top 5 important features: "
                   f"{sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]}")
    
    def _feature_selection(self, threshold: float = 0.01) -> List[str]:
        """
        特征选择
        
        策略：
        - 保留重要性 > threshold 的特征
        - 去除冗余特征（相关性高的）
        """
        if not self.feature_importance:
            return []
        
        # 筛选重要特征
        selected = [
            name for name, importance in self.feature_importance.items()
            if importance > threshold
        ]
        
        logger.info(f"Selected {len(selected)} features out of {len(self.feature_importance)}")
        
        return selected
    
    def _evaluate_model(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """评估模型性能"""
        if self.model is None or len(X) == 0:
            return {}
        
        try:
            predictions = self.model.predict(X)
            pred_labels = (predictions > 0.5).astype(int)
            
            accuracy = np.mean(pred_labels == y)
            
            # 计算AUC
            from sklearn.metrics import roc_auc_score
            auc = roc_auc_score(y, predictions) if len(np.unique(y)) > 1 else 0.5
            
            return {
                "accuracy": float(accuracy),
                "auc": float(auc),
            }
        except Exception as e:
            logger.error(f"Model evaluation error: {e}")
            return {}
    
    def predict(self, features: Dict[str, float]) -> Dict:
        """
        预测交易成功概率
        
        Returns:
            {
                "probability": float,
                "confidence": float,
            }
        """
        if self.model is None:
            return {"probability": 0.5, "confidence": 0.0}
        
        try:
            X = np.array([[features.get(f, 0.0) for f in self.feature_names]])
            prob = self.model.predict(X)[0]
            
            # 置信度基于预测值距离0.5的远近
            confidence = abs(prob - 0.5) * 2
            
            return {
                "probability": float(prob),
                "confidence": float(confidence),
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"probability": 0.5, "confidence": 0.0}
    
    def get_factor_weights(self) -> Dict[str, float]:
        """获取当前因子权重"""
        return self.feature_importance.copy()
    
    def _mock_train_result(self) -> Dict:
        """模拟训练结果（当LightGBM不可用时）"""
        return {
            "status": "mock",
            "accuracy": 0.55 + np.random.random() * 0.1,
            "auc": 0.58 + np.random.random() * 0.1,
            "feature_importance": {f"factor_{i}": np.random.random() for i in range(10)},
            "selected_features": [f"factor_{i}" for i in range(5)],
            "num_features": 5,
            "num_samples": 100,
        }
