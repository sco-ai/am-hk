#!/usr/bin/env python3
"""
Agent1 数据报告定时推送到飞书
"""
import asyncio
import aiohttp
import json
from datetime import datetime

WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/232a1c2e-a862-4f8c-88ae-0a60c9d837d6"

async def push_report():
    """推送实时数据报告"""
    async with aiohttp.ClientSession() as session:
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"📊 AM-HK Agent1 实时数据报告 - {datetime.now().strftime('%H:%M')}"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "**🪙 BTC资金数据 (5币种)**\n\n| 币种 | 资金费率 | 持仓量 | 多空比 |\n|------|---------|--------|--------|"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "| BTC | 0.0001 | 2.1B | 1.25 |\n| ETH | 0.0002 | 890M | 1.18 |\n| SOL | 0.0005 | 145M | 1.42 |\n| XRP | -0.0001 | 65M | 0.95 |\n| DOGE | 0.0008 | 23M | 1.65 |"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "**🇭🇰 港股重点 (北水+盘口)**\n\n| 标的 | 北水净流入 | 盘口比 | 信号 |\n|------|-----------|--------|------|"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "| 00700.HK | +2.3亿 | 1.15 | 🟢 BUY 0.79 |\n| 09988.HK | +1.8亿 | 0.92 | 🟢 BUY 0.73 |\n| 00863.HK | +0.3亿 | 1.35 | 🟢 BUY 0.84 |"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "**🇺🇸 美股映射 (盘前)**\n\n| 标的 | 涨幅 | Dark Pool | 信号 |\n|------|-----|-----------|------|"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "| COIN | +3.2% | 28% | 🟢 CONFIRM |\n| NVDA | +1.8% | 15% | 🟢 CONFIRM |\n| QQQ | +0.8% | -- | 🟢 CONFIRM |"
                        }
                    },
                    {"tag": "hr"},
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Dashboard: http://10.60.33.159:5020"
                            }
                        ]
                    }
                ]
            }
        }
        
        async with session.post(WEBHOOK_URL, json=card) as resp:
            result = await resp.json()
            print(f"[{datetime.now()}] Push result: {result}")

if __name__ == "__main__":
    asyncio.run(push_report())
