#!/bin/sh
set -e
SRC=/mnt/f/redmi8a-linux/backups/sdm439-xiaomi-olive.dtb.pre-20261108-142111
W=/mnt/f/redmi8a-linux/dtb

echo "===== 1. 反编译当前 DTB ====="
dtc -I dtb -O dts "$SRC" -o "$W/olive-current.dts" 2>"$W/dtc-in.log"
wc -l "$W/olive-current.dts"

echo "===== 2. 打补丁 ====="
python3 /mnt/f/redmi8a-linux/make-spi-dtb.py > "$W/patch.log"
tail -30 "$W/patch.log"

echo "===== 3. 编译实验 DTB ====="
dtc -I dts -O dtb "$W/olive-spi-probe.dts" -o "$W/olive-spi-probe.dtb" 2>"$W/dtc-out.log"
ls -l "$W/olive-spi-probe.dtb"
grep -c 'Warning' "$W/dtc-out.log" || true

echo "===== 4. 回读并 diff（确认只有预期改动）====="
dtc -I dtb -O dts "$W/olive-spi-probe.dtb" -o "$W/olive-spi-probe-check.dts" 2>/dev/null
diff -u "$W/olive-current.dts" "$W/olive-spi-probe-check.dts" | head -45 || true

echo "===== 5. 校验和 ====="
sha256sum "$SRC" "$W/olive-spi-probe.dtb"
