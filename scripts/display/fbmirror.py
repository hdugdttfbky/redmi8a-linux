#!/usr/bin/env python3
"""
fbmirror.py - mirror a landscape X display onto /dev/fb0 with 90-degree rotation.

Why this exists
---------------
The Redmi 8A panel has a fixed 720x1520 scanout programmed by the boot loader.
Xorg's modesetting driver can drive it directly (portrait), but its RandR
software rotation produces a black screen on this simpledrm device.  So we run
Xvfb at landscape 1520x720 with -fbdir, which exposes its framebuffer as a
memory-mappable XWD file, and rotate those pixels into the real framebuffer.
VNC sees the same landscape screen; hold the device sideways to view it.

Reading the XWD file is a plain memcpy - no XGetImage socket transfer, no libX11.
numpy does the rotation.

Environment:
  MIRROR_XWD        default /run/xvfb/Xvfb_screen0
  MIRROR_FB         default /dev/fb0
  MIRROR_FPS        default 8   (active)
  MIRROR_IDLE_FPS   default 2   (static desktop)
  MIRROR_ROT        cw | ccw   (default cw; ccw if the picture is upside down)
"""
import hashlib
import mmap
import os
import struct
import sys
import time

try:
    import numpy as np
except ImportError:
    sys.exit('fbmirror: python3-numpy is required')

XWD = os.environ.get('MIRROR_XWD', '/run/xvfb/Xvfb_screen0')
FB = os.environ.get('MIRROR_FB', '/dev/fb0')
SYSFB = '/sys/class/graphics/fb0'
FPS = float(os.environ.get('MIRROR_FPS', '8'))
IDLE_FPS = float(os.environ.get('MIRROR_IDLE_FPS', '2'))
ROT = os.environ.get('MIRROR_ROT', 'cw')
if ROT not in ('cw', 'ccw'):
    ROT = 'cw'


def read_stride():
    try:
        return int(open(os.path.join(SYSFB, 'stride')).read().strip())
    except Exception:
        return 2160


def open_dump():
    fd = os.open(XWD, os.O_RDONLY)
    mm = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
    os.close(fd)
    # XWDFileHeader is 25 big-endian CARD32 values.
    v = struct.unpack('>25I', mm[:100])
    header_size, ncolors = v[0], v[19]
    sw, sh, bpl = v[4], v[5], v[12]
    off = header_size + ncolors * 12
    if bpl < sw * 4 or off + bpl * sh > len(mm):
        raise RuntimeError('bad XWD geometry: %dx%d bpl=%d off=%d size=%d' %
                           (sw, sh, bpl, off, len(mm)))
    return mm, sw, sh, bpl, off


def read_frame(mm, sw, sh, bpl, off):
    # A plain bytes copy (~4 ms) avoids memoryview lifetime trouble when the
    # mmap has to be closed; it is not the bottleneck.
    return mm[off:off + bpl * sh]


def convert(raw, sw, sh, bpl, stride):
    """BGRX32 landscape (sw x sh) -> RGB24 portrait (sh x sw), rotated."""
    dest_w, dest_h = sh, sw
    if stride < dest_w * 3:
        raise RuntimeError('fb stride %d too small for %d px' % (stride, dest_w))

    px_per_line = bpl // 4
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(sh, px_per_line, 4)
    # Slice views only - a fancy index here would force a per-pixel gather and
    # triple the frame time on this CPU.
    rgb = arr[:, :sw, 2::-1]                          # BGRX -> RGB (view)
    if ROT == 'cw':
        rot = rgb[::-1].transpose(1, 0, 2)
    else:
        rot = rgb[:, ::-1].transpose(1, 0, 2)
    out = np.ascontiguousarray(rot).tobytes()         # (sw, sh, 3)
    if stride == dest_w * 3:
        return out
    buf = bytearray(stride * dest_h)
    row = dest_w * 3
    for y in range(dest_h):
        buf[y * stride:y * stride + row] = out[y * row:(y + 1) * row]
    return buf


def main():
    stride = read_stride()
    active_interval = 1.0 / max(1.0, FPS)
    idle_interval = 1.0 / max(0.2, IDLE_FPS)
    print('fbmirror: xwd=%s rot=%s active=%g fps idle=%g fps fb=%s stride=%d' %
          (XWD, ROT, 1 / active_interval, 1 / idle_interval, FB, stride), flush=True)
    while True:
        mm = None
        fb = None
        try:
            mm, sw, sh, bpl, off = open_dump()
            fb = open(FB, 'r+b', buffering=0)
            print('fbmirror: mapped %dx%d bpl=%d offset=%d' %
                  (sw, sh, bpl, off), flush=True)
            last = None
            idle = 0
            while True:
                t0 = time.time()
                raw = read_frame(mm, sw, sh, bpl, off)
                out = convert(raw, sw, sh, bpl, stride)
                # Sampled hash: a full 3.3 MB blake2b costs ~15 ms per frame.
                digest = hashlib.blake2b(out[::1024], digest_size=8).digest()
                if digest != last:
                    fb.seek(0)
                    fb.write(out)
                    last = digest
                    idle = 0
                else:
                    idle += 1
                interval = active_interval if idle < 6 else idle_interval
                dt = time.time() - t0
                if dt < interval:
                    time.sleep(interval - dt)
        except Exception as e:
            print('fbmirror: %s (retry in 2s)' % e, flush=True)
        finally:
            try:
                if fb:
                    fb.close()
            except Exception:
                pass
            try:
                if mm:
                    mm.close()
            except Exception:
                pass
        time.sleep(2)


if __name__ == '__main__':
    sys.exit(main())
