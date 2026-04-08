"""
Agent 7: PerformanceAnalyzer 测试
"""
import pytest
import numpy as np
from datetime import datetime, timedelta

from agents.agent7_performance.modules.metrics_calculator import MetricsCalculator
from agents.agent7_performance.modules.attribution_analyzer import AttributionAnalyzer
from agents.agent7_performance.modules.risk_analyzer import RiskAnalyzer
from agents.agent7_performance.modules.report_generator import ReportGenerator


class TestMetricsCalculator:
    """测试绩效指标计算模块"""
    
    def test_empty_trades(self):
        """测试空交易列表"""
        calc = MetricsCalculator()
        metrics = calc.calculate([], 1000000)
        assert metrics["total_return"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0
    
    def test_total_return(self):
        """测试总收益率计算"""
        calc = MetricsCalculator()
        trades = [
            {"pnl": 1000, "pnl_pct": 0.001},
            {"pnl": -500, "pnl_pct": -0.0005},
            {"pnl": 2000, "pnl_pct": 0.002},
        ]
        metrics = calc.calculate(trades, 1000000)
        assert metrics["total_return"] == 0.0025  # 2500 / 1000000
    
    def test_win_rate(self):
        """测试胜率计算"""
        calc = MetricsCalculator()
        trades = [
            {"pnl": 100, "pnl_pct": 0.001},
            {"pnl": -50, "pnl_pct": -0.0005},
            {"pnl": 200, "pnl_pct": 0.002},
            {"pnl": -30, "pnl_pct": -0.0003},
        ]
        metrics = calc.calculate(trades, 1000000)
        assert metrics["win_rate"] == 0.5  # 2/4
    
    def test_pl_ratio(self):
        """测试盈亏比计算"""
        calc = MetricsCalculator()
        trades = [
            {"pnl": 200, "pnl_pct": 0.002},
            {"pnl": -100, "pnl_pct": -0.001},
        ]
        metrics = calc.calculate(trades, 1000000)
        assert metrics["profit_loss_ratio"] == 2.0  # 200 / 100
    
    def test_max_drawdown(self):
        """测试最大回撤计算"""
        calc = MetricsCalculator()
        trades = [
            {"pnl": 1000, "pnl_pct": 0.001},
            {"pnl": 500, "pnl_pct": 0.0005},
            {"pnl": -2000, "pnl_pct": -0.002},  # 回撤
            {"pnl": 1000, "pnl_pct": 0.001},
            {"pnl": -3000, "pnl_pct": -0.003},  # 更大回撤
        ]
        metrics = calc.calculate(trades, 1000000)
        assert metrics["max_drawdown"] < 0


class TestAttributionAnalyzer:
    """测试策略归因分析模块"""
    
    def test_empty_trades(self):
        """测试空交易列表"""
        analyzer = AttributionAnalyzer()
        result = analyzer.analyze([])
        assert result["strategy_contributions"] == {}
    
    def test_strategy_contributions(self):
        """测试策略贡献度分析"""
        analyzer = AttributionAnalyzer()
        trades = [
            {"symbol": "BTC", "strategy": "momentum", "pnl": 1000},
            {"symbol": "ETH", "strategy": "momentum", "pnl": 500},
            {"symbol": "BTC", "strategy": "value", "pnl": -300},
            {"symbol": "ETH", "strategy": "sentiment", "pnl": 200},
        ]
        result = analyzer.analyze(trades)
        
        contributions = result["strategy_contributions"]
        assert contributions["momentum"]["total_pnl"] == 1500
        assert contributions["value"]["total_pnl"] == -300
        assert contributions["sentiment"]["total_pnl"] == 200
    
    def test_time_analysis(self):
        """测试时间维度分析"""
        analyzer = AttributionAnalyzer()
        now = datetime.now()
        trades = [
            {"symbol": "BTC", "pnl": 100, "timestamp": now},
            {"symbol": "ETH", "pnl": 200, "timestamp": now - timedelta(hours=1)},
        ]
        result = analyzer.analyze(trades)
        
        time_analysis = result["time_analysis"]
        assert "daily_pnl" in time_analysis


class TestRiskAnalyzer:
    """测试风险分析模块"""
    
    def test_empty_trades(self):
        """测试空交易列表"""
        analyzer = RiskAnalyzer()
        result = analyzer.analyze([])
        assert result["var"] == {}
        assert result["cvar"] == {}
    
    def test_var_calculation(self):
        """测试VaR计算"""
        analyzer = RiskAnalyzer()
        np.random.seed(42)
        returns = np.random.normal(0, 0.02, 1000)  # 正态分布收益率
        trades = [{"pnl_pct": r} for r in returns]
        
        result = analyzer.analyze(trades)
        var_95 = result["var"]["var_95_historical"]
        
        # VaR应该是负数（表示损失）
        assert var_95 < 0
        # 约5%的数据应该小于VaR
        count_below_var = sum(1 for r in returns if r <= var_95)
        assert 0.04 < count_below_var / len(returns) < 0.06
    
    def test_volatility_calculation(self):
        """测试波动率计算"""
        analyzer = RiskAnalyzer()
        np.random.seed(42)
        returns = np.random.normal(0, 0.02, 252)  # 一年的日收益率
        trades = [{"pnl_pct": r} for r in returns]
        
        result = analyzer.analyze(trades)
        volatility = result["volatility"]
        
        # 年化波动率应该接近 0.02 * sqrt(252)
        expected_vol = 0.02 * np.sqrt(252)
        assert abs(volatility - expected_vol) < 0.1
    
    def test_tail_risk(self):
        """测试尾部风险分析"""
        analyzer = RiskAnalyzer()
        # 创建一个负偏分布
        returns = np.concatenate([
            np.random.normal(0.001, 0.01, 900),
            np.random.normal(-0.05, 0.02, 100)  # 尾部损失
        ])
        trades = [{"pnl_pct": r} for r in returns]
        
        result = analyzer.analyze(trades)
        tail_risk = result["tail_risk"]
        
        assert tail_risk["skewness"] < 0  # 负偏
        assert tail_risk["is_negative_skewed"] == True


class TestReportGenerator:
    """测试报告生成模块"""
    
    def test_generate_report(self):
        """测试报告生成"""
        generator = ReportGenerator()
        
        report = generator.generate(
            report_type="daily",
            timestamp=datetime.now(),
            metrics={
                "total_return": 0.05,
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.1,
                "win_rate": 0.6,
                "profit_loss_ratio": 2.0,
                "sortino_ratio": 1.8,
                "calmar_ratio": 0.5,
                "total_pnl": 50000,
                "avg_pnl": 500,
            },
            attribution={
                "strategy_contributions": {
                    "momentum": {
                        "contribution": 0.03,
                        "contribution_pct": 0.6,
                        "win_rate": 0.65,
                        "trade_count": 50,
                        "avg_pnl": 600,
                    }
                }
            },
            risk_metrics={
                "var": {"var_95_historical": -0.025},
                "cvar": {"cvar_95_historical": -0.035},
                "volatility": 0.18,
                "tail_risk": {"skewness": -0.5, "kurtosis": 3.5},
                "drawdown_analysis": {"current_drawdown": -0.05},
            },
            recommendations=["建议1", "建议2"],
            trade_count=100
        )
        
        assert report["report_type"] == "daily"
        assert report["summary"]["total_return"] == 0.05
        assert len(report["recommendations"]) == 2
    
    def test_html_report(self):
        """测试HTML报告生成"""
        generator = ReportGenerator()
        
        report = {
            "report_type": "daily",
            "generated_at": "2024-01-01T00:00:00",
            "trade_count": 100,
            "summary": {
                "total_return": 0.05,
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.1,
                "win_rate": 0.6,
            },
            "strategy_attribution": {
                "momentum": {"contribution": 0.03, "win_rate": 0.65}
            },
            "risk_metrics": {
                "var_95": -0.025,
                "cvar_95": -0.035,
            },
            "recommendations": ["建议1"],
        }
        
        html = generator.generate_html_report(report)
        assert "绩效报告" in html
        assert "DAILY" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
