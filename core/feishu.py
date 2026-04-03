"""
飞书通知模块
支持交互式卡片、文本消息、Markdown等多种格式
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from core.config import settings
from core.utils import setup_logging

logger = setup_logging("feishu_notifier")


class FeishuNotifier:
    """
    飞书通知器
    
    支持：
    - 文本消息
    - Markdown消息
    - 交互式卡片
    - 交易信号通知
    - 系统状态报告
    """
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or settings.FEISHU_WEBHOOK_URL
        self.client = httpx.AsyncClient(timeout=30.0)
        
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")
        
        logger.info("Feishu notifier initialized")
    
    async def send_text(self, text: str, at_all: bool = False) -> bool:
        """
        发送纯文本消息
        
        Args:
            text: 消息内容
            at_all: 是否@所有人
        """
        if not self.webhook_url:
            logger.error("Webhook URL not configured")
            return False
        
        payload = {
            "msg_type": "text",
            "content": {
                "text": text,
            },
        }
        
        if at_all:
            payload["content"]["text"] += "\n<at user_id=\"all\">所有人</at>"
        
        return await self._send(payload)
    
    async def send_markdown(self, title: str, content: str) -> bool:
        """
        发送Markdown消息
        
        Args:
            title: 标题
            content: Markdown内容
        """
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        },
                    }
                ],
            },
        }
        
        return await self._send(payload)
    
    async def send_signal_card(
        self,
        symbol: str,
        action: str,
        confidence: float,
        predicted_return: float,
        reasoning: str,
        position_size: float,
        stop_loss: float,
        take_profit: float,
        market: str = "US",
    ) -> bool:
        """
        发送交易信号卡片
        
        示例:
            🟢 BUY BTCUSDT
            置信度: 75%
            预期收益: +3.2%
            ...
        """
        # 根据action设置颜色
        color_map = {
            "buy": "green",
            "sell": "red",
            "hold": "grey",
        }
        template = color_map.get(action.lower(), "blue")
        
        # 图标
        icon_map = {
            "buy": "🟢",
            "sell": "🔴",
            "hold": "⚪",
        }
        icon = icon_map.get(action.lower(), "⚪")
        
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{icon} {action.upper()} {symbol}",
                },
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**置信度**\n{confidence:.1%}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**预期收益**\n{predicted_return:+.2f}%",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**仓位**\n{position_size:.1%}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**止盈/止损**\n{take_profit:.1%} / {stop_loss:.1%}",
                            },
                        },
                    ],
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**推理分析**\n{reasoning}",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 确认执行",
                            },
                            "type": "primary",
                            "value": {
                                "action": "confirm_trade",
                                "symbol": symbol,
                                "trade_action": action,
                            },
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 拒绝",
                            },
                            "type": "danger",
                            "value": {
                                "action": "reject_trade",
                                "symbol": symbol,
                            },
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📊 详情",
                            },
                            "type": "default",
                            "value": {
                                "action": "view_details",
                                "symbol": symbol,
                            },
                        },
                    ],
                },
            ],
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        
        return await self._send(payload)
    
    async def send_status_report(
        self,
        system_status: str,
        active_agents: int,
        total_trades: int,
        daily_pnl: float,
        positions: List[Dict],
    ) -> bool:
        """
        发送系统状态报告
        """
        # 构建持仓信息
        position_text = ""
        for pos in positions[:5]:
            pnl_emoji = "🟢" if pos.get("pnl", 0) > 0 else "🔴"
            position_text += f"- {pos.get('symbol')}: {pos.get('quantity')}股 {pnl_emoji} ${pos.get('pnl', 0):,.2f}\n"
        
        if len(positions) > 5:
            position_text += f"- ... 还有 {len(positions) - 5} 个持仓\n"
        
        pnl_emoji = "🟢" if daily_pnl > 0 else "🔴"
        
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 AM-HK 系统状态报告",
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**系统状态**\n{system_status}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**活跃Agent**\n{active_agents}/6",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**今日交易**\n{total_trades}笔",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**今日盈亏**\n{pnl_emoji} ${daily_pnl:,.2f}",
                            },
                        },
                    ],
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**当前持仓**\n{position_text}",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "🚀 启动交易",
                            },
                            "type": "primary",
                            "value": {"action": "start_trading"},
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "🛑 停止交易",
                            },
                            "type": "danger",
                            "value": {"action": "stop_trading"},
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📈 查看详情",
                            },
                            "type": "default",
                            "value": {"action": "view_full_report"},
                        },
                    ],
                },
            ],
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        
        return await self._send(payload)
    
    async def send_daily_report(
        self,
        date: str,
        total_trades: int,
        win_rate: float,
        total_pnl: float,
        sharpe_ratio: float,
        best_trade: Dict,
        worst_trade: Dict,
    ) -> bool:
        """
        发送每日交易报告
        """
        pnl_emoji = "🟢" if total_pnl > 0 else "🔴"
        
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📈 {date} 交易日报",
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**总交易**\n{total_trades}笔",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**胜率**\n{win_rate:.1%}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**总盈亏**\n{pnl_emoji} ${total_pnl:,.2f}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**夏普比率**\n{sharpe_ratio:.2f}",
                            },
                        },
                    ],
                },
                {
                    "tag": "hr",
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**最佳交易** 🏆\n"
                            f"{best_trade.get('symbol')} {best_trade.get('action')} "
                            f"+${best_trade.get('pnl', 0):,.2f}\n\n"
                            f"**最差交易** 📉\n"
                            f"{worst_trade.get('symbol')} {worst_trade.get('action')} "
                            f"${worst_trade.get('pnl', 0):,.2f}"
                        ),
                    },
                },
            ],
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        
        return await self._send(payload)
    
    async def send_alert(
        self,
        title: str,
        message: str,
        level: str = "warning",
    ) -> bool:
        """
        发送告警通知
        
        Args:
            level: "info", "warning", "error", "critical"
        """
        color_map = {
            "info": "blue",
            "warning": "orange",
            "error": "red",
            "critical": "red",
        }
        icon_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }
        
        template = color_map.get(level, "blue")
        icon = icon_map.get(level, "ℹ️")
        
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{icon} {title}",
                },
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": message,
                    },
                },
            ],
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        
        return await self._send(payload)
    
    async def _send(self, payload: Dict) -> bool:
        """
        发送消息到飞书
        
        Args:
            payload: 消息体
        
        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.error("Webhook URL not configured")
            return False
        
        try:
            response = await self.client.post(
                self.webhook_url,
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") != 0:
                logger.error(f"Feishu API error: {result}")
                return False
            
            logger.info("Message sent to Feishu successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send Feishu message: {e}")
            return False
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


# === 便捷函数 ===

async def notify_signal(**kwargs) -> bool:
    """快速发送交易信号通知"""
    notifier = FeishuNotifier()
    try:
        return await notifier.send_signal_card(**kwargs)
    finally:
        await notifier.close()


async def notify_alert(title: str, message: str, level: str = "warning") -> bool:
    """快速发送告警通知"""
    notifier = FeishuNotifier()
    try:
        return await notifier.send_alert(title, message, level)
    finally:
        await notifier.close()
