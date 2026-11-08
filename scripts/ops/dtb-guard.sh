#!/bin/sh
# Safety net for a DTB experiment: if the operator does not confirm within
# 10 minutes of boot, restore the known-good DTB and reboot.
# Confirm with:  touch /root/.dtb-confirmed
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
LOG=/root/dtb-guard.log
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

[ -f /root/.dtb-confirmed ] && { log "already confirmed"; exit 0; }
log "armed, waiting 600s"
sleep 600
[ -f /root/.dtb-confirmed ] && { log "confirmed during wait"; exit 0; }
log "no confirmation -> rolling back DTB"
/usr/local/bin/rollback-dtb.sh >> "$LOG" 2>&1
sync
sleep 3
/sbin/reboot
