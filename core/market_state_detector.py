"""
市场状态识别模块 (Market State Detector)
用于判断当前市场处于牛市/熊市/震荡市
"""
import logging
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("market_state_detector")


class MarketState(Enum):
    """市场状态枚举"""
    BULL = "bull"           # 牛市 - 积极做多
    BEAR = "bear"           # 熊市 - 防守/做空
    RANGE = "range"         # 震荡市 - 区间套利
    UNCERTAIN = "uncertain" # 不确定 - 观望


@dataclass
class MarketStateSignal:
    """市场状态信号数据结构"""
    state: MarketState
    confidence: float              # 置信度 0-1
    crypto_score: float            # Layer1 信号
    us_score: float                # Layer2 信号
    hk_volatility: float           # 港股波动率
    timestamp: str
    
    # 细分指标
    btc_momentum: float = 0.0
    eth_momentum: float = 0.0
    coin_momentum: float = 0.0
    nvda_momentum: float = 0.0
    qqq_momentum: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "state": self.state.value,
            "confidence": round(self.confidence, 2),
            "crypto_score": round(self.crypto_score, 2),
            "us_score": round(self.us_score, 2),
            "hk_volatility": round(self.hk_volatility, 2),
            "timestamp": self.timestamp,
            "details": {
                "btc_momentum": round(self.btc_momentum, 2),
                "eth_momentum": round(self.eth_momentum, 2),
                "coin_momentum": round(self.coin_momentum, 2),
                "nvda_momentum": round(self.nvda_momentum, 2),
                "qqq_momentum": round(self.qqq_momentum, 2),
            }
        }


class MarketStateDetector:
    """
    市场状态识别器
    
    根据 Layer1 (Crypto) 和 Layer2 (美股) 信号判断市场状态
    """
    
    def __init__(self):
        self.history: list = []  # 历史状态用于平滑
        self.max_history = 10
        
        # 状态判定阈值
        self.thresholds = {
            "bull_crypto": 0.5,     # Crypto > 0.5 才考虑牛市
            "bull_us": 0.4,         # 美股 > 0.4 确认牛市
            "bear_crypto": -0.3,    # Crypto < -0.3 考虑熊市
            "bear_us": -0.2,        # 美股 < -0.2 确认熊市
            "range_limit": 0.2,     # |信号| < 0.2 为震荡
        }
    
    def detect(self, 
               crypto_signal: float,
               us_signal: float,
               hk_volatility: float = 0.0,
               details: Optional[Dict] = None) -> MarketStateSignal:
        """
        检测市场状态
        
        Args:
            crypto_signal: Layer1 综合信号 (-1.0 ~ 1.0)
            us_signal: Layer2 综合信号 (-1.0 ~ 1.0)
            hk_volatility: 港股波动率 (可选)
            details: 细分指标详情
        
        Returns:
            MarketStateSignal 市场状态信号
        """
        details = details or {}
        
        # 判定逻辑
        if crypto_signal > self.thresholds["bull_crypto"] and \
           us_signal > self.thresholds["bull_us"]:
            state = MarketState.BULL
            confidence = min(1.0, (crypto_signal + us_signal) / 1.5)
            
        elif crypto_signal < self.thresholds["bear_crypto"] and \
             us_signal < self.thresholds["bear_us"]:
            state = MarketState.BEAR
            confidence = min(1.0, (abs(crypto_signal) + abs(us_signal)) / 1.0)
            
        elif abs(crypto_signal) < self.thresholds["range_limit"] and \
             abs(us_signal) < self.thresholds["range_limit"]:
            state = MarketState.RANGE
            confidence = 0.7
            
        else:
            state = MarketState.UNCERTAIN
            confidence = 0.5
        
        # 平滑处理 (防止状态频繁切换)
        state = self._smooth_state(state)
        
        signal = MarketStateSignal(
            state=state,
            confidence=round(confidence, 2),
            crypto_score=round(crypto_signal, 2),
            us_score=round(us_signal, 2),
            hk_volatility=round(hk_volatility, 2),
            timestamp=datetime.now().isoformat(),
            btc_momentum=details.get("btc_momentum", 0.0),
            eth_momentum=details.get("eth_momentum", 0.0),
            coin_momentum=details.get("coin_momentum", 0.0),
            nvda_momentum=details.get("nvda_momentum", 0.0),
            qqq_momentum=details.get("qqq_momentum", 0.0),
        )
        
        logger.info(f"[MarketState] {state.value.upper()} | "
                   f"crypto={crypto_signal:+.2f} us={us_signal:+.2f} | "
                   f"confidence={confidence:.2f}")
        
        return signal
    
    def _smooth_state(self, new_state: MarketState) -> MarketState:
        """状态平滑 - 防止频繁切换"""
        self.history.append(new_state)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        if len(self.history) < 3:
            return new_state
        
        # 如果最近3个状态都相同，确认该状态
        recent = self.history[-3:]
        if all(s == recent[0] for s in recent):
            return recent[0]
        
        # 否则保持上一个确认状态
        return self.history[-2] if len(self.history) >= 2 else new_state
    
    def get_state_description(self, state: MarketState) -> str:
        """获取状态描述"""
        descriptions = {
            MarketState.BULL: "牛市 - 积极做多，重仓持有",
            MarketState.BEAR: "熊市 - 防守为主，降低仓位",
            MarketState.RANGE: "震荡市 - 区间套利，高频交易",
            MarketState.UNCERTAIN: "不确定 - 观望等待，轻仓试探",
        }
        return descriptions.get(state, "未知状态")


# === 便捷函数 ===

def detect_market_state(cross_market_factors: Dict) -> MarketStateSignal:
    """
    从跨市场因子中检测市场状态
    
    Usage:
        signal = detect_market_state({
            "layer1_signal": 0.65,
            "layer2_confirm": 0.55,
            "btc_momentum": 1.2,
            "eth_momentum": 0.8,
            ...
        })
    """
    detector = MarketStateDetector()
    
    layer1 = cross_market_factors.get("layer1_signal", 0.0)
    layer2 = cross_market_factors.get("layer2_confirm", 0.0)
    
    details = {
        "btc_momentum": cross_market_factors.get("btc_momentum_5m", 0.0),
        "eth_momentum": cross_market_factors.get("eth_momentum_5m", 0.0),
        "coin_momentum": cross_market_factors.get("coin_momentum", 0.0),
        "nvda_momentum": cross_market_factors.get("nvda_momentum", 0.0),
        "qqq_momentum": cross_market_factors.get("qqq_momentum", 0.0),
    }
    
    return detector.detect(
        crypto_signal=layer1,
        us_signal=layer2,
        details=details
    )


if __name__ == "__main__":
    # 测试
    detector = MarketStateDetector()
    
    test_cases = [
        # (crypto, us, expected)
        (0.75, 0.65, "BULL"),
        (-0.5, -0.4, "BEAR"),
        (0.1, 0.05, "RANGE"),
        (0.6, 0.1, "UNCERTAIN"),
    ]
    
    print("市场状态识别测试:")
    print("=" * 50)
    
    for crypto, us, expected in test_cases:
        signal = detector.detect(crypto, us)
        status = "✅" if signal.state.value == expected.lower() else "❌"
        print(f"{status} Crypto={crypto:+.2f}, US={us:+.2f} → "
              f"{signal.state.value.upper()} (预期: {expected})")
        print(f"   置信度: {signal.confidence}")
        print(f"   描述: {detector.get_state_description(signal.state)}")
        print()
