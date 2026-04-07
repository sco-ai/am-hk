"""
Agent 6: LearningFeedback - 学习反馈与进化引擎
核心模块集成入口
"""
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import deque

from core.kafka import MessageBus, AgentConsumer
from core.models import TradeDecision, Signal, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

# 导入子模块
from agents.agent6_learning.modules.lightgbm_trainer import LightGBMTrainer
from agents.agent6_learning.modules.informer_finetune import InformerFineTuner
from agents.agent6_learning.modules.ppo_trainer import PPOTrainer
from agents.agent6_learning.modules.kelly_optimizer import KellyOptimizer
from agents.agent6_learning.modules.gnn_trainer import TemporalGNNTTrainer
from agents.agent6_learning.modules.model_manager import ModelVersionManager
from agents.agent6_learning.modules.evaluator import ModelEvaluator

logger = setup_logging("agent6_learning")


class LearningFeedback:
    """
    Agent 6: 学习反馈与进化引擎
    
    职责：
    - 交易结果记录与分析
    - LightGBM增量学习（因子权重优化）
    - Informer微调（时序预测优化）
    - PPO + LSTM强化学习（策略参数优化）
    - Temporal GNN（市场关系图学习）
    - 凯利公式仓位优化
    - 模型版本管理与A/B测试
    
    输入：
    - Kafka: am-hk-trade-results (交易执行结果)
    - 包含：实际成交价格、盈亏、持仓时间等
    
    输出：
    - Kafka: am-hk-model-updates (广播给所有Agent)
    """
    
    def __init__(self):
        self.agent_name = "agent6_learning"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-trade-results", "am-hk-executions", "am-hk-feedback"]
        )
        
        # 初始化各模块
        self.lightgbm_trainer = LightGBMTrainer()
        self.informer_tuner = InformerFineTuner()
        self.ppo_trainer = PPOTrainer()
        self.kelly_optimizer = KellyOptimizer()
        self.gnn_trainer = TemporalGNNTTrainer()
        self.model_manager = ModelVersionManager()
        self.evaluator = ModelEvaluator()
        
        # 交易历史缓存
        self.trade_history: deque = deque(maxlen=50000)
        self.min_samples_for_training = 100
        
        # 学习配置
        self.learning_interval = 3600  # 每小时学习一次
        self.evaluation_interval = 1800  # 每半小时评估一次
        
        # 性能统计
        self.performance_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
            "total_cost": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
        }
        
        self.running = False
        logger.info(f"{self.agent_name} initialized with all learning modules")
    
    async def start(self):
        """启动学习引擎"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 加载历史数据
        await self._load_trade_history()
        
        # 加载当前模型版本
        self.model_manager.load_current_versions()
        
        # 注册消息处理器
        self.consumer.register_handler("trade_result", self._on_trade_result)
        self.consumer.register_handler("execution_order", self._on_execution)
        self.consumer.register_handler("model_evaluation", self._on_evaluation_request)
        
        # 发布状态
        self._publish_status("running")
        
        # 启动定时任务
        tasks = [
            asyncio.create_task(self._learning_loop()),
            asyncio.create_task(self._evaluation_loop()),
            asyncio.create_task(self._kelly_optimization_loop()),
        ]
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            for task in tasks:
                task.cancel()
            await self.stop()
    
    async def stop(self):
        """停止学习引擎"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        # 保存历史数据
        await self._save_trade_history()
        
        # 保存模型版本信息
        self.model_manager.save_versions()
        
        self._publish_status("stopped")
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_trade_result(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易结果"""
        try:
            payload = value.get("payload", {})
            
            trade_record = {
                "msg_id": value.get("msg_id"),
                "timestamp": payload.get("timestamp", generate_timestamp()),
                "symbol": payload.get("symbol"),
                "action": payload.get("action"),
                "entry_price": payload.get("entry_price"),
                "exit_price": payload.get("exit_price"),
                "quantity": payload.get("quantity"),
                "pnl": payload.get("pnl", 0.0),
                "pnl_pct": payload.get("pnl_pct", 0.0),
                "holding_time": payload.get("holding_time", 0),
                "transaction_cost": payload.get("transaction_cost", 0.0),
                "slippage": payload.get("slippage", 0.0),
                "factors": payload.get("factors", {}),
                "signal_confidence": payload.get("signal_confidence", 0.0),
                "predicted_return": payload.get("predicted_return", 0.0),
            }
            
            self._add_trade_record(trade_record)
            
            # 实时更新PPO经验池
            self.ppo_trainer.add_experience(trade_record)
            
            # 实时更新LightGBM训练数据
            self.lightgbm_trainer.add_sample(trade_record)
            
            logger.info(f"Recorded trade result: {trade_record['symbol']} "
                       f"PNL={trade_record['pnl']:.2f} "
                       f"holding_time={trade_record['holding_time']}s")
        
        except Exception as e:
            logger.error(f"Error processing trade result: {e}", exc_info=True)
    
    def _on_execution(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理执行结果"""
        try:
            payload = value.get("payload", {})
            decision_data = payload.get("decision", {})
            
            execution_record = {
                "msg_id": value.get("msg_id"),
                "timestamp": generate_timestamp(),
                "symbol": decision_data.get("signal", {}).get("symbol"),
                "action": decision_data.get("signal", {}).get("action"),
                "position_size": decision_data.get("position_size"),
                "confidence": decision_data.get("signal", {}).get("confidence"),
                "predicted_return": decision_data.get("signal", {}).get("predicted_return"),
                "factors": decision_data.get("signal", {}).get("metadata", {}).get("factors", {}),
                "status": "executed",
            }
            
            self._add_trade_record(execution_record)
            
            logger.debug(f"Recorded execution: {execution_record['symbol']} "
                        f"action={execution_record['action']}")
        
        except Exception as e:
            logger.error(f"Error processing execution: {e}", exc_info=True)
    
    def _on_evaluation_request(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理评估请求"""
        try:
            payload = value.get("payload", {})
            model_type = payload.get("model_type", "all")
            
            logger.info(f"Received evaluation request for {model_type}")
            
            # 执行评估
            results = self.evaluator.evaluate_all_models(
                self.trade_history,
                self.model_manager.get_current_versions()
            )
            
            # 发布评估结果
            self._publish_evaluation_results(results)
            
        except Exception as e:
            logger.error(f"Error processing evaluation request: {e}", exc_info=True)
    
    def _add_trade_record(self, record: Dict):
        """添加交易记录"""
        self.trade_history.append(record)
        
        # 更新统计
        if record.get("pnl") is not None:
            self.performance_stats["total_trades"] += 1
            if record["pnl"] > 0:
                self.performance_stats["winning_trades"] += 1
            self.performance_stats["total_pnl"] += record["pnl"]
            self.performance_stats["total_cost"] += record.get("transaction_cost", 0)
            
            # 计算胜率
            total = self.performance_stats["total_trades"]
            if total > 0:
                self.performance_stats["win_rate"] = (
                    self.performance_stats["winning_trades"] / total
                )
    
    async def _learning_loop(self):
        """定时学习循环"""
        while self.running:
            try:
                await asyncio.sleep(self.learning_interval)
                
                if len(self.trade_history) >= self.min_samples_for_training:
                    await self._run_learning_cycle()
                else:
                    logger.info(f"Not enough samples for training: "
                               f"{len(self.trade_history)}/{self.min_samples_for_training}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Learning loop error: {e}", exc_info=True)
    
    async def _evaluation_loop(self):
        """定时评估循环"""
        while self.running:
            try:
                await asyncio.sleep(self.evaluation_interval)
                
                if len(self.trade_history) >= self.min_samples_for_training:
                    await self._run_evaluation_cycle()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Evaluation loop error: {e}", exc_info=True)
    
    async def _kelly_optimization_loop(self):
        """凯利公式优化循环（每10分钟）"""
        while self.running:
            try:
                await asyncio.sleep(600)  # 10分钟
                
                if len(self.trade_history) >= 50:  # 至少需要50笔交易
                    await self._run_kelly_optimization()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Kelly optimization loop error: {e}", exc_info=True)
    
    async def _run_learning_cycle(self):
        """执行学习周期"""
        logger.info("=" * 60)
        logger.info("Starting learning cycle...")
        logger.info("=" * 60)
        
        # 1. LightGBM增量学习
        lightgbm_update = await self._train_lightgbm()
        
        # 2. Informer微调
        informer_update = await self._finetune_informer()
        
        # 3. PPO+LSTM训练
        ppo_update = await self._train_ppo()
        
        # 4. Temporal GNN训练
        gnn_update = await self._train_gnn()
        
        # 5. 综合模型更新广播
        await self._publish_model_updates({
            "lightgbm": lightgbm_update,
            "informer": informer_update,
            "ppo": ppo_update,
            "gnn": gnn_update,
        })
        
        logger.info("Learning cycle completed")
        logger.info("=" * 60)
    
    async def _run_evaluation_cycle(self):
        """执行评估周期"""
        logger.info("Running evaluation cycle...")
        
        # 评估各模型性能
        results = self.evaluator.evaluate_all_models(
            list(self.trade_history),
            self.model_manager.get_current_versions()
        )
        
        # 如果新模型表现更好，执行升级
        for model_name, evaluation in results.items():
            if evaluation.get("should_promote", False):
                logger.info(f"Promoting {model_name} to production")
                self.model_manager.promote_version(model_name, evaluation["version"])
        
        logger.info("Evaluation cycle completed")
    
    async def _run_kelly_optimization(self):
        """执行凯利公式仓位优化"""
        try:
            kelly_result = self.kelly_optimizer.optimize(
                list(self.trade_history),
                window_size=100  # 最近100笔交易
            )
            
            # 发布仓位优化结果
            self._publish_kelly_update(kelly_result)
            
            logger.info(f"Kelly optimization: position={kelly_result['optimal_position']:.2%}, "
                       f"win_rate={kelly_result['win_rate']:.2%}, "
                       f"pl_ratio={kelly_result['profit_loss_ratio']:.2f}")
        
        except Exception as e:
            logger.error(f"Kelly optimization error: {e}")
    
    async def _train_lightgbm(self) -> Dict:
        """LightGBM增量学习"""
        try:
            logger.info("Training LightGBM (incremental)...")
            
            # 准备训练数据
            training_data = self.lightgbm_trainer.prepare_training_data(
                list(self.trade_history)
            )
            
            if len(training_data) < self.min_samples_for_training:
                logger.warning("Not enough data for LightGBM training")
                return {"status": "skipped", "reason": "insufficient_data"}
            
            # 执行增量训练
            result = await self.lightgbm_trainer.incremental_train(training_data)
            
            # 更新模型版本
            new_version = self.model_manager.bump_version("lightgbm")
            result["version"] = new_version
            
            logger.info(f"LightGBM training complete: version={new_version}, "
                       f"accuracy={result.get('accuracy', 0):.3f}")
            
            return result
        
        except Exception as e:
            logger.error(f"LightGBM training error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _finetune_informer(self) -> Dict:
        """Informer微调"""
        try:
            logger.info("Fine-tuning Informer...")
            
            # 准备时序数据
            timeseries_data = self.informer_tuner.prepare_timeseries_data(
                list(self.trade_history)
            )
            
            if len(timeseries_data) < 50:
                logger.warning("Not enough data for Informer fine-tuning")
                return {"status": "skipped", "reason": "insufficient_data"}
            
            # 执行微调
            result = await self.informer_tuner.finetune(timeseries_data)
            
            # 更新模型版本
            new_version = self.model_manager.bump_version("informer")
            result["version"] = new_version
            
            logger.info(f"Informer fine-tuning complete: version={new_version}, "
                       f"mse={result.get('mse', 0):.4f}")
            
            return result
        
        except Exception as e:
            logger.error(f"Informer fine-tuning error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _train_ppo(self) -> Dict:
        """PPO+LSTM训练"""
        try:
            logger.info("Training PPO+LSTM...")
            
            # 准备RL经验数据
            if not self.ppo_trainer.has_enough_experiences():
                logger.warning("Not enough experiences for PPO training")
                return {"status": "skipped", "reason": "insufficient_experiences"}
            
            # 执行训练
            result = await self.ppo_trainer.train()
            
            # 更新模型版本
            new_version = self.model_manager.bump_version("ppo")
            result["version"] = new_version
            
            logger.info(f"PPO training complete: version={new_version}, "
                       f"policy_improvement={result.get('policy_improvement', 0):.4f}")
            
            return result
        
        except Exception as e:
            logger.error(f"PPO training error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _train_gnn(self) -> Dict:
        """Temporal GNN训练"""
        try:
            logger.info("Training Temporal GNN...")
            
            # 准备图数据
            graph_data = self.gnn_trainer.prepare_graph_data(
                list(self.trade_history)
            )
            
            if len(graph_data["nodes"]) < 10:
                logger.warning("Not enough data for GNN training")
                return {"status": "skipped", "reason": "insufficient_data"}
            
            # 执行训练
            result = await self.gnn_trainer.train(graph_data)
            
            # 更新模型版本
            new_version = self.model_manager.bump_version("gnn")
            result["version"] = new_version
            
            logger.info(f"GNN training complete: version={new_version}, "
                       f"correlation_improvement={result.get('correlation_improvement', 0):.4f}")
            
            return result
        
        except Exception as e:
            logger.error(f"GNN training error: {e}")
            return {"status": "error", "error": str(e)}
    
    def _publish_model_updates(self, updates: Dict[str, Dict]):
        """发布模型更新"""
        message = {
            "update_type": "strategy_weights",
            "timestamp": generate_timestamp(),
            "lightgbm_update": updates.get("lightgbm", {}),
            "informer_update": updates.get("informer", {}),
            "ppo_update": updates.get("ppo", {}),
            "gnn_update": updates.get("gnn", {}),
        }
        
        self.bus.send("am-hk-model-updates", "all", message)
        self.bus.flush()
        
        logger.info(f"Published model updates to am-hk-model-updates")
    
    def _publish_kelly_update(self, kelly_result: Dict):
        """发布凯利公式优化结果"""
        message = {
            "update_type": "kelly_optimization",
            "timestamp": generate_timestamp(),
            "kelly_optimization": kelly_result,
        }
        
        self.bus.send("am-hk-model-updates", "all", message)
        self.bus.flush()
    
    def _publish_evaluation_results(self, results: Dict):
        """发布评估结果"""
        message = {
            "update_type": "model_evaluation",
            "timestamp": generate_timestamp(),
            "evaluation_results": results,
        }
        
        self.bus.send("am-hk-model-updates", "all", message)
        self.bus.flush()
    
    def _publish_status(self, state: str):
        """发布Agent状态"""
        status = {
            "state": state,
            "models": list(self.model_manager.get_current_versions().keys()),
            "history_size": len(self.trade_history),
            "performance": self.performance_stats,
        }
        self.bus.publish_status(status)
    
    async def _load_trade_history(self):
        """加载历史交易数据"""
        try:
            # TODO: 从数据库加载历史数据
            logger.info("Loading trade history...")
            # 模拟加载数据
            logger.info(f"Loaded {len(self.trade_history)} historical trades")
        except Exception as e:
            logger.error(f"Failed to load trade history: {e}")
    
    async def _save_trade_history(self):
        """保存交易历史"""
        try:
            # TODO: 持久化到数据库
            logger.info(f"Saving {len(self.trade_history)} trade records")
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")


if __name__ == "__main__":
    learning = LearningFeedback()
    asyncio.run(learning.start())
