"""
飞书命令处理器
处理来自飞书的交互指令
"""
import json
import logging
from typing import Dict, Optional

from core.feishu import FeishuNotifier
from core.kafka import MessageBus
from core.utils import setup_logging

logger = setup_logging("feishu_commands")


class FeishuCommandHandler:
    """
    飞书命令处理器
    
    支持命令：
    - /start_trading - 启动交易
    - /stop_trading - 停止交易
    - /status - 查看系统状态
    - /positions - 查看持仓
    - /set_risk <value> - 设置风险等级
    - /help - 帮助信息
    """
    
    def __init__(self):
        self.agent_name = "feishu_handler"
        self.bus = MessageBus(self.agent_name)
        self.notifier = FeishuNotifier()
        
        logger.info("Feishu command handler initialized")
    
    async def handle_webhook(self, payload: Dict) -> Dict:
        """
        处理飞书Webhook请求
        
        Args:
            payload: 飞书发送的消息体
        
        Returns:
            响应内容
        """
        try:
            # 获取消息类型
            msg_type = payload.get("header", {}).get("event_type", "")
            
            # 处理卡片回调
            if msg_type == "interactive_card_callback":
                return await self._handle_card_callback(payload)
            
            # 处理文本消息
            if msg_type == "im.message.receive_v1":
                return await self._handle_text_message(payload)
            
            # 处理URL验证
            if "challenge" in payload:
                return {"challenge": payload["challenge"]}
            
            logger.warning(f"Unknown message type: {msg_type}")
            return {"status": "ignored"}
        
        except Exception as e:
            logger.error(f"Error handling webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    async def _handle_text_message(self, payload: Dict) -> Dict:
        """处理文本消息命令"""
        event = payload.get("event", {})
        message = event.get("message", {})
        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "").strip()
        
        # 解析命令
        command = text.lower().split()[0] if text else ""
        args = text.split()[1:] if len(text.split()) > 1 else []
        
        logger.info(f"Received command: {command}, args: {args}")
        
        # 命令路由
        handlers = {
            "/start_trading": self._cmd_start_trading,
            "/stop_trading": self._cmd_stop_trading,
            "/status": self._cmd_status,
            "/positions": self._cmd_positions,
            "/set_risk": self._cmd_set_risk,
            "/help": self._cmd_help,
        }
        
        handler = handlers.get(command, self._cmd_unknown)
        return await handler(args)
    
    async def _handle_card_callback(self, payload: Dict) -> Dict:
        """处理卡片按钮回调"""
        action = payload.get("action", {})
        action_value = action.get("value", {})
        
        action_type = action_value.get("action")
        symbol = action_value.get("symbol")
        
        logger.info(f"Card callback: action={action_type}, symbol={symbol}")
        
        if action_type == "confirm_trade":
            # 发送确认交易命令
            self.bus.publish_command("agent5_guardian", {
                "type": "confirm_trade",
                "symbol": symbol,
                "action": action_value.get("trade_action"),
            })
            await self.notifier.send_text(f"✅ 已确认交易: {symbol}")
            return {"status": "success", "message": "Trade confirmed"}
        
        elif action_type == "reject_trade":
            # 发送拒绝交易命令
            self.bus.publish_command("agent5_guardian", {
                "type": "reject_trade",
                "symbol": symbol,
            })
            await self.notifier.send_text(f"❌ 已拒绝交易: {symbol}")
            return {"status": "success", "message": "Trade rejected"}
        
        elif action_type == "view_details":
            # 请求详细信息
            await self.notifier.send_text(f"📊 正在获取 {symbol} 详细信息...")
            return {"status": "success"}
        
        elif action_type == "start_trading":
            return await self._cmd_start_trading([])
        
        elif action_type == "stop_trading":
            return await self._cmd_stop_trading([])
        
        elif action_type == "view_full_report":
            await self.notifier.send_text("📈 详细报告功能开发中...")
            return {"status": "success"}
        
        return {"status": "ignored"}
    
    async def _cmd_start_trading(self, args: list) -> Dict:
        """启动交易命令"""
        self.bus.publish_command("agent1_harvester", {"type": "start"})
        self.bus.publish_command("agent2_curator", {"type": "start"})
        self.bus.publish_command("agent3_scanner", {"type": "start"})
        
        await self.notifier.send_alert(
            title="🚀 交易已启动",
            message="系统开始采集数据并生成交易信号",
            level="info",
        )
        return {"status": "success", "message": "Trading started"}
    
    async def _cmd_stop_trading(self, args: list) -> Dict:
        """停止交易命令"""
        self.bus.publish_command("all_agents", {"type": "stop"})
        
        await self.notifier.send_alert(
            title="🛑 交易已停止",
            message="系统已停止生成新的交易信号",
            level="warning",
        )
        return {"status": "success", "message": "Trading stopped"}
    
    async def _cmd_status(self, args: list) -> Dict:
        """系统状态命令"""
        # 请求各Agent状态
        self.bus.publish_command("all_agents", {"type": "get_status"})
        
        await self.notifier.send_status_report(
            system_status="运行中",
            active_agents=6,
            total_trades=0,
            daily_pnl=0.0,
            positions=[],
        )
        return {"status": "success"}
    
    async def _cmd_positions(self, args: list) -> Dict:
        """查看持仓命令"""
        # 从Agent5获取持仓
        self.bus.publish_command("agent5_guardian", {"type": "get_positions"})
        
        await self.notifier.send_text("📊 正在查询持仓信息...")
        return {"status": "success"}
    
    async def _cmd_set_risk(self, args: list) -> Dict:
        """设置风险等级命令"""
        if not args:
            await self.notifier.send_text(
                "⚠️ 请指定风险等级，例如：\n/set_risk 0.05"
            )
            return {"status": "error", "message": "Missing risk value"}
        
        try:
            risk_value = float(args[0])
            if not 0 < risk_value <= 0.5:
                await self.notifier.send_text(
                    "⚠️ 风险等级必须在 0.01 ~ 0.5 之间"
                )
                return {"status": "error", "message": "Invalid risk value"}
            
            # 更新风险配置
            self.bus.publish_command("agent5_guardian", {
                "type": "set_risk",
                "value": risk_value,
            })
            
            await self.notifier.send_alert(
                title="⚙️ 风险配置已更新",
                message=f"最大仓位限制已设置为 {risk_value:.1%}",
                level="info",
            )
            return {"status": "success"}
        
        except ValueError:
            await self.notifier.send_text("⚠️ 请输入有效的数字")
            return {"status": "error", "message": "Invalid number"}
    
    async def _cmd_help(self, args: list) -> Dict:
        """帮助命令"""
        help_text = """📖 **AM-HK 命令列表**

**交易控制**
• `/start_trading` - 启动交易
• `/stop_trading` - 停止交易
• `/status` - 查看系统状态

**查询命令**
• `/positions` - 查看当前持仓
• `/set_risk <value>` - 设置最大仓位 (0.01~0.5)

**交互功能**
• 收到交易信号卡片后，可点击：
  ✅ 确认执行 - 确认并执行交易
  ❌ 拒绝 - 跳过本次机会
  📊 详情 - 查看更多分析

**说明**
系统会自动推送交易信号到本群，您可以实时查看并控制交易。"""
        
        await self.notifier.send_markdown("📖 使用帮助", help_text)
        return {"status": "success"}
    
    async def _cmd_unknown(self, args: list) -> Dict:
        """未知命令"""
        await self.notifier.send_text(
            "❓ 未知命令，输入 /help 查看可用命令"
        )
        return {"status": "error", "message": "Unknown command"}


# === 通知集成 ===

async def send_trade_signal(signal_data: Dict) -> bool:
    """
    发送交易信号通知
    
    由Agent4调用，当产生交易信号时自动推送
    """
    notifier = FeishuNotifier()
    try:
        return await notifier.send_signal_card(
            symbol=signal_data.get("symbol", "UNKNOWN"),
            action=signal_data.get("action", "HOLD"),
            confidence=signal_data.get("confidence", 0.5),
            predicted_return=signal_data.get("predicted_return", 0),
            reasoning=signal_data.get("reasoning", "无"),
            position_size=signal_data.get("position_size", 0),
            stop_loss=signal_data.get("stop_loss", 0.02),
            take_profit=signal_data.get("take_profit", 0.05),
            market=signal_data.get("market", "US"),
        )
    finally:
        await notifier.close()


async def send_system_alert(title: str, message: str, level: str = "warning") -> bool:
    """
    发送系统告警
    
    由各Agent调用，当发生异常时自动推送
    """
    notifier = FeishuNotifier()
    try:
        return await notifier.send_alert(title, message, level)
    finally:
        await notifier.close()
