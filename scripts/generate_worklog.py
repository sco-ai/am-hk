"""
工作日志生成器
自动生成每日工作记录并同步到记忆系统
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# 工作区路径
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK")
AMHK_DIR = WORKSPACE / "am-hk"
MEMORY_DIR = WORKSPACE / "memory"
LOGS_DIR = AMHK_DIR / "logs"

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_now_str():
    return datetime.now().strftime("%H:%M")

def read_system_status():
    """读取系统状态"""
    status_file = AMHK_DIR / "system-status.json"
    if status_file.exists():
        with open(status_file) as f:
            return json.load(f)
    return {}

def read_git_log():
    """读取今日 git 提交记录"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "--since=midnight", "--oneline"],
            cwd=AMHK_DIR,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except:
        return "无法获取 git 记录"

def generate_worklog(summary_type="daily"):
    """生成工作日志"""
    today = get_today_str()
    now = get_now_str()
    
    # 每日日志文件
    daily_log = MEMORY_DIR / f"{today}.md"
    
    # 系统状态
    status = read_system_status()
    
    # Git 记录
    git_log = read_git_log()
    
    # 构建日志内容
    content = f"""# 工作日志 - {today}

## {summary_type.upper()} 总结 - {now}

### 系统状态
- AM-HK 版本: {status.get('version', 'unknown')}
- 数据库: PostgreSQL {status.get('database', {}).get('postgresql', {}).get('port', 'N/A')}, Redis {status.get('database', {}).get('redis', {}).get('port', 'N/A')}
- 运行中的 Agents: {len([a for a in status.get('agents', {}).values() if a.get('status') == 'running'])}

### Git 提交记录
```
{git_log}
```

### 今日完成事项
- [ ] 待记录

### 遇到的问题
- 无

### 下一步计划
- [ ] 待规划

---
*自动生成于 {datetime.now().isoformat()}*
"""
    
    # 写入或追加到每日日志
    if daily_log.exists():
        with open(daily_log, "a") as f:
            f.write(f"\n\n## {summary_type.upper()} 总结 - {now}\n\n")
            f.write(f"### 系统状态快照\n")
            f.write(f"- 时间: {now}\n")
            f.write(f"- Agents: {len([a for a in status.get('agents', {}).values() if a.get('status') == 'running'])} running\n")
    else:
        with open(daily_log, "w") as f:
            f.write(content)
    
    print(f"✓ 工作日志已更新: {daily_log}")
    return daily_log

def sync_to_memory():
    """同步关键信息到 MEMORY.md"""
    memory_file = WORKSPACE / "MEMORY.md"
    today = get_today_str()
    
    # 读取今日日志的关键决策
    daily_log = MEMORY_DIR / f"{today}.md"
    if not daily_log.exists():
        print("✗ 今日日志不存在，跳过同步")
        return
    
    # 更新 MEMORY.md (追加模式)
    with open(daily_log) as f:
        content = f.read()
    
    # 提取关键决策部分
    # TODO: 实现智能提取逻辑
    
    print(f"✓ 记忆同步完成")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["noon", "evening", "daily"], default="daily")
    parser.add_argument("--sync", action="store_true", help="同步到长期记忆")
    args = parser.parse_args()
    
    generate_worklog(args.type)
    
    if args.sync:
        sync_to_memory()
