#!/bin/bash
# Linux OS Log Collector v0.2rc1
# Usage: chmod +x linux-os-log-collect.sh && sudo ./linux-os-log-collect.sh

set -euo pipefail

# Trap for cleanup on exit
TMPDIR=""
cleanup() {
  if [[ -n "$TMPDIR" && -d "$TMPDIR" ]]; then
    rm -rf "$TMPDIR" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# 检查 root 权限
check_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "警告: 部分命令需要 root 权限，建议用 sudo 运行"
  fi
}

# 使用 mktemp 创建安全临时目录
TMPDIR=$(mktemp -d /tmp/log_collector.XXXXXX)
DEST="/tmp/system-logs-$(hostname)-$(date +%Y%m%d_%H%M%S).tar.gz"

echo "开始收集系统日志..."
echo "临时目录: $TMPDIR"

check_root

# 收集函数 - 权限不足时跳过
collect_safe() {
  local cmd="$1"
  local output="$2"
  eval "$cmd" > "$output" 2>/dev/null && return 0 || return 1
}

echo ">> 收集系统信息..."
uname -a > "$TMPDIR/01_system_info.txt"
uptime >> "$TMPDIR/01_system_info.txt"
free -h >> "$TMPDIR/01_system_info.txt"
df -h >> "$TMPDIR/01_system_info.txt"
cat /proc/cpuinfo | grep -E "model name|cpu cores" >> "$TMPDIR/01_system_info.txt" 2>/dev/null || true

echo ">> 收集硬件日志..."
dmesg -T > "$TMPDIR/02_dmesg.log" 2>/dev/null || dmesg > "$TMPDIR/02_dmesg.log" 2>/dev/null || true
cat /var/log/dmesg* > "$TMPDIR/02_dmesg.old" 2>/dev/null || true

# dmidecode 需要 root
if collect_safe "dmidecode" "$TMPDIR/03_hardware.txt"; then
  echo "   [dmidecode OK]"
else
  echo "   [dmidecode SKIP: 需要 root]"
fi

collect_safe "lspci -vvv" "$TMPDIR/04_pci.txt" || echo "   [lspci SKIP: 需要 root]"
lsblk -a > "$TMPDIR/05_block_devices.txt"
cat /proc/diskstats > "$TMPDIR/06_diskstats.txt"
smartctl --scan > "$TMPDIR/07_smart_devices.txt" 2>/dev/null || true

echo ">> 收集存储/Smart信息..."
while IFS= read -r dev; do
  dev=$(echo "$dev" | tr -d ' ')
  if [[ -b "/dev/$dev" ]]; then
    smartctl -a "/dev/$dev" > "$TMPDIR/08_smart_${dev}.txt" 2>/dev/null || true
  fi
done < <(lsblk -d -n -o NAME | grep -E '^sd|^nvme' || true)

cat /proc/mdstat > "$TMPDIR/09_raid_status.txt" 2>/dev/null || true
lsblk -f > "$TMPDIR/10_filesystems.txt"

echo ">> 收集内存信息..."
cat /proc/meminfo > "$TMPDIR/11_memory.txt"
dmesg | grep -i -E "memory|uce|err|correctable" > "$TMPDIR/12_mem_errors.txt" 2>/dev/null || true
cat /proc/buddyinfo > "$TMPDIR/13_buddyinfo.txt" 2>/dev/null || true

echo ">> 收集网络信息..."
ip addr > "$TMPDIR/14_ip_addr.txt"
ip link > "$TMPDIR/15_ip_link.txt"
ip -s link > "$TMPDIR/16_ip_link_stats.txt"
cat /proc/net/dev > "$TMPDIR/17_net_dev.txt"
cat /proc/net/tcp > "$TMPDIR/18_net_tcp.txt"
ss -tuln > "$TMPDIR/19_ss_ports.txt" 2>/dev/null || true

# ethtool ring buffer - 可能需要 root
NET_DEV=$(ip -o link show | grep -v lo | head -1 | awk -F: '{print $2}' | tr -d ' ')
if [[ -n "$NET_DEV" ]]; then
  ethtool -g "$NET_DEV" > "$TMPDIR/20_ethtool_ring.txt" 2>/dev/null || true
fi

echo ">> 收集光纤/光模块信息..."
ls -l /sys/class/net/ > "$TMPDIR/21_net_class.txt"
cat /sys/class/net/*/speed > "$TMPDIR/22_net_speed.txt" 2>/dev/null || true
dmesg | grep -i -E "optical|fiber|sfp|sfpp|sff|module|link" > "$TMPDIR/23_optical.log" 2>/dev/null || true

echo ">> 收集 IO/CPU 性能..."
iostat -x 2 5 > "$TMPDIR/24_iostat.txt" 2>/dev/null || echo "   [iostat SKIP: 需要 sysstat]"
mpstat -A 2 3 > "$TMPDIR/25_mpstat.txt" 2>/dev/null || echo "   [mpstat SKIP: 需要 sysstat]"
pidstat -u 2 5 > "$TMPDIR/26_pidstat.txt" 2>/dev/null || echo "   [pidstat SKIP: 需要 sysstat]"

# nmon 采样 (后台运行)
which nmon >/dev/null 2>&1 && nmon -f -s 1 -c 10 -m "$TMPDIR/" 2>/dev/null &

sleep 12
ps aux --no-headers > "$TMPDIR/27_processes.txt"
top -bn1 -o %MEM | head -30 > "$TMPDIR/28_top_mem.txt"
top -bn1 -o %CPU | head -30 > "$TMPDIR/29_top_cpu.txt"

echo ">> 收集系统日志..."
journalctl -k --no-pager > "$TMPDIR/30_kernel.log" 2>/dev/null || echo "   [journalctl SKIP: 需要 root]"
journalctl --no-pager -p err > "$TMPDIR/31_errors.log" 2>/dev/null || true
journalctl --no-pager -p warning > "$TMPDIR/32_warnings.log" 2>/dev/null || true
cp /var/log/syslog "$TMPDIR/33_syslog.txt" 2>/dev/null || true
cp /var/log/messages "$TMPDIR/33_messages.txt" 2>/dev/null || true

echo ">> 收集网络连接/会话..."
netstat -ant > "$TMPDIR/34_netstat_tcp.txt" 2>/dev/null || true
netstat -anu > "$TMPDIR/35_netstat_udp.txt" 2>/dev/null || true
ss -s > "$TMPDIR/36_ss_summary.txt" 2>/dev/null || true

echo ">> 打包..."
tar -czf "$DEST" -C "$(dirname "$TMPDIR")" "$(basename "$TMPDIR")"

echo ""
echo "=== 完成 ==="
echo "输出文件: $DEST"
echo "文件大小: $(du -h "$DEST" | cut -f1)"
echo "收集时间: $(date)"