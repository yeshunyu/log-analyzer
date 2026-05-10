# LogScope v0.3rc1

单文件 HTML 工具，用于 Linux 系统日志分析，支持 LLM 智能分析和硬件问题诊断。

## 功能特性

### 核心分析
- **LLM 智能分析** - 基于 DeepSeek 大模型，识别硬件故障和性能问题
- **规则匹配** - 本地规则引擎，支持离线使用
- **对话追问** - 分析后可继续追问，获取详细建议

### 硬件问题诊断
- 硬盘慢盘 / 坏道检测
- 光模块 / 光纤异常识别
- 内存 UCE / ERR 错误分析
- CPU / IO 性能瓶颈

### 交互方式
- 粘贴日志文本
- 拖拽上传日志文件
- 配置 DeepSeek API（支持自定义端点）

## 部署方式

### 方式一：浏览器直接打开
直接双击 `linux-os-log-analyzer.html` 即可使用，无需安装。

### 方式二：Docker 部署
适合团队共享或服务器长期运行：
```bash
docker run -d -p 5000:5000 yuyeshun2/logscope:v0.3rc1
```

或使用 docker-compose：
```bash
DEEPSEEK_API_KEY=your_key docker-compose up -d
```

## 配置 API

首次使用需要配置 DeepSeek API Key：
1. 选择模型（V4 Flash / V4 Pro）
2. 输入 API Key
3. 可选填自定义 API 地址
4. 点击「保存」

## 收集日志

在目标 Linux 服务器执行日志收集脚本：
```bash
chmod +x linux-os-log-collect.sh
sudo ./linux-os-log-collect.sh
```
收集完成后，将生成的 `system-logs-*.tar.gz` 解压，上传日志文件到分析器。

### 收集脚本功能

`linux-os-log-collect.sh` 收集内容：
- 系统信息（CPU/内存/磁盘）
- dmesg 内核日志
- SMART 硬盘信息
- 内存错误日志（UCE/ERR）
- 光模块/光纤状态
- iostat/mpstat 性能数据
- journalctl 错误日志

## 分析日志

- 粘贴日志或拖拽文件
- 点击「开始分析」
- 查看问题卡片和 LLM 综合报告
- 可继续追问获取更多帮助

## 文件列表

| 文件 | 说明 |
|------|------|
| `linux-os-log-analyzer.html` | 主程序，直接浏览器打开 |
| `linux-os-log-collect.sh` | Linux 日志收集脚本 |
| `backend/app.py` | 可选的 Flask 静态文件服务器 |
| `Dockerfile` | 容器构建文件 |
| `docker-compose.yml` | 容器编排 |
| `README.md` / `README-en.md` | 文档（中文 / 英文） |

## License

MIT
