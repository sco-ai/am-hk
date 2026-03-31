# Python依赖合规检查清单 - AlphaMind HK 市场分析

## 检查原则
1. **精确版本**: 所有依赖必须使用 `==` 精确锁定版本
2. **安全优先**: 定期检查安全漏洞
3. **最小依赖**: 只包含必要的依赖
4. **环境隔离**: 使用虚拟环境

## 依赖管理检查清单

### ✅ 1. 虚拟环境配置
- [ ] 使用 `.venv/` 作为虚拟环境目录
- [ ] `.gitignore` 中已排除 `.venv/`
- [ ] 虚拟环境基于 Python 3.8+
- [ ] 虚拟环境路径正确配置

### ✅ 2. requirements.txt 规范
- [ ] 使用 `==` 精确版本锁定
- [ ] 按字母顺序排序
- [ ] 包含所有运行时依赖
- [ ] 开发依赖在 `requirements-dev.txt` 中
- [ ] 注释清晰，说明依赖用途

### ✅ 3. 依赖安全性检查
- [ ] 使用 `safety check` 检查安全漏洞
- [ ] 无已知高危漏洞（CVSS ≥ 7.0）
- [ ] 依赖更新到最新安全版本
- [ ] 定期（每月）检查依赖安全

### ✅ 4. 许可证合规性
- [ ] 所有依赖许可证兼容项目许可证
- [ ] 无 GPL 等传染性许可证（如项目为商业用途）
- [ ] 记录主要依赖许可证信息

### ✅ 5. 依赖版本兼容性
- [ ] 检查 Python 版本兼容性
- [ ] 检查依赖间版本冲突
- [ ] 测试关键功能在指定版本下正常工作

### ✅ 6. 构建和部署检查
- [ ] `requirements.txt` 可用于生产部署
- [ ] 依赖安装无编译问题
- [ ] 部署脚本正确处理依赖安装

## 检查工具和命令

### 安全扫描
```bash
# 安装 safety
pip install safety

# 检查安全漏洞
safety check -r requirements.txt

# 检查所有依赖（包括间接依赖）
pip freeze | safety check --stdin
```

### 依赖分析
```bash
# 生成依赖树
pipdeptree

# 检查许可证
pip-licenses

# 检查过时依赖
pip list --outdated
```

### 虚拟环境管理
```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 生成 requirements.txt
pip freeze > requirements.txt
```

## requirements.txt 示例
```txt
# 核心框架
FastAPI==0.104.1
uvicorn==0.24.0

# 数据库
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
redis==5.0.1

# 数据处理
pandas==2.1.4
numpy==1.26.2
scipy==1.11.4

# 消息队列
celery==5.3.4
kafka-python==2.0.2

# 开发依赖（在 requirements-dev.txt 中）
# pytest==7.4.3
# black==23.11.0
# flake8==6.1.0
```

## .gitignore 配置
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# 虚拟环境
.venv/
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
```

## 定期维护任务
| 频率 | 任务 | 负责人 |
|------|------|--------|
| 每周 | 检查安全漏洞 | 开发人员 |
| 每月 | 更新次要版本 | 开发人员 |
| 每季度 | 评估主要版本升级 | 技术负责人 |
| 每次发布 | 完整依赖检查 | 发布经理 |

## 问题处理流程
1. **发现安全漏洞** → 立即评估风险 → 制定升级计划
2. **版本冲突** → 分析冲突原因 → 调整版本或寻找替代
3. **许可证问题** → 评估法律风险 → 更换依赖或获取许可

## 更新记录
| 日期 | 检查结果 | 处理措施 | 检查人 |
|------|----------|----------|--------|
| 2026-03-30 | 初始检查 | 创建检查清单 | 陈精坤 |

---

**注意**: 每次依赖变更必须通过此清单检查，确保项目依赖健康。