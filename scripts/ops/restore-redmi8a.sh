#!/bin/sh
# Restore a backup produced by backup-redmi8a.sh.
# Usage: restore-redmi8a.sh /root/redmi8a-backup/redmi8a-config-XXXX.tar.gz
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TAR=${1:-}
[ -n "$TAR" ] && [ -f "$TAR" ] || { echo "usage: $0 <backup.tar.gz>" >&2; exit 1; }

if [ -f "$TAR.sha256" ]; then
    sha256sum -c "$TAR.sha256" || { echo "checksum mismatch, abort" >&2; exit 1; }
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$TAR" -C "$TMP"
D=$(find "$TMP" -maxdepth 1 -type d -name 'redmi8a-config-*' | head -1)
[ -d "$D" ] || { echo "bad archive" >&2; exit 1; }

echo "restoring from $(basename "$TAR") ..."
[ -d "$D/systemd-system" ]   && { mkdir -p /etc/systemd/system; cp -a "$D/systemd-system/." /etc/systemd/system/; }
[ -d "$D/modprobe.d" ]       && { mkdir -p /etc/modprobe.d;     cp -a "$D/modprobe.d/." /etc/modprobe.d/; }
[ -f "$D/nftables.conf" ]    && cp -a "$D/nftables.conf" /etc/nftables.conf
[ -d "$D/X11" ]              && { mkdir -p /etc/X11;             cp -a "$D/X11/." /etc/X11/; }
[ -f "$D/sources.list" ]     && cp -a "$D/sources.list" /etc/apt/sources.list
[ -d "$D/sources.list.d" ]   && { mkdir -p /etc/apt/sources.list.d; cp -a "$D/sources.list.d/." /etc/apt/sources.list.d/; }
[ -d "$D/local-bin" ]        && { mkdir -p /usr/local/bin;        cp -a "$D/local-bin/." /usr/local/bin/; }
[ -f "$D/vnc-terminal.sh" ]  && cp -a "$D/vnc-terminal.sh" /root/vnc-terminal.sh
[ -d "$D/vnc" ]              && { mkdir -p /root/.vnc;            cp -a "$D/vnc/." /root/.vnc/; }

K=$(uname -r)
MDIR=/lib/modules/$K/kernel/drivers/gpu/drm
for f in "$D"/modules/*; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in
        msm.ko.zst)     mkdir -p "$MDIR/msm";   cp -a "$f" "$MDIR/msm/msm.ko.zst" ;;
        *olive*)        mkdir -p "$MDIR/panel"; cp -a "$f" "$MDIR/panel/" ;;
    esac
done
for f in "$D"/wcn36xx.ko.zst.*; do
    [ -f "$f" ] && cp -a "$f" /root/
done

chmod 755 /root/vnc-terminal.sh /usr/local/bin/*.sh 2>/dev/null || true
chmod 600 /root/.vnc/passwd 2>/dev/null || true

if [ "$K" != "$(sed -n 's/^kernel  : Linux .* \([^ ]*\) .*/\1/p' "$D/MANIFEST.txt" | head -1)" ]; then
    echo "WARNING: kernel version differs from the backup; module paths may not match." >&2
fi

systemctl daemon-reload
for u in xvfb.service x11vnc.service vnc-session.service vnc-terminal.service codearts.service fbmirror.service fb-unblank.service ktd3137-backlight.service; do
    systemctl is-enabled "$u" >/dev/null 2>&1 && systemctl enable "$u" >/dev/null 2>&1 || true
done
systemctl restart xvfb.service fbmirror.service x11vnc.service vnc-session.service vnc-terminal.service codearts.service 2>/dev/null || true
echo "restore done. A reboot is recommended to re-establish the lk display pipeline."
