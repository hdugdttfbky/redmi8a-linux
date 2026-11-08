#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
GEOM=$(DISPLAY=:1 xdpyinfo 2>/dev/null | grep dimensions | head -1 | tr -s ' ' | cut -d' ' -f3)
echo "======================================================="
echo "  Redmi 8A / Linux micro server"
echo "======================================================="
uname -sr
echo
echo "  Time    : $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  Uptime  : $(uptime -p 2>/dev/null | sed 's/^up //')"
echo "  LAN IP  : $(ip -4 addr show wlan0 2>/dev/null | grep inet | head -1 | tr -s ' ' | cut -d' ' -f3 | cut -d/ -f1)"
echo "  TS IP   : $(ip -4 addr show tailscale0 2>/dev/null | grep inet | head -1 | tr -s ' ' | cut -d' ' -f3 | cut -d/ -f1)"
echo "  Memory  : $(free -h 2>/dev/null | grep '^Mem:' | tr -s ' ' | cut -d' ' -f3) / $(free -h 2>/dev/null | grep '^Mem:' | tr -s ' ' | cut -d' ' -f2)"
echo "  Desktop : ${GEOM:-unknown} @ 24bpp (landscape)"
echo "  Panel   : 720x1520 physical, rotated mirror; hold sideways"
echo
echo "  VNC :1 / port 5900 (SSH tunnel)"
echo "  Rotate: display-rotate.sh cw|ccw|status"
echo "-------------------------------------------------------"
echo
exec /bin/sh
