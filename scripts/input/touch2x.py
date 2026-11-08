#!/usr/bin/env python3
"""
touch2x.py - bridge evdev input devices into the landscape Xvfb desktop.

The panel physically scans 720x1520 while X is 1520x720 (fbmirror.py rotates
the picture 90 degrees).  This does the inverse transform for INPUT, so a
touch at physical (tx, ty) lands on the correct X pixel.

Xvfb has no evdev input driver, so XTEST is used to inject pointer events.
Works for any ABS touchscreen and for REL mice (e.g. USB OTG), which makes it
useful right now; it will automatically pick up a real touchscreen driver as
soon as one is enabled in the device tree.

Environment:
  TOUCH2X_DISPLAY  default :1
  TOUCH2X_ROT      cw | ccw   (must match MIRROR_ROT, default cw)
  TOUCH2X_XMAX     X screen width  (default 1520)
  TOUCH2X_YMAX     X screen height (default 720)
  TOUCH2X_PANEL_W  physical width  (default 720)
  TOUCH2X_PANEL_H  physical height (default 1520)
"""
import ctypes
import fcntl
import glob
import os
import re
import struct
import subprocess
import sys
import time

DISPLAY = os.environ.get('TOUCH2X_DISPLAY', ':1').encode()

# Follow MIRROR_ROT automatically so display-rotate.sh never desyncs input.
ROT = os.environ.get('TOUCH2X_ROT', '')
if not ROT:
    try:
        env = subprocess.check_output(
            ['systemctl', 'show', 'fbmirror.service', '-p',
             'Environment', '--value'], text=True, timeout=3)
        m = re.search(r'MIRROR_ROT=(\w+)', env)
        ROT = m.group(1) if m else 'cw'
    except Exception:
        ROT = 'cw'
if ROT not in ('cw', 'ccw'):
    ROT = 'cw'
XW = int(os.environ.get('TOUCH2X_XMAX', '1520'))
XH = int(os.environ.get('TOUCH2X_YMAX', '720'))
PW = int(os.environ.get('TOUCH2X_PANEL_W', '720'))
PH = int(os.environ.get('TOUCH2X_PANEL_H', '1520'))

EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3
ABS_X, ABS_Y = 0x00, 0x01
ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0x35, 0x36, 0x39
BTN_TOUCH, BTN_LEFT = 0x14a, 0x110
REL_X, REL_Y = 0x00, 0x01
EV_EVENT = struct.Struct('=qqHHi')          # 24 bytes on aarch64
EVIOCGBIT_EV = 0x80084520                   # _IOR('E', 0x20, 8 bytes)
EVIOCGABS = lambda code: 0x80184540 + code  # _IOR('E', 0x40+code, 24 bytes)


class XTest:
    def __init__(self):
        self.x = ctypes.CDLL('libX11.so.6')
        self.t = ctypes.CDLL('libXtst.so.6')
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.t.XTestFakeMotionEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_ulong]
        self.t.XTestFakeButtonEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.dpy = self.x.XOpenDisplay(DISPLAY)
        if not self.dpy:
            raise RuntimeError('cannot open display ' + DISPLAY.decode())
        self.cx, self.cy = XW // 2, XH // 2
        self.down = False

    def motion(self, px, py):
        px = max(0, min(XW - 1, int(px)))
        py = max(0, min(XH - 1, int(py)))
        if (px, py) == (self.cx, self.cy):
            return
        self.cx, self.cy = px, py
        self.t.XTestFakeMotionEvent(self.dpy, -1, px, py, 0)
        self.x.XFlush(self.dpy)

    def button(self, pressed):
        if pressed == self.down:
            return
        self.down = pressed
        self.t.XTestFakeButtonEvent(self.dpy, 1, 1 if pressed else 0, 0)
        self.x.XFlush(self.dpy)

    def close(self):
        self.x.XCloseDisplay(self.dpy)


def map_abs(tx, ty, max_x, max_y):
    """Physical panel coords -> landscape X coords (inverse of fbmirror cw)."""
    nx = tx / max(max_x, 1)
    ny = ty / max(max_y, 1)
    nx = max(0.0, min(1.0, nx))
    ny = max(0.0, min(1.0, ny))
    if ROT == 'cw':
        return ny * (XW - 1), (1.0 - nx) * (XH - 1)
    return (1.0 - ny) * (XW - 1), nx * (XH - 1)


def map_rel(dx, dy):
    if ROT == 'cw':
        return dy, -dx
    return -dy, dx


def get_abs_range(fd, code, fallback):
    buf = bytearray(24)
    try:
        fcntl.ioctl(fd, EVIOCGABS(code), buf, True)
        _val, lo, hi = struct.unpack_from('=iii', buf, 0)
        if hi > lo:
            return hi
    except Exception:
        pass
    return fallback


def discover():
    """Return [(path, kind, {code: max})] for ABS-touch and REL-mouse devices."""
    out = []
    for path in sorted(glob.glob('/dev/input/event*')):
        sysd = '/sys/class/input/%s/device/capabilities/ev' % os.path.basename(path)
        try:
            evbits = int(open(sysd).read().strip(), 16)
        except Exception:
            continue
        is_abs = bool(evbits & (1 << EV_ABS))
        is_rel = bool(evbits & (1 << EV_REL))
        if not (is_abs or is_rel):
            continue
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except Exception:
            continue
        rng = {}
        if is_abs:
            # Prefer MT axes, fall back to single-touch ABS_X/Y.
            xmax = get_abs_range(fd, ABS_MT_POSITION_X, 0)
            ymax = get_abs_range(fd, ABS_MT_POSITION_Y, 0)
            if not xmax:
                xmax = get_abs_range(fd, ABS_X, PW - 1)
            if not ymax:
                ymax = get_abs_range(fd, ABS_Y, PH - 1)
            rng = {'xmax': xmax, 'ymax': ymax}
        os.close(fd)
        out.append((path, 'abs' if is_abs else 'rel', rng))
    return out


def run_device(xt, path, kind, rng, stop_check):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    tx = ty = 0
    touched = False
    idle = 0
    try:
        while not stop_check():
            try:
                data = os.read(fd, EV_EVENT.size * 16)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            except OSError:
                break
            if not data:
                idle += 1
                if idle > 200:
                    break
                time.sleep(0.02)
                continue
            idle = 0
            for chunk in range(0, len(data) - EV_EVENT.size + 1, EV_EVENT.size):
                _s, _us, etype, code, value = EV_EVENT.unpack_from(data, chunk)
                if kind == 'abs':
                    if code in (ABS_X, ABS_MT_POSITION_X):
                        tx = value
                    elif code in (ABS_Y, ABS_MT_POSITION_Y):
                        ty = value
                    elif code == BTN_TOUCH:
                        touched = value != 0
                    elif code == ABS_MT_TRACKING_ID and value == -1:
                        touched = False
                    elif etype == EV_SYN and code == 0:
                        px, py = map_abs(tx, ty, rng.get('xmax', PW - 1),
                                         rng.get('ymax', PH - 1))
                        xt.motion(px, py)
                        xt.button(touched)
                else:
                    if etype == EV_REL and code == REL_X:
                        dx, dy = map_rel(value, 0)
                        xt.motion(xt.cx + dx, xt.cy + dy)
                    elif etype == EV_REL and code == REL_Y:
                        dx, dy = map_rel(0, value)
                        xt.motion(xt.cx + dx, xt.cy + dy)
                    elif etype == EV_KEY and code == BTN_LEFT:
                        xt.button(value != 0)
    finally:
        xt.button(False)
        os.close(fd)


def selftest():
    print('map_abs (physical -> X), rot=%s, X=%dx%d, panel=%dx%d' %
          (ROT, XW, XH, PW, PH))
    for p in [(0, 0), (PW - 1, 0), (0, PH - 1), (PW - 1, PH - 1),
              (PW // 2, PH // 2)]:
        print('  panel %-12s -> X %s' % (str(p),
              tuple(round(v) for v in map_abs(p[0], p[1], PW - 1, PH - 1))))
    print('map_rel dx=+10 ->', map_rel(10, 0), ' dy=+10 ->', map_rel(0, 10))
    print('devices:', discover())
    xt = XTest()
    px, py = map_abs(0, 0, PW - 1, PH - 1)
    xt.motion(px, py)
    print('injected X coordinate: %d,%d' % (xt.cx, xt.cy))
    xt.close()
    return 0


def main():
    print('touch2x: display=%s rot=%s X=%dx%d panel=%dx%d' %
          (DISPLAY.decode(), ROT, XW, XH, PW, PH), flush=True)
    xt = None
    while True:
        if xt is None:
            try:
                xt = XTest()
                print('touch2x: connected to X', flush=True)
            except Exception as e:
                print('touch2x: %s (retry)' % e, flush=True)
                time.sleep(2)
                continue
        devs = discover()
        if not devs:
            time.sleep(3)
            continue
        print('touch2x: devices %s' % [(d[0], d[1]) for d in devs], flush=True)
        # Drive one device at a time; re-scan when it disappears.
        stop = lambda: not os.path.exists(devs[0][0])
        try:
            run_device(xt, devs[0][0], devs[0][1], devs[0][2], stop)
        except Exception as e:
            print('touch2x: device error %s (retry)' % e, flush=True)
        time.sleep(1)


if __name__ == '__main__':
    sys.exit(selftest() if '--selftest' in sys.argv else main())
