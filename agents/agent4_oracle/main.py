"""
Agent 4: TrendOracle
核心决策层 - 时间序列预测 + 强化学习 + LLM
P2阶段: 增加飞书交互功能
"""
import asyncio
import logging
import json
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime

from core.ai_models import ModelFactory
from core.config import settings
from core.kafka import MessageBus, AgentConsumer
from core.models import Signal, TradeDecision, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

logger = setup_logging("agent4_oracle")


class FeishuNotifier:
    """飞书通知器 - P2阶段新增"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def send_trade_decision(self, decision: TradeDecision, 
                                   predictions: Dict, 
                                   analysis: Dict) -> bool:
        """发送交易决策到飞书"""
        if not self.enabled:
            return False
        
        try:
            # 构建飞书卡片消息
            card = self._build_decision_card(decision, predictions, analysis)
            
            session = await self._get_session()
            async with session.post(self.webhook_url, json=card) as resp:
                result = await resp.json()
                if result.get("code") == 0:
                    logger.info("✅ Feishu notification sent successfully")
                    return True
                else:
                    logger.error(f"❌ Feishu API error: {result}")
                    return False
        
        except Exception as e:
            logger.error(f"❌ Failed to send Feishu notification: {e}")
            return False
    
    def _build_decision_card(self, decision: TradeDecision, 
                             predictions: Dict, 
                             analysis: Dict) -> Dict:
        """构建飞书卡片消息"""
        signal = decision.signal
        action_emoji = {
            "buy": "🟢",
            "sell": "🔴", 
            "hold": "⚪"
        }.get(signal.action.value, "⚪")
        
        # 预测方向
        pred_direction = ""
        for tf, pred in predictions.items():
            direction = pred.get("direction", "unknown")
            emoji = {"up": "📈", "down": "📉", "sideways": "➡️"}.get(direction, "❓")
            pred_direction += f"{tf}: {emoji} "
        
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"{action_emoji} {signal.symbol} 交易决策"
                    },
                    "template": "blue" if signal.action.value == "buy" else "red" if signal.action.value == "sell" else "gray"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**市场:** {signal.market.value}\n"
                                      f"**动作:** {signal.action.value.upper()}\n"
                                      f"**置信度:** {signal.confidence:.1%}\n"
                                      f"**预测:** {pred_direction}"
                        }
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**仓位:** {decision.position_size:.2%}\n"
                                      f"**止损:** {decision.stop_loss:.2%}\n"
                                      f"**止盈:** {decision.take_profit:.2%}\n"
                                      f"**风险分:** {decision.risk_score:.2f}"
                        }
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**AI分析:**\n{analysis.get('recommendation', 'N/A')}"
                        }
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Agent4 TrendOracle"
                            }
                        ]
                    }
                ]
            }
        }
        return card
    
    async def send_alert(self, title: str, content: str, level: str = "info") -> bool:
        """发送告警消息"""
        if not self.enabled:
            return False
        
        template = {
            "info": "blue",
            "warning": "orange",
            "error": "red"
        }.get(level, "blue")
        
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": template
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": content}
                    }
                ]
            }
        }
        
        try:
            session = await self._get_session()
            async with session.post(self.webhook_url, json=card) as resp:
                result = await resp.json()
                return result.get("code") == 0
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()


class TrendOracle:
    """
    Agent 4: 趋势预测与决策核心
    
    职责：
    - 时间序列预测（Informer / N-HiTS）
    - 强化学习交易决策（PPO）
    - AI生成交易指令（GPT-4.1）
    - 仓位计算（Kelly + RL）
    - 多时间框架预测（5min/15min/1h）
    - P2: 飞书实时通知
    """
    
    def __init__(self):
        self.agent_name = "agent4_oracle"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-signals"]
        )
        
        # P2: 初始化飞书通知器
        feishu_webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/232a1c2e-a862-4f8c-88ae-0a60c9d837d6"
        self.feishu = FeishuNotifier(feishu_webhook)
        
        # 时间框架配置
        self.timeframes = ["5min", "15min", "1h"]
        self.prediction_horizon = {
            "5min": 5,
            "15min": 15,
            "1h": 60,
        }
        
        # AI模型实例
        self.informer = ModelFactory.get_informer()
        self.nhits = ModelFactory.get_nhits()
        self.rl_model = ModelFactory.get_rl_model()
        self.llm = ModelFactory.get_llm_analyzer()
        
        # 配置开关
        self.use_informer = settings.ai_model_enabled("informer")
        self.use_nhits = settings.ai_model_enabled("n-hits")
        self.use_rl = settings.ai_model_enabled("rl")
        self.use_llm = settings.ai_model_enabled("openai") or settings.ai_model_enabled("deepseek")
        
        # 价格缓存（用于预测）
        self.price_cache: Dict[str, List[float]] = {}
        self.max_cache_size = 200
        
        logger.info(f"{self.agent_name} initialized")
        logger.info(f"Models enabled: informer={self.use_informer}, "
                   f"rl={self.use_rl}, llm={self.use_llm}")
        logger.info(f"Feishu notifier: enabled={self.feishu.enabled}")
    
    async def start(self):
        """启动决策核心"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 发送启动通知
        await self.feishu.send_alert(
            "🚀 Agent4 TrendOracle 已启动",
            "P2阶段: 飞书交互功能已启用\n实时交易决策将推送至此群组",
            "info"
        )
        
        # 注册消息处理器
        self.consumer.register_handler("signal", self._on_signal)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "models": {
                "informer": self.use_informer,
                "n-hits": self.use_nhits,
                "rl": self.use_rl,
                "llm": self.use_llm,
            },
            "timeframes": self.timeframes,
            "feishu_enabled": self.feishu.enabled,
        })
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
            await self.feishu.send_alert(
                "❌ Agent4 启动失败",
                f"错误: {str(e)[:200]}",
                "error"
            )
        finally:
            await self.stop()
    
    async def stop(self):
        """停止决策核心"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        # 发送停止通知
        await self.feishu.send_alert(
            "🛑 Agent4 TrendOracle 已停止",
            "决策核心已关闭",
            "warning"
        )
        
        # 关闭飞书 session
        await self.feishu.close()
        
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_signal(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易信号 - 同步包装"""
        asyncio.create_task(self._process_signal_async(key, value, headers))
    
    async def _process_signal_async(self, key: str, value: Dict, headers: Optional[Dict]):
        """异步处理交易信号"""
        try:
            payload = value.get("payload", {})
            signal = Signal(**payload)
            factors = payload.get("factors", {})
            
            logger.info(f"📊 Processing signal: {signal.symbol} {signal.action.value}")
            
            # 更新价格缓存
            await self._update_price_cache(signal.symbol, factors)
            
            # Step 1: 时间序列预测（Informer）
            predictions = await self._predict_price(signal)
            
            # Step 2: 强化学习决策
            rl_decision = await self._rl_decision(signal, predictions, factors)
            
            # Step 3: LLM生成推理
            llm_analysis = await self._llm_analysis(signal, predictions, rl_decision, factors)
            
            # Step 4: 融合决策
            decision = self._make_decision(signal, predictions, rl_decision, llm_analysis)
            
            # Step 5: 仓位计算
            position = self._calculate_position(decision, rl_decision)
            
            # 构造交易决策
            trade_decision = TradeDecision(
                signal=signal,
                position_size=position["size"],
                stop_loss=position["stop_loss"],
                take_profit=position["take_profit"],
                risk_score=position["risk_score"],
                approved=False,
                approval_reason="",
            )
            
            # 发布决策
            self._publish_decision(trade_decision, predictions, llm_analysis)
            
            # P2: 发送到飞书
            await self.feishu.send_trade_decision(trade_decision, predictions, llm_analysis)
            
            logger.info(f"✅ Decision: {signal.symbol} | "
                       f"action={signal.action.value} | "
                       f"position={position['size']:.2%} | "
                       f"risk={position['risk_score']:.2f}")
        
        except Exception as e:
            logger.error(f"❌ Error processing signal: {e}", exc_info=True)
            # P2: 发送错误告警
            await self.feishu.send_alert(
                f"❌ {signal.symbol} 决策失败",
                f"错误: {str(e)[:500]}",
                "error"
            )
    
    async def _update_price_cache(self, symbol: str, factors: Dict):
        """更新价格缓存"""
        if "close" in factors:
            price = factors["close"]
        elif "price" in factors:
            price = factors["price"]
        else:
            return
        
        if symbol not in self.price_cache:
            self.price_cache[symbol] = []
        
        self.price_cache[symbol].append(float(price))
        
        # 限制缓存大小
        if len(self.price_cache[symbol]) > self.max_cache_size:
            self.price_cache[symbol] = self.price_cache[symbol][-self.max_cache_size:]
    
    async def _predict_price(self, signal: Signal) -> Dict[str, Dict]:
        """
        时间序列预测
        
        使用Informer模型进行多时间框架预测
        """
        predictions = {}
        prices = self.price_cache.get(signal.symbol, [])
        
        if len(prices) < 60:
            logger.warning(f"Insufficient price data for {signal.symbol}: {len(prices)} points")
            return self._empty_predictions()
        
        for tf in self.timeframes:
            try:
                horizon = self.prediction_horizon[tf]
                
                # 调用Informer API
                result = await self.informer.predict({
                    "symbol": signal.symbol,
                    "prices": prices,
                    "prediction_length": horizon,
                })
                
                predictions[tf] = {
                    "pred_prices": result.get("predictions", []),
                    "confidence": result.get("confidence", 0.5),
                    "direction": self._determine_direction(result.get("predictions", []), prices[-1]),
                    "source": result.get("source", "informer"),
                }
                
                logger.debug(f"Prediction {tf}: {predictions[tf]['direction']} "
                            f"conf={predictions[tf]['confidence']:.2%}")
            
            except Exception as e:
                logger.error(f"Prediction failed for {tf}: {e}")
                predictions[tf] = {
                    "pred_prices": [],
                    "confidence": 0.0,
                    "direction": "unknown",
                    "source": "error",
                }
        
        return predictions
    
    def _empty_predictions(self) -> Dict[str, Dict]:
        """空预测结果"""
        return {
            tf: {"pred_prices": [], "confidence": 0, "direction": "unknown", "source": "empty"}
            for tf in self.timeframes
        }
    
    def _determine_direction(self, predictions: List[float], current_price: float) -> str:
        """确定预测方向"""
        if not predictions or current_price == 0:
            return "unknown"
        
        avg_pred = sum(predictions) / len(predictions)
        change = (avg_pred - current_price) / current_price
        
        if change > 0.005:
            return "up"
        elif change < -0.005:
            return "down"
        else:
            return "sideways"
    
    async def _rl_decision(self, signal: Signal, predictions: Dict, factors: Dict) -> Dict:
        """
        强化学习决策
        
        使用PPO模型输出交易动作和仓位比例
        """
        try:
            # 构建状态
            state = self._build_rl_state(signal, predictions, factors)
            
            # 调用RL模型
            result = await self.rl_model.predict({
                "state": state,
                "available_actions": ["buy", "sell", "hold"],
            })
            
            return {
                "action": result.get("action", signal.action.value),
                "confidence": result.get("action_prob", 0.5),
                "position_ratio": result.get("position_ratio", 0.05),
                "value_estimate": result.get("value_estimate", 0),
                "source": result.get("source", "rl"),
            }
        
        except Exception as e:
            logger.error(f"RL decision failed: {e}")
            return self._fallback_rl_decision(signal, predictions)
    
    def _build_rl_state(self, signal: Signal, predictions: Dict, factors: Dict) -> Dict:
        """构建RL状态向量"""
        return {
            "trend": factors.get("mom_5m", 0) / 100,
            "volatility": factors.get("volatility_5m", 0) / 100,
            "rsi": (factors.get("rsi", 50) - 50) / 50,
            "macd": factors.get("macd", 0),
            "volume_ratio": factors.get("volume_ma_ratio", 1) - 1,
            "prediction_confidence": sum(p.get("confidence", 0) for p in predictions.values()) / len(predictions) if predictions else 0,
        }
    
    def _fallback_rl_decision(self, signal: Signal, predictions: Dict) -> Dict:
        """RL fallback决策"""
        confidences = [p.get("confidence", 0) for p in predictions.values() if p.get("confidence", 0) > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
        
        # 基于置信度确定仓位
        if avg_conf > 0.7:
            ratio = 0.08
        elif avg_conf > 0.6:
            ratio = 0.05
        else:
            ratio = 0.03
        
        return {
            "action": signal.action.value,
            "confidence": avg_conf,
            "position_ratio": ratio,
            "value_estimate": 0,
            "source": "fallback_rule",
        }
    
    async def _llm_analysis(self, signal: Signal, predictions: Dict, 
                           rl_decision: Dict, factors: Dict) -> Dict:
        """
        LLM深度分析
        
        使用GPT-4.1生成交易分析和建议
        """
        if not self.use_llm:
            return self._fallback_analysis(signal, predictions, factors)
        
        try:
            # 构建市场数据
            market_data = {
                "current_price": self.price_cache.get(signal.symbol, [0])[-1],
                "factors": factors,
            }
            
            # 调用LLM分析
            analysis = await self.llm.analyze_trading_opportunity(
                symbol=signal.symbol,
                market_data=market_data,
                predictions=predictions,
                factors=factors,
            )
            
            return analysis
        
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_analysis(signal, predictions, factors)
    
    def _fallback_analysis(self, signal: Signal, predictions: Dict, factors: Dict) -> Dict:
        """Fallback分析"""
        buy_count = sum(1 for p in predictions.values() if p.get("direction") == "up")
        sell_count = sum(1 for p in predictions.values() if p.get("direction") == "down")
        
        if buy_count > sell_count:
            rec = "看涨，建议买入"
            level = "medium"
        elif sell_count > buy_count:
            rec = "看跌，建议卖出"
            level = "medium"
        else:
            rec = "方向不明，观望"
            level = "low"
        
        return {
            "recommendation": rec,
            "confidence": 0.5,
            "reasoning": signal.reasoning,
            "risk_level": level,
            "risk_factors": ["模型API不可用"],
            "key_levels": {},
            "source": "fallback",
        }
    
    def _make_decision(self, signal: Signal, predictions: Dict, 
                       rl_decision: Dict, llm_analysis: Dict) -> Dict:
        """融合所有模型做出最终决策"""
        # 综合置信度
        model_conf = rl_decision.get("confidence", 0.5)
        llm_conf = llm_analysis.get("confidence", 0.5)
        signal_conf = signal.confidence
        
        # 加权平均
        combined_conf = (signal_conf * 0.3 + model_conf * 0.4 + llm_conf * 0.3)
        
        return {
            "symbol": signal.symbol,
            "market": signal.market.value,
            "action": signal.action.value,
            "confidence": combined_conf,
            "predictions": predictions,
            "rl_decision": rl_decision,
            "llm_analysis": llm_analysis,
        }
    
    def _calculate_position(self, decision: Dict, rl_decision: Dict) -> Dict:
        """仓位计算（Kelly + RL融合）"""
        confidence = decision.get("confidence", 0.5)
        rl_ratio = rl_decision.get("position_ratio", 0.05)
        
        # Kelly公式
        win_prob = confidence
        loss_prob = 1 - win_prob
        kelly = (2 * win_prob - loss_prob) / 2  # 假设赔率2:1
        kelly = max(0, min(kelly, 0.25))
        
        # 半Kelly + RL融合
        position_size = min(rl_ratio, kelly * 0.5)
        position_size = min(position_size, 0.1)  # 最大10%
        
        # 动态止盈止损
        volatility = decision.get("predictions", {}).get("5min", {}).get("confidence", 0.5)
        stop_loss = 0.015 + (1 - volatility) * 0.015  # 1.5% - 3%
        take_profit = stop_loss * 2.5  # 盈亏比2.5:1
        
        return {
            "size": position_size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_score": 1 - confidence,
            "kelly_fraction": kelly,
        }
    
    def _publish_decision(self, decision: TradeDecision, predictions: Dict, analysis: Dict):
        """发布交易决策"""
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "trade_decision",
            "source_agent": self.agent_name,
            "target_agent": "agent5_guardian",
            "timestamp": generate_timestamp(),
            "priority": 2,
            "payload": {
                "decision": decision.dict(),
                "predictions": predictions,
                "analysis": analysis,
            },
        }
        
        self.bus.publish_decision(message)
        self.bus.flush()


if __name__ == "__main__":
    oracle = TrendOracle()
    asyncio.run(oracle.start())
