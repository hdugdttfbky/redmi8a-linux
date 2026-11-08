#!/bin/sh
# Redmi 8A panel rotation helper (mirror-based landscape).
#
# The physical panel always scans 720x1520.  fbmirror.py rotates the landscape
# X desktop into that buffer, so the device has to be held sideways.  If the
# picture looks upside down, flip the rotation direction:
#
#   display-rotate.sh cw        (default)
#   display-rotate.sh ccw
#   display-rotate.sh status
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
DIR=/etc/systemd/system/fbmirror.service.d

case "${1:-status}" in
    cw|ccw)
        mkdir -p "$DIR"
        cat > "$DIR/rotation.conf" <<EOF
[Service]
Environment=MIRROR_ROT=$1
EOF
        systemctl daemon-reload
        systemctl restart fbmirror.service
        echo "MIRROR_ROT=$1 applied"
        ;;
    status)
        echo "--- fbmirror ---"
        systemctl is-active fbmirror.service
        systemctl show fbmirror.service -p Environment --value 2>/dev/null | tr ' ' '\n' | grep MIRROR || true
        echo "--- X screen ---"
        DISPLAY=:1 xdpyinfo 2>/dev/null | grep dimensions
        echo "--- last log ---"
        journalctl -u fbmirror.service -n 4 --no-pager 2>/dev/null
        ;;
    *)
        echo "usage: $0 cw|ccw|status" >&2
        exit 1 ;;
esac
