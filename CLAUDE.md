# CLAUDE.md

LogScope - Linux 系统日志分析工具

## 项目定位

单文件 HTML 前端 + Flask 静态文件服务 + Shell 日志收集脚本。无数据库，无复杂状态管理。

## 技术栈

- `linux-os-log-analyzer.html` — 纯前端单文件，浏览器直接打开
- `linux-os-log-collect.sh` — Bash 脚本，Linux 服务器端运行
- `backend/app.py` — Flask 静态文件服务器（可选）
- `Dockerfile` + `docker-compose.yml` — 容器化

## 开发 & 测试

- 前端：浏览器直接打开 HTML 文件即可
- 后端：`cd backend && pip install -r requirements.txt && python app.py`
- 容器：`docker build -t logscope . && docker run -p 5000:5000 logscope`

## 安全准则

- API Key 存前端 localStorage（用户自己配置，不经过服务端）
- 所有用户输入必须 `escapeHtml` 再插入 innerHTML
- 添加了 CSP meta 标签，connect-src 只允许指定 LLM API
- shell 脚本用 `set -euo pipefail`，变量加引号，防注入

## 注意事项

- HTML 里版本号要同步更新（界面显示 + 脚本注释 + README）
- 推送前确认 `.env` 未提交
- 安全问题及时报告，不要等到发布后
