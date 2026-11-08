#!/bin/sh
# Restore the last known-good DTB and extlinux.conf.
# Usage: rollback-dtb.sh [--reboot]
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
D=/root/dtb-backup
DTB=$(ls -1t "$D"/sdm439-xiaomi-olive.dtb.pre-* 2>/dev/null | head -1)
CFG=$(ls -1t "$D"/extlinux.conf.pre-* 2>/dev/null | head -1)
[ -n "$DTB" ] && [ -f "$DTB" ] || { echo "no DTB backup found" >&2; exit 1; }
[ -n "$CFG" ] && [ -f "$CFG" ] || { echo "no extlinux backup found" >&2; exit 1; }

mountpoint -q /boot || mount /boot 2>/dev/null || true
cp "$DTB" /boot/sdm439-xiaomi-olive.dtb
cp "$CFG" /boot/extlinux/extlinux.conf
sync
echo "restored DTB  : $DTB"
echo "restored cfg : $CFG"
sha256sum /boot/sdm439-xiaomi-olive.dtb "$DTB"
echo "rollback applied."
if [ "$1" = "--reboot" ]; then
    echo "rebooting in 3s..."; sleep 3; /sbin/reboot
else
    echo "run 'rollback-dtb.sh --reboot' or reboot manually to take effect."
fi
