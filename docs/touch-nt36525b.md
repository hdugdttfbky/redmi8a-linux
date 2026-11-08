# 触控：硬件与协议已完全摸清，但最终放弃

**结论先行：在当前架构下不可修。** 触控固件没有运行，芯片停在 boot ROM；
要让它工作必须在用户态做 Host Download 把 118 KB 固件写进 TDDI 的 SRAM ——
而这颗 TDDI 同时驱动着 LCD，复位它会**连带让屏幕黑掉**，而我们的显示完全依赖
LK 遗留的流水线。不值得为触摸冒这个风险。

下面是完整的排查过程，以及如果要继续该从哪一步开始。

---

## 1. 先确认一件事：不是"没接进 X"

```
/dev/input/event0  pm8941_pwrkey          电源键
/dev/input/event1  pm8941_resin           音量下
/dev/input/event2  gpio-keys
/dev/input/event3  pm8xxx_vib_ffmemless   振动器
```

**一个触摸设备都没有。** 所以问题不在输入层，而是触控 IC 的驱动压根没起来。

---

## 2. 走错的第一段路：以为是 I2C

依据是主线 `novatek-nvt-ts.c`（支持 `nt11205-ts` / `nt36672a-ts`）是 I2C 驱动。
于是在两条 i2c 总线 0/1 上强制读 `0x01 0x62 0x14 0x5d 0x38 0x48 0x41 0x70` ——
**全部无应答**，得出"芯片没上电"的结论。

同时查了：
- 主线 `sdm439-xiaomi-olive.dts` 里只有注释占位：`&blsp1_spi3 { status="disabled"; /* novatek,nt36525b@1 */ }`
- 完整 `dtbobak` 分区（`/dev/mmcblk0p40`，8 MB，20 个 dtb）逐个反编译 → **没有触控节点**
- 内核 7.1.3 源码树没有 `nt36xxx.c`

> 顺带一个教训：设备上**没有装 `strings`**，第一次搜空是工具缺失造成的误判。
> 用 `dd` 把分区导回 WSL 再搜才是对的。

---

## 3. 真正的接法：SPI，不是 I2C

来源：Xiaomi 官方开源内核 `MiCode/Xiaomi_Kernel_OpenSource` 分支 `olive-q-oss`，
文件 `arch/arm64/boot/dts/qcom/sdm439-ctp-olive.dtsi`（CTP = 电容触控）：

```dts
&spi@78b7000 {                      /* = blsp1_spi3，主线 DTS 里正是被 disabled 的那个 */
    status = "okay";
    ilitek_spi@00 { compatible = "tchip,ilitek";  reg = <0>; ... };
    novatek@1 {
        compatible = "novatek,NVT-ts-spi";
        reg = <1>;                              /* CS1 */
        spi-max-frequency = <9600000>;
        novatek,reset-gpio       = <&tlmm 64 0x00>;
        novatek,irq-gpio         = <&tlmm 65 0x2001>;
        novatek,swrst-n8-addr    = <0x03F0FE>;  /* 672A / 525B / 675 */
        novatek,spi-rd-fast-addr = <0x03F310>;
    };
    focaltech@2 { compatible = "focaltech,fts"; reg = <2>; ... };
};
```

注释 `for Xiaomi C3I 525B BOE 6.217"` 与本机面板 `qcom,mdss_dsi_nvt36525b_hdplus_video_c3i`
完全对应 ⇒ 本机用 **`novatek@1` / CS1**。同总线还有 ilitek(CS0) 与 focaltech(CS2)，
对应不同面板供应商批次。Device Info HW 也标注本机触控为 `NVT-ts`。

⇒ 两条 i2c 总线全空是正常的，**芯片根本不在这儿**。

---

## 4. 驱动现状

| 来源 | 情况 |
|---|---|
| 下游 `drivers/input/touchscreen/NT36525B/` | 完整但约 **220 KB**（`nt36xxx.c` 58 KB + 固件更新 26 KB + MP 测试 88 KB + 扩展 proc 40 KB），强依赖 4.9 Qualcomm 下游框架，整体移植不现实 |
| 主线 | SPI 版仍是 2026-09 的 **RFC**（`novatek-nt36672a-spi.c`，674 行，未合入），依赖 `request_firmware()` + `drm_panel_follower`，与本机架构冲突 |
| 主线 `nt36xxx` | LKML v10 的 **I2C 版**，不适用本机 SPI 接法；7.1.3 树里也没有 |

---

## 5. 运行时 DT overlay 走不通

内核确实有 `CONFIG_OF_OVERLAY=y`、`CONFIG_OF_DYNAMIC=y`，configfs 也挂了，
`CONFIG_SPI_SPIDEV=m`、`SPI_QUP=y`。看起来可以动态挂 `spidev@1`、删目录即恢复。

**但 `/sys/kernel/config/device-tree/overlays` 不存在** —— `CONFIG_OF_CONFIGFS` 没编进去。
所以只能改 DTB 本身。

---

## 6. 改 DTB（可回退）

改动只有 3 处，反编译 → 精确替换 → 重编译 → 回读 diff 确认其余 3100 行一字未变：

```diff
- i2c@78b7000   status = "okay"      →  "disabled"
- spi@78b7000   status = "disabled"  →  "okay"
+ spidev@1 { compatible = "rohm,dh2228fv"; reg = <1>; spi-max-frequency = <9600000>; }
```

（同一个 QUP 硬件块 `78b7000` 在主线和下游被分别配置成 i2c 与 spi，两个节点一个 `okay` 一个 `disabled`。）

结果：`spi_qup 78b7000.spi` 成功 probe，**`/dev/spidev0.1` 出现**，系统正常启动。

**副作用**：i2c 编号重排（`1-0036` → `0-0036`），背光脚本失效 —— 见 [backlight.md](backlight.md#为什么必须自动探测总线)。

脚本见 `drivers/dts/`。

---

## 7. SPI 协议（关键的坑）

### `SPI_IOC_MESSAGE` 编码

这个内核的 `SPI_IOC_MESSAGE(1)` = **`0x40206B00`**（size 字段 32），**不是** 40 字节版的 `0x40286B00`。
用后者一律 `EINVAL`。

```python
tr = struct.pack('=QQIIHHBBBBB7x', tx_ptr, rx_ptr, n, speed, 0, 8, 0, 0, 0, 0, 0)
fcntl.ioctl(fd, 0x40206B00, tr)
```

### 读写命令

- **SPI_MODE_0 / 8 bit / 1 MHz**，全双工
- `SPI_WRITE_MASK` / `SPI_READ_MASK` 都是 **identity**（不 `&0x7F`、不 `|0x80`）
- `set_page(addr)` = `[0xFF, (addr>>15)&0xFF, (addr>>7)&0xFF]`
- 读 chip ID：`set_page(0x1F600)` 然后发 `0x4E`

### 芯片确认

```
chipid → 0b 00 00 25 65 03
              ^^^^^^^^^^^
```

后三字节 `25 65 03` 与下游 `trim_id_table` 的 **NT36525** 条目精确匹配，
多个 page 上稳定复现 ⇒ **读法正确、芯片确实是 NT36525，不是 NT36672A。**

---

## 8. 硬阻碍：固件没跑

`EVENT_BUF_ADDR = 0x11A00`（NT36525）以及 fwinfo 页全部读回 **`0xFF`**。
所有候选地址（`0x21C00` / `0x11E00` / `0x22D00`）都读不到结构化数据：

- 没有 `fw_ver + ~fw_ver == 0xFF`（FW info 有效的判据）
- 没有有效 point data

⇒ **芯片停在 boot ROM，触控固件没有运行。**

固件确实存在：下游 `NT36525B/include/firmware/novatek_ts_fw.bin`，**118,784 字节**。
主线 RFC 驱动靠 `request_firmware()` 做 **Host Download 把固件写进 TDDI SRAM** 才有触控事件。

---

## 9. 最后的低风险尝试（失败）

只向 HOST_CMD(`0x50`) 写 `0x00` / `0x35`，**没发 `0x69`、没发 `0xA5`、没动 GPIO64、没刷固件**：

| 基址 | RESET_COMPLETE | FW info | point data |
|---|---|---|---|
| `0x11A00` (NT36525) | 全 `FF` | 全 `FF` | 全 `FF` |
| `0x21C00` (NT36672A) | `71 72 06 39 6e`（非 0xA0–0xAF 有效状态） | 全 `00` | 全 `00` |

写入前后完全无变化 ⇒ 低风险路径穷尽。随后执行 DTB 回退，系统恢复原状。

---

## 10. ⚠️ 如果要继续：风险在哪

主线 RFC 原文警告：

> writing `0x69` resets the entire IC (display timing generator, DCS registers, PWM)
> and causes the physical LCD to go completely black.

也就是说 **Host Download 会复位整颗 TDDI，连带重置显示时序**。本机显示完全依赖 LK 留下的
MDP/DSI 状态，一旦被复位，**当前唯一的显示路径就没了**。

如果以后愿意承担这个风险，从这一步接：

1. 用 `drivers/dts/` 的脚本生成实验 DTB（启用 spi + spidev）
2. 移植 Host Download：写 `0x69` → 等 `RESET_COMPLETE == 0xA0..0xAF` → 分页写 118 KB 固件 →
   等 `FW_READY` → 读 point data
3. 解析 point data（6 字节/手指，65+1 字节缓冲）：
   ```
   x = (d[p+1] << 4) | (d[p+3] >> 4)
   y = (d[p+2] << 4) | (d[p+3] & 0x0F)
   ```
4. 喂给已经写好的 `scripts/input/touch2x.py`（它是通用的 evdev→XTEST 桥，不用改）

准备好一整套回退工具（`rollback-dtb.sh` + `dtb-guard.sh`）再动，别裸上。

## 11. 顺带修好的一层：输入桥

虽然硬件没成，`touch2x.py` 是完好的：它接受任何 **ABS 触摸** 或 **REL 鼠标** evdev 设备，
做逆旋转映射后注入 Xvfb。所以现在**插个 USB OTG 鼠标就能操作横屏桌面**，
而且以后触控驱动一旦就绪，这一层不用再改。
