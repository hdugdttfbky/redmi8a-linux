# Redmi 8A · 独立 Linux 实战记录

把一台 **Redmi 8A（olivelite）** 彻底刷掉 Android、跑起纯 Debian Linux，并让它变成一台
**带屏幕、可 VNC、能当微型服务器** 的设备 —— 全部过程、结论与踩坑。

> 这不是一份"照着做就能成功"的教程。它是一份**实验记录**：哪些路走通了、哪些是死胡同、
> 以及为什么。显示链路的结论与常见文档**相反**，触控的结论是"当前架构下做不到"。
> 如果你也在折腾 Qualcomm msm89x7 + simpledrm 的设备，这里省下的可能是一周。

---

## 一句话结论

**不要重建显示流水线 —— 劫持 bootloader 留下的那条。**

这块屏能用，靠的是 LK（bootloader）把 MDP5 + DSI PHY + 面板全部配置好并**持续以 60 fps 扫描**，
Linux 侧的 `simpledrm` 只是往它那块 framebuffer 里写像素。一旦加载 `msm` 驱动，
它会把 MDP 的 CTL / LM / INTF 全部改写，屏幕立刻变黑。所以正解是：**blacklist 掉 msm，只写 `/dev/fb0`。**

---

## 当前状态

| 能力 | 状态 | 说明 |
|---|---|---|
| 独立启动 Linux（无 Android） | ✅ | Debian 12 arm64，冷启动约 11 秒 |
| 屏幕显示（720×1520） | ✅ | LK 流水线 + simpledrm，60 fps |
| 横屏桌面（1520×720） | ✅ | 用户态旋转镜像，CPU 约 9.5% |
| VNC 远程桌面 | ✅ | x11vnc :5900，nftables 限制来源 |
| 背光亮度 / 电源键开关屏 | ✅ | KTD3137，i2c 直控 |
| WiFi | ✅ | wcn36xx，关闭 2.4G HT 后 0% 丢包 |
| 触摸 | ❌ | 触控 IC 停在 boot ROM，见 [docs/touch.md](docs/touch.md) |
| GPU 加速（Adreno 505） | ❌ | 依赖 msm，与当前显示方案冲突 |
| USB 网络（NCM） | ⚠️ | 设备侧正常，Windows 侧驱动有问题 |

---

## 硬件

```
SoC      Qualcomm SDM439 / MSM8937   (8× Cortex-A53)
RAM/ROM  3 GB / 32 GB
面板     Novatek NT36525B TDDI, 720×1520, 4-lane DSI, 12nm PHY
触控     NT36525B 集成 (in-cell)，走 SPI CS1 —— 不是 I2C
背光     Kinetic KTD3137 @ i2c 0x36  (DT 里被错写成 TI LM3697)
内核     7.1.3-msm89x7 (aarch64, mainline 系)
用户态   Debian 12 bookworm arm64
```

---

## 显示架构（最终可用方案）

```
                  ┌─────────────────────────────────────────┐
   LK / bootloader │  MDP5 ──── DSI ──── NT36525B panel      │  60 fps 持续扫描
   留下的状态      │  (CTL/LM/INTF/PP/PHY 全部已配置)         │  ← 绝对不要去改
                  └───────────────┬─────────────────────────┘
                                  │  framebuffer (stolen)
                    simpledrm     ▼
                  /dev/fb0   720×1520, 24bpp, stride 2160
                                  ▲
                                  │ write()  旋转 90°
                        ┌─────────┴──────────┐
                        │    fbmirror.py     │  mmap + numpy
                        └─────────▲──────────┘
                                  │ XWD 文件 (零 socket 拷贝)
                  ┌───────────────┴─────────────────────────┐
                  │  Xvfb :1   1520×720×24  -fbdir /run/xvfb │  ← 横屏在这里
                  │      ├── openbox / lxpanel               │
                  │      ├── xterm (开机信息屏)               │
                  │      └── x11vnc :5900  →  VNC 客户端      │
                  └─────────────────────────────────────────┘
                                  ▲
                        ┌─────────┴──────────┐
                        │    touch2x.py      │  evdev → XTEST（逆旋转映射）
                        └────────────────────┘
```

关键点：**横屏是在 X server 里做的，不是靠 RandR 旋转。**
`Xvfb -fbdir` 把 framebuffer 直接暴露成一个可 mmap 的 XWD 文件，镜像程序只做一次内存拷贝 +
numpy 转置，避免了 `XGetImage` 每帧 4.4 MB 的 socket 传输。

---

## 最有价值的 6 条结论

1. **`modprobe msm` 会毁掉显示。** 它把 `ctl_op` 从 `0x1f20` 改成 `0x20`、`lm_blend` 从
   `0x100` 三个全改 0，MDP 就不再产帧。内核 cmdline 里的 `modprobe.blacklist=bl_lm3697,msm`
   **必须保留**。想恢复只能重启。

2. **两个 framebuffer 是不同格式。** simpledrm 的 `/dev/fb0` 是 **24bpp / stride 2160**；
   msm 自己的 fbdev 才是 **16bpp / pitch 1472**。按 16bpp 往 24bpp 里写，屏幕当然全黑 ——
   这一条曾让我误判了好几轮。

3. **Xorg 的 fbdev 驱动在这块 simpledrm 上不能用**，`FBIOPUT_VSCREENINFO` 一律 `EINVAL`（试了 5 组配置）。
   Xorg 的 **modesetting** 驱动可以直出竖屏，但它的 **RandR 软件旋转不上屏** —— 转完就黑屏。

4. **背光芯片不是 DT 里写的 LM3697，是 KTD3137。** `0x00` 读回 `0x18` 就是它的 Device ID。
   出厂默认 `0x02=0x98`（BL_EN=0），所以"全链路正常却全黑"的真正原因是背光从没使能。

5. **`ret=0` 不代表 DSI 通了。** 面板驱动的 init 序列返回 0 只说明写请求入队成功。
   唯一可靠的判据是 **DCS read（读 `0x0A` 电源模式）**：`rc=1` 才是真通，`rc=-110` 就是超时。

6. **触控走 SPI，不走 I2C。** 在两条 i2c 总线上探测全是空，因为芯片根本不在这儿。
   实际接法是 `spi@78b7000`(blsp1_spi3) CS1，reset GPIO64 / irq GPIO65。

---

## 仓库结构

```
docs/
  display-pipeline.md   msm 攻坚全过程 + LK/驱动寄存器对照表（含死路记录）
  backlight.md          KTD3137 寄存器表与点亮配方
  desktop-vnc.md        横屏镜像方案 + CPU 从 92% 压到 9.5% 的优化过程
  touch-nt36525b.md     触控硬件/协议完全摸清，以及为什么最终放弃
  operations.md         备份、回滚、灾难恢复
  known-issues.md       已知问题与不要做的事

scripts/
  display/    fbmirror.py  check-mirror.py  fbshow.py  display-rotate.sh  system-info.sh
  input/      touch2x.py
  backlight/  ktd3137-bl  bl-guard.sh  screen-toggle.py
  ops/        backup-redmi8a.sh  restore-redmi8a.sh  rollback-dtb.sh  dtb-guard.sh
  probe/      probe-nvt-full.py  diag-spi-ioctl.py

config/systemd/           9 个 unit（Xvfb / 镜像 / 输入桥 / 背光 / 守卫 / DTB 回滚）
drivers/mdppoke/          MDP 寄存器在线读写观测模块（调试利器）
drivers/panel/            自写的 NT36525B DRM 面板驱动
drivers/dts/              启用 SPI 触控的 DTB 修改脚本
```

---

## 复现要点

**内核 cmdline**（这行是整套方案能成立的前提）：

```
consoleblank=0 modprobe.blacklist=bl_lm3697,msm
```

**依赖**：`xvfb openbox lxpanel x11vnc xterm python3-numpy i2c-tools`
（`xserver-xorg-*` 只在探路阶段用到，最终方案不需要）

**安装**：把 `scripts/*/*.py|*.sh` 放到 `/usr/local/bin/`，`config/systemd/*` 放到
`/etc/systemd/system/`，然后：

```sh
systemctl daemon-reload
systemctl enable --now ktd3137-backlight fb-unblank bl-guard.timer \
                        xvfb fbmirror touch2x screen-toggle
```

⚠️ 脚本里凡是涉及 i2c 的，**都会自动探测 0x36 落在哪条总线** —— 因为把 `spi@78b7000`
从 i2c 切成 spi 会让总线编号重排（`1-0036` → `0-0036`），硬编码会直接失效。这个坑我们踩过。

---

## 明确不要做的事

| 操作 | 后果 |
|---|---|
| `modprobe msm` | MDP 寄存器被改写，屏幕黑，只能重启 |
| `rmmod bl_lm3697` / unbind `1-0036` | HWEN 拉低 → 背光芯片断电 → 黑屏 |
| `echo 1 > /dev/fb0 blank` 循环 | DSI 链路被破坏，`prepare()` 报 `-22`，随后 oops |
| 给触控 IC 发 `0x69` | 复位整颗 TDDI，**连带 LCD 黑屏** |

---

## English abstract

A hands-on write-up of replacing Android with standalone Debian Linux on a Xiaomi
Redmi 8A (SDM439 / MSM8937, NT36525B 720×1520 panel).

The central finding: **the display only works because the bootloader leaves a live
MDP5/DSI pipeline behind.** Loading the mainline `msm` driver rewrites the MDP
registers and blanks the panel, so the working approach is to blacklist `msm` and
only write pixels into simpledrm's `/dev/fb0` (24 bpp, stride 2160). Landscape mode
is achieved by running Xvfb at 1520×720 with `-fbdir` and rotating the pixels into
the portrait framebuffer in userspace (~9.5% CPU). Touch is documented in full
(SPI CS1, chip ID `0b 00 00 25 65 03`) but abandoned: the touch firmware never runs,
and flashing it risks the only working display path.

## License

MIT. 代码可自由使用；文档中的硬件结论请自行验证，风险自负。
