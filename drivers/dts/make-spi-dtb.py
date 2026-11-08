import re, sys

src = '/mnt/f/redmi8a-linux/dtb/olive-current.dts'
out = '/mnt/f/redmi8a-linux/dtb/olive-spi-probe.dts'
s = open(src, encoding='utf-8', errors='surrogateescape').read()


def node_span(text, name):
    start = text.find(name + ' {')
    if start < 0:
        raise SystemExit('node not found: ' + name)
    # find the matching closing brace at the same indentation
    line_start = text.rfind('\n', 0, start) + 1
    indent = text[line_start:start]
    end_marker = indent + '};'
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit('no closing brace for ' + name)
    return start, end, indent


# --- 1. disable the I2C controller that shares the same QUP block ---
a, b, _ = node_span(s, 'i2c@78b7000')
block = s[a:b]
if 'status = "okay";' not in block:
    raise SystemExit('i2c status not "okay"')
block = block.replace('status = "okay";', 'status = "disabled";')
s = s[:a] + block + s[b:]

# --- 2. enable the SPI controller and add a spidev on CS1 ---
a, b, indent = node_span(s, 'spi@78b7000')
block = s[a:b]
if 'status = "disabled";' not in block:
    raise SystemExit('spi status not "disabled"')
block = block.replace('status = "disabled";', 'status = "okay";')
child = (
    '\n' + indent + '\tspidev@1 {\n'
    + indent + '\t\tcompatible = "rohm,dh2228fv";\n'
    + indent + '\t\treg = <0x01>;\n'
    + indent + '\t\tspi-max-frequency = <9600000>;\n'
    + indent + '\t};\n'
)
# insert before the node's closing brace (just before the last line)
idx = block.rfind('\n')
block = block[:idx] + child + block[idx:]
s = s[:a] + block + s[b:]

open(out, 'w', encoding='utf-8', errors='surrogateescape').write(s)
print('wrote', out)

# show the edited region
i = s.find('i2c@78b7000 {')
print(s[i:i + 1400])
