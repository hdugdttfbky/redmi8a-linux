# 桌面与 VNC：横屏镜像方案

目标：屏幕上要看到真实桌面，VNC 里看到**同一块画面**，而且整体是**横屏**。

---

## 1. 三条路的对比

### ❌ 方案 A：Xorg `fbdev` 驱动

装了 `xserver-xorg-video-fbdev`，试了 5 组配置（有无 `Modes` / `ShadowFB` 开关 / `DefaultFbBpp` 24 与 32），
全部失败，日志固定为：

```
FBIOPUT_VSCREENINFO: Invalid argument
mode "720x1520" not found
```

原因：simpledrm 的 fbdev 仿真层**不接受改模式**。Debian 也没有 kdrive 的 `Xfbdev`。

### ⚠️ 方案 B：Xorg `modesetting` 驱动（能出图，但只能竖屏）

```ini
Section "Device"
    Identifier  "Card0"
    Driver      "modesetting"
    Option      "kmsdev"    "/dev/dri/card0"
EndSection
```

`modesetting_drv.so` 由 `xserver-xorg-core` 自带，**不写 `Modes`**，让 DRM 自动给出 720×1520×24。
起在 `:2` 上 `xsetroot -solid '#00ff00'` → 用户确认屏幕变绿 → **DRM framebuffer 直接上屏，零额外开销**。

**但一旦旋转就黑屏**：

```sh
xrandr --output None-1 --rotate right   # 逻辑分辨率变成 1520x720，VNC 也跟着变
                                        # → 屏幕直接黑；xsetroot + xrefresh 强制重绘也无效
```

结论：**modesetting 的 RandR 软件旋转在这块 simpledrm 上不送到物理面板**
（旋转后的 shadow framebuffer 没被提交）。别再试 `DefaultFbBpp` / `ShadowFB`，跟它无关。

### ✅ 方案 C：Xvfb `-fbdir` + 用户态旋转镜像（最终采用）

核心思路：**横屏在 X server 里做，不在 DRM 里做。**

```sh
Xvfb :1 -screen 0 1520x720x24 -fbdir /run/xvfb -nolisten tcp -ac +extension RANDR
```

`-fbdir` 把 framebuffer 暴露成普通文件 `/run/xvfb/Xvfb_screen0`（XWD 格式），
镜像程序直接 mmap 读，**不需要 `XGetImage` 走 socket 拷 4.4 MB**。

XWD 文件格式（实测）：

```
总大小        4,380,832 字节
header_size   160
ncolors       256
像素偏移      3232  (= 160 + 256*12)
像素格式      32bpp BGRX
尺寸          1520×720, bytes_per_line = 6080
```

镜像程序 `fbmirror.py`：mmap XWD → numpy 转置 90° → RGB24 写 `/dev/fb0`（720×1520, stride 2160）。

因为 X server 本身就是 1520×720，**VNC 天然是横屏**，屏幕和 VNC 是同一块画面。

---

## 2. CPU 从 92% 压到 9.5%

第一版常驻镜像吃掉一个核（负载 2.49），逐段 benchmark 后定位并修掉三处：

| 阶段 | 单帧 | 稳态 CPU |
|---|---|---|
| ctypes `XGetImage`（4.4 MB socket 拷贝）+ 纯 Python 逐行旋转 | ~380 ms | **92%** |
| XWD mmap + fancy indexing + 全帧 blake2b | 115 ms | 77% |
| view 转置 + 抽样 hash + 自适应帧率 | ~53 ms | **9.5%** |

三个关键点：

1. **`arr[:, :sw, [2,1,0]]` 是 fancy index**，触发逐像素 gather（87 ms）。
   换成 slice view：`arr[:, :sw, 2::-1]` + `rgb[::-1].transpose(1,0,2)` → **45 ms，输出逐字节一致**。

2. **全帧 `blake2b(out)` 要 14.7 ms**（3.3 MB）。改成 `blake2b(out[::1024])` 抽样 → **0.42 ms**。

3. **`memoryview(mm)[...]` 会让 `mm.close()` 抛 `BufferError`**（exported pointers）。
   改回普通 bytes 切片，每帧多 4 ms，可忽略。

另外加了自适应帧率：画面不变时 1.5 fps，一有变化立刻回 6 fps。

`ccw` 的逆映射：`rgb[:, ::-1].transpose(1,0,2)`。

---

## 3. 输入桥：touch2x.py

Xvfb **没有 evdev 输入驱动**，所以用 XTEST 注入。同时要做镜像旋转的**逆变换**：

```
物理面板 (tx, ty)  →  X 坐标
cw:   X_x = ty/max_y * (W-1)          X_y = (1 - tx/max_x) * (H-1)
ccw:  X_x = (1 - ty/max_y) * (W-1)    X_y = tx/max_x * (H-1)
REL 鼠标 delta: cw (dy, -dx) / ccw (-dy, dx)
```

`touch2x.py` 会**自动从 `fbmirror.service` 读 `MIRROR_ROT`**，所以
`display-rotate.sh ccw` 切方向时输入不会脱节。

自检（`touch2x.py --selftest`）实测：

```
(0,0)        -> (0, 719)
(719,0)      -> (0, 0)
(0,1519)     -> (1519, 719)
(719,1519)   -> (1519, 0)
注入后 xdotool 读回 x:0 y:719  ← 与预期一致
```

当前系统里没有触摸设备（见 [touch-nt36525b.md](touch-nt36525b.md)），但**插 USB OTG 鼠标即可直接操作横屏桌面**。

---

## 4. 服务依赖链

```
ktd3137-backlight  (背光使能)
        ↓
fb-unblank         (清 /sys/class/graphics/fb0/blank = 4)
        ↓
xvfb.service       (Xvfb :1 1520x720x24 -fbdir /run/xvfb)
        ↓                    ├── fbmirror.service  → /dev/fb0
        │                    ├── touch2x.service
        │                    ├── x11vnc.service   → :5900
        │                    ├── vnc-session / vnc-terminal
        │                    └── codearts
        └── screen-toggle.service  (电源键)
```

**`xvfb.service` 这个 unit 名字是故意保留的** —— x11vnc / vnc-session / vnc-terminal / codearts
全都 `Requires=xvfb.service`，改名会牵动 4 个服务。

---

## 5. VNC 暴露面

`x11vnc` 监听 `0.0.0.0:5900` + `[::]:5900`，用 `-rfbauth /root/.vnc/passwd`。
看起来像暴露在公网，但 `/etc/nftables.conf` 已经收敛：

```
table inet filter
  chain input  policy drop
    5900 只放行  iifname wlan* / usb*  +  ip saddr @lan4 (10/8, 172.16/12, 192.168/16)
    5900 放行    iifname tailscale0
    全局 IPv6 5900 未放行 → drop
```

⇒ 实际只在 LAN / Tailscale 可达，加上密码。

**所以没有改成 `127.0.0.1`** —— 那样会立刻断掉正在使用的直连会话，且没有额外收益。
如果以后想改纯 SSH 隧道，用 `vnc-localhost.sh localhost`（默认未启用）。

---

## 6. 冷启动实测

```
11.08 s 进系统          8 个服务全 active   失败单元 0
Xvfb 1520x720           VNC 5900 监听       blank=0
背光 0x02=0x99          msm 未加载
fb0 与 X 画面稳态一致（差异 0.037%，只是采样瞬间的光标/时钟）
```

> 开机瞬间一致性差异可到 8%，那是因为桌面程序还在初始化动画，属正常。

## 7. 注意

- **设备要横过来拿**：物理面板始终竖着扫 720×1520，画面被软件转了 90°。
- 软件旋转约 9.5% CPU 开销，静止时更低。
- `/etc/X11/xorg.conf` 是方案 B 的遗留（Xvfb 不读它），留着无害。
- `display-rotate.sh cw|ccw|status` 切换方向；`check-mirror.py` 随时比对 fb0 与 X 画面是否一致。
