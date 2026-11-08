#!/bin/sh
# KTD3137 背光守护：芯片被外部 unbind / 断电时自动重绑并恢复原状态
# 只做「让 HWEN 保持高」这一件事，不主动 unbind，不碰 framebuffer
# Auto-detect the bus that answers at 0x36 (i2c numbering changes when the
# 78b7000 QUP block is switched between i2c and spi).
BUS=
for b in 0 1 2 3 4 5; do
    [ -e /dev/i2c-$b ] || continue
    if i2cget -y -f $b 0x36 0x00 b >/dev/null 2>&1; then BUS=$b; break; fi
done
[ -n "$BUS" ] || exit 0
ADDR=0x36
SAVED=/run/screen-toggle.brightness
POWER=/run/screen-toggle.power

id() { i2cget -y -f $BUS $ADDR 0x00 b 2>/dev/null; }

I=$(id)
[ "$I" = "0x18" ] && exit 0

logger -t bl-guard "KTD3137 offline (id=${I:-NACK}), rebinding ${BUS}-0036"
echo ${BUS}-0036 > /sys/bus/i2c/drivers/lm3697/bind 2>/dev/null

n=0
while [ $n -lt 25 ]; do
    sleep 0.2
    I=$(id)
    [ "$I" = "0x18" ] && break
    n=$((n + 1))
done

if [ "$I" != "0x18" ]; then
    logger -t bl-guard "bind did not help, reloading bl_lm3697"
    modprobe bl_lm3697 2>/dev/null
    sleep 0.5
    I=$(id)
fi

if [ "$I" != "0x18" ]; then
    logger -t bl-guard "FAILED: 0x36 still NACK — HWEN (PM8953 GPIO4) 需人工检查"
    exit 1
fi

V=$(cat $SAVED 2>/dev/null)
case "$V" in ''|*[!0-9]*) V=1400 ;; esac
[ "$V" -lt 1 ] && V=1400
[ "$V" -gt 2047 ] && V=2047
P=$(cat $POWER 2>/dev/null)
[ -z "$P" ] && P=on

if [ "$P" = "on" ]; then
    /usr/local/bin/ktd3137-bl "$V" >/dev/null 2>&1
    logger -t bl-guard "restored: bound + backlight $V (screen was on)"
else
    i2cset -y -f $BUS $ADDR 0x04 $((V & 7)) 2>/dev/null
    i2cset -y -f $BUS $ADDR 0x05 $((V >> 3)) 2>/dev/null
    i2cset -y -f $BUS $ADDR 0x02 0x98 2>/dev/null
    logger -t bl-guard "restored: bound + brightness $V kept off"
fi
exit 0
