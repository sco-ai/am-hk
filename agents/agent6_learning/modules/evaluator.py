"""
模型性能评估模块
负责评估各模型的性能并提供改进建议
"""
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
from dataclasses import dataclass
import numpy as np

from core.utils import setup_logging

logger = setup_logging("model_evaluator")


@dataclass
class EvaluationMetrics:
    """评估指标"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.5
    mse: float = 0.0
    mae: float = 0.0
    
    # 交易相关指标
    win_rate: float = 0.0
    profit_loss_ratio: float = 1.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    
    # 统计指标
    total_samples: int = 0
    positive_samples: int = 0


class ModelEvaluator:
    """
    模型性能评估器
    
    功能：
    - 多维度模型评估
    - 回测性能分析
    - 模型对比
    - 生成评估报告
    """
    
    def __init__(self):
        # 评估阈值
        self.thresholds = {
            "accuracy": 0.55,
            "win_rate": 0.52,
            "sharpe_ratio": 1.0,
            "max_drawdown": 0.15,
        }
        
        # 评估历史
        self.evaluation_history: List[Dict] = []
        
        logger.info("Model evaluator initialized")
    
    def evaluate_all_models(self, 
                           trade_history: List[Dict],
                           model_versions: Dict[str, str]) -> Dict[str, Dict]:
        """
        评估所有模型
        
        返回各模型的评估结果
        """
        results = {}
        
        # LightGBM评估
        results["lightgbm"] = self._evaluate_lightgbm(trade_history, model_versions.get("lightgbm"))
        
        # Informer评估
        results["informer"] = self._evaluate_informer(trade_history, model_versions.get("informer"))
        
        # PPO评估
        results["ppo"] = self._evaluate_ppo(trade_history, model_versions.get("ppo"))
        
        # GNN评估
        results["gnn"] = self._evaluate_gnn(trade_history, model_versions.get("gnn"))
        
        # 记录评估历史
        self.evaluation_history.append({
            "timestamp": datetime.now().isoformat(),
            "results": results,
        })
        
        return results
    
    def _evaluate_lightgbm(self, trade_history: List[Dict], 
                          version: str) -> Dict:
        """评估LightGBM模型"""
        # 基于交易结果评估因子模型的效果
        
        if len(trade_history) < 30:
            return {
                "version": version,
                "status": "insufficient_data",
                "metrics": {},
            }
        
        # 分析因子预测准确性
        predictions = []
        actuals = []
        
        for trade in trade_history:
            if "factors" in trade and "pnl" in trade:
                # 简化：假设因子预测与实际盈亏一致
                pred_confidence = trade.get("signal_confidence", 0.5)
                actual = 1 if trade["pnl"] > 0 else 0
                
                predictions.append(pred_confidence > 0.5)
                actuals.append(actual)
        
        if len(predictions) < 30:
            return {
                "version": version,
                "status": "insufficient_predictions",
                "metrics": {},
            }
        
        metrics = self._calculate_classification_metrics(predictions, actuals)
        
        # 计算因子重要性变化
        feature_importance = trade_history[-1].get("factors", {}) if trade_history else {}
        
        # 判断是否需要升级
        should_promote = (
            metrics.accuracy > self.thresholds["accuracy"] and
            metrics.win_rate > self.thresholds["win_rate"]
        )
        
        return {
            "version": version,
            "status": "success",
            "metrics": {
                "accuracy": round(metrics.accuracy, 4),
                "precision": round(metrics.precision, 4),
                "recall": round(metrics.recall, 4),
                "f1_score": round(metrics.f1_score, 4),
                "win_rate": round(metrics.win_rate, 4),
                "total_samples": metrics.total_samples,
            },
            "should_promote": should_promote,
            "top_factors": sorted(feature_importance.items(), 
                                 key=lambda x: abs(x[1]), reverse=True)[:5] if feature_importance else [],
        }
    
    def _evaluate_informer(self, trade_history: List[Dict],
                          version: str) -> Dict:
        """评估Informer模型"""
        # 评估预测准确性
        
        if len(trade_history) < 50:
            return {
                "version": version,
                "status": "insufficient_data",
                "metrics": {},
            }
        
        # 分析预测误差
        errors = []
        for trade in trade_history:
            if "predicted_return" in trade and "pnl_pct" in trade:
                predicted = trade["predicted_return"]
                actual = trade["pnl_pct"]
                error = abs(predicted - actual)
                errors.append(error)
        
        if len(errors) < 30:
            return {
                "version": version,
                "status": "insufficient_predictions",
                "metrics": {},
            }
        
        mse = np.mean([e**2 for e in errors])
        mae = np.mean(errors)
        
        # 方向准确性
        directional_correct = sum(
            1 for t in trade_history
            if "predicted_return" in t and "pnl_pct" in t
            and (t["predicted_return"] > 0) == (t["pnl_pct"] > 0)
        )
        directional_accuracy = directional_correct / len(trade_history) if trade_history else 0
        
        should_promote = mae < 0.05 and directional_accuracy > 0.55
        
        return {
            "version": version,
            "status": "success",
            "metrics": {
                "mse": round(mse, 6),
                "mae": round(mae, 6),
                "rmse": round(np.sqrt(mse), 6),
                "directional_accuracy": round(directional_accuracy, 4),
                "mean_error": round(np.mean(errors), 6),
                "max_error": round(np.max(errors), 6),
            },
            "should_promote": should_promote,
        }
    
    def _evaluate_ppo(self, trade_history: List[Dict],
                     version: str) -> Dict:
        """评估PPO模型"""
        # 评估RL策略的效果
        
        if len(trade_history) < 50:
            return {
                "version": version,
                "status": "insufficient_data",
                "metrics": {},
            }
        
        # 计算策略收益指标
        returns = [t.get("pnl_pct", 0) for t in trade_history if t.get("pnl_pct") is not None]
        
        if len(returns) < 30:
            return {
                "version": version,
                "status": "insufficient_returns",
                "metrics": {},
            }
        
        # 夏普比率近似
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe = mean_return / (std_return + 1e-8) * np.sqrt(252)  # 年化
        
        # 最大回撤
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / (running_max + 1e-8)
        max_drawdown = abs(np.min(drawdown))
        
        # 胜率
        wins = sum(1 for r in returns if r > 0)
        win_rate = wins / len(returns)
        
        # 盈亏比
        avg_win = np.mean([r for r in returns if r > 0]) if wins > 0 else 0
        avg_loss = abs(np.mean([r for r in returns if r <= 0])) if wins < len(returns) else 1
        pl_ratio = avg_win / avg_loss if avg_loss > 0 else 1
        
        should_promote = (
            sharpe > self.thresholds["sharpe_ratio"] and
            win_rate > self.thresholds["win_rate"] and
            max_drawdown < self.thresholds["max_drawdown"]
        )
        
        return {
            "version": version,
            "status": "success",
            "metrics": {
                "sharpe_ratio": round(sharpe, 4),
                "max_drawdown": round(max_drawdown, 4),
                "win_rate": round(win_rate, 4),
                "profit_loss_ratio": round(pl_ratio, 4),
                "total_return": round(sum(returns), 4),
                "avg_return": round(mean_return, 6),
            },
            "should_promote": should_promote,
        }
    
    def _evaluate_gnn(self, trade_history: List[Dict],
                     version: str) -> Dict:
        """评估GNN模型"""
        # 评估关系学习的有效性
        
        if len(trade_history) < 100:
            return {
                "version": version,
                "status": "insufficient_data",
                "metrics": {},
            }
        
        # 分析跨标的相关性预测效果
        symbols = defaultdict(list)
        for trade in trade_history:
            sym = trade.get("symbol")
            if sym and "pnl_pct" in trade:
                symbols[sym].append(trade["pnl_pct"])
        
        # 计算标的间相关性
        correlations = []
        symbol_list = list(symbols.keys())
        
        for i, sym1 in enumerate(symbol_list):
            for sym2 in symbol_list[i+1:]:
                returns1 = symbols[sym1]
                returns2 = symbols[sym2]
                
                if len(returns1) > 10 and len(returns2) > 10:
                    min_len = min(len(returns1), len(returns2))
                    corr = np.corrcoef(returns1[-min_len:], returns2[-min_len:])[0, 1]
                    if not np.isnan(corr):
                        correlations.append(abs(corr))
        
        avg_correlation = np.mean(correlations) if correlations else 0
        
        # GNN效果：高相关性意味着关系学习有价值
        should_promote = avg_correlation > 0.3
        
        return {
            "version": version,
            "status": "success",
            "metrics": {
                "avg_correlation": round(avg_correlation, 4),
                "num_symbols": len(symbol_list),
                "num_correlations": len(correlations),
                "max_correlation": round(max(correlations), 4) if correlations else 0,
            },
            "should_promote": should_promote,
        }
    
    def _calculate_classification_metrics(self, 
                                         predictions: List[bool],
                                         actuals: List[int]) -> EvaluationMetrics:
        """计算分类指标"""
        n = len(predictions)
        if n == 0:
            return EvaluationMetrics()
        
        # 混淆矩阵
        tp = sum(1 for p, a in zip(predictions, actuals) if p and a == 1)
        fp = sum(1 for p, a in zip(predictions, actuals) if p and a == 0)
        tn = sum(1 for p, a in zip(predictions, actuals) if not p and a == 0)
        fn = sum(1 for p, a in zip(predictions, actuals) if not p and a == 1)
        
        # 基础指标
        accuracy = (tp + tn) / n if n > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # 胜率
        win_rate = recall  # 简化处理
        
        return EvaluationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            win_rate=win_rate,
            total_samples=n,
            positive_samples=tp + fn,
        )
    
    def generate_report(self, evaluation_results: Dict[str, Dict]) -> str:
        """
        生成评估报告
        
        返回Markdown格式的报告
        """
        report = """# 模型评估报告

生成时间: {timestamp}

## 总体概况

""".format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        for model_name, result in evaluation_results.items():
            report += f"\n### {model_name.upper()}\n\n"
            report += f"- 版本: {result.get('version', 'N/A')}\n"
            report += f"- 状态: {result.get('status', 'unknown')}\n"
            
            metrics = result.get('metrics', {})
            if metrics:
                report += "- 指标:\n"
                for key, value in metrics.items():
                    report += f"  - {key}: {value}\n"
            
            report += f"- 建议升级: {'是' if result.get('should_promote') else '否'}\n"
        
        # 改进建议
        report += "\n## 改进建议\n\n"
        
        suggestions = self._generate_suggestions(evaluation_results)
        for i, suggestion in enumerate(suggestions, 1):
            report += f"{i}. {suggestion}\n"
        
        return report
    
    def _generate_suggestions(self, results: Dict[str, Dict]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        # LightGBM建议
        lgbm_result = results.get("lightgbm", {})
        if lgbm_result.get("status") == "success":
            acc = lgbm_result.get("metrics", {}).get("accuracy", 0)
            if acc < 0.55:
                suggestions.append("LightGBM准确率偏低，建议增加训练数据或调整特征工程")
            elif acc > 0.65:
                suggestions.append("LightGBM表现良好，可以考虑提升版本")
        
        # Informer建议
        informer_result = results.get("informer", {})
        if informer_result.get("status") == "success":
            mae = informer_result.get("metrics", {}).get("mae", 1)
            if mae > 0.05:
                suggestions.append("Informer预测误差较大，建议调整预测窗口或增加历史数据")
        
        # PPO建议
        ppo_result = results.get("ppo", {})
        if ppo_result.get("status") == "success":
            sharpe = ppo_result.get("metrics", {}).get("sharpe_ratio", 0)
            if sharpe < 1:
                suggestions.append("PPO策略夏普比率偏低，建议调整奖励函数或增加探索")
        
        if not suggestions:
            suggestions.append("所有模型运行正常，继续监控性能")
        
        return suggestions
    
    def compare_versions(self, 
                        model_name: str,
                        version1: str,
                        version2: str) -> Dict:
        """
        比较两个版本的性能
        """
        # 从评估历史中查找
        metrics1 = None
        metrics2 = None
        
        for eval_record in reversed(self.evaluation_history):
            results = eval_record.get("results", {})
            model_result = results.get(model_name, {})
            
            if model_result.get("version") == version1 and not metrics1:
                metrics1 = model_result.get("metrics", {})
            
            if model_result.get("version") == version2 and not metrics2:
                metrics2 = model_result.get("metrics", {})
            
            if metrics1 and metrics2:
                break
        
        if not metrics1 or not metrics2:
            return {
                "error": "Versions not found in evaluation history",
            }
        
        # 计算差异
        comparison = {}
        all_keys = set(metrics1.keys()) | set(metrics2.keys())
        
        for key in all_keys:
            v1 = metrics1.get(key, 0)
            v2 = metrics2.get(key, 0)
            diff = v2 - v1
            pct_change = (diff / v1 * 100) if v1 != 0 else 0
            
            comparison[key] = {
                "version1": v1,
                "version2": v2,
                "difference": round(diff, 6),
                "percent_change": round(pct_change, 2),
            }
        
        return {
            "model_name": model_name,
            "version1": version1,
            "version2": version2,
            "comparison": comparison,
        }


from datetime import datetime  # 放在文件末尾避免循环导入