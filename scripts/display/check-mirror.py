"""Compare the rotated Xvfb framebuffer with the current /dev/fb0 contents."""
import importlib.util

spec = importlib.util.spec_from_file_location('fbmirror', '/usr/local/bin/fbmirror.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

mm, sw, sh, bpl, off = m.open_dump()
raw = m.read_frame(mm, sw, sh, bpl, off)
out = bytes(m.convert(raw, sw, sh, bpl, m.read_stride()))
mm.close()

fb = open('/dev/fb0', 'rb').read(len(out))
print('X screen   : %dx%d bpl=%d' % (sw, sh, bpl))
print('rot=%s out=%d bytes, fb=%d bytes' % (m.ROT, len(out), len(fb)))
print('fb0[0..11]    :', fb[:12].hex(' '))
print('expected[0..11]:', out[:12].hex(' '))
print('exact match   :', fb == out)
if fb != out:
    diff = sum(1 for a, b in zip(fb, out) if a != b)
    print('differing bytes: %d / %d' % (diff, len(out)))
