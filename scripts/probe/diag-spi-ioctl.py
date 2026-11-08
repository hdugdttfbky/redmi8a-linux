#!/usr/bin/env python3
"""Find the working SPI_IOC_MESSAGE(1) encoding on this kernel."""
import ctypes, fcntl, os, struct

DEV = '/dev/spidev0.1'
WR_MODE, WR_BITS, WR_SPEED = 0x40016B01, 0x40016B03, 0x40046B04
RD_MODE, RD_BITS, RD_SPEED = 0x80016B01, 0x80016B03, 0x80046B04

fd = os.open(DEV, os.O_RDWR)
fcntl.ioctl(fd, WR_MODE, struct.pack('=B', 0))
fcntl.ioctl(fd, WR_BITS, struct.pack('=B', 8))
fcntl.ioctl(fd, WR_SPEED, struct.pack('=I', 1000000))
print('mode  =', fcntl.ioctl(fd, RD_MODE, struct.pack('=B', 0))[0])
print('bits  =', fcntl.ioctl(fd, RD_BITS, struct.pack('=B', 0))[0])
print('speed =', struct.unpack('=I', fcntl.ioctl(fd, RD_SPEED, struct.pack('=I', 0)))[0])

print('\nheader present:', os.path.exists('/usr/include/linux/spi/spidev.h'))
if os.path.exists('/usr/include/linux/spi/spidev.h'):
    txt = open('/usr/include/linux/spi/spidev.h').read()
    for line in txt.split('\n'):
        if 'spi_ioc_transfer' in line or 'SPI_MSGSIZE' in line or 'SPI_IOC_MESSAGE' in line:
            print('  ', line.strip())

tx = ctypes.create_string_buffer(b'\x4e\x00\x00', 3)
rx = ctypes.create_string_buffer(3)

# try several plausible encodings / struct sizes
for size_field, req in [(40, 0x40286B00), (32, 0x40206B00), (33, 0x40216B00)]:
    for packed in (
        struct.pack('=QQIIHHBBBBB7x', ctypes.addressof(tx), ctypes.addressof(rx),
                    3, 1000000, 0, 8, 0, 0, 0, 0, 0),          # 40 bytes
        struct.pack('=QQIIHHBBBBB', ctypes.addressof(tx), ctypes.addressof(rx),
                    3, 1000000, 0, 8, 0, 0, 0, 0, 0),           # 33 bytes
    ):
        try:
            out = fcntl.ioctl(fd, req, packed)
            print('OK req=%08x sizefield=%d packed=%d -> %s' %
                  (req, size_field, len(packed), out[:3].hex(' ')))
        except OSError as e:
            print('ERR req=%08x sizefield=%d packed=%d -> %s' %
                  (req, size_field, len(packed), e))

# also try the "no struct size" variant with a plain mutable buffer
buf = bytearray(struct.pack('=QQIIHHBBBBB7x', ctypes.addressof(tx),
                            ctypes.addressof(rx), 3, 1000000, 0, 8,
                            0, 0, 0, 0, 0))
try:
    out = fcntl.ioctl(fd, 0x40286B00, buf, True)
    print('OK mutable-buffer req=%08x -> %s' % (0x40286B00, out[:3].hex(' ')))
except OSError as e:
    print('ERR mutable-buffer:', e)

os.close(fd)
