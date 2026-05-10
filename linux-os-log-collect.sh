#!/bin/bash
# OS Log Collector - 适合硬件/存储/网络运维
# Usage: chmod +x collect.sh && ./collect.sh

OUTPUT="system-logs-$(hostname)-$(date +%Y%m%d_%H%M%S).tar.gz"
DEST="/tmp/$OUTPUT"

echo "开始收集系统日志..."
mkdir -p /tmp/log_collector

echo ">> 收集系统信息..."
uname -a > /tmp/log_collector/01_system_info.txt
uptime >> /tmp/log_collector/01_system_info.txt
free -h >> /tmp/log_collector/01_system_info.txt
df -h >> /tmp/log_collector/01_system_info.txt
cat /proc/cpuinfo | grep -E "model name|cpu cores" >> /tmp/log_collector/01_system_info.txt 2>/dev/null

echo ">> 收集硬件日志..."
dmesg -T > /tmp/log_collector/02_dmesg.log 2>/dev/null || dmesg > /tmp/log_collector/02_dmesg.log
cat /var/log/dmesg* > /tmp/log_collector/02_dmesg.old 2>/dev/null
dmidecode > /tmp/log_collector/03_hardware.txt 2>/dev/null
lspci -vvv > /tmp/log_collector/04_pci.txt 2>/dev/null
lsblk -a > /tmp/log_collector/05_block_devices.txt
cat /proc/diskstats > /tmp/log_collector/06_diskstats.txt
smartctl --scan > /tmp/log_collector/07_smart_devices.txt 2>/dev/null

echo ">> 收集存储/Smart信息..."
for dev in $(lsblk -d -n -o NAME | grep -E 'sd|nvme'); do
  smartctl -a /dev/$dev >> /tmp/log_collector/08_smart_$dev.txt 2>/dev/null
done
cat /proc/mdstat > /tmp/log_collector/09_raid_status.txt 2>/dev/null
lsblk -f > /tmp/log_collector/10_filesystems.txt

echo ">> 收集内存信息..."
cat /proc/meminfo > /tmp/log_collector/11_memory.txt
dmesg | grep -i -E "memory|uce|err|correctable" > /tmp/log_collector/12_mem_errors.txt 2>/dev/null
cat /proc/buddyinfo > /tmp/log_collector/13_buddyinfo.txt 2>/dev/null

echo ">> 收集网络信息..."
ip addr > /tmp/log_collector/14_ip_addr.txt
ip link > /tmp/log_collector/15_ip_link.txt
ip -s link > /tmp/log_collector/16_ip_link_stats.txt
cat /proc/net/dev > /tmp/log_collector/17_net_dev.txt
cat /proc/net/tcp > /tmp/log_collector/18_net_tcp.txt
ss -tuln > /tmp/log_collector/19_ss_ports.txt
ethtool -g $(ip -o link show | grep -v lo | head -1 | awk -F: '{print $2}') > /tmp/log_collector/20_ethtool_ring.txt 2>/dev/null

echo ">> 收集光纤/光模块信息..."
ls -l /sys/class/net/ > /tmp/log_collector/21_net_class.txt
cat /sys/class/net/*/speed 2>/dev/null > /tmp/log_collector/22_net_speed.txt
dmesg | grep -i -E "optical|fiber|sfp|sfpp|sff|module|link" > /tmp/log_collector/23_optical.log 2>/dev/null

echo ">> 收集 IO/CPU 性能..."
iostat -x 2 5 > /tmp/log_collector/24_iostat.txt 2>/dev/null
mpstat -A 2 3 > /tmp/log_collector/25_mpstat.txt 2>/dev/null
pidstat -u 2 5 > /tmp/log_collector/26_pidstat.txt 2>/dev/null
nmon -f -s 1 -c 10 -m /tmp/log_collector/ 2>/dev/null &
sleep 12
ps aux --no-headers > /tmp/log_collector/27_processes.txt
top -bn1 -o %MEM | head -30 > /tmp/log_collector/28_top_mem.txt
top -bn1 -o %CPU | head -30 > /tmp/log_collector/29_top_cpu.txt

echo ">> 收集系统日志..."
journalctl -k --no-pager > /tmp/log_collector/30_kernel.log 2>/dev/null
journalctl --no-pager -p err > /tmp/log_collector/31_errors.log 2>/dev/null
journalctl --no-pager -p warning > /tmp/log_collector/32_warnings.log 2>/dev/null
cp /var/log/syslog /tmp/log_collector/33_syslog.txt 2>/dev/null
cp /var/log/messages /tmp/log_collector/33_messages.txt 2>/dev/null

echo ">> 收集网络连接/会话..."
netstat -ant > /tmp/log_collector/34_netstat_tcp.txt 2>/dev/null
netstat -anu > /tmp/log_collector/35_netstat_udp.txt 2>/dev/null
ss -s > /tmp/log_collector/36_ss_summary.txt

echo ">> 打包..."
tar -czf "$DEST" -C /tmp log_collector
rm -rf /tmp/log_collector

echo ""
echo "=== 完成 ==="
echo "输出文件: $DEST"
echo "文件大小: $(du -h $DEST | cut -f1)"
echo "收集时间: $(date)"