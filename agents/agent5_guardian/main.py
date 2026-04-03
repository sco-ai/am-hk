"""
Agent 5: RiskGuardian
风控守卫者
"""
import asyncio
import logging
from typing import Dict, List, Optional

from core.kafka import MessageBus, AgentConsumer
from core.models import TradeDecision, Signal, ActionType
from core.utils import generate_msg_id, generate_timestamp, setup_logging

logger = setup_logging("agent5_guardian")


class RiskGuardian:
    """
    Agent 5: 风控审批中心
    
    职责：
    - 审批所有交易决策
    - 风控规则执行
    - 异常检测
    - 仓位限制检查
    
    模型：
    - 风控规则：参数化规则
    - 异常检测：Isolation Forest API
    - AI风控：GPT-4.1 / Claude
    """
    
    def __init__(self):
        self.agent_name = "agent5_guardian"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-decisions"]
        )
        
        # 风控配置
        self.max_position_size = 0.1  # 最大10%仓位
        self.max_daily_loss = 0.05    # 最大日亏损5%
        self.max_drawdown = 0.15      # 最大回撤15%
        self.min_confidence = 0.5     # 最小置信度50%
        
        # 持仓状态
        self.positions: Dict[str, Dict] = {}
        self.daily_stats = {
            "trades_count": 0,
            "total_pnl": 0.0,
            "max_loss": 0.0,
        }
        
        # 风险黑名单
        self.blacklist: List[str] = []
        
        self.running = False
        logger.info(f"{self.agent_name} initialized")
    
    async def start(self):
        """启动风控中心"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("trade_decision", self._on_decision)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "rules": [
                "max_position_size_10%",
                "max_daily_loss_5%",
                "min_confidence_50%",
            ],
        })
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def stop(self):
        """停止风控中心"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        self.bus.publish_status({"state": "stopped"})
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_decision(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理交易决策"""
        try:
            payload = value.get("payload", {})
            decision_data = payload.get("decision", {})
            decision = TradeDecision(**decision_data)
            
            logger.info(f"Reviewing decision: {decision.signal.symbol} "
                       f"action={decision.signal.action.value}")
            
            # 执行风控检查
            checks = self._run_risk_checks(decision)
            
            # 异常检测
            anomaly_score = self._detect_anomaly(decision)
            
            # AI风控审查
            ai_review = self._ai_risk_review(decision, checks, anomaly_score)
            
            # 综合审批
            approved, reason = self._make_decision(checks, anomaly_score, ai_review)
            
            # 更新决策状态
            decision.approved = approved
            decision.approval_reason = reason
            
            # 发布执行指令
            if approved:
                self._publish_execution(decision)
                logger.info(f"✅ Approved: {decision.signal.symbol} - {reason}")
            else:
                self._publish_rejection(decision)
                logger.warning(f"❌ Rejected: {decision.signal.symbol} - {reason}")
        
        except Exception as e:
            logger.error(f"Error processing decision: {e}", exc_info=True)
    
    def _run_risk_checks(self, decision: TradeDecision) -> List[Dict]:
        """执行风控规则检查"""
        checks = []
        
        signal = decision.signal
        symbol = signal.symbol
        
        # 检查1: 置信度
        check1 = {
            "name": "confidence_check",
            "passed": signal.confidence >= self.min_confidence,
            "value": signal.confidence,
            "threshold": self.min_confidence,
        }
        checks.append(check1)
        
        # 检查2: 仓位限制
        current_position = self.positions.get(symbol, {}).get("size", 0)
        new_position = current_position + decision.position_size
        check2 = {
            "name": "position_limit",
            "passed": new_position <= self.max_position_size,
            "current": current_position,
            "new": new_position,
            "limit": self.max_position_size,
        }
        checks.append(check2)
        
        # 检查3: 日亏损限制
        check3 = {
            "name": "daily_loss_limit",
            "passed": abs(self.daily_stats["max_loss"]) < self.max_daily_loss,
            "current_loss": self.daily_stats["max_loss"],
            "limit": self.max_daily_loss,
        }
        checks.append(check3)
        
        # 检查4: 风险评分
        check4 = {
            "name": "risk_score",
            "passed": decision.risk_score < 0.7,  # 风险评分<0.7通过
            "score": decision.risk_score,
            "threshold": 0.7,
        }
        checks.append(check4)
        
        # 检查5: 黑名单
        check5 = {
            "name": "blacklist_check",
            "passed": symbol not in self.blacklist,
            "symbol": symbol,
        }
        checks.append(check5)
        
        # 检查6: 止盈止损合理性
        check6 = {
            "name": "stop_profit_loss_ratio",
            "passed": decision.take_profit / decision.stop_loss >= 2.0,  # 盈亏比>2
            "tp": decision.take_profit,
            "sl": decision.stop_loss,
            "ratio": decision.take_profit / decision.stop_loss if decision.stop_loss > 0 else 0,
        }
        checks.append(check6)
        
        return checks
    
    def _detect_anomaly(self, decision: TradeDecision) -> float:
        """
        异常检测
        
        Returns:
            异常分数 (0-1, 越高越异常)
        """
        # TODO: 调用Isolation Forest API
        # 当前使用规则检测
        
        anomaly_score = 0.0
        
        # 异常1: 过大仓位
        if decision.position_size > self.max_position_size * 0.8:
            anomaly_score += 0.3
        
        # 异常2: 风险过高
        if decision.risk_score > 0.8:
            anomaly_score += 0.3
        
        # 异常3: 置信度过低
        if decision.signal.confidence < 0.6:
            anomaly_score += 0.2
        
        # 异常4: 频繁交易
        if self.daily_stats["trades_count"] > 50:
            anomaly_score += 0.2
        
        return min(anomaly_score, 1.0)
    
    def _ai_risk_review(self, decision: TradeDecision, 
                        checks: List[Dict], anomaly_score: float) -> Dict:
        """
        AI风控审查
        
        TODO: 接入GPT-4.1进行深度分析
        """
        # 当前返回规则判断结果
        failed_checks = [c for c in checks if not c["passed"]]
        
        risk_level = "low"
        if anomaly_score > 0.5 or len(failed_checks) > 1:
            risk_level = "high"
        elif anomaly_score > 0.2 or len(failed_checks) == 1:
            risk_level = "medium"
        
        return {
            "risk_level": risk_level,
            "anomaly_score": anomaly_score,
            "failed_checks": len(failed_checks),
            "recommendation": "reject" if risk_level == "high" else "caution" if risk_level == "medium" else "approve",
        }
    
    def _make_decision(self, checks: List[Dict], anomaly_score: float, 
                       ai_review: Dict) -> tuple:
        """
        综合决策
        
        Returns:
            (approved: bool, reason: str)
        """
        # 硬规则不通过，直接拒绝
        hard_checks = ["position_limit", "daily_loss_limit", "blacklist_check"]
        for check in checks:
            if check["name"] in hard_checks and not check["passed"]:
                return False, f"Hard rule failed: {check['name']}"
        
        # AI建议拒绝
        if ai_review.get("recommendation") == "reject":
            return False, "AI risk review rejected"
        
        # 异常分数过高
        if anomaly_score > 0.7:
            return False, f"Anomaly score too high: {anomaly_score:.2f}"
        
        # 检查通过，可以交易
        passed_count = sum(1 for c in checks if c["passed"])
        total_count = len(checks)
        
        return True, f"All checks passed ({passed_count}/{total_count})"
    
    def _publish_execution(self, decision: TradeDecision):
        """发布执行指令"""
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "execution_order",
            "source_agent": self.agent_name,
            "target_agent": "executor",
            "timestamp": generate_timestamp(),
            "priority": 1,  # 最高优先级
            "payload": {
                "decision": decision.dict(),
                "approved": True,
            },
        }
        
        # 发布到执行队列
        self.bus.send("am-hk-executions", decision.signal.symbol, message)
        
        # 更新持仓
        self._update_position(decision)
        
        # 更新统计
        self.daily_stats["trades_count"] += 1
        
        self.bus.flush()
    
    def _publish_rejection(self, decision: TradeDecision):
        """发布拒绝通知"""
        message = {
            "msg_id": generate_msg_id(),
            "msg_type": "execution_rejected",
            "source_agent": self.agent_name,
            "target_agent": "agent6_learning",
            "timestamp": generate_timestamp(),
            "priority": 3,
            "payload": {
                "decision": decision.dict(),
                "approved": False,
                "reason": decision.approval_reason,
            },
        }
        
        # 发送到学习反馈队列
        self.bus.publish_feedback(message)
        self.bus.flush()
    
    def _update_position(self, decision: TradeDecision):
        """更新持仓状态"""
        symbol = decision.signal.symbol
        
        if symbol not in self.positions:
            self.positions[symbol] = {
                "symbol": symbol,
                "size": 0.0,
                "entry_price": 0.0,
                "trades": [],
            }
        
        pos = self.positions[symbol]
        
        if decision.signal.action == ActionType.BUY:
            pos["size"] += decision.position_size
        elif decision.signal.action == ActionType.SELL:
            pos["size"] -= decision.position_size
        
        pos["trades"].append({
            "timestamp": generate_timestamp(),
            "action": decision.signal.action.value,
            "size": decision.position_size,
        })


if __name__ == "__main__":
    guardian = RiskGuardian()
    asyncio.run(guardian.start())
