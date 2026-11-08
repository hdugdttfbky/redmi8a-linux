#!/usr/bin/env python3
"""
fbshow.py - draw on the LK/simpledrm framebuffer of the Redmi 8A.

IMPORTANT (learned the hard way):
  * This is NOT the msmdrmfb.  The boot loader leaves a live 60 fps MDP/DSI
    pipeline behind; simpledrm exposes its framebuffer as /dev/fb0.
  * Geometry is 720x1520, **24 bpp**, stride **2160** bytes.
    (msm's own fbdev is 16 bpp / pitch 1472 - do not mix them up.)
  * /sys/class/graphics/fb0/blank is 4 (POWERDOWN) at boot; set it to 0.

Usage:
  fbshow.py solid ff0000        # whole screen one RGB colour
  fbshow.py split ff0000 00ff00 # top / bottom halves
  fbshow.py bars                # 8 colour bars
  fbshow.py info                # print geometry only
"""
import os
import sys

FB = '/dev/fb0'
SYS = '/sys/class/graphics/fb0'


def readi(name, default):
    try:
        return int(open(os.path.join(SYS, name)).read().strip())
    except Exception:
        return default


def geometry():
    w, h = (readi('virtual_size', 0), 0)
    try:
        w, h = [int(x) for x in open(os.path.join(SYS, 'virtual_size')).read().strip().split(',')]
    except Exception:
        w, h = 720, 1520
    bpp = readi('bits_per_pixel', 24)
    stride = readi('stride', w * (bpp // 8))
    return w, h, bpp, stride


def rgb(hexstr):
    h = hexstr.lstrip('#')
    if len(h) != 6:
        raise ValueError('colour must be 6 hex digits, got %r' % hexstr)
    return bytes.fromhex(h)


def row(colour, stride, bpp):
    px = (colour * ((stride // len(colour)) + 1))[:stride]
    return px


def main():
    w, h, bpp, stride = geometry()
    mode = sys.argv[1] if len(sys.argv) > 1 else 'info'
    print('fb0: %dx%d bpp=%d stride=%d blank=%s' %
          (w, h, bpp, stride, open(os.path.join(SYS, 'blank')).read().strip()))
    if mode == 'info':
        return

    if bpp != 24:
        print('WARNING: expected 24 bpp, got %d - output may look wrong' % bpp)

    if mode == 'solid':
        c = rgb(sys.argv[2])
        data = row(c, stride, bpp) * h
    elif mode == 'split':
        top = row(rgb(sys.argv[2]), stride, bpp)
        bot = row(rgb(sys.argv[3]), stride, bpp)
        data = top * (h // 2) + bot * (h - h // 2)
    elif mode == 'bars':
        colours = ['ffffff', 'ffff00', '00ffff', '00ff00',
                   'ff00ff', 'ff0000', '0000ff', '000000']
        data = b''.join(row(rgb(c), stride, bpp) * (h // len(colours))
                        for c in colours)
        data += row(rgb(colours[-1]), stride, bpp) * (h - len(colours) * (h // len(colours)))
    else:
        raise SystemExit(__doc__)

    try:
        open(os.path.join(SYS, 'blank'), 'w').write('0\n')
    except Exception as e:
        print('could not unblank:', e)

    with open(FB, 'wb') as f:
        f.write(data)
    print('wrote %d bytes (%s)' % (len(data), mode))


if __name__ == '__main__':
    main()
