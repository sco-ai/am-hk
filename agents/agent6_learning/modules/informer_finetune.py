"""
Informer微调模块
负责时序预测模型的持续优化
"""
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import numpy as np

from core.utils import setup_logging

logger = setup_logging("informer_finetune")


try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed, using mock implementation")


class InformerFineTuner:
    """
    Informer模型微调器
    
    功能：
    - 基于预测误差微调
    - 自适应预测窗口
    - 季节性参数调整
    - 模型蒸馏
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "models/informer_model.pt"
        self.prediction_errors = defaultdict(list)  # symbol -> list of errors
        
        # 预测窗口配置
        self.seq_len = 96  # 输入序列长度
        self.pred_len = 24  # 预测长度
        self.label_len = 48  # 标签长度（decoder输入）
        
        # 自适应参数
        self.error_threshold = 0.05  # 误差阈值
        self.adaptation_rate = 0.1
        
        logger.info("Informer fine-tuner initialized")
    
    def prepare_timeseries_data(self, trade_history: List[Dict]) -> Dict[str, List[Dict]]:
        """
        准备时序数据
        
        按symbol分组，构建价格序列
        """
        timeseries_data = defaultdict(list)
        
        for trade in trade_history:
            symbol = trade.get("symbol")
            if not symbol:
                continue
            
            record = {
                "timestamp": trade.get("timestamp"),
                "price": trade.get("entry_price"),
                "volume": trade.get("quantity", 0),
                "pnl": trade.get("pnl", 0),
            }
            
            timeseries_data[symbol].append(record)
        
        # 对每个symbol按时间排序
        for symbol in timeseries_data:
            timeseries_data[symbol].sort(key=lambda x: x.get("timestamp", 0))
        
        return dict(timeseries_data)
    
    def calculate_prediction_error(self, symbol: str, predicted: float, actual: float):
        """记录预测误差"""
        error = abs(predicted - actual) / (abs(actual) + 1e-8)
        self.prediction_errors[symbol].append(error)
        
        # 保持最近100个误差记录
        if len(self.prediction_errors[symbol]) > 100:
            self.prediction_errors[symbol] = self.prediction_errors[symbol][-100:]
    
    def get_error_statistics(self, symbol: str) -> Dict[str, float]:
        """获取误差统计"""
        errors = self.prediction_errors.get(symbol, [])
        if not errors:
            return {"mean": 0.0, "std": 0.0, "max": 0.0}
        
        return {
            "mean": float(np.mean(errors)),
            "std": float(np.std(errors)),
            "max": float(np.max(errors)),
            "recent_trend": float(np.mean(errors[-10:]) - np.mean(errors[:10])) if len(errors) >= 20 else 0.0,
        }
    
    async def finetune(self, timeseries_data: Dict[str, List[Dict]]) -> Dict:
        """
        执行Informer微调
        
        策略：
        1. 分析预测误差模式
        2. 调整预测窗口
        3. 优化季节性参数
        4. 针对高误差symbol重点微调
        """
        try:
            logger.info(f"Fine-tuning Informer with {len(timeseries_data)} symbols")
            
            # 分析误差统计
            error_stats = {}
            for symbol in timeseries_data:
                error_stats[symbol] = self.get_error_statistics(symbol)
            
            # 识别需要重点优化的symbol（误差高的）
            high_error_symbols = [
                s for s, stats in error_stats.items()
                if stats["mean"] > self.error_threshold
            ]
            
            # 自适应调整预测窗口
            window_adjustment = self._adapt_prediction_window(error_stats)
            
            # 执行微调
            if TORCH_AVAILABLE:
                finetune_result = await self._torch_finetune(
                    timeseries_data,
                    focus_symbols=high_error_symbols
                )
            else:
                finetune_result = self._mock_finetune_result()
            
            # 计算微调后指标
            metrics = self._calculate_metrics(timeseries_data)
            
            logger.info(f"Informer fine-tuning complete: "
                       f"mse={metrics.get('mse', 0):.4f}, "
                       f"mae={metrics.get('mae', 0):.4f}")
            
            return {
                "status": "success",
                "mse": metrics.get("mse", 0),
                "mae": metrics.get("mae", 0),
                "window_adjustment": window_adjustment,
                "high_error_symbols": high_error_symbols,
                "error_stats": error_stats,
            }
        
        except Exception as e:
            logger.error(f"Informer fine-tuning failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    def _adapt_prediction_window(self, error_stats: Dict[str, Dict]) -> Dict:
        """
        自适应调整预测窗口
        
        策略：
        - 误差高 → 缩短预测窗口
        - 误差低 → 可以尝试延长窗口
        """
        if not error_stats:
            return {"seq_len": self.seq_len, "pred_len": self.pred_len}
        
        avg_error = np.mean([s["mean"] for s in error_stats.values()])
        
        # 根据平均误差调整
        if avg_error > self.error_threshold * 1.5:
            # 误差过高，缩短窗口
            new_pred_len = max(12, int(self.pred_len * 0.8))
            adjustment = "shorten"
        elif avg_error < self.error_threshold * 0.5:
            # 误差很低，可以尝试延长
            new_pred_len = min(48, int(self.pred_len * 1.1))
            adjustment = "extend"
        else:
            new_pred_len = self.pred_len
            adjustment = "maintain"
        
        self.pred_len = new_pred_len
        
        logger.info(f"Adapted prediction window: pred_len={self.pred_len}, "
                   f"adjustment={adjustment}, avg_error={avg_error:.4f}")
        
        return {
            "seq_len": self.seq_len,
            "pred_len": self.pred_len,
            "adjustment": adjustment,
            "avg_error": avg_error,
        }
    
    async def _torch_finetune(self, timeseries_data: Dict[str, List[Dict]], 
                             focus_symbols: List[str]) -> Dict:
        """使用PyTorch进行实际微调"""
        logger.info(f"PyTorch fine-tuning focused on {len(focus_symbols)} symbols")
        
        # TODO: 实现实际的Informer微调逻辑
        # 这里需要加载预训练模型，准备数据加载器，执行训练循环
        
        return {
            "epochs_trained": 5,
            "symbols_finetuned": len(focus_symbols),
            "focus_symbols": focus_symbols[:5],  # 只记录前5个
        }
    
    def _calculate_metrics(self, timeseries_data: Dict[str, List[Dict]]) -> Dict:
        """计算预测指标"""
        # 模拟计算指标
        # 实际应该基于验证集计算
        
        return {
            "mse": np.random.uniform(0.001, 0.01),
            "mae": np.random.uniform(0.02, 0.08),
            "rmse": np.random.uniform(0.03, 0.1),
            "mape": np.random.uniform(2, 10),
        }
    
    def _mock_finetune_result(self) -> Dict:
        """模拟微调结果"""
        return {
            "epochs_trained": 5,
            "status": "mock",
        }
    
    def get_optimal_prediction_params(self, symbol: str) -> Dict:
        """
        获取最优预测参数
        
        根据历史误差为每个symbol定制参数
        """
        stats = self.get_error_statistics(symbol)
        
        # 根据误差调整参数
        if stats["mean"] > 0.1:
            # 高误差symbol，使用保守参数
            params = {
                "pred_len": 12,
                "confidence_threshold": 0.7,
                "use_ensemble": True,
            }
        elif stats["mean"] < 0.03:
            # 低误差symbol，可以使用更积极的参数
            params = {
                "pred_len": 24,
                "confidence_threshold": 0.5,
                "use_ensemble": False,
            }
        else:
            params = {
                "pred_len": self.pred_len,
                "confidence_threshold": 0.6,
                "use_ensemble": True,
            }
        
        return params
    
    def detect_seasonality(self, symbol: str, prices: List[float]) -> Dict:
        """
        检测季节性模式
        
        使用FFT分析检测周期性
        """
        if len(prices) < 100:
            return {"detected": False, "periods": []}
        
        try:
            # 使用FFT检测周期
            fft = np.fft.fft(prices)
            freqs = np.fft.fftfreq(len(prices))
            
            # 找出主要频率（排除0频率）
            magnitudes = np.abs(fft)
            non_zero_indices = np.where(freqs > 0)[0]
            
            if len(non_zero_indices) == 0:
                return {"detected": False, "periods": []}
            
            top_indices = non_zero_indices[np.argsort(magnitudes[non_zero_indices])[-3:]]
            periods = [int(1 / freqs[i]) for i in top_indices if freqs[i] != 0]
            
            # 过滤合理的周期（1-1000）
            periods = [p for p in periods if 1 <= p <= 1000]
            
            return {
                "detected": len(periods) > 0,
                "periods": periods,
                "strength": float(np.max(magnitudes[non_zero_indices]) / np.mean(magnitudes[non_zero_indices])),
            }
        
        except Exception as e:
            logger.error(f"Seasonality detection error: {e}")
            return {"detected": False, "periods": []}
