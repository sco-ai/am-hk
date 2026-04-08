"""
AM-HK 交易监控面板
展示完整的交易闭环：选股池 → 信号 → 确认 → 执行 → 盈亏
"""
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class SignalStatus(str, Enum):
    PENDING = "待确认"
    CONFIRMED = "已确认"
    REJECTED = "已拒绝"
    EXECUTED = "已执行"
    CLOSED = "已平仓"


class TradeDirection(str, Enum):
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"


@dataclass
class StockPool:
    """选股池"""
    symbol: str
    name: str
    price: float
    market_cap: float
    signal_score: float
    ai_recommendation: str
    confidence: float
    key_factors: List[str]


@dataclass
class TradeSignal:
    """交易信号"""
    id: str
    timestamp: str
    symbol: str
    direction: TradeDirection
    price: float
    target_price: float
    stop_loss: float
    position_size: int
    confidence: float
    reasoning: str
    status: SignalStatus
    agent_source: str
    requires_confirmation: bool
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None


@dataclass
class TradeExecution:
    """交易执行结果"""
    signal_id: str
    executed_at: str
    filled_price: float
    filled_quantity: int
    commission: float
    status: str


@dataclass
class Position:
    """持仓"""
    symbol: str
    entry_price: float
    current_price: float
    quantity: int
    entry_time: str
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: float
    take_profit: float
    days_held: int


class TradingMonitor:
    """交易监控器"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M")
        self.start_time = datetime.now()
        self.signals: List[TradeSignal] = []
        self.positions: List[Position] = []
        self.executions: List[TradeExecution] = []
        self.signal_counter = 0
    
    def generate_stock_pool(self) -> List[StockPool]:
        """生成当前选股池"""
        base_stocks = [
            ("00700", "腾讯控股", 380.0, 36000),
            ("09988", "阿里巴巴", 85.0, 18000),
            ("03690", "美团", 125.0, 7800),
            ("01211", "比亚迪", 245.0, 7200),
            ("01810", "小米集团", 18.5, 4600),
            ("00863", "OSL集团", 12.5, 85),
            ("02318", "中国平安", 42.0, 7600),
            ("02015", "理想汽车", 95.0, 2000),
            ("09618", "京东", 145.0, 4500),
            ("09888", "百度", 105.0, 2900),
        ]
        
        pool = []
        for symbol, name, base_price, cap in base_stocks:
            score = random.uniform(0.4, 0.95)
            rec = "BUY" if score > 0.75 else "SELL" if score < 0.4 else "HOLD"
            
            stock = StockPool(
                symbol=symbol,
                name=name,
                price=base_price * (1 + random.uniform(-0.02, 0.02)),
                market_cap=cap,
                signal_score=score,
                ai_recommendation=rec,
                confidence=score,
                key_factors=random.sample([
                    "动量突破", "北水流入", "Layer1信号", "RSI超卖",
                    "主力吸筹", "突破均线", "放量上涨", "cross_market"
                ], 3)
            )
            pool.append(stock)
        
        pool.sort(key=lambda x: x.signal_score, reverse=True)
        return pool
    
    def generate_signal(self, stock: StockPool) -> TradeSignal:
        """生成交易信号"""
        self.signal_counter += 1
        signal_id = f"SIG_{self.session_id}_{self.signal_counter:03d}"
        now = datetime.now()
        
        if stock.ai_recommendation == "BUY":
            direction = TradeDirection.BUY
            target = stock.price * 1.05
            stop = stock.price * 0.97
            size = min(1000, int(50000 / stock.price))
        else:
            direction = TradeDirection.SELL
            target = stock.price * 0.95
            stop = stock.price * 1.03
            size = 0
        
        signal = TradeSignal(
            id=signal_id,
            timestamp=now.strftime("%H:%M:%S"),
            symbol=stock.symbol,
            direction=direction,
            price=stock.price,
            target_price=round(target, 2),
            stop_loss=round(stop, 2),
            position_size=size,
            confidence=stock.confidence,
            reasoning=f"AI模型分析: {', '.join(stock.key_factors)}",
            status=SignalStatus.PENDING,
            agent_source="Agent3+Ollama",
            requires_confirmation=True
        )
        self.signals.append(signal)
        return signal
    
    def confirm_signal(self, signal_id: str, confirmed: bool, by: str = "system") -> bool:
        """确认或拒绝信号"""
        for signal in self.signals:
            if signal.id == signal_id:
                if confirmed:
                    signal.status = SignalStatus.CONFIRMED
                    signal.confirmed_by = by
                    signal.confirmed_at = datetime.now().strftime("%H:%M:%S")
                    self.execute_signal(signal)
                else:
                    signal.status = SignalStatus.REJECTED
                    signal.confirmed_by = by
                    signal.confirmed_at = datetime.now().strftime("%H:%M:%S")
                return True
        return False
    
    def execute_signal(self, signal: TradeSignal):
        """执行交易"""
        execution = TradeExecution(
            signal_id=signal.id,
            executed_at=datetime.now().strftime("%H:%M:%S"),
            filled_price=signal.price * (1 + random.uniform(-0.001, 0.001)),
            filled_quantity=signal.position_size,
            commission=round(signal.price * signal.position_size * 0.001, 2),
            status="已成交"
        )
        self.executions.append(execution)
        signal.status = SignalStatus.EXECUTED
        
        position = Position(
            symbol=signal.symbol,
            entry_price=execution.filled_price,
            current_price=execution.filled_price,
            quantity=signal.position_size,
            entry_time=execution.executed_at,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            stop_loss=signal.stop_loss,
            take_profit=signal.target_price,
            days_held=0
        )
        self.positions.append(position)
    
    def update_positions(self):
        """更新持仓盈亏"""
        for pos in self.positions:
            change = random.uniform(-0.02, 0.025)
            pos.current_price = pos.entry_price * (1 + change)
            pnl = (pos.current_price - pos.entry_price) * pos.quantity
            pos.unrealized_pnl = round(pnl, 2)
            pos.unrealized_pnl_pct = round(change * 100, 2)
    
    def get_summary(self) -> Dict:
        """获取交易摘要"""
        total_pnl = sum(p.unrealized_pnl for p in self.positions)
        confirmed = len([s for s in self.signals if s.status == SignalStatus.CONFIRMED])
        executed = len([s for s in self.signals if s.status == SignalStatus.EXECUTED])
        
        return {
            "session_id": self.session_id,
            "运行时间": str(datetime.now() - self.start_time).split('.')[0],
            "选股池": 10,
            "生成信号": len(self.signals),
            "已确认": confirmed,
            "已执行": executed,
            "当前持仓": len(self.positions),
            "未实现盈亏": f"{total_pnl:+.2f} HKD",
        }


def print_dashboard(monitor: TradingMonitor):
    """打印交易监控面板"""
    print("\n" + "=" * 80)
    print(f"🎯 AM-HK 交易监控面板 | 会话: {monitor.session_id}")
    print("=" * 80)
    
    print("\n📊 港股选股池 (Top10)")
    print("-" * 80)
    print(f"{'排名':<4} {'代码':<8} {'名称':<12} {'价格':<10} {'AI推荐':<8} {'置信度':<8} {'关键因子'}")
    print("-" * 80)
    
    pool = monitor.generate_stock_pool()
    for i, stock in enumerate(pool[:10], 1):
        factors = ", ".join(stock.key_factors[:2])
        print(f"{i:<4} {stock.symbol:<8} {stock.name:<12} {stock.price:<10.2f} "
              f"{stock.ai_recommendation:<8} {stock.confidence:<8.0%} {factors}")
    
    print("\n🚨 交易信号 (需确认)")
    print("-" * 80)
    if monitor.signals:
        print(f"{'信号ID':<20} {'时间':<10} {'标的':<8} {'方向':<6} {'价格':<10} {'状态':<10}")
        print("-" * 80)
        for sig in monitor.signals[-5:]:
            print(f"{sig.id:<20} {sig.timestamp:<10} {sig.symbol:<8} "
                  f"{sig.direction.value:<6} {sig.price:<10.2f} {sig.status.value:<10}")
    else:
        print("暂无信号")
    
    print("\n💼 当前持仓")
    print("-" * 80)
    if monitor.positions:
        print(f"{'标的':<8} {'买入价':<10} {'现价':<10} {'数量':<8} {'盈亏':<15} {'盈亏%':<8}")
        print("-" * 80)
        for pos in monitor.positions:
            emoji = "🟢" if pos.unrealized_pnl > 0 else "🔴"
            print(f"{pos.symbol:<8} {pos.entry_price:<10.2f} {pos.current_price:<10.2f} "
                  f"{pos.quantity:<8} {emoji} {pos.unrealized_pnl:+.2f} {pos.unrealized_pnl_pct:+.2f}%")
    else:
        print("暂无持仓")
    
    print("\n📈 交易摘要")
    print("-" * 80)
    summary = monitor.get_summary()
    for key, value in summary.items():
        if key != "session_id":
            print(f"  {key}: {value}")
    
    print("=" * 80)


def simulate_20min():
    """模拟20分钟交易"""
    print("\n" + "🔄" * 40)
    print("🚀 开始模拟 20分钟 交易会话")
    print("🔄" * 40)
    
    monitor = TradingMonitor()
    pool = monitor.generate_stock_pool()
    
    events = [
        ("00:00", "系统启动，生成选股池"),
        ("02:00", "Agent3生成买入信号: 00700"),
        ("02:30", "风控确认通过"),
        ("03:00", "执行买入 00700 @ 380.00"),
        ("05:00", "Agent3生成买入信号: 09988"),
        ("05:15", "人工确认通过"),
        ("05:30", "执行买入 09988 @ 85.20"),
        ("08:00", "00700 价格上涨 +2.5%"),
        ("10:00", "Agent4生成卖出信号: 00700 (止盈)"),
        ("10:30", "自动确认 (止盈策略)"),
        ("11:00", "执行卖出 00700 @ 389.50"),
        ("15:00", "09988 价格下跌 -1.8%"),
        ("18:00", "更新持仓盈亏"),
        ("20:00", "会话结束"),
    ]
    
    for time_str, event in events:
        print(f"\n[{time_str}] {event}")
        
        if "买入信号" in event:
            symbol = event.split(":")[1].strip()
            stock = next((s for s in pool if s.symbol == symbol), None)
            if stock:
                signal = monitor.generate_signal(stock)
                print(f"  📋 信号: {signal.id}")
                print(f"     方向: {signal.direction.value}, 价格: {signal.price:.2f}")
                print(f"     目标: {signal.target_price:.2f}, 止损: {signal.stop_loss:.2f}")
                print(f"     需要确认: {'是' if signal.requires_confirmation else '否'}")
        
        elif "确认通过" in event:
            if monitor.signals:
                latest = monitor.signals[-1]
                by = "人工" if "人工" in event else "风控"
                monitor.confirm_signal(latest.id, True, by)
                print(f"  ✅ 信号 {latest.id} 已确认 (by {by})")
        
        elif "执行" in event and ("买入" in event or "卖出" in event):
            if monitor.executions:
                latest = monitor.executions[-1]
                print(f"  💰 成交: {latest.filled_quantity}股 @ {latest.filled_price:.2f}")
                print(f"     佣金: {latest.commission:.2f} HKD")
        
        elif "价格" in event:
            monitor.update_positions()
            print(f"  📊 持仓盈亏已更新")
    
    print_dashboard(monitor)
    
    # 报告
    print("\n" + "=" * 80)
    print("📊 交易报告")
    print("=" * 80)
    print(f"\n🚨 信号统计:")
    for status in SignalStatus:
        count = len([s for s in monitor.signals if s.status == status])
        print(f"  {status.value}: {count}")
    
    print(f"\n💰 成交记录:")
    for exe in monitor.executions:
        print(f"  {exe.signal_id}: {exe.filled_quantity}股 @ {exe.filled_price:.2f}")
    
    total_pnl = sum(p.unrealized_pnl for p in monitor.positions)
    print(f"\n📈 盈亏统计:")
    print(f"  总盈亏: {total_pnl:+.2f} HKD")
    print(f"  持仓数量: {len(monitor.positions)}")
    print("=" * 80)
    
    return monitor


if __name__ == "__main__":
    simulate_20min()
