#!/usr/bin/env python3
"""电源键短按 = 屏幕开关（只动 KTD3137 背光，绝不卸载驱动）

硬件事实：
  * 0x36 上挂的是 KTD3137，不是 DT 里写的 LM3697
  * 0x02 bit0 = BL_EN，bit[7:3] = 电流档（10011 = 20.2mA）
  * 0x04 / 0x05 = 11 位亮度的低 3 位 / 高 8 位
  * DT 里的 lm3697 驱动唯一作用是拉高 PM8953 GPIO4(HWEN) 给芯片供电
    —— 一旦 unbind 或 modprobe -r，HWEN 变低、芯片断电、i2c 直接 NACK

所以本程序只读写 i2c 寄存器，驱动一律不动。
用法：screen-toggle.py [--daemon|--off|--on|--toggle|--status]
"""
import glob
import os
import struct
import subprocess
import sys
import time

def _find_bus():
    """i2c numbering changes when the 78b7000 QUP block switches i2c<->spi."""
    for b in range(0, 6):
        if not os.path.exists("/dev/i2c-%d" % b):
            continue
        r = subprocess.run(["i2cget", "-y", "-f", str(b), "0x36", "0x00", "b"],
                           capture_output=True)
        if r.returncode == 0:
            return str(b)
    return "0"


BUS = _find_bus()
ADDR = "0x36"
DEV_ID = 0x18
FMT = "llHHi"
SIZE = struct.calcsize(FMT)
KEY_POWER = 116

STATE = "/run/screen-toggle.brightness"
STATE_POWER = "/run/screen-toggle.power"
LOG = "/var/log/screen-toggle.log"
FB_BLANK = "/sys/class/graphics/fb0/blank"
DRIVER = "/sys/bus/i2c/drivers/lm3697"
BOUND = DRIVER + "/" + BUS + "-0036"
DEFAULT_BRIGHT = 1400


def log(msg):
    line = "%s %s\n" % (time.strftime("%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG, "a") as f:
            f.write(line)
    except OSError:
        pass
    sys.stdout.write(line)
    sys.stdout.flush()


def i2cget(reg):
    r = subprocess.run(["i2cget", "-y", "-f", BUS, ADDR, hex(reg), "b"],
                       capture_output=True, text=True)
    try:
        return int(r.stdout.strip(), 16)
    except ValueError:
        return None


def i2cset(reg, val):
    r = subprocess.run(["i2cset", "-y", "-f", BUS, ADDR, hex(reg), hex(val)],
                       capture_output=True, text=True)
    return r.returncode == 0


def chip_online():
    return i2cget(0x00) == DEV_ID


def ensure_chip():
    """芯片不在线时只做「让 HWEN 保持高」的补救，绝不 unbind。"""
    if chip_online():
        return True
    log("chip offline, trying to re-bind %s-0036 (keeps HWEN high)" % BUS)
    if not os.path.exists(BOUND):
        try:
            with open(DRIVER + "/bind", "w") as f:
                f.write(BUS + "-0036\n")
        except OSError:
            subprocess.run(["modprobe", "bl_lm3697"], capture_output=True)
    for _ in range(30):
        time.sleep(0.1)
        if chip_online():
            log("chip back online (id=0x18)")
            return True
    log("FAILED: 0x36 still NACK — HWEN(PM8953 GPIO4) 可能没拉高，需要人工处理")
    return False


def brightness_now():
    lsb = i2cget(0x04)
    msb = i2cget(0x05)
    if lsb is None or msb is None:
        return None
    return ((msb & 0xFF) << 3) | (lsb & 0x07)


def save_brightness(v):
    try:
        with open(STATE, "w") as f:
            f.write(str(v))
    except OSError:
        pass


def load_brightness():
    try:
        with open(STATE) as f:
            v = int(f.read().strip())
        if 0 < v <= 2047:
            return v
    except (OSError, ValueError):
        pass
    return DEFAULT_BRIGHT


def save_power(v):
    """记录屏幕是开还是灭，供 bl-guard 在芯片被外部解绑后恢复。"""
    try:
        with open(STATE_POWER, "w") as f:
            f.write("on" if v else "off")
    except OSError:
        pass


def is_on():
    v = i2cget(0x02)
    if v is None:
        return False
    return (v & 0x01) == 1


def fb_blank():
    try:
        with open(FB_BLANK) as f:
            return f.read().strip()
    except OSError:
        return "?"


def screen_off():
    if not ensure_chip():
        return False
    cur = brightness_now()
    if cur and cur > 0:
        save_brightness(cur)
    i2cset(0x02, 0x98)              # BL_EN=0，保留电流档 10011
    ok = not is_on()
    save_power(False)
    log("screen OFF  0x02=%s saved=%s" % (hex(i2cget(0x02) or 0), cur))
    return ok


def screen_on():
    if not ensure_chip():
        return False
    v = load_brightness()
    i2cset(0x04, v & 0x07)
    i2cset(0x05, (v >> 3) & 0xFF)
    i2cset(0x02, 0x99)              # BL_EN=1
    # 顺手修掉上一版脚本遗留的 fb POWERDOWN
    if fb_blank() not in ("0", "?"):
        try:
            with open(FB_BLANK, "w") as f:
                f.write("0")
        except OSError:
            pass
    ok = is_on()
    save_power(ok)
    log("screen ON   0x02=%s brightness=%s fb_blank=%s"
        % (hex(i2cget(0x02) or 0), v, fb_blank()))
    return ok


def toggle():
    return screen_off() if is_on() else screen_on()


def find_pwrkey():
    for path in sorted(glob.glob("/dev/input/event*")):
        base = os.path.basename(path)
        try:
            with open("/sys/class/input/%s/device/name" % base) as f:
                if f.read().strip() == "pm8941_pwrkey":
                    return path
        except OSError:
            continue
    return None


def daemon():
    debounce = 0.6
    last = 0.0
    while True:
        dev = find_pwrkey()
        if not dev:
            log("pm8941_pwrkey not found, retry in 5s")
            time.sleep(5)
            continue
        try:
            fd = os.open(dev, os.O_RDONLY)
        except OSError as e:
            log("open %s failed: %s" % (dev, e))
            time.sleep(5)
            continue
        log("watching %s" % dev)
        while True:
            try:
                data = os.read(fd, SIZE)
            except OSError as e:
                log("read error: %s, reopening" % e)
                break
            if len(data) < SIZE:
                continue
            _sec, _usec, typ, code, value = struct.unpack(FMT, data)
            if typ == 1 and code == KEY_POWER and value == 1:
                now = time.monotonic()
                if now - last < debounce:
                    continue
                last = now
                toggle()
        os.close(fd)
        time.sleep(1)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--daemon"
    if arg == "--daemon":
        daemon()
        return 0
    if arg == "--off":
        return 0 if screen_off() else 1
    if arg == "--on":
        return 0 if screen_on() else 1
    if arg == "--toggle":
        return 0 if toggle() else 1
    if arg == "--status":
        print("chip=%s  0x02=%s  brightness=%s  fb_blank=%s  driver_bound=%s"
              % ("online" if chip_online() else "OFFLINE",
                 hex(i2cget(0x02) or 0), brightness_now(), fb_blank(),
                 os.path.exists(BOUND)))
        return 0
    sys.stderr.write("usage: %s [--daemon|--off|--on|--toggle|--status]\n" % sys.argv[0])
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
