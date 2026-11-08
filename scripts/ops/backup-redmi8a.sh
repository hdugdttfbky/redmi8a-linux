#!/bin/sh
# Back up the entire working Redmi 8A desktop/display configuration.
# Produces a self-contained tarball + manifest under /root/redmi8a-backup/.
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

OUT=/root/redmi8a-backup
STAMP=$(date '+%Y%m%d-%H%M%S')
NAME="redmi8a-config-$STAMP"
TMP=$(mktemp -d)
K=$(uname -r)
MDIR=/lib/modules/$K/kernel/drivers/gpu/drm

mkdir -p "$OUT" "$TMP/$NAME"

# --- files to preserve ---
cp -a /etc/systemd/system          "$TMP/$NAME/systemd-system"
cp -a /etc/modprobe.d              "$TMP/$NAME/modprobe.d"      2>/dev/null || true
cp -a /etc/nftables.conf           "$TMP/$NAME/nftables.conf"   2>/dev/null || true
cp -a /etc/X11                     "$TMP/$NAME/X11"             2>/dev/null || true
cp -a /etc/apt/sources.list        "$TMP/$NAME/sources.list"    2>/dev/null || true
cp -a /etc/apt/sources.list.d      "$TMP/$NAME/sources.list.d"  2>/dev/null || true
cp -a /usr/local/bin               "$TMP/$NAME/local-bin"
cp -a /root/vnc-terminal.sh        "$TMP/$NAME/vnc-terminal.sh" 2>/dev/null || true
cp -a /root/.vnc                   "$TMP/$NAME/vnc"             2>/dev/null || true
cp -a /root/wcn36xx.ko.zst.orig    "$TMP/$NAME/"                2>/dev/null || true
cp -a /root/wcn36xx.ko.zst.htoff   "$TMP/$NAME/"                2>/dev/null || true
mkdir -p "$TMP/$NAME/modules"
cp -a "$MDIR/msm/msm.ko.zst"       "$TMP/$NAME/modules/"        2>/dev/null || true
cp -a "$MDIR/panel/"*olive*        "$TMP/$NAME/modules/"        2>/dev/null || true

# --- manifest: enough context to rebuild this exact state ---
{
    echo "Redmi 8A working configuration backup"
    echo "created : $(date -Is)"
    echo "hostname: $(hostname)"
    echo "kernel  : $(uname -a)"
    echo
    echo "=== kernel cmdline (KEEP modprobe.blacklist=bl_lm3697,msm) ==="
    cat /proc/cmdline
    echo
    echo "=== display chain ==="
    echo "Xvfb :1 1520x720x24 -fbdir /run/xvfb  ->  /run/xvfb/Xvfb_screen0 (XWD)"
    echo "fbmirror.py: mmap XWD -> numpy rotate 90deg -> /dev/fb0 (720x1520, stride 2160)"
    echo "lk boot-loader pipeline still scans the panel at 60 fps."
    echo "DO NOT modprobe msm: it rewrites MDP registers and blanks the screen."
    echo
    echo "=== VNC exposure ==="
    echo "x11vnc listens 0.0.0.0:5900 + [::]:5900 with -rfbauth /root/.vnc/passwd."
    echo "nftables input policy is DROP; 5900 is only accepted from wlan*/usb*"
    echo "with private source @lan4, plus tailscale0. Global IPv6 5900 is dropped."
    echo "=> already LAN/Tailscale-only; NOT changed to 127.0.0.1 because the"
    echo "   user connects directly from <client-lan-ip>."
    echo "   See local-bin/vnc-localhost.sh if pure SSH-tunnel mode is wanted later."
    echo
    echo "=== fb0 / X state ==="
    echo "fb0: $(cat /sys/class/graphics/fb0/virtual_size) bpp=$(cat /sys/class/graphics/fb0/bits_per_pixel) stride=$(cat /sys/class/graphics/fb0/stride) blank=$(cat /sys/class/graphics/fb0/blank)"
    DISPLAY=:1 xdpyinfo 2>/dev/null | grep dimensions || true
    echo
    echo "=== failed units ==="
    systemctl --failed --no-legend || true
    echo
    echo "=== enabled display units ==="
    systemctl list-unit-files --no-legend 2>/dev/null | grep -E 'xvfb|fbmirror|x11vnc|vnc-|codearts|fb-unblank|ktd3137|bl-guard|screen-toggle|battery' || true
    echo
    echo "=== installed packages (dpkg) ==="
    dpkg -l 2>/dev/null | grep '^ii' | awk '{print $2" "$3}'
    echo
    echo "=== nft ruleset ==="
    nft list ruleset 2>/dev/null || true
    echo
    echo "=== file list ==="
    find "$TMP/$NAME" -type f -printf '%P %s bytes\n' | sort
} > "$TMP/$NAME/MANIFEST.txt" 2>&1

tar -czf "$OUT/$NAME.tar.gz" -C "$TMP" "$NAME"
sha256sum "$OUT/$NAME.tar.gz" > "$OUT/$NAME.tar.gz.sha256"
rm -rf "$TMP"

# keep the 5 newest backups
ls -1t "$OUT"/redmi8a-config-*.tar.gz 2>/dev/null | tail -n +6 | while read -r f; do
    rm -f "$f" "$f.sha256"
done

echo "backup: $OUT/$NAME.tar.gz"
ls -lh "$OUT/$NAME.tar.gz"
cat "$OUT/$NAME.tar.gz.sha256"
