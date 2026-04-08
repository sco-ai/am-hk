"""
Agent 7: PerformanceAnalyzer 使用示例
"""
import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from datetime import datetime, timedelta
import numpy as np

from agents.agent7_performance.modules.metrics_calculator import MetricsCalculator
from agents.agent7_performance.modules.attribution_analyzer import AttributionAnalyzer
from agents.agent7_performance.modules.risk_analyzer import RiskAnalyzer
from agents.agent7_performance.modules.report_generator import ReportGenerator


def generate_sample_trades(n=100):
    """生成示例交易数据"""
    np.random.seed(42)
    strategies = ["momentum", "value", "sentiment", "cross_market"]
    symbols = ["BTC", "ETH", "00700", "AAPL"]
    
    trades = []
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(n):
        strategy = np.random.choice(strategies)
        symbol = np.random.choice(symbols)
        
        # 不同策略有不同的胜率
        if strategy == "momentum":
            win_prob = 0.68
            avg_pnl = 150
        elif strategy == "value":
            win_prob = 0.55
            avg_pnl = 80
        elif strategy == "sentiment":
            win_prob = 0.60
            avg_pnl = 100
        else:  # cross_market
            win_prob = 0.58
            avg_pnl = 50
        
        is_win = np.random.random() < win_prob
        pnl = np.random.normal(avg_pnl if is_win else -avg_pnl/2, 50)
        
        trade = {
            "symbol": symbol,
            "strategy": strategy,
            "pnl": pnl,
            "pnl_pct": pnl / 10000,  # 假设每单1万
            "timestamp": base_time + timedelta(hours=i*2),
            "entry_price": 100 + np.random.random() * 50,
            "exit_price": 100 + np.random.random() * 50,
            "holding_time": np.random.randint(300, 7200),
            "slippage": np.random.random() * 0.001,
            "transaction_cost": 5 + np.random.random() * 10,
            "factors": {
                "rsi": np.random.random() * 100,
                "macd": np.random.random() * 10 - 5,
                "volume_ratio": 0.5 + np.random.random() * 2,
            },
            "market_condition": {
                "volatility": np.random.choice(["low", "medium", "high"]),
                "trend": np.random.choice(["up", "down", "sideways"]),
            }
        }
        trades.append(trade)
    
    return trades


async def main():
    """主函数"""
    print("=" * 60)
    print("Agent 7: PerformanceAnalyzer 示例")
    print("=" * 60)
    
    # 生成示例数据
    print("\n1. 生成示例交易数据...")
    trades = generate_sample_trades(100)
    print(f"   生成了 {len(trades)} 笔交易记录")
    
    initial_capital = 1000000  # 100万初始资金
    
    # 计算绩效指标
    print("\n2. 计算绩效指标...")
    metrics_calc = MetricsCalculator()
    metrics = metrics_calc.calculate(trades, initial_capital)
    
    print(f"   总收益率: {metrics['total_return']:.2%}")
    print(f"   夏普比率: {metrics['sharpe_ratio']:.2f}")
    print(f"   最大回撤: {metrics['max_drawdown']:.2%}")
    print(f"   胜率: {metrics['win_rate']:.1%}")
    print(f"   盈亏比: {metrics['profit_loss_ratio']:.2f}")
    print(f"   索提诺比率: {metrics['sortino_ratio']:.2f}")
    print(f"   卡尔马比率: {metrics['calmar_ratio']:.2f}")
    
    # 策略归因分析
    print("\n3. 策略归因分析...")
    attribution_analyzer = AttributionAnalyzer()
    attribution = attribution_analyzer.analyze(trades)
    
    for strategy, data in attribution["strategy_contributions"].items():
        print(f"   {strategy}: 贡献={data['contribution']:.2f}, "
              f"胜率={data['win_rate']:.1%}, "
              f"交易数={data['trade_count']}")
    
    # 风险分析
    print("\n4. 风险分析...")
    risk_analyzer = RiskAnalyzer()
    risk_metrics = risk_analyzer.analyze(trades)
    
    var_data = risk_metrics["var"]
    cvar_data = risk_metrics["cvar"]
    tail_risk = risk_metrics["tail_risk"]
    
    print(f"   VaR (95%): {var_data.get('var_95_historical', 0):.2%}")
    print(f"   CVaR (95%): {cvar_data.get('cvar_95_historical', 0):.2%}")
    print(f"   波动率: {risk_metrics['volatility']:.2%}")
    print(f"   偏度: {tail_risk.get('skewness', 0):.2f}")
    print(f"   峰度: {tail_risk.get('kurtosis', 0):.2f}")
    
    # 生成报告
    print("\n5. 生成报告...")
    report_gen = ReportGenerator()
    
    # 生成建议
    recommendations = [
        "增加动量策略权重(当前贡献最高)",
        "优化跨市场传导信号阈值",
    ]
    
    report = report_gen.generate(
        report_type="daily",
        timestamp=datetime.now(),
        metrics=metrics,
        attribution=attribution,
        risk_metrics=risk_metrics,
        recommendations=recommendations,
        trade_count=len(trades)
    )
    
    # 打印报告摘要
    print("\n" + "=" * 60)
    print("报告摘要")
    print("=" * 60)
    print(f"报告类型: {report['report_type']}")
    print(f"交易笔数: {report['trade_count']}")
    print(f"总收益率: {report['summary']['total_return']:.2%}")
    print(f"夏普比率: {report['summary']['sharpe_ratio']:.2f}")
    
    # 生成文本报告
    text_report = report_gen.generate_text_report(report)
    print("\n" + "=" * 60)
    print("完整文本报告")
    print("=" * 60)
    print(text_report)
    
    # 生成HTML报告
    html_report = report_gen.generate_html_report(report)
    html_path = "/tmp/performance_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"\nHTML报告已保存到: {html_path}")
    
    print("\n" + "=" * 60)
    print("示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
