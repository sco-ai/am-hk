#!/usr/bin/env python3
"""
AM-HK 综合测试 - 推送到飞书
测试所有通知类型：系统状态、交易信号、每日报告、告警
"""
import sys
import asyncio
from datetime import datetime, timedelta
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.feishu import FeishuNotifier
from core.gnn_model import GNNMarketAnalyzer, analyze_market_correlation
from core.cross_market_strategy import CrossMarketStrategy, scan_cross_market_opportunities

async def test_system_status():
    """测试系统状态报告"""
    print("="*60)
    print("📊 测试1: 系统状态报告")
    print("="*60)
    
    notifier = FeishuNotifier()
    
    positions = [
        {"symbol": "BTCUSDT", "quantity": 0.5, "current_price": 65700, "pnl": 1250.0},
        {"symbol": "AAPL", "quantity": 100, "current_price": 182.5, "pnl": -150.0},
        {"symbol": "00700", "quantity": 200, "current_price": 385.0, "pnl": 800.0},
    ]
    
    success = await notifier.send_status_report(
        system_status="🟢 正常运行",
        active_agents=6,
        total_trades=12,
        daily_pnl=1900.0,
        positions=positions,
    )
    
    if success:
        print("✅ 系统状态报告已发送")
    else:
        print("❌ 发送失败")
    
    await notifier.close()
    print()

async def test_trading_signals():
    """测试交易信号通知"""
    print("="*60)
    print("🎯 测试2: 交易信号通知")
    print("="*60)
    
    notifier = FeishuNotifier()
    
    # 模拟多个交易信号
    signals = [
        {
            "symbol": "BTCUSDT",
            "action": "buy",
            "confidence": 0.78,
            "predicted_return": 4.2,
            "reasoning": "BTC突破关键阻力位$65,000，动量指标强劲，GNN检测到加密板块联动上涨",
            "position_size": 0.08,
            "stop_loss": 0.025,
            "take_profit": 0.06,
            "market": "BTC",
        },
        {
            "symbol": "00700",
            "action": "buy",
            "confidence": 0.72,
            "predicted_return": 3.5,
            "reasoning": "美股科技股NVDA大涨，GNN预测港股科技板块跟随上涨，腾讯历史相关性0.73",
            "position_size": 0.05,
            "stop_loss": 0.02,
            "take_profit": 0.05,
            "market": "HK",
        },
    ]
    
    for i, signal in enumerate(signals, 1):
        print(f"\n📤 发送信号 {i}/{len(signals)}: {signal['symbol']} {signal['action'].upper()}")
        
        success = await notifier.send_signal_card(**signal)
        if success:
            print(f"   ✅ {signal['symbol']} 信号已发送")
        else:
            print(f"   ❌ {signal['symbol']} 发送失败")
    
    await notifier.close()
    print()

async def test_daily_report():
    """测试每日交易报告"""
    print("="*60)
    print("📈 测试3: 每日交易报告")
    print("="*60)
    
    notifier = FeishuNotifier()
    
    success = await notifier.send_daily_report(
        date="2026-04-03",
        total_trades=15,
        win_rate=0.73,
        total_pnl=3250.50,
        sharpe_ratio=2.1,
        best_trade={
            "symbol": "BTCUSDT",
            "action": "buy",
            "pnl": 1850.0,
        },
        worst_trade={
            "symbol": "AAPL",
            "action": "sell",
            "pnl": -280.0,
        },
    )
    
    if success:
        print("✅ 每日报告已发送")
    else:
        print("❌ 发送失败")
    
    await notifier.close()
    print()

async def test_alerts():
    """测试告警通知"""
    print("="*60)
    print("🚨 测试4: 告警通知")
    print("="*60)
    
    notifier = FeishuNotifier()
    
    alerts = [
        {
            "title": "⚠️ 高波动率告警",
            "message": "BTC 5分钟波动率超过阈值(>15%)，当前波动率: 18.5%",
            "level": "warning",
        },
        {
            "title": "✅ 策略优化完成",
            "message": "Agent6完成今日策略回测，胜率从68%提升至73%",
            "level": "info",
        },
        {
            "title": "🔴 风险告警",
            "message": "日亏损接近上限(当前: 4.2%，上限: 5%)，建议降低仓位",
            "level": "error",
        },
    ]
    
    for alert in alerts:
        print(f"\n📤 发送告警: {alert['title']}")
        success = await notifier.send_alert(**alert)
        if success:
            print(f"   ✅ 已发送")
        else:
            print(f"   ❌ 发送失败")
    
    await notifier.close()
    print()

async def test_gnn_analysis():
    """测试GNN市场联动分析并发送结果"""
    print("="*60)
    print("🧠 测试5: GNN市场联动分析")
    print("="*60)
    
    # 模拟多市场数据
    market_data = {
        "BTCUSDT": {"price": 65700, "change_pct": 3.5, "volume": 15000},
        "ETHUSDT": {"price": 3450, "change_pct": 2.8, "volume": 8000},
        "AAPL": {"price": 182.5, "change_pct": 1.8, "volume": 50000},
        "NVDA": {"price": 875.0, "change_pct": 4.2, "volume": 35000},
        "00700": {"price": 385.0, "change_pct": 0.5, "volume": 12000},
        "09988": {"price": 72.5, "change_pct": 0.8, "volume": 8000},
    }
    
    print("📊 分析市场数据...")
    result = await analyze_market_correlation(market_data)
    
    print(f"\n📈 分析结果:")
    print(f"   节点数: {result['graph_stats']['node_count']}")
    print(f"   边数: {result['graph_stats']['edge_count']}")
    print(f"   传染风险: {result['contagion_risk']:.1%}")
    
    # 发送GNN分析结果
    notifier = FeishuNotifier()
    
    # 构建分析摘要
    lead_lag = result.get('lead_lag_relations', [])
    clusters = result.get('sector_clusters', [])
    predictions = result.get('predictions', [])
    
    summary = f"""**GNN市场联动分析结果**

**领先-滞后关系 ({len(lead_lag)}个):**
"""
    for rel in lead_lag[:3]:
        summary += f"• {rel['leader']} → {rel['follower']} (相关:{rel['correlation']:.2f})\n"
    
    summary += f"\n**板块聚类 ({len(clusters)}个):**\n"
    for cluster in clusters[:2]:
        summary += f"• {cluster['theme']}: {cluster['momentum']} (平均:{cluster['avg_change_pct']:+.1f}%)\n"
    
    summary += f"\n**跨市场预测 ({len(predictions)}个):**\n"
    for pred in predictions[:2]:
        summary += f"• {pred['target_symbol']}: {pred['predicted_change_pct']:+.1f}% (置信:{pred['confidence']:.1%})\n"
    
    summary += f"\n**传染风险评分: {result['contagion_risk']:.1%}**"
    
    success = await notifier.send_markdown("🧠 GNN市场联动分析", summary)
    
    if success:
        print("✅ GNN分析结果已发送到飞书")
    else:
        print("❌ 发送失败")
    
    await notifier.close()
    print()

async def test_cross_market_strategy():
    """测试跨市场策略并发送信号"""
    print("="*60)
    print("🌐 测试6: 跨市场联动策略")
    print("="*60)
    
    # 模拟市场数据
    market_data = {
        "BTCUSDT": {"price": 65700, "change_pct": 3.5, "volume": 15000},
        "AAPL": {"price": 182.5, "change_pct": 1.8, "volume": 50000},
        "NVDA": {"price": 875.0, "change_pct": 4.2, "volume": 35000},
        "00700": {"price": 385.0, "change_pct": 0.5, "volume": 12000},
        "09988": {"price": 72.5, "change_pct": 0.8, "volume": 8000},
    }
    
    print("🔍 扫描跨市场机会...")
    signals = await scan_cross_market_opportunities(market_data)
    
    print(f"✅ 发现 {len(signals)} 个交易机会")
    
    notifier = FeishuNotifier()
    
    for i, signal in enumerate(signals, 1):
        print(f"\n📤 发送跨市场信号 {i}: {signal.symbol} {signal.action.value.upper()}")
        
        # 转换为signal card格式
        success = await notifier.send_signal_card(
            symbol=signal.symbol,
            action=signal.action.value,
            confidence=signal.confidence,
            predicted_return=signal.predicted_return,
            reasoning=signal.reasoning,
            position_size=0.05,
            stop_loss=0.02,
            take_profit=0.05,
            market=signal.market,
        )
        
        if success:
            print(f"   ✅ 信号已发送")
        else:
            print(f"   ❌ 发送失败")
    
    await notifier.close()
    print()

async def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("🚀 AM-HK 综合测试 - 飞书推送")
    print("="*60 + "\n")
    
    # 运行所有测试
    await test_system_status()
    await test_trading_signals()
    await test_daily_report()
    await test_alerts()
    await test_gnn_analysis()
    await test_cross_market_strategy()
    
    print("="*60)
    print("✅ 所有测试完成！请检查飞书群聊")
    print("="*60)
    print("\n已发送的通知类型：")
    print("  1. 📊 系统状态报告 (含持仓)")
    print("  2. 🎯 交易信号卡片 x2")
    print("  3. 📈 每日交易报告")
    print("  4. 🚨 告警通知 x3")
    print("  5. 🧠 GNN市场联动分析")
    print("  6. 🌐 跨市场策略信号")

if __name__ == "__main__":
    asyncio.run(main())
