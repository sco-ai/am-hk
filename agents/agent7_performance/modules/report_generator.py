"""
报告生成模块
生成日报/周报/月报
"""
from typing import Dict, List, Any
from datetime import datetime


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        pass
    
    def generate(
        self,
        report_type: str,
        timestamp: datetime,
        metrics: Dict,
        attribution: Dict,
        risk_metrics: Dict,
        recommendations: List[str],
        trade_count: int
    ) -> Dict:
        """
        生成绩效报告
        
        Args:
            report_type: 报告类型 (daily/weekly/monthly)
            timestamp: 时间戳
            metrics: 绩效指标
            attribution: 归因分析
            risk_metrics: 风险指标
            recommendations: 建议列表
            trade_count: 交易数量
        
        Returns:
            报告字典
        """
        # 格式化策略归因
        strategy_attribution = self._format_strategy_attribution(
            attribution.get("strategy_contributions", {})
        )
        
        # 格式化风险指标
        formatted_risk = self._format_risk_metrics(risk_metrics)
        
        # 格式化摘要
        summary = self._format_summary(metrics)
        
        report = {
            "report_type": report_type,
            "timestamp": int(timestamp.timestamp() * 1000),
            "generated_at": timestamp.isoformat(),
            "summary": summary,
            "strategy_attribution": strategy_attribution,
            "risk_metrics": formatted_risk,
            "recommendations": recommendations,
            "trade_count": trade_count,
            "metadata": {
                "attribution_details": attribution,
                "risk_details": risk_metrics,
                "full_metrics": metrics,
            }
        }
        
        return report
    
    def _format_summary(self, metrics: Dict) -> Dict:
        """格式化摘要指标"""
        return {
            "total_return": round(metrics.get("total_return", 0), 4),
            "sharpe_ratio": round(metrics.get("sharpe_ratio", 0), 2),
            "max_drawdown": round(metrics.get("max_drawdown", 0), 4),
            "win_rate": round(metrics.get("win_rate", 0), 2),
            "profit_loss_ratio": round(metrics.get("profit_loss_ratio", 0), 2),
            "sortino_ratio": round(metrics.get("sortino_ratio", 0), 2),
            "calmar_ratio": round(metrics.get("calmar_ratio", 0), 2),
            "total_pnl": round(metrics.get("total_pnl", 0), 2),
            "avg_pnl": round(metrics.get("avg_pnl", 0), 2),
        }
    
    def _format_strategy_attribution(self, contributions: Dict) -> Dict[str, Dict]:
        """格式化策略归因"""
        formatted = {}
        
        for strategy, data in contributions.items():
            formatted[strategy] = {
                "contribution": round(data.get("contribution", 0), 4),
                "contribution_pct": round(data.get("contribution_pct", 0), 4),
                "win_rate": round(data.get("win_rate", 0), 2),
                "trade_count": data.get("trade_count", 0),
                "avg_pnl": round(data.get("avg_pnl", 0), 2),
            }
        
        return formatted
    
    def _format_risk_metrics(self, risk_metrics: Dict) -> Dict:
        """格式化风险指标"""
        var_data = risk_metrics.get("var", {})
        cvar_data = risk_metrics.get("cvar", {})
        tail_risk = risk_metrics.get("tail_risk", {})
        
        return {
            "var_95": round(var_data.get("var_95_historical", 0), 4),
            "var_99": round(var_data.get("var_99_historical", 0), 4),
            "cvar_95": round(cvar_data.get("cvar_95_historical", 0), 4),
            "cvar_99": round(cvar_data.get("cvar_99_historical", 0), 4),
            "volatility": round(risk_metrics.get("volatility", 0), 4),
            "skewness": round(tail_risk.get("skewness", 0), 2),
            "kurtosis": round(tail_risk.get("kurtosis", 0), 2),
            "max_loss": round(tail_risk.get("max_loss", 0), 4),
            "current_drawdown": round(
                risk_metrics.get("drawdown_analysis", {}).get("current_drawdown", 0), 4
            ),
        }
    
    def generate_html_report(self, report: Dict) -> str:
        """
        生成HTML格式的报告（用于可视化展示）
        """
        report_type = report.get("report_type", "daily").upper()
        summary = report.get("summary", {})
        attribution = report.get("strategy_attribution", {})
        risk = report.get("risk_metrics", {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>绩效报告 - {report_type}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
                h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
                h2 {{ color: #555; margin-top: 30px; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
                .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
                .metric-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
                .positive {{ color: #4CAF50; }}
                .negative {{ color: #f44336; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #4CAF50; color: white; }}
                tr:hover {{ background: #f5f5f5; }}
                .recommendations {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin-top: 20px; }}
                .recommendations li {{ margin: 10px 0; color: #1565c0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 {report_type} 绩效报告</h1>
                <p>生成时间: {report.get("generated_at", "")}</p>
                <p>交易笔数: {report.get("trade_count", 0)}</p>
                
                <h2>核心指标</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value {"positive" if summary.get("total_return", 0) >= 0 else "negative"}">
                            {summary.get("total_return", 0):.2%}
                        </div>
                        <div class="metric-label">总收益率</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{summary.get("sharpe_ratio", 0):.2f}</div>
                        <div class="metric-label">夏普比率</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value negative">{summary.get("max_drawdown", 0):.2%}</div>
                        <div class="metric-label">最大回撤</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{summary.get("win_rate", 0):.1%}</div>
                        <div class="metric-label">胜率</div>
                    </div>
                </div>
                
                <h2>策略归因</h2>
                <table>
                    <tr>
                        <th>策略</th>
                        <th>贡献度</th>
                        <th>胜率</th>
                        <th>交易数</th>
                    </tr>
        """
        
        for strategy, data in attribution.items():
            html += f"""
                    <tr>
                        <td>{strategy}</td>
                        <td class="{"positive" if data.get("contribution", 0) >= 0 else "negative"}">
                            {data.get("contribution", 0):.2%}
                        </td>
                        <td>{data.get("win_rate", 0):.1%}</td>
                        <td>{data.get("trade_count", 0)}</td>
                    </tr>
            """
        
        html += """
                </table>
                
                <h2>风险指标</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">{:.2%}</div>
                        <div class="metric-label">VaR (95%)</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{:.2%}</div>
                        <div class="metric-label">CVaR (95%)</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{:.1%}</div>
                        <div class="metric-label">波动率</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{:.2%}</div>
                        <div class="metric-label">当前回撤</div>
                    </div>
                </div>
        """.format(
            risk.get("var_95", 0),
            risk.get("cvar_95", 0),
            risk.get("volatility", 0),
            risk.get("current_drawdown", 0)
        )
        
        html += """
                <h2>优化建议</h2>
                <div class="recommendations">
                    <ul>
        """
        
        for rec in report.get("recommendations", []):
            html += f"<li>{rec}</li>"
        
        html += """
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def generate_text_report(self, report: Dict) -> str:
        """
        生成文本格式的报告
        """
        lines = [
            f"📊 {report.get('report_type', 'daily').upper()} 绩效报告",
            f"生成时间: {report.get('generated_at', '')}",
            f"交易笔数: {report.get('trade_count', 0)}",
            "",
            "【核心指标】",
        ]
        
        summary = report.get("summary", {})
        lines.extend([
            f"总收益率: {summary.get('total_return', 0):.2%}",
            f"夏普比率: {summary.get('sharpe_ratio', 0):.2f}",
            f"最大回撤: {summary.get('max_drawdown', 0):.2%}",
            f"胜率: {summary.get('win_rate', 0):.1%}",
            f"盈亏比: {summary.get('profit_loss_ratio', 0):.2f}",
            f"索提诺比率: {summary.get('sortino_ratio', 0):.2f}",
            f"卡尔马比率: {summary.get('calmar_ratio', 0):.2f}",
            "",
            "【策略归因】",
        ])
        
        for strategy, data in report.get("strategy_attribution", {}).items():
            lines.append(
                f"{strategy}: 贡献={data.get('contribution', 0):.2%}, "
                f"胜率={data.get('win_rate', 0):.1%}, "
                f"交易数={data.get('trade_count', 0)}"
            )
        
        risk = report.get("risk_metrics", {})
        lines.extend([
            "",
            "【风险指标】",
            f"VaR (95%): {risk.get('var_95', 0):.2%}",
            f"CVaR (95%): {risk.get('cvar_95', 0):.2%}",
            f"波动率: {risk.get('volatility', 0):.1%}",
            f"当前回撤: {risk.get('current_drawdown', 0):.2%}",
            "",
            "【优化建议】",
        ])
        
        for rec in report.get("recommendations", []):
            lines.append(f"• {rec}")
        
        return "\n".join(lines)
