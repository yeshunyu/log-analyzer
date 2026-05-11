# LogScope v0.3rc2

Single-file HTML tool for Linux system log analysis, with LLM-powered diagnosis for hardware issues.

## Features

### Core Analysis
- **LLM Analysis** - Powered by DeepSeek, identifies hardware faults and performance issues
- **Rule Matching** - Local rule engine, works offline
- **Chat Follow-up** - Continue asking questions after initial analysis

### Hardware Diagnostics
- Slow/failing disks and bad sectors
- Optical module / fiber abnormalities
- Memory UCE / ERR error analysis
- CPU / IO performance bottlenecks

### Input Methods
- Paste log text directly
- Drag and drop log files
- Configure DeepSeek API (custom endpoints supported)

## Deployment

### Option 1: Browser
Simply open `linux-os-log-analyzer.html` in your browser - no installation needed.

### Option 2: Docker
For team sharing or long-running server deployment:
```bash
docker run -d -p 5000:5000 yuyeshun2/logscope:v0.3rc2
```

Or with docker-compose:
```bash
DEEPSEEK_API_KEY=your_key docker-compose up -d
```

## Configure API

On first use, configure your DeepSeek API Key:
1. Select model (V4 Flash / V4 Pro)
2. Enter API Key
3. Optionally set custom API endpoint
4. Click "Save"

## Collect Logs

On your target Linux server, run the collection script:
```bash
chmod +x linux-os-log-collect.sh
sudo ./linux-os-log-collect.sh
```
The script outputs a `.tar.gz` archive. Transfer it to your workstation, extract, and upload logs to the analyzer.

### Collect Script Capabilities

`linux-os-log-collect.sh` collects:
- System info (CPU/memory/disk)
- dmesg kernel logs
- SMART disk info
- Memory error logs (UCE/ERR)
- Optical/fiber module status
- iostat/mpstat performance data
- journalctl error logs

## Analyze

- Paste or drag log files
- Click "Start Analysis"
- Review issue cards and LLM summary
- Ask follow-up questions

## File List

| File | Description |
|------|-------------|
| `linux-os-log-analyzer.html` | Main program, open directly in browser |
| `linux-os-log-collect.sh` | Linux log collection script |
| `backend/app.py` | Optional Flask static file server |
| `Dockerfile` | Container build definition |
| `docker-compose.yml` | Container orchestration |
| `README.md` / `README-en.md` | Documentation (Chinese / English) |

## License

MIT

---

## Changelog

### v0.3rc2 (2026-05-11)
- **Security**: Upload size limit (100MB), API rate limiting (20 req/min/IP)
- **Bug fix**: "About" dropdown not working
- **Enhance**: Collect script synced with standalone version (added dmidecode/ethtool/netstat etc.)
- **Backend**: /api/history/<id> endpoint for single item lookup, deduplicated extraction logic
- **Code quality**: Fixed bare except anti-patterns
