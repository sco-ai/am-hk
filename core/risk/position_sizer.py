"""
仓位管理器 - Position Sizer
基于风险和账户状态计算最优仓位
"""
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PositionSizeResult:
    """仓位计算结果"""
    target_position: float  # 目标仓位 (0-1)
    max_position: float     # 最大允许仓位
    risk_adjusted_size: float  # 风险调整后的仓位
    
    # 计算参数
    volatility_factor: float
    liquidity_factor: float
    correlation_factor: float
    
    # 说明
    reasoning: str
    timestamp: datetime


class PositionSizer:
    """
    仓位管理器
    
    基于凯利公式和风险管理原则计算最优仓位
    """
    
    def __init__(
        self,
        max_position_pct: float = 0.3,  # 最大仓位30%
        max_risk_per_trade: float = 0.02,  # 单笔最大风险2%
        account_risk_limit: float = 0.06,  # 账户总风险6%
    ):
        self.max_position_pct = max_position_pct
        self.max_risk_per_trade = max_risk_per_trade
        self.account_risk_limit = account_risk_limit
        
        # 当前持仓
        self.current_positions: Dict[str, float] = {}
        self.position_history: list = []
    
    def calculate_position_size(
        self,
        symbol: str,
        signal_strength: float,  # 0-1
        confidence: float,       # 0-1
        volatility: float,       # 波动率 (%)
        liquidity_score: float,  # 0-1
        stop_loss_pct: float,    # 止损百分比
        portfolio_value: float,
        correlation_with_portfolio: float = 0.0
    ) -> PositionSizeResult:
        """
        计算仓位大小
        
        Args:
            symbol: 交易对
            signal_strength: 信号强度
            confidence: 模型置信度
            volatility: 波动率
            liquidity_score: 流动性评分
            stop_loss_pct: 止损百分比
            portfolio_value: 账户总值
            correlation_with_portfolio: 与现有持仓的相关性
            
        Returns:
            PositionSizeResult
        """
        timestamp = datetime.now()
        
        # 1. 基于凯利公式的仓位
        kelly_size = self._kelly_criterion(signal_strength, confidence, stop_loss_pct)
        
        # 2. 波动率调整
        vol_factor = self._volatility_adjustment(volatility)
        
        # 3. 流动性调整
        liq_factor = liquidity_score
        
        # 4. 相关性调整
        corr_factor = self._correlation_adjustment(correlation_with_portfolio)
        
        # 5. 计算调整后的仓位
        adjusted_size = kelly_size * vol_factor * liq_factor * corr_factor
        
        # 6. 应用限制
        max_pos = min(self.max_position_pct, self.max_risk_per_trade / max(stop_loss_pct, 0.001))
        final_size = min(adjusted_size, max_pos)
        
        # 7. 检查账户总风险
        current_total_risk = self._calculate_total_risk()
        available_risk = self.account_risk_limit - current_total_risk
        
        if available_risk <= 0:
            final_size = 0
            reasoning = "账户风险已达上限"
        else:
            risk_based_limit = available_risk / max(stop_loss_pct, 0.001)
            final_size = min(final_size, risk_based_limit)
            reasoning = f"凯利仓位{kelly_size:.2%}, 波动调整{vol_factor:.2f}, 流动性{liq_factor:.2f}"
        
        return PositionSizeResult(
            target_position=round(final_size, 4),
            max_position=round(max_pos, 4),
            risk_adjusted_size=round(adjusted_size, 4),
            volatility_factor=round(vol_factor, 4),
            liquidity_factor=round(liq_factor, 4),
            correlation_factor=round(corr_factor, 4),
            reasoning=reasoning,
            timestamp=timestamp
        )
    
    def _kelly_criterion(
        self,
        signal_strength: float,
        confidence: float,
        stop_loss_pct: float
    ) -> float:
        """
        凯利公式计算仓位
        
        f* = (bp - q) / b
        其中: b = 赔率, p = 胜率, q = 败率
        """
        # 简化版凯利公式
        # 假设胜率与信号强度和置信度相关
        win_prob = 0.5 + signal_strength * 0.3 + confidence * 0.2
        win_prob = min(0.9, max(0.1, win_prob))
        
        # 赔率 (假设止盈为止损的2倍)
        reward_risk_ratio = 2.0
        
        # 凯利分数
        kelly_f = (win_prob * reward_risk_ratio - (1 - win_prob)) / reward_risk_ratio
        
        # 使用半凯利 (更保守)
        half_kelly = kelly_f * 0.5
        
        return max(0, min(half_kelly, self.max_position_pct))
    
    def _volatility_adjustment(self, volatility: float) -> float:
        """基于波动率调整仓位"""
        # 基准波动率 50%年化
        base_vol = 50.0
        
        if volatility <= 0:
            return 1.0
        
        # 波动率越高,仓位越小
        adjustment = base_vol / volatility
        
        # 限制范围
        return max(0.2, min(1.5, adjustment))
    
    def _correlation_adjustment(self, correlation: float) -> float:
        """基于相关性调整仓位"""
        # 相关性越高,仓位越小 (分散风险)
        if correlation > 0.8:
            return 0.5
        elif correlation > 0.5:
            return 0.8
        else:
            return 1.0
    
    def _calculate_total_risk(self) -> float:
        """计算账户总风险"""
        return sum(self.current_positions.values()) * 0.02  # 简化计算
    
    def update_position(self, symbol: str, position_pct: float):
        """更新持仓"""
        self.current_positions[symbol] = position_pct
        self.position_history.append({
            "symbol": symbol,
            "position": position_pct,
            "timestamp": datetime.now()
        })
    
    def close_position(self, symbol: str):
        """平仓"""
        if symbol in self.current_positions:
            del self.current_positions[symbol]
    
    def get_position(self, symbol: str) -> float:
        """获取当前仓位"""
        return self.current_positions.get(symbol, 0.0)
    
    def get_total_exposure(self) -> float:
        """获取总敞口"""
        return sum(abs(pos) for pos in self.current_positions.values())


# 全局实例
position_sizer = PositionSizer()
