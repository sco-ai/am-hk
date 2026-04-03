"""
Agent 3: AlphaScanner
交易机会扫描器
"""
import asyncio
import logging
from typing import Dict, List, Optional

from core.kafka import MessageBus, AgentConsumer
from core.models import Signal, MarketType, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

logger = setup_logging("agent3_scanner")


class AlphaScanner:
    """
    Agent 3: 交易机会扫描器
    
    职责：
    - 多策略扫描
    - Top机会筛选
    - 因子评分
    - 策略优化
    
    模型：
    - 因子评分：LightGBM（云训练）
    - 策略优化：GPT-4.1
    """
    
    def __init__(self):
        self.agent_name = "agent3_scanner"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-factor-data"]
        )
        
        # 机会阈值
        self.opportunity_threshold = 0.6  # 置信度阈值
        self.top_n = 3  # 只选Top 3机会
        
        # 候选信号缓存
        self.candidate_signals: List[Dict] = []
        
        self.running = False
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动扫描器"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("factor_data", self._on_factor_data)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "threshold": self.opportunity_threshold,
        })
        
        # 启动定时扫描任务
        scan_task = asyncio.create_task(self._scan_loop())
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            scan_task.cancel()
            await self.stop()
    
    async def stop(self):
        """停止扫描器"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_factor_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理因子数据"""
        try:
            symbol = value.get("symbol")
            market = value.get("market")
            factors = value.get("factors", {})
            
            # 计算信号得分
            score = self._calculate_signal_score(factors)
            
            if score >= self.opportunity_threshold:
                # 生成候选信号
                signal = self._generate_candidate_signal(symbol, market, factors, score)
                self.candidate_signals.append(signal)
                
                # 限制缓存大小
                if len(self.candidate_signals) > 100:
                    self.candidate_signals = sorted(
                        self.candidate_signals,
                        key=lambda x: x["confidence"],
                        reverse=True
                    )[:50]
                
                logger.debug(f"Added candidate signal for {symbol}: score={score:.3f}")
        
        except Exception as e:
            logger.error(f"Error processing factor data: {e}", exc_info=True)
    
    async def _scan_loop(self):
        """定时扫描循环"""
        while self.running:
            try:
                await self._publish_top_signals()
                await asyncio.sleep(60)  # 每分钟扫描一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scan loop error: {e}", exc_info=True)
                await asyncio.sleep(10)
    
    async def _publish_top_signals(self):
        """发布Top信号"""
        if not self.candidate_signals:
            return
        
        # 按置信度排序，取Top N
        top_signals = sorted(
            self.candidate_signals,
            key=lambda x: x["confidence"],
            reverse=True
        )[:self.top_n]
        
        for signal in top_signals:
            # 构建完整信号
            full_signal = {
                "msg_id": generate_msg_id(),
                "msg_type": "signal",
                "source_agent": self.agent_name,
                "target_agent": "agent4_oracle",
                "timestamp": generate_timestamp(),
                "payload": signal,
                "priority": 3,  # 高优先级
            }
            
            # 发布信号
            self.bus.publish_signal(full_signal)
            
            logger.info(f"Published signal: {signal['symbol']} "
                       f"action={signal['action']} "
                       f"confidence={signal['confidence']:.3f}")
        
        # 清空候选列表
        self.candidate_signals = []
        self.bus.flush()
    
    def _calculate_signal_score(self, factors: Dict[str, float]) -> float:
        """
        计算信号得分（LightGBM预测）
        
        当前使用规则评分，后续接入云训练模型
        """
        if not factors:
            return 0.0
        
        score = 0.0
        weights = 0.0
        
        # 动量因子
        if "mom_5m" in factors:
            mom = factors["mom_5m"]
            score += min(abs(mom) / 2.0, 1.0) * 0.2
            weights += 0.2
        
        if "mom_15m" in factors:
            mom = factors["mom_15m"]
            score += min(abs(mom) / 3.0, 1.0) * 0.15
            weights += 0.15
        
        # RSI
        if "rsi" in factors:
            rsi = factors["rsi"]
            # RSI 超买超卖信号
            if rsi > 70 or rsi < 30:
                score += 0.15
            weights += 0.15
        
        # 波动率
        if "volatility_5m" in factors:
            vol = factors["volatility_5m"]
            score += min(vol / 50.0, 1.0) * 0.1
            weights += 0.1
        
        # MACD
        if "macd" in factors:
            macd = factors["macd"]
            score += min(abs(macd) / 1.0, 1.0) * 0.15
            weights += 0.15
        
        # 成交量
        if "volume_ma_ratio" in factors:
            vol_ratio = factors["volume_ma_ratio"]
            score += min(abs(vol_ratio - 1.0), 1.0) * 0.1
            weights += 0.1
        
        # EMA差异
        if "ema_diff" in factors:
            ema_diff = factors["ema_diff"]
            score += min(abs(ema_diff) / 0.5, 1.0) * 0.15
            weights += 0.15
        
        return score / weights if weights > 0 else 0.0
    
    def _generate_candidate_signal(self, symbol: str, market: str, 
                                   factors: Dict[str, float], score: float) -> Dict:
        """生成候选信号"""
        # 基于因子判断方向
        action = self._determine_action(factors)
        
        # 生成推理
        reasoning = self._generate_reasoning(symbol, factors, action)
        
        return {
            "symbol": symbol,
            "market": market,
            "action": action.value,
            "confidence": score,
            "predicted_return": self._estimate_return(factors),
            "timeframe": "15min",  # 默认15分钟
            "reasoning": reasoning,
            "agent_id": self.agent_name,
            "timestamp": generate_timestamp(),
            "factors": factors,  # 传递因子给Agent4
        }
    
    def _determine_action(self, factors: Dict[str, float]) -> ActionType:
        """确定操作方向"""
        score = 0.0
        
        # 动量方向
        if "mom_5m" in factors:
            score += factors["mom_5m"] * 0.3
        if "macd" in factors:
            score += factors["macd"] * 0.3
        if "ema_diff" in factors:
            score += factors["ema_diff"] * 0.2
        if "mom_15m" in factors:
            score += factors["mom_15m"] * 0.2
        
        if score > 0.5:
            return ActionType.BUY
        elif score < -0.5:
            return ActionType.SELL
        else:
            return ActionType.HOLD
    
    def _generate_reasoning(self, symbol: str, factors: Dict[str, float], 
                           action: ActionType) -> str:
        """生成推理说明"""
        reasons = []
        
        if "mom_5m" in factors and abs(factors["mom_5m"]) > 1.0:
            reasons.append(f"5分钟动量: {factors['mom_5m']:+.2f}%")
        
        if "rsi" in factors:
            rsi = factors["rsi"]
            if rsi > 70:
                reasons.append(f"RSI超买: {rsi:.1f}")
            elif rsi < 30:
                reasons.append(f"RSI超卖: {rsi:.1f}")
        
        if "macd" in factors:
            reasons.append(f"MACD: {factors['macd']:+.3f}")
        
        if "volume_ma_ratio" in factors:
            ratio = factors["volume_ma_ratio"]
            if ratio > 1.5:
                reasons.append(f"成交量放大: {ratio:.1f}x")
        
        reasoning = f"[{action.value.upper()}] " + "; ".join(reasons)
        return reasoning
    
    def _estimate_return(self, factors: Dict[str, float]) -> float:
        """预估收益率"""
        # 基于历史回测的简单预估
        if "mom_5m" in factors and "mom_15m" in factors:
            return (factors["mom_5m"] + factors["mom_15m"]) / 2
        return 0.0
    
    async def _optimize_with_llm(self, signals: List[Dict]) -> List[Dict]:
        """
        使用GPT-4.1优化信号
        
        TODO: 接入OpenAI API进行策略优化
        """
        # 目前直接返回，后续接入LLM优化
        return signals


if __name__ == "__main__":
    scanner = AlphaScanner()
    asyncio.run(scanner.start())
