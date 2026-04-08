#!/usr/bin/env python3
"""
Agent 7 测试脚本 - PerformanceAnalyzer 绩效分析层
测试绩效指标计算、策略归因、报告生成
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import time
import random


class PerformanceAnalyzer:
    """Agent 7: 绩效分析器"""
    
    def __init__(self):
        self.trades = []
        self.equity_curve = [1.0]  # 从1.0开始
    
    def calculate_returns(self, trades):
        """计算收益率"""
        if not trades:
            return 0.0, 0.0
        
        returns = [t.get("pnl", 0) for t in trades]
        total_return = sum(returns)
        
        # 年化收益 (假设252个交易日)
        days = 30  # 假设测试周期30天
        annualized_return = total_return * (252 / max(days, 1))
        
        return total_return, annualized_return
    
    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """计算夏普比率"""
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        return (mean_return - risk_free_rate / 252) / std_dev * (252 ** 0.5)
    
    def calculate_max_drawdown(self, equity_curve):
        """计算最大回撤"""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def calculate_win_rate(self, trades):
        """计算胜率"""
        if not trades:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return winning_trades / len(trades)
    
    def calculate_profit_loss_ratio(self, trades):
        """计算盈亏比"""
        profits = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]
        losses = [abs(t.get("pnl", 0)) for t in trades if t.get("pnl", 0) < 0]
        
        if not losses:
            return float('inf') if profits else 0.0
        
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses) / len(losses) if losses else 0.001
        
        return avg_profit / avg_loss
    
    def calculate_var_cvar(self, returns, confidence=0.95):
        """计算VaR和CVaR"""
        if len(returns) < 10:
            return 0.0, 0.0
        
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        var = sorted_returns[max(0, index)]
        
        # CVaR是超过VaR阈值的平均损失
        cvar = sum(r for r in sorted_returns if r <= var) / max(1, index)
        
        return var, cvar
    
    def analyze_strategy_attribution(self, trades):
        """策略归因分析"""
        strategy_stats = {
            "momentum": {"returns": [], "pnl": 0, "trades": 0},
            "value": {"returns": [], "pnl": 0, "trades": 0},
            "sentiment": {"returns": [], "pnl": 0, "trades": 0},
            "cross_market": {"returns": [], "pnl": 0, "trades": 0}
        }
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        
        for trade in trades:
            strategy = trade.get("strategy", "momentum")
            if strategy in strategy_stats:
                strategy_stats[strategy]["returns"].append(trade.get("pnl", 0))
                strategy_stats[strategy]["pnl"] += trade.get("pnl", 0)
                strategy_stats[strategy]["trades"] += 1
        
        attributions = {}
        for name, stats in strategy_stats.items():
            if stats["trades"] > 0:
                wins = sum(1 for r in stats["returns"] if r > 0)
                attributions[name] = {
                    "contribution": round(stats["pnl"] / max(0.001, total_pnl), 4),
                    "win_rate": round(wins / stats["trades"], 4),
                    "trade_count": stats["trades"],
                    "total_pnl": round(stats["pnl"], 4)
                }
        
        return attributions
    
    def generate_recommendations(self, metrics, attributions):
        """生成改进建议"""
        recommendations = []
        
        if metrics["sharpe_ratio"] < 1.0:
            recommendations.append(f"夏普比率偏低({metrics['sharpe_ratio']:.2f})，建议优化风险控制")
        
        if metrics["max_drawdown"] < -0.15:
            recommendations.append(f"最大回撤较大({metrics['max_drawdown']:.1%})，建议收紧止损")
        
        if metrics["win_rate"] < 0.5:
            recommendations.append(f"胜率偏低({metrics['win_rate']:.1%})，建议优化入场信号")
        
        if attributions:
            best_strategy = max(attributions.items(), key=lambda x: x[1]["contribution"])
            worst_strategy = min(attributions.items(), key=lambda x: x[1]["contribution"])
            
            if best_strategy[1]["contribution"] > 0.3:
                recommendations.append(f"{best_strategy[0]}策略贡献突出({best_strategy[1]['contribution']:.1%})，建议增加权重")
            
            if worst_strategy[1]["contribution"] < 0.1:
                recommendations.append(f"{worst_strategy[0]}策略表现较弱，建议优化或降低权重")
        
        return recommendations if recommendations else ["当前策略运行平稳，继续保持"]
    
    def generate_report(self, trades, report_type="daily"):
        """生成绩效报告"""
        print(f"\n{'='*60}")
        print(f"📊 Agent 7 - 绩效分析报告 ({report_type.upper()})")
        print(f"{'='*60}")
        
        if not trades:
            print("⚠️ 无交易数据")
            return None
        
        returns = [t.get("pnl", 0) for t in trades]
        
        # 计算核心指标
        total_return, annualized_return = self.calculate_returns(trades)
        sharpe_ratio = self.calculate_sharpe_ratio(returns)
        max_drawdown = self.calculate_max_drawdown(self.equity_curve)
        win_rate = self.calculate_win_rate(trades)
        pl_ratio = self.calculate_profit_loss_ratio(trades)
        volatility = (sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns)) ** 0.5 * (252 ** 0.5)
        var_95, cvar_95 = self.calculate_var_cvar(returns)
        
        # 卡尔马比率
        calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        print(f"\n📈 核心绩效指标")
        print("-" * 50)
        print(f"   总收益率: {total_return:+.2%}")
        print(f"   年化收益率: {annualized_return:+.2%}")
        print(f"   夏普比率: {sharpe_ratio:.2f}")
        print(f"   最大回撤: {max_drawdown:.2%}")
        print(f"   卡尔马比率: {calmar:.2f}")
        print(f"   胜率: {win_rate:.2%}")
        print(f"   盈亏比: {pl_ratio:.2f}")
        print(f"   波动率: {volatility:.2%}")
        
        print(f"\n📉 风险指标")
        print("-" * 50)
        print(f"   VaR (95%): {var_95:.2%}")
        print(f"   CVaR (95%): {cvar_95:.2%}")
        
        # 策略归因
        print(f"\n🎯 策略归因分析")
        print("-" * 50)
        attributions = self.analyze_strategy_attribution(trades)
        for name, attr in attributions.items():
            print(f"   {name:<15}: 贡献度={attr['contribution']:+.2%}, "
                  f"胜率={attr['win_rate']:.1%}, 交易数={attr['trade_count']}")
        
        # 生成建议
        metrics = {
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate
        }
        recommendations = self.generate_recommendations(metrics, attributions)
        
        print(f"\n💡 改进建议")
        print("-" * 50)
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
        
        # 构建报告
        report = {
            "report_type": report_type,
            "timestamp": int(time.time() * 1000),
            "period": {
                "trade_count": len(trades),
                "start_time": min(t.get("entry_time", 0) for t in trades),
                "end_time": max(t.get("exit_time", 0) for t in trades)
            },
            "summary": {
                "total_return": round(total_return, 4),
                "annualized_return": round(annualized_return, 4),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "max_drawdown": round(max_drawdown, 4),
                "calmar_ratio": round(calmar, 4),
                "win_rate": round(win_rate, 4),
                "profit_loss_ratio": round(pl_ratio, 4),
                "volatility": round(volatility, 4)
            },
            "risk_metrics": {
                "var_95": round(var_95, 4),
                "cvar_95": round(cvar_95, 4)
            },
            "strategy_attribution": attributions,
            "recommendations": recommendations,
            "equity_curve_sample": self.equity_curve[-10:] if len(self.equity_curve) > 10 else self.equity_curve
        }
        
        return report


def main():
    """主测试函数"""
    print("🚀 Agent 7 (PerformanceAnalyzer) 测试")
    print("="*60)
    
    # 模拟交易结果
    trades = [
        {
            "symbol": "XRPUSDT",
            "strategy": "momentum",
            "entry_time": 1775600000000,
            "exit_time": 1775607200000,
            "entry_price": 100,
            "exit_price": 104.5,
            "pnl": 0.045,
            "hold_time": "2h"
        },
        {
            "symbol": "DOGEUSDT",
            "strategy": "sentiment",
            "entry_time": 1775601000000,
            "exit_time": 1775608200000,
            "entry_price": 100,
            "exit_price": 97.8,
            "pnl": -0.022,
            "hold_time": "3h"
        },
        {
            "symbol": "SOLUSDT",
            "strategy": "momentum",
            "entry_time": 1775602000000,
            "exit_time": 1775607400000,
            "entry_price": 150,
            "exit_price": 158,
            "pnl": 0.053,
            "hold_time": "1.5h"
        },
        {
            "symbol": "ETHUSDT",
            "strategy": "value",
            "entry_time": 1775603000000,
            "exit_time": 1775609000000,
            "entry_price": 3500,
            "exit_price": 3542,
            "pnl": 0.012,
            "hold_time": "1.7h"
        },
        {
            "symbol": "BTCUSDT",
            "strategy": "cross_market",
            "entry_time": 1775604000000,
            "exit_time": 1775610000000,
            "entry_price": 65000,
            "exit_price": 65975,
            "pnl": 0.015,
            "hold_time": "1.7h"
        }
    ]
    
    print(f"\n📥 输入: {len(trades)} 笔交易记录")
    
    # 初始化分析器
    analyzer = PerformanceAnalyzer()
    
    # 更新权益曲线
    for trade in trades:
        pnl = trade["pnl"]
        current = analyzer.equity_curve[-1] * (1 + pnl)
        analyzer.equity_curve.append(current)
    
    # 生成报告
    report = analyzer.generate_report(trades, "daily")
    
    # 输出结果
    print("\n" + "="*60)
    print("📤 Agent7 输出格式 (Kafka: am-hk-performance-reports)")
    print("="*60)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    print("\n" + "="*60)
    print("📊 绩效分析汇总")
    print("="*60)
    print(f"   报告类型: {report['report_type']}")
    print(f"   交易笔数: {report['period']['trade_count']}")
    print(f"   总收益: {report['summary']['total_return']:+.2%}")
    print(f"   夏普比率: {report['summary']['sharpe_ratio']:.2f}")
    print(f"   最大回撤: {report['summary']['max_drawdown']:.2%}")
    print(f"   胜率: {report['summary']['win_rate']:.1%}")
    
    print("\n✅ Agent7 测试完成")
    print(f"   输出: 绩效分析报告")
    print(f"   推送到: am-hk-performance-reports")
    print(f"   广播给: 所有Agent (Agent3/4/5/6)")
    
    return report


if __name__ == "__main__":
    main()
