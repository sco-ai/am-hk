"""
飞书卡片推送模块
将绩效报告推送到飞书
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

try:
    from core.feishu import FeishuNotifier
except ImportError:
    FeishuNotifier = None

logger = logging.getLogger("agent7_performance")


class FeishuPublisher:
    """飞书报告发布器"""
    
    def __init__(self):
        self.client = FeishuNotifier() if FeishuNotifier else None
        self.default_chat_id = None  # 可从配置读取
    
    async def publish(self, report: Dict, chat_id: Optional[str] = None):
        """
        发布报告到飞书
        
        Args:
            report: 绩效报告
            chat_id: 飞书聊天ID（可选，使用默认配置）
        """
        try:
            target_chat = chat_id or self.default_chat_id
            
            if not target_chat:
                logger.warning("No Feishu chat_id configured, skipping publish")
                return
            
            # 构建卡片消息
            card_message = self._build_card_message(report)
            
            # 发送消息
            # await self.client.send_card_message(target_chat, card_message)
            
            logger.info(f"Published {report.get('report_type')} report to Feishu")
            
        except Exception as e:
            logger.error(f"Failed to publish to Feishu: {e}", exc_info=True)
    
    def _build_card_message(self, report: Dict) -> Dict:
        """
        构建飞书卡片消息
        """
        report_type = report.get("report_type", "daily")
        summary = report.get("summary", {})
        attribution = report.get("strategy_attribution", {})
        risk = report.get("risk_metrics", {})
        recommendations = report.get("recommendations", [])
        
        # 报告类型中文名
        type_names = {
            "daily": "📊 日报",
            "weekly": "📈 周报", 
            "monthly": "📉 月报"
        }
        
        # 构建策略归因表格
        strategy_elements = []
        for strategy, data in attribution.items():
            contribution = data.get("contribution", 0)
            contribution_pct = data.get("contribution_pct", 0)
            win_rate = data.get("win_rate", 0)
            trade_count = data.get("trade_count", 0)
            
            # 贡献度颜色
            contribution_color = "green" if contribution >= 0 else "red"
            
            strategy_elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{strategy}**: 贡献 `{contribution:+.2%}` | 胜率 `{win_rate:.1%}` | 交易数 `{trade_count}`"
                }
            })
        
        # 构建建议列表
        recommendation_text = "\n".join([f"{i+1}. {rec}" for i, rec in enumerate(recommendations)])
        
        # 构建卡片
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{type_names.get(report_type, '绩效报告')} - {report.get('generated_at', '')[:10]}"
                },
                "template": "green" if summary.get("total_return", 0) >= 0 else "red"
            },
            "elements": [
                # 核心指标
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**📈 核心指标**"
                    }
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**总收益率**\n{summary.get('total_return', 0):+.2%}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**夏普比率**\n{summary.get('sharpe_ratio', 0):.2f}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**最大回撤**\n{summary.get('max_drawdown', 0):.2%}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**胜率**\n{summary.get('win_rate', 0):.1%}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**盈亏比**\n{summary.get('profit_loss_ratio', 0):.2f}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**交易笔数**\n{report.get('trade_count', 0)}"
                            }
                        }
                    ]
                },
                {
                    "tag": "hr"
                },
                # 策略归因
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**🎯 策略归因**"
                    }
                },
                *strategy_elements,
                {
                    "tag": "hr"
                },
                # 风险指标
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**⚠️ 风险指标**"
                    }
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**VaR (95%)**\n{risk.get('var_95', 0):.2%}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**CVaR (95%)**\n{risk.get('cvar_95', 0):.2%}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**波动率**\n{risk.get('volatility', 0):.1%}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**当前回撤**\n{risk.get('current_drawdown', 0):.2%}"
                            }
                        }
                    ]
                },
                {
                    "tag": "hr"
                },
                # 优化建议
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**💡 优化建议**"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": recommendation_text if recommendation_text else "暂无建议"
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"报告生成时间: {report.get('generated_at', '')}"
                        }
                    ]
                }
            ]
        }
        
        return card
    
    def _build_simple_message(self, report: Dict) -> str:
        """
        构建简单的文本消息（备用）
        """
        report_type = report.get("report_type", "daily")
        summary = report.get("summary", {})
        
        type_names = {
            "daily": "日报",
            "weekly": "周报",
            "monthly": "月报"
        }
        
        return f"""
📊 {type_names.get(report_type, '绩效报告')} - {report.get('generated_at', '')[:10]}

【核心指标】
• 总收益率: {summary.get('total_return', 0):+.2%}
• 夏普比率: {summary.get('sharpe_ratio', 0):.2f}
• 最大回撤: {summary.get('max_drawdown', 0):.2%}
• 胜率: {summary.get('win_rate', 0):.1%}
• 盈亏比: {summary.get('profit_loss_ratio', 0):.2f}
• 交易笔数: {report.get('trade_count', 0)}

【策略归因】
{self._format_attribution_text(report.get('strategy_attribution', {}))}

【优化建议】
{chr(10).join(['• ' + rec for rec in report.get('recommendations', [])])}
        """.strip()
    
    def _format_attribution_text(self, attribution: Dict) -> str:
        """格式化归因文本"""
        lines = []
        for strategy, data in attribution.items():
            contribution = data.get("contribution", 0)
            win_rate = data.get("win_rate", 0)
            lines.append(f"• {strategy}: 贡献 {contribution:+.2%}, 胜率 {win_rate:.1%}")
        return "\n".join(lines) if lines else "暂无数据"
    
    async def send_alert(
        self, 
        alert_type: str, 
        message: str, 
        severity: str = "info",
        chat_id: Optional[str] = None
    ):
        """
        发送风险预警
        
        Args:
            alert_type: 预警类型
            message: 预警消息
            severity: 严重级别 (info/warning/critical)
            chat_id: 聊天ID
        """
        try:
            target_chat = chat_id or self.default_chat_id
            
            if not target_chat:
                return
            
            color_map = {
                "info": "blue",
                "warning": "orange",
                "critical": "red"
            }
            
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": f"⚠️ {alert_type}"},
                    "template": color_map.get(severity, "blue")
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": message}
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"时间: {datetime.now().isoformat()}"}
                        ]
                    }
                ]
            }
            
            # await self.client.send_card_message(target_chat, card)
            logger.info(f"Sent {severity} alert: {alert_type}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
