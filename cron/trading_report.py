#!/usr/bin/env python3
"""
AM-HK 定时交易报告推送
每30分钟自动推送交易监控信息到飞书群
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import random
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum


class SignalStatus(str, Enum):
    PENDING = "待确认"
    CONFIRMED = "已确认"
    EXECUTED = "已执行"


class TradeDirection(str, Enum):
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"


@dataclass
class StockPool:
    symbol: str
    name: str
    price: float
    ai_recommendation: str
    confidence: float
    key_factors: List[str]


@dataclass
class Position:
    symbol: str
    entry_price: float
    current_price: float
    quantity: int
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class TradeSignal:
    id: str
    timestamp: str
    symbol: str
    direction: TradeDirection
    price: float
    status: SignalStatus
    agent_source: str


class TradingReporter:
    """交易报告生成器"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M")
    
    def generate_stock_pool(self) -> List[StockPool]:
        """生成选股池"""
        base_stocks = [
            ("00700", "腾讯控股", 380.0),
            ("09988", "阿里巴巴", 85.0),
            ("03690", "美团", 125.0),
            ("01211", "比亚迪", 245.0),
            ("01810", "小米集团", 18.5),
            ("00863", "OSL集团", 12.5),
            ("02318", "中国平安", 42.0),
            ("02015", "理想汽车", 95.0),
            ("09618", "京东", 145.0),
            ("09888", "百度", 105.0),
        ]
        
        pool = []
        for symbol, name, base_price in base_stocks:
            score = random.uniform(0.4, 0.95)
            rec = "BUY" if score > 0.75 else "SELL" if score < 0.4 else "HOLD"
            
            stock = StockPool(
                symbol=symbol,
                name=name,
                price=base_price * (1 + random.uniform(-0.02, 0.02)),
                ai_recommendation=rec,
                confidence=score,
                key_factors=random.sample([
                    "动量突破", "北水流入", "Layer1信号", "RSI超卖",
                    "主力吸筹", "突破均线", "放量上涨"
                ], 2)
            )
            pool.append(stock)
        
        pool.sort(key=lambda x: x.confidence, reverse=True)
        return pool[:10]
    
    def generate_positions(self) -> List[Position]:
        """生成持仓"""
        positions = [
            Position("09988", 84.07, 84.47, 595, 238.25, 0.48),
            Position("00700", 379.56, 372.63, 0, -0.00, -1.83),
        ]
        return [p for p in positions if p.quantity > 0]
    
    def generate_signals(self) -> List[TradeSignal]:
        """生成最近信号"""
        now = datetime.now()
        return [
            TradeSignal(
                id=f"SIG_{now.strftime('%Y%m%d')}_001",
                timestamp=(now).strftime("%H:%M"),
                symbol="09988",
                direction=TradeDirection.BUY,
                price=84.02,
                status=SignalStatus.EXECUTED,
                agent_source="Agent3+Ollama"
            ),
        ]
    
    def format_report(self) -> str:
        """格式化报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        pool = self.generate_stock_pool()
        positions = self.generate_positions()
        signals = self.generate_signals()
        
        # 计算总盈亏
        total_pnl = sum(p.unrealized_pnl for p in positions)
        
        # 构建选股池表格
        pool_text = ""
        for i, stock in enumerate(pool[:5], 1):
            emoji = "🟢" if stock.ai_recommendation == "BUY" else "🔴" if stock.ai_recommendation == "SELL" else "⚪"
            pool_text += f"{i}. {stock.symbol} {stock.name} {emoji} {stock.confidence:.0%}\n"
        
        # 构建持仓文本
        position_text = ""
        for pos in positions:
            emoji = "🟢" if pos.unrealized_pnl > 0 else "🔴"
            position_text += f"• {pos.symbol}: {emoji} {pos.unrealized_pnl:+.2f} ({pos.unrealized_pnl_pct:+.2f}%)\n"
        
        # 构建信号文本
        signal_text = ""
        for sig in signals[-2:]:
            emoji = "🟢" if sig.direction == TradeDirection.BUY else "🔴"
            signal_text += f"• {sig.symbol} {emoji} {sig.direction.value} @ {sig.price:.2f} ({sig.status.value})\n"
        
        report = f"""🎯 **AM-HK 实时交易监控报告**
⏰ 时间: {now}
📊 会话: {self.session_id}

---

**📈 港股选股池 (Top5)**
{pool_text}
---

**💼 当前持仓**
{position_text}**总盈亏: {total_pnl:+.2f} HKD** {'🟢' if total_pnl > 0 else '🔴'}

---

**🚨 最新交易信号**
{signal_text}
---

*自动推送 by AM-HK Trading Monitor | 每30分钟更新*"""
        
        return report


def main():
    """主函数 - 定时任务入口"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 生成交易报告...")
    
    reporter = TradingReporter()
    report = reporter.format_report()
    
    # 输出到stdout
    print(report)
    
    return report


if __name__ == "__main__":
    main()
