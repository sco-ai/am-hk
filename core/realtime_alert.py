#!/usr/bin/env python3
"""
AM-HK 实时信号推送模块
当有交易信号生成时立即推送到飞书群
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from datetime import datetime
from enum import Enum


class AlertType(str, Enum):
    SIGNAL_GENERATED = "signal_generated"  # 信号生成
    SIGNAL_CONFIRMED = "signal_confirmed"  # 信号确认
    SIGNAL_EXECUTED = "signal_executed"    # 信号执行
    RISK_TRIGGERED = "risk_triggered"      # 风控触发
    SYSTEM_ERROR = "system_error"          # 系统错误


class RealtimeAlert:
    """实时告警推送器"""
    
    @staticmethod
    def push_signal(symbol: str, direction: str, price: float, confidence: float, 
                    agent: str = "Agent3", requires_confirmation: bool = True):
        """推送交易信号"""
        emoji = "🟢" if direction == "买入" else "🔴" if direction == "卖出" else "⚪"
        confirm_text = "(需确认)" if requires_confirmation else "(自动执行)"
        
        message = f"""🚨 **实时交易信号** {confirm_text}

📌 标的: **{symbol}**
{emoji} 方向: **{direction}**
💰 价格: {price:.2f} HKD
📊 置信度: {confidence:.1%}
🤖 来源: {agent}
⏰ 时间: {datetime.now().strftime('%H:%M:%S')}

---
💡 操作建议: {'请确认后执行' if requires_confirmation else '已自动执行'}"""
        
        print(message)
        return message
    
    @staticmethod
    def push_risk_alert(symbol: str, risk_type: str, risk_level: str, 
                       current_value: float, limit_value: float):
        """推送风控告警"""
        level_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk_level, "⚪")
        
        message = f"""{level_emoji} **风控告警** {level_emoji}

⚠️ 风险类型: {risk_type}
📌 标的: {symbol}
📊 当前值: {current_value:.2f}
🚫 限制值: {limit_value:.2f}
⏰ 时间: {datetime.now().strftime('%H:%M:%S')}

---
💡 建议: 请立即检查持仓并调整策略"""
        
        print(message)
        return message
    
    @staticmethod
    def push_system_error(component: str, error_msg: str, severity: str = "HIGH"):
        """推送系统错误"""
        emoji = "🔴" if severity == "HIGH" else "🟡"
        
        message = f"""{emoji} **系统异常告警** {emoji}

🔧 组件: {component}
❌ 错误: {error_msg}
⚡ 级别: {severity}
⏰ 时间: {datetime.now().strftime('%H:%M:%S')}

---
💡 建议: 请检查系统日志并联系技术支持"""
        
        print(message)
        return message


def test_alerts():
    """测试告警推送"""
    print("\n" + "=" * 60)
    print("测试实时告警推送")
    print("=" * 60)
    
    # 测试1: 信号推送
    print("\n【测试1】交易信号推送")
    RealtimeAlert.push_signal(
        symbol="00700",
        direction="买入",
        price=380.50,
        confidence=0.85,
        agent="Agent3+Ollama",
        requires_confirmation=True
    )
    
    # 测试2: 风控告警
    print("\n【测试2】风控告警推送")
    RealtimeAlert.push_risk_alert(
        symbol="09988",
        risk_type="单日亏损超限",
        risk_level="HIGH",
        current_value=5.2,
        limit_value=5.0
    )
    
    # 测试3: 系统错误
    print("\n【测试3】系统错误推送")
    RealtimeAlert.push_system_error(
        component="Agent3-Scanner",
        error_msg="Ollama连接超时",
        severity="HIGH"
    )
    
    print("\n" + "=" * 60)
    print("测试完成")


if __name__ == "__main__":
    test_alerts()
