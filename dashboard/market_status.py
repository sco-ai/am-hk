"""市场状态检测"""
from datetime import datetime
import pytz

def get_market_status():
    """获取美股和港股市场状态"""
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    weekday = now.weekday()  # 0=周一, 6=周日
    hour = now.hour
    minute = now.minute
    time_val = hour * 100 + minute
    
    # 美股: 夏令时 21:30-04:00, 冬令时 22:30-05:00 (UTC+8)
    # 简化判断: 21:00-04:00 为交易时间
    us_open = (time_val >= 2130 and time_val <= 2359) or (time_val >= 0 and time_val <= 400)
    us_trading = us_open and weekday < 5
    
    # 港股: 09:30-12:00, 13:00-16:00 (UTC+8)
    hk_am = time_val >= 930 and time_val <= 1200
    hk_pm = time_val >= 1300 and time_val <= 1600
    hk_trading = (hk_am or hk_pm) and weekday < 5
    
    return {
        "us_trading": us_trading,
        "hk_trading": hk_trading,
        "current_time": now.strftime("%H:%M"),
        "weekday": weekday
    }
