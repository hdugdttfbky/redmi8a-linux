#!/usr/bin/env python3
"""
Full-duplex READ-ONLY NVT SPI probe. NEVER sends 0x69 (blanks the LCD).
Finds the page/read command combination that yields valid FW info / point data.
"""
import ctypes, fcntl, os, struct, sys

DEV = '/dev/spidev0.1'
WR_MODE, WR_BITS, WR_SPEED = 0x40016B01, 0x40016B03, 0x40046B04
SPI_IOC_MESSAGE_1 = 0x40206B00        # THIS kernel encodes size=32

fd = os.open(DEV, os.O_RDWR)
fcntl.ioctl(fd, WR_MODE, struct.pack('=B', 0))
fcntl.ioctl(fd, WR_BITS, struct.pack('=B', 8))
fcntl.ioctl(fd, WR_SPEED, struct.pack('=I', 1000000))


def xfer(tx, speed=1000000):
    n = len(tx)
    t = ctypes.create_string_buffer(bytes(tx), n)
    r = ctypes.create_string_buffer(n)
    tr = struct.pack('=QQIIHHBBBBB7x', ctypes.addressof(t), ctypes.addressof(r),
                     n, speed, 0, 8, 0, 0, 0, 0, 0)
    fcntl.ioctl(fd, SPI_IOC_MESSAGE_1, tr)
    return r.raw[:n]


def set_page(addr, first=0xFF):
    xfer([first, (addr >> 15) & 0xFF, (addr >> 7) & 0xFF])


def read(cmd, length):
    raw = xfer([cmd] + [0] * (length + 1))
    return raw[2:2 + length - 1], raw   # driver copies rbuf[2:] into buf[1:]


def note(data):
    if not data:
        return ''
    u = set(data)
    if u == {0xFF} or u == {0x00}:
        return ''
    return 'NONTRIV'


pages = {
    'chipid':          (0x1F600, 0x4E, 7),
    'nt36525_fwinfo':  (0x11A78, 0x78, 17),
    'nt36672_fwinfo':  (0x21C78, 0x78, 17),
    'nt36525_pid':     (0x11A9A, 0x9A, 3),
    'nt36672_pid':     (0x21C9A, 0x9A, 3),
    'nt36525_event':   (0x11A00, 0x00, 66),
    'nt36672_event':   (0x21C00, 0x00, 66),
}

print('full-duplex READ-ONLY probe, ioctl=%08x' % SPI_IOC_MESSAGE_1, flush=True)
for page_first in (0xFF, 0x7F):
    for read_or in (0x00, 0x80):
        for name, (addr, cmd, ln) in pages.items():
            set_page(addr, page_first)
            payload, raw = read(cmd | read_or, ln)
            tag = note(payload) or '       '
            extra = ''
            if len(payload) >= 2 and name.endswith('fwinfo'):
                if (payload[0] + payload[1]) & 0xFF == 0xFF and payload[0] not in (0, 0xFF):
                    extra = ' <== FW INFO VALID (ver + ~ver == 0xFF)'
            print('%s pfirst=%02x ror=%02x %-16s %s%s' %
                  (tag, page_first, read_or, name,
                   payload[:12].hex(' '), extra), flush=True)
os.close(fd)
