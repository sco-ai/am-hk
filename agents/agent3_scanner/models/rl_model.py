"""
强化学习仓位控制模型 - RL Model (PPO)
用于动态仓位管理和风险控制
"""
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json


class PositionAction(Enum):
    """仓位动作"""
    INCREASE = "increase"    # 加仓
    DECREASE = "decrease"    # 减仓
    HOLD = "hold"           # 保持
    CLOSE = "close"         # 平仓


@dataclass
class PositionState:
    """仓位状态"""
    current_position: float  # 当前仓位 (0-1)
    entry_price: float
    unrealized_pnl: float
    holding_time: int  # 持仓时间 (bars)


@dataclass
class RLDecision:
    """RL决策结果"""
    action: PositionAction
    target_position: float  # 目标仓位
    size_delta: float  # 仓位变化量
    confidence: float
    reasoning: str


class PPOPositionController:
    """
    PPO仓位控制器
    
    基于市场状态动态调整仓位大小
    状态空间: [趋势强度, 波动率, 流动性, 情绪, 当前仓位, 持仓时间, 未实现盈亏]
    动作空间: [加仓, 减仓, 保持, 平仓]
    """
    
    # 状态权重 (模拟训练好的策略网络)
    STATE_WEIGHTS = {
        "trend_strength": 0.15,
        "volatility": -0.20,  # 高波动减仓
        "liquidity": 0.10,
        "sentiment": 0.15,
        "current_position": -0.05,  # 已有仓位时偏保守
        "holding_time": -0.05,  # 持仓时间长偏保守
        "unrealized_pnl": 0.10,  # 盈利时倾向于持有
    }
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.version = "v1.0-ppo-simulated"
        self.last_update = datetime.now()
        
        # 仓位限制
        self.min_position = 0.0
        self.max_position = 1.0
        self.max_position_per_trade = 0.3  # 单次最大调整
        
        # 缓存
        self.position_states: Dict[str, PositionState] = {}
    
    def decide_position(
        self,
        symbol: str,
        market_state: Dict[str, float],
        signal_strength: float,  # 来自LightGBM的信号强度
        current_price: float
    ) -> RLDecision:
        """
        决定仓位调整
        
        Args:
            symbol: 交易对
            market_state: 市场状态
            signal_strength: 信号强度 (-1 到 1)
            current_price: 当前价格
            
        Returns:
            RLDecision
        """
        # 获取或初始化仓位状态
        pos_state = self.position_states.get(symbol, PositionState(
            current_position=0.0,
            entry_price=0.0,
            unrealized_pnl=0.0,
            holding_time=0
        ))
        
        # 构建状态向量
        state_vector = self._build_state_vector(market_state, pos_state, signal_strength)
        
        # 计算动作偏好
        action_preference = self._calculate_action_preference(state_vector)
        
        # 确定动作
        action = self._select_action(action_preference, pos_state, signal_strength)
        
        # 计算目标仓位
        target_position = self._calculate_target_position(
            action, pos_state, signal_strength, market_state
        )
        
        # 计算仓位变化
        size_delta = target_position - pos_state.current_position
        size_delta = np.clip(size_delta, -self.max_position_per_trade, self.max_position_per_trade)
        
        # 更新状态
        if abs(size_delta) > 0.01:  # 有实际交易
            if pos_state.current_position == 0:  # 新开仓
                pos_state.entry_price = current_price
                pos_state.holding_time = 0
            pos_state.current_position = target_position
        
        pos_state.holding_time += 1
        
        # 计算未实现盈亏
        if pos_state.current_position > 0 and pos_state.entry_price > 0:
            pos_state.unrealized_pnl = (current_price - pos_state.entry_price) / pos_state.entry_price
        
        self.position_states[symbol] = pos_state
        
        return RLDecision(
            action=action,
            target_position=target_position,
            size_delta=size_delta,
            confidence=action_preference[action],
            reasoning=self._generate_reasoning(action, state_vector, pos_state)
        )
    
    def _build_state_vector(
        self,
        market_state: Dict[str, float],
        pos_state: PositionState,
        signal_strength: float
    ) -> Dict[str, float]:
        """构建状态向量"""
        return {
            "trend_strength": market_state.get("trend_score", 0),
            "volatility": market_state.get("volatility_ratio", 1.0),
            "liquidity": market_state.get("liquidity_score", 0.5),
            "sentiment": market_state.get("sentiment_composite", 0),
            "current_position": pos_state.current_position,
            "holding_time": min(pos_state.holding_time / 100, 1.0),  # 归一化
            "unrealized_pnl": np.tanh(pos_state.unrealized_pnl * 10),  # 归一化
            "signal_strength": signal_strength,
        }
    
    def _calculate_action_preference(self, state: Dict[str, float]) -> Dict[PositionAction, float]:
        """计算动作偏好"""
        # 基础分数
        score = 0
        for key, weight in self.STATE_WEIGHTS.items():
            if key in state:
                score += state[key] * weight
        
        # 加入信号强度
        score += state["signal_strength"] * 0.3
        
        # 各动作偏好
        preferences = {
            PositionAction.INCREASE: max(0, score) * 0.5,
            PositionAction.DECREASE: max(0, -score) * 0.5,
            PositionAction.HOLD: 0.3 - abs(score) * 0.2,
            PositionAction.CLOSE: 0.1,
        }
        
        # 根据持仓调整
        current_pos = state["current_position"]
        if current_pos >= self.max_position:
            preferences[PositionAction.INCREASE] = 0
        if current_pos <= 0:
            preferences[PositionAction.DECREASE] = 0
            preferences[PositionAction.CLOSE] = 0
        
        # 止盈止损逻辑
        unrealized = state["unrealized_pnl"]
        if unrealized > 0.05:  # 盈利5%以上,倾向于减仓
            preferences[PositionAction.DECREASE] += 0.2
        if unrealized < -0.03:  # 亏损3%以上,考虑平仓
            preferences[PositionAction.CLOSE] += 0.3
        
        # 归一化
        total = sum(preferences.values())
        if total > 0:
            preferences = {k: v/total for k, v in preferences.items()}
        
        return preferences
    
    def _select_action(
        self,
        preferences: Dict[PositionAction, float],
        pos_state: PositionState,
        signal_strength: float
    ) -> PositionAction:
        """选择动作"""
        # 贪心选择
        return max(preferences, key=preferences.get)
    
    def _calculate_target_position(
        self,
        action: PositionAction,
        pos_state: PositionState,
        signal_strength: float,
        market_state: Dict[str, float]
    ) -> float:
        """计算目标仓位"""
        current = pos_state.current_position
        
        # 基础仓位大小 (基于信号强度)
        base_size = abs(signal_strength) * self.max_position
        
        # 波动率调整
        vol_ratio = market_state.get("volatility_ratio", 1.0)
        vol_adjustment = 1 / (1 + vol_ratio)  # 高波动降低仓位
        
        # 流动性调整
        liq_score = market_state.get("liquidity_score", 0.5)
        
        adjusted_size = base_size * vol_adjustment * (0.5 + liq_score * 0.5)
        
        if action == PositionAction.INCREASE:
            target = min(current + adjusted_size, self.max_position)
        elif action == PositionAction.DECREASE:
            target = max(current - adjusted_size * 0.5, 0)
        elif action == PositionAction.CLOSE:
            target = 0
        else:  # HOLD
            target = current
        
        return round(target, 4)
    
    def _generate_reasoning(
        self,
        action: PositionAction,
        state: Dict[str, float],
        pos_state: PositionState
    ) -> str:
        """生成决策理由"""
        reasons = []
        
        if action == PositionAction.INCREASE:
            reasons.append("信号强度支持加仓")
            if state["trend_strength"] > 0.3:
                reasons.append("趋势有利")
        elif action == PositionAction.DECREASE:
            reasons.append("风险管理要求减仓")
            if pos_state.unrealized_pnl > 0.03:
                reasons.append("获利了结")
        elif action == PositionAction.CLOSE:
            if pos_state.unrealized_pnl < -0.02:
                reasons.append("止损")
            else:
                reasons.append("信号减弱")
        else:
            reasons.append("保持观望")
        
        if state["volatility"] > 1.5:
            reasons.append("高波动环境")
        
        return "; ".join(reasons)
    
    def reset_position(self, symbol: str):
        """重置仓位状态"""
        if symbol in self.position_states:
            del self.position_states[symbol]
    
    def get_position_state(self, symbol: str) -> Optional[PositionState]:
        """获取仓位状态"""
        return self.position_states.get(symbol)
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy",
            "version": self.version,
            "active_positions": len(self.position_states),
            "last_update": self.last_update.isoformat(),
        }


# 全局实例
rl_model = PPOPositionController()
