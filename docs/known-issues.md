# 已知问题与遗留

按"是否值得现在动"排序。每条都写明为什么不建议动，避免重复投入。

---

## ❌ GPU 加速（Adreno 505）未启用

**状态**：`msm` 未加载、无 `/dev/kgsl`、无 `renderD128`，桌面走 llvmpipe 软件渲染。

**曾经的卡点**：`CP hang`，`status 0x800001C1`。

**为什么不建议现在动**：GPU 依赖 `msm` 模块，而这个模块**一加载就会把 MDP 寄存器改坏、屏幕变黑**。
要用 GPU 就必须先解决显示与 msm 的冲突（即"劫持 LK 流水线"那条路，见
[display-pipeline.md §8](display-pipeline.md#8-如果以后要继续攻-msm)）。这是独立的一轮大工程。

顺带纠正一个常见误判：**`adreno` probe 成功、`devfreq` 有读数 ≠ GPU 可用**。
当时的诊断里还有 `cur_freq 报 49999987`（不在档位表 19.2/216/300/375/400/450 内）、
`devfreq 1c00000.gpu: Couldn't update frequency transition information`，
以及 `Zap shader not enabled - using SECVID_TRUST_CNTL instead`。

---

## ❌ 触摸不可用

详见 [touch-nt36525b.md](touch-nt36525b.md)。一句话：芯片停在 boot ROM，
刷固件会连带复位显示。

**替代方案**：插 USB OTG 鼠标，`touch2x.py` 会直接接管（已自测通过）。

---

## ⚠️ USB 网络（NCM/RNDIS）

**状态**：设备侧 `usb0` / UDC 配置正常，Windows 侧报 `ProblemCode 28`（驱动未安装）。

这是 **Windows 侧驱动问题**，不是设备问题。设备的 gadget 配置（`inspect-gadget*.sh`
系列的输出）是正常的。

---

## ⚠️ i2c 总线编号会随 DTB 变化

把 `spi@78b7000` 从 i2c 切成 spi 之后，i2c 控制器编号重排（`1-0036` → `0-0036`）。

**已处理**：`ktd3137-bl`、`bl-guard.sh`、`screen-toggle.py` 三个脚本都改成自动探测
0x36 所在总线，新旧 DTB 都兼容。

**但注意**：`config/systemd/bl-guard.service` 里还留着 `ConditionPathExists=/dev/i2c-1`，
如果哪天总线编号变成别的，这个 unit 会直接跳过。脚本本身能自适应，删掉这行更稳妥。

---

## ⚠️ `/etc/X11/xorg.conf` 是遗留

它属于"Xorg modesetting 竖屏"方案（已放弃）。现在跑的是 Xvfb，不读这个文件。
`xserver-xorg-*` 包也因此没用了，可以卸，但不影响任何东西。

---

## ✅ WiFi 丢包（已修复，记录备查）

**症状**：ping 大量丢包、吞吐极低。

**根因**：`wcn36xx` 的固件**独占速率决策**，驱动设的速率不起作用，
结果恒定使用 **MCS7**（HT 最高阶），在这个信号条件下必然大量重传。

**修复**：关闭 2.4 GHz 的 HT 能力（`ht_supported = false`），强制走 802.11g：

```c
/* wcn36xx 模块补丁：上报的 band 能力里去掉 HT */
```

产物 `wcn36xx-htoff.ko.zst`，设备侧备份 `/root/wcn36xx.ko.zst.{orig,htoff}`。
效果：**丢包率 0%**。

> 这个模块文件没有传到仓库（只在本机 `F:\redmi8a-linux\`），因为它是对特定内核版本编译的二进制。

---

## 遗留的调试工具（保留，有用）

| 工具 | 用途 |
|---|---|
| `drivers/mdppoke/` | MDP 寄存器在线读写 + 实时状态观测（`pokes` / `physpokes` / `dumps`） |
| `scripts/probe/probe-nvt-full.py` | 全双工只读 NVT SPI 探测（找 chip ID） |
| `scripts/probe/diag-spi-ioctl.py` | 探测本机 `SPI_IOC_MESSAGE` 编码 |
| `scripts/display/check-mirror.py` | 逐字节比对 X 画面与 `/dev/fb0` |
| `scripts/display/fbshow.py` | 在未启动 X 时直接画测试图（solid / split / bars） |
