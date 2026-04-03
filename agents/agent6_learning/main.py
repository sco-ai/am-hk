"""
Agent 6: LearningFeedback
学习反馈与进化引擎
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional

from core.kafka import MessageBus, AgentConsumer
from core.models import TradeDecision, Signal, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

logger = setup_logging("agent6_learning")


class LearningFeedback:
    """
    Agent 6: 学习反馈与进化引擎
    
    职责：
    - 交易结果记录与分析
    - 策略优化（GPT-4.1）
    - 因子训练（LightGBM云训练）
    - RL训练（PPO Ray RLlib）
    - GNN训练（市场联动）
    - 情绪分析模型训练（FinBERT）
    
    模型：
    - 策略优化：GPT-4.1 / DeepSeek
    - 因子训练：LightGBM（云训练）
    - RL训练：PPO（Ray RLlib）
    - GNN：Temporal GNN（云GPU）
    - 情绪分析：FinBERT API
    """
    
    def __init__(self):
        self.agent_name = "agent6_learning"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-executions", "am-hk-feedback", "am-hk-signals"]
        )
        
        # 交易历史
        self.trade_history: List[Dict] = []
        self.max_history_size = 10000
        
        # 模型版本
        self.model_versions = {
            "factor_model": "v1.0",
            "rl_model": "v1.0",
            "gnn_model": "v1.0",
            "sentiment_model": "v1.0",
        }
        
        # 学习配置
        self.learning_interval = 3600  # 每小时学习一次
        self.min_samples_for_training = 100
        
        # 性能指标
        self.performance_metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
        }
        
        self.running = False
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动学习引擎"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("execution_order", self._on_execution)
        self.consumer.register_handler("execution_rejected", self._on_rejection)
        self.consumer.register_handler("signal", self._on_signal_feedback)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "models": list(self.model_versions.keys()),
            "history_size": len(self.trade_history),
        })
        
        # 启动定时学习任务
        learning_task = asyncio.create_task(self._learning_loop())
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            learning_task.cancel()
            await self.stop()
    
    async def stop(self):
        """停止学习引擎"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        # 保存历史数据
        await self._save_history()
        
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_execution(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理执行结果"""
        try:
            payload = value.get("payload", {})
            decision_data = payload.get("decision", {})
            decision = TradeDecision(**decision_data)
            
            # 记录交易
            trade_record = {
                "msg_id": value.get("msg_id"),
                "timestamp": generate_timestamp(),
                "symbol": decision.signal.symbol,
                "action": decision.signal.action.value,
                "position_size": decision.position_size,
                "confidence": decision.signal.confidence,
                "predicted_return": decision.signal.predicted_return,
                "approved": True,
                "factors": decision.signal.metadata.get("factors", {}),
            }
            
            self._add_trade_record(trade_record)
            
            logger.info(f"Recorded executed trade: {decision.signal.symbol} "
                       f"action={decision.signal.action.value}")
        
        except Exception as e:
            logger.error(f"Error processing execution: {e}", exc_info=True)
    
    def _on_rejection(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理被拒绝的交易"""
        try:
            payload = value.get("payload", {})
            decision_data = payload.get("decision", {})
            reason = payload.get("reason", "unknown")
            
            # 记录被拒绝的交易（用于学习）
            rejection_record = {
                "msg_id": value.get("msg_id"),
                "timestamp": generate_timestamp(),
                "symbol": decision_data.get("signal", {}).get("symbol"),
                "action": decision_data.get("signal", {}).get("action"),
                "rejection_reason": reason,
                "confidence": decision_data.get("signal", {}).get("confidence"),
            }
            
            self._add_trade_record(rejection_record)
            
            logger.info(f"Recorded rejected trade: {rejection_record['symbol']} "
                       f"reason={reason}")
        
        except Exception as e:
            logger.error(f"Error processing rejection: {e}", exc_info=True)
    
    def _on_signal_feedback(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理信号反馈（后续盈亏数据）"""
        # TODO: 接入实际盈亏数据，计算信号准确性
        pass
    
    def _add_trade_record(self, record: Dict):
        """添加交易记录"""
        self.trade_history.append(record)
        
        # 限制历史大小
        if len(self.trade_history) > self.max_history_size:
            self.trade_history = self.trade_history[-self.max_history_size:]
        
        # 更新统计
        self.performance_metrics["total_trades"] += 1
    
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
    
    async def _run_learning_cycle(self):
        """执行学习周期"""
        logger.info("=" * 50)
        logger.info("Starting learning cycle...")
        
        # 1. 性能分析
        await self._analyze_performance()
        
        # 2. 策略优化（GPT-4.1）
        await self._optimize_strategy()
        
        # 3. 因子模型训练（LightGBM）
        await self._train_factor_model()
        
        # 4. RL模型训练（PPO）
        await self._train_rl_model()
        
        # 5. 模型更新通知
        await self._publish_model_updates()
        
        logger.info("Learning cycle completed")
        logger.info("=" * 50)
    
    async def _analyze_performance(self):
        """分析交易性能"""
        logger.info("Analyzing performance...")
        
        if not self.trade_history:
            return
        
        # 计算基础指标
        total = len(self.trade_history)
        approved = sum(1 for t in self.trade_history if t.get("approved", False))
        rejected = total - approved
        
        # 胜率（假设有实际结果字段）
        # TODO: 接入实际盈亏数据
        
        self.performance_metrics.update({
            "total_trades": total,
            "approval_rate": approved / total if total > 0 else 0,
        })
        
        logger.info(f"Performance: total={total}, approved={approved}, "
                   f"rejected={rejected}, approval_rate={self.performance_metrics['approval_rate']:.2%}")
    
    async def _optimize_strategy(self):
        """
        策略优化（GPT-4.1）
        
        分析交易历史，生成策略优化建议
        """
        logger.info("Optimizing strategy with LLM...")
        
        # 准备数据摘要
        recent_trades = self.trade_history[-100:]  # 最近100笔
        
        # 构造prompt
        prompt = self._build_strategy_prompt(recent_trades)
        
        # TODO: 调用GPT-4.1 API
        # response = await self._call_openai(prompt)
        
        # 模拟优化建议
        optimization = {
            "suggestions": [
                "提高动量因子权重",
                "降低高波动时段的交易频率",
                "增加成交量确认条件",
            ],
            "confidence": 0.75,
        }
        
        logger.info(f"Strategy optimization: {len(optimization['suggestions'])} suggestions")
        
        # 保存优化建议
        await self._save_optimization(optimization)
    
    def _build_strategy_prompt(self, trades: List[Dict]) -> str:
        """构造策略优化prompt"""
        prompt = """
你是一位量化交易策略优化专家。请分析以下交易数据并提供优化建议：

最近交易统计：
"""
        # 汇总数据
        symbols = {}
        for t in trades:
            sym = t.get("symbol", "unknown")
            if sym not in symbols:
                symbols[sym] = {"count": 0, "actions": []}
            symbols[sym]["count"] += 1
            symbols[sym]["actions"].append(t.get("action"))
        
        for sym, stats in symbols.items():
            prompt += f"- {sym}: {stats['count']}笔交易\n"
        
        prompt += f"\n总交易数: {len(trades)}\n"
        prompt += "\n请提供：\n1. 当前策略的问题\n2. 具体优化建议\n3. 预期改进效果\n"
        
        return prompt
    
    async def _train_factor_model(self):
        """
        训练因子模型（LightGBM云训练）
        
        TODO: 接入云训练平台
        """
        logger.info("Training factor model (LightGBM)...")
        
        # 准备训练数据
        training_data = self._prepare_training_data()
        
        if len(training_data) < self.min_samples_for_training:
            logger.warning("Not enough data for factor model training")
            return
        
        # TODO: 提交云训练任务
        # job_id = await self._submit_cloud_training("lightgbm", training_data)
        
        logger.info(f"Factor model training prepared with {len(training_data)} samples")
        
        # 更新版本
        self.model_versions["factor_model"] = "v1.1"
    
    def _prepare_training_data(self) -> List[Dict]:
        """准备训练数据"""
        # 提取特征和标签
        data = []
        for trade in self.trade_history:
            if "factors" in trade:
                data.append({
                    "features": trade["factors"],
                    "label": 1 if trade.get("approved") else 0,
                    "confidence": trade.get("confidence", 0),
                })
        return data
    
    async def _train_rl_model(self):
        """
        训练RL模型（PPO Ray RLlib）
        
        TODO: 接入Ray RLlib云训练
        """
        logger.info("Training RL model (PPO)...")
        
        # 构建环境数据
        env_data = self._build_rl_environment()
        
        if len(env_data) < self.min_samples_for_training:
            logger.warning("Not enough data for RL training")
            return
        
        # TODO: 启动Ray RLlib训练
        # trainer = await self._start_rl_training(env_data)
        
        logger.info(f"RL training prepared with {len(env_data)} episodes")
        
        # 更新版本
        self.model_versions["rl_model"] = "v1.1"
    
    def _build_rl_environment(self) -> List[Dict]:
        """构建RL环境数据"""
        episodes = []
        # 按交易对分组
        symbol_trades = {}
        for trade in self.trade_history:
            sym = trade.get("symbol")
            if sym not in symbol_trades:
                symbol_trades[sym] = []
            symbol_trades[sym].append(trade)
        
        # 构建episode
        for sym, trades in symbol_trades.items():
            if len(trades) >= 10:
                episodes.append({
                    "symbol": sym,
                    "trades": trades,
                })
        
        return episodes
    
    async def _publish_model_updates(self):
        """发布模型更新通知"""
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "model_update",
            "source_agent": self.agent_name,
            "timestamp": generate_timestamp(),
            "payload": {
                "model_versions": self.model_versions,
                "performance": self.performance_metrics,
            },
        }
        
        self.bus.send("am-hk-model-updates", "all", message)
        self.bus.flush()
        
        logger.info(f"Published model updates: {self.model_versions}")
    
    async def _save_history(self):
        """保存历史数据"""
        try:
            # TODO: 持久化到数据库
            logger.info(f"Saving {len(self.trade_history)} trade records")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    async def _save_optimization(self, optimization: Dict):
        """保存优化建议"""
        # TODO: 保存到数据库
        logger.info(f"Saved optimization: {optimization}")


if __name__ == "__main__":
    learning = LearningFeedback()
    asyncio.run(learning.start())
