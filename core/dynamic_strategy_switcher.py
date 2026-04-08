"""
动态策略切换模块 (Dynamic Strategy Switcher)
根据市场状态自动调整交易参数
"""
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.market_state_detector import MarketState, MarketStateSignal

logger = logging.getLogger("dynamic_strategy_switcher")


@dataclass
class StrategyParams:
    """策略参数数据结构"""
    # 仓位管理
    position_limit: float = 0.90       # 最大仓位比例 (0-1)
    max_positions: int = 10            # 最大持仓数量
    
    # 持仓周期
    holding_period: str = "1-3d"       # 持仓周期
    
    # 风控参数
    stop_loss: float = 0.05            # 止损宽度 (5%)
    take_profit: float = 0.15          # 止盈目标 (15%)
    trailing_stop: float = 0.03        # 移动止损 (3%)
    
    # 交易频率
    rebalance_freq: str = "daily"      # 调仓频率
    min_hold_hours: int = 24           # 最小持仓时间
    
    # 选股偏好
    beta_preference: str = "high"      # high/mid/low
    sector_focus: list = field(default_factory=list)  # 关注板块
    
    # 评分权重
    crypto_weight: float = 0.40
    us_weight: float = 0.40
    hk_weight: float = 0.20
    
    def to_dict(self) -> Dict:
        return {
            "position_limit": self.position_limit,
            "max_positions": self.max_positions,
            "holding_period": self.holding_period,
            "stop_loss": f"{self.stop_loss*100:.0f}%",
            "take_profit": f"{self.take_profit*100:.0f}%",
            "trailing_stop": f"{self.trailing_stop*100:.0f}%",
            "rebalance_freq": self.rebalance_freq,
            "min_hold_hours": self.min_hold_hours,
            "beta_preference": self.beta_preference,
            "sector_focus": self.sector_focus,
            "weights": {
                "crypto": self.crypto_weight,
                "us": self.us_weight,
                "hk": self.hk_weight,
            }
        }


class DynamicStrategySwitcher:
    """
    动态策略切换器
    
    根据市场状态自动调整策略参数
    """
    
    # 预设策略参数
    STRATEGY_PRESETS = {
        MarketState.BULL: StrategyParams(
            position_limit=0.90,      # 牛市重仓
            max_positions=10,
            holding_period="1-3d",
            stop_loss=0.05,           # 止损5%
            take_profit=0.15,         # 止盈15%
            trailing_stop=0.03,
            rebalance_freq="daily",
            min_hold_hours=24,
            beta_preference="high",   # 高Beta成长股
            sector_focus=["tech", "crypto", "growth"],
            crypto_weight=0.40,
            us_weight=0.40,
            hk_weight=0.20,
        ),
        
        MarketState.BEAR: StrategyParams(
            position_limit=0.30,      # 熊市轻仓
            max_positions=3,
            holding_period="intraday",
            stop_loss=0.03,           # 收紧止损3%
            take_profit=0.08,         # 降低止盈8%
            trailing_stop=0.02,
            rebalance_freq="intraday",
            min_hold_hours=0,
            beta_preference="low",    # 低Beta防御股
            sector_focus=["defensive", "dividend"],
            crypto_weight=0.20,       # 降低Crypto权重
            us_weight=0.30,
            hk_weight=0.50,           # 增加本地因子权重
        ),
        
        MarketState.RANGE: StrategyParams(
            position_limit=0.50,      # 震荡市中等仓位
            max_positions=6,
            holding_period="intraday",
            stop_loss=0.02,           #  tighter止损2%
            take_profit=0.05,         # 降低止盈5%
            trailing_stop=0.015,
            rebalance_freq="intraday",
            min_hold_hours=0,
            beta_preference="mid",    # 中等Beta
            sector_focus=["mean_reversion", "volatile"],
            crypto_weight=0.35,
            us_weight=0.35,
            hk_weight=0.30,
        ),
        
        MarketState.UNCERTAIN: StrategyParams(
            position_limit=0.20,      # 不确定时极低仓位
            max_positions=2,
            holding_period="intraday",
            stop_loss=0.02,
            take_profit=0.04,
            trailing_stop=0.01,
            rebalance_freq="intraday",
            min_hold_hours=0,
            beta_preference="low",
            sector_focus=["cash", "hedge"],
            crypto_weight=0.33,
            us_weight=0.33,
            hk_weight=0.34,
        ),
    }
    
    def __init__(self):
        self.current_state: Optional[MarketState] = None
        self.current_params: StrategyParams = self.STRATEGY_PRESETS[MarketState.UNCERTAIN]
        self.state_change_history: list = []
    
    def switch_strategy(self, market_state_signal: MarketStateSignal) -> Dict:
        """
        根据市场状态切换策略
        
        Args:
            market_state_signal: 市场状态信号
        
        Returns:
            策略切换结果
        """
        new_state = market_state_signal.state
        
        # 检查状态是否变化
        state_changed = (self.current_state != new_state)
        
        if state_changed:
            logger.warning(f"[StrategySwitch] {self.current_state} → {new_state} | "
                          f"Confidence: {market_state_signal.confidence}")
            
            # 记录状态变更
            self.state_change_history.append({
                "from": self.current_state.value if self.current_state else None,
                "to": new_state.value,
                "timestamp": datetime.now().isoformat(),
                "crypto_score": market_state_signal.crypto_score,
                "us_score": market_state_signal.us_score,
            })
        
        # 获取新策略参数
        self.current_state = new_state
        self.current_params = self.STRATEGY_PRESETS[new_state]
        
        # 根据置信度微调参数
        adjusted_params = self._adjust_by_confidence(
            self.current_params,
            market_state_signal.confidence
        )
        
        result = {
            "state": new_state.value,
            "state_changed": state_changed,
            "confidence": market_state_signal.confidence,
            "params": adjusted_params.to_dict(),
            "recommendation": self._get_recommendation(new_state),
            "timestamp": datetime.now().isoformat(),
        }
        
        if state_changed:
            logger.info(f"[StrategySwitch] New params: position_limit={adjusted_params.position_limit}, "
                       f"stop_loss={adjusted_params.stop_loss}, holding={adjusted_params.holding_period}")
        
        return result
    
    def _adjust_by_confidence(self, params: StrategyParams, confidence: float) -> StrategyParams:
        """根据置信度微调参数"""
        # 置信度低时进一步降低仓位
        if confidence < 0.6:
            adjusted_position = params.position_limit * 0.7
        elif confidence < 0.8:
            adjusted_position = params.position_limit * 0.85
        else:
            adjusted_position = params.position_limit
        
        # 创建调整后的参数副本
        adjusted = StrategyParams(
            position_limit=round(adjusted_position, 2),
            max_positions=params.max_positions,
            holding_period=params.holding_period,
            stop_loss=params.stop_loss,
            take_profit=params.take_profit,
            trailing_stop=params.trailing_stop,
            rebalance_freq=params.rebalance_freq,
            min_hold_hours=params.min_hold_hours,
            beta_preference=params.beta_preference,
            sector_focus=params.sector_focus.copy(),
            crypto_weight=params.crypto_weight,
            us_weight=params.us_weight,
            hk_weight=params.hk_weight,
        )
        
        return adjusted
    
    def _get_recommendation(self, state: MarketState) -> str:
        """获取操作建议"""
        recommendations = {
            MarketState.BULL: "牛市启动，重仓追击高Beta成长股，持仓1-3天",
            MarketState.BEAR: "熊市信号，降低仓位至30%以下，优先防守",
            MarketState.RANGE: "震荡行情，区间套利为主，严格止损",
            MarketState.UNCERTAIN: "市场方向不明，观望或轻仓试探",
        }
        return recommendations.get(state, "保持谨慎")
    
    def get_current_params(self) -> StrategyParams:
        """获取当前策略参数"""
        return self.current_params
    
    def get_state_changes(self) -> list:
        """获取状态变更历史"""
        return self.state_change_history.copy()


# === 便捷函数 ===

def switch_strategy_by_state(market_state_dict: Dict) -> Dict:
    """
    根据市场状态字典切换策略
    
    Usage:
        result = switch_strategy_by_state({
            "state": "bull",
            "confidence": 0.85,
            "crypto_score": 0.72,
            "us_score": 0.68
        })
    """
    switcher = DynamicStrategySwitcher()
    
    state_str = market_state_dict.get("state", "uncertain")
    state = MarketState(state_str)
    
    signal = MarketStateSignal(
        state=state,
        confidence=market_state_dict.get("confidence", 0.5),
        crypto_score=market_state_dict.get("crypto_score", 0.0),
        us_score=market_state_dict.get("us_score", 0.0),
        hk_volatility=market_state_dict.get("hk_volatility", 0.0),
        timestamp=datetime.now().isoformat()
    )
    
    return switcher.switch_strategy(signal)


if __name__ == "__main__":
    # 测试
    switcher = DynamicStrategySwitcher()
    
    test_states = [
        MarketState.BULL,
        MarketState.BEAR,
        MarketState.RANGE,
        MarketState.UNCERTAIN,
    ]
    
    print("动态策略切换测试:")
    print("=" * 60)
    
    for state in test_states:
        signal = MarketStateSignal(
            state=state,
            confidence=0.85,
            crypto_score=0.6 if state == MarketState.BULL else -0.4,
            us_score=0.5 if state == MarketState.BULL else -0.3,
            hk_volatility=0.15,
            timestamp=datetime.now().isoformat()
        )
        
        result = switcher.switch_strategy(signal)
        params = result["params"]
        
        print(f"\n【{state.value.upper()}】策略参数:")
        print(f"  仓位上限: {params['position_limit']*100:.0f}%")
        print(f"  持仓周期: {params['holding_period']}")
        print(f"  止损: {params['stop_loss']} | 止盈: {params['take_profit']}")
        print(f"  调仓频率: {params['rebalance_freq']}")
        print(f"  Beta偏好: {params['beta_preference']}")
        print(f"  建议: {result['recommendation']}")
