#!/bin/sh
# OPTIONAL - not enabled by default.
#
# Switch VNC to localhost-only (use together with an SSH tunnel such as
#   ssh -L 5900:127.0.0.1:5900 root@<device-lan-ip>
# ), or restore direct LAN access.
#
# WARNING: "localhost" will immediately drop any active LAN VNC session
# (the user currently connects directly from <client-lan-ip>).
#
#   vnc-localhost.sh localhost
#   vnc-localhost.sh lan
#   vnc-localhost.sh status
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
D=/etc/systemd/system/x11vnc.service.d
BASE='/usr/bin/x11vnc -display :1 -rfbauth /root/.vnc/passwd -forever -shared -noxdamage -repeat -rfbport 5900'

case "${1:-status}" in
    localhost)
        mkdir -p "$D"
        printf '[Service]\nExecStart=\nExecStart=%s -localhost\n' "$BASE" > "$D/listen.conf"
        ;;
    lan)
        rm -f "$D/listen.conf"
        ;;
    status)
        [ -f "$D/listen.conf" ] && echo "VNC mode: localhost-only" || echo "VNC mode: LAN (nftables-filtered)"
        ss -lntp 2>/dev/null | grep 5900
        exit 0 ;;
    *)
        echo "usage: $0 localhost|lan|status" >&2; exit 1 ;;
esac

systemctl daemon-reload
systemctl restart x11vnc.service
sleep 2
echo "x11vnc: $(systemctl is-active x11vnc.service)"
ss -lntp 2>/dev/null | grep 5900
