# 显示链路：从全黑到可用

这份文档记录的是一条**走了很久才走对的弯路**。结论在最后，但过程更有价值 ——
因为它包含了 6 个曾经让我误判的"假指标"。

---

## 0. 起点：为什么一开始方向就错了

设备上电后，屏幕能不能亮，取决于三个彼此独立的东西：

1. **背光**（KTD3137 使能 + 亮度）
2. **面板出图**（DSI 链路 + 面板 init + 像素数据）
3. **MDP 产帧**（CTL → LM → INTF → DSI）

我最初假设"Linux 驱动要把整条链路重新建起来"，于是花了大量时间修 `msm.ko`。
**实际发生的是相反的事**：LK 已经把整条链路建好并在跑，Linux 侧的 `msm` 驱动
反而把它拆坏了。

`simpledrm` 之所以能显示，是因为它**不碰** MDP，只是往 LK 留下的那块 framebuffer 里写像素。

---

## 1. 判定"帧到底有没有在产"的唯一可靠指标

这一节最重要。**下面这些寄存器/计数器全都不可信**，我曾据此得出多个错误结论：

| 指标 | 为什么不可用 |
|---|---|
| `PP0_LINE_COUNT` / `OUT_LINE_COUNT` | 在 LK 正常出图时**也是 0** |
| `CTL_START` / `CTL_FLUSH` | 同上，读回永远是 0 |
| `DMA0_CURRENT_SRC0_ADDR` | 静态帧不变化，不能用来看"是否在跑" |
| `DSI_LANE_STATUS` | bit0-3 是 **STOPSTATE**（置 1 表示停在 stop 态）→ **0 才是好**，不是坏 |
| 面板驱动 `init sequence done, ret=0` | 只代表写请求入队成功，**不代表发到了面板** |
| `PP_RD_PTR_IRQ` / `INT_COUNT_VAL` | 只是阈值配置寄存器，不是实时计数 |

### 唯一可信的两个

**① `INTF1_FRAME_COUNT` @ `0x6a8ac`** —— 实时帧计数，两次采样相减得帧率：

```sh
# 需要 mdppoke 模块（见 drivers/mdppoke/）
modprobe mdppoke
dmesg | grep MDPPOKE     # 里面就有 frame_cnt
```

- LK 状态：**59~60 fps** ✅
- msm 接管后：**717 fps** ❌ ← 正好 12 倍，这个数字是破案的关键

**② DCS read** —— 判断 DSI 链路能否双向通信。在面板驱动里插一次
`mipi_dsi_dcs_read(dsi, 0x0A, &val, 1)`：

```
rc=1          → 链路通，面板应答了
rc=-110       → ETIMEDOUT，链路断
```

---

## 2. 根因一：DSI 像素时钟是 VCO 直出（12 倍速）

717 fps × htotal(828) × vtotal(1540) ≈ **1030 MHz** —— 正好等于 DSI PLL 的 VCO 频率。
也就是说 MDP 的像素时钟**没有分频**，直接吃了 VCO。

而 Linux 时钟框架显示 `pclk0 = 85839000`（VCO/12），**这是假的**：那两个分频器是
用 `devm_clk_hw_register_fixed_factor_parent_hw()` 注册的**纯软件分频器**，硬件上并不存在。

硬件分频字段在 PHY 的 `+0x3b8`（代码里叫 `DSIPHY_SSC9` / `pixel_divhf`），
而 DT 里写的是 `qcom,pll-divhf = <0x00>`。

实测规律：**像素时钟 = VCO / (SSC9 + 1)**

| 写入 PHY+0x3b8 | 实测帧率 |
|---|---|
| 0（原状） | 717/s |
| 2 | 239/s |
| **11** | **59~60/s** ✅ |

这块屏需要 `/12`，所以 `SSC9 = 0x0b`。

工厂实际配置是 `gp_div_mux = 2, divhf = 2`（`gp_div(4) × (divhf+1)(3) = 12`），
对应 `PLL_CTRL(0x3f8) = 0x45`、`SSC9(0x3b8) = 0x02`。

---

## 3. 根因二：PHY timing 字节序错误

DT 里没有 `qcom,mdss-dsi-panel-timings-phy-12nm`，驱动走内置默认值：

```c
/* 错（小端解析） */  { 0x03, 0x06, 0x07, 0x0b, 0x09, 0x03, 0x05, 0x00 }
/* 对（大端解析） */  { 0x0b, 0x07, 0x06, 0x03, 0x00, 0x05, 0x03, 0x09 }
```

判据是从 LK 实测寄存器反解，逐项吻合：

| 寄存器 | LK | 反解 t[] | 旧驱动 | 反解 t[] |
|---|---|---|---|---|
| `0x188` CLK HS0 | `0x8b` | t0=0x0b | `0x83` | t0=0x03 |
| `0x18c` CLK TRAIL | `0x47` | t1=0x07 | `0x46` | t1=0x06 |
| `0x194` CLK POST | `0x46` | t2=0x06 | `0x47` | t2=0x07 |
| `0x180` CLK REQ | `0x03` | t3=0x03 | `0x0b` | t3=0x0b |
| `0x1c8` DAT HS0 | `0x80` | t4=0x00 | `0x89` | t4=0x09 |

修完后 PHY `0x180~0x1d0` 与 LK 逐字节相同。

---

## 4. 根因三：缺 lane trim 块（唯一让 DCS 读从 -110 变 rc=1 的改动）

同一次启动内，LK 交接态 vs 驱动态对 PHY(`0x1a94400`) 做全量 diff，
除上面两处外唯一成块缺失：

```
0x360 = 0xac   0x364 = 0x4c   0x368 = 0x80
0x36c = 0x00   0x370 = 0xa0   0x374 = 0x0f
```

驱动侧全 0。写进 `phy_12nm_hstx_enable()` 后，**`DCS_READ 0x0A` 从 `rc=-110` 变成 `rc=1 val=0xf1`**。

> ⚠️ 但**不稳定**：下一次冷启动又回到 `-110`。说明 trim 写入与 PLL/HSTX 启动有竞争，
> 应移到 `pll_12nm_vco_prepare()` 里 commit 之前。这一条没验证完就转向了更简单的方案。

---

## 5. 死路清单（别再走了）

| 尝试 | 结果 |
|---|---|
| 在 `phy_12nm_hstx_enable()` 三处幂等写 trim | DCS 读仍 `-110` |
| DCS 读加 6 次重试 | `try0=-110`，`try1..5=-22`（控制器进了错误态） |
| `xfer_prepare()` 里命令期间清 `VID_MODE_EN`（避免 VID+CMD 双开） | 无效 |
| 面板驱动加 `skip_init`，保留 LK 初始化好的面板、不 reset | 仍黑 |
| 在线 poke `LM_BLEND0=0x100` + `FG_ALPHA=0xff` | 无变化 |
| 删掉 `MDP5_DIAG_V14` 的 `format \|= 0x3F` | 空操作 —— 入参本来 `0x213f`，`0x213f\|0x3f == 0x213f` |
| 写 `INTF_BORDER_COLOR` 为纯绿 | 无变化 |

完整日志最终定位到：

```
dsi_cmds2buf_tx: cmd dma tx failed, ret=-110
```

等 `CMD_DMA_DONE` 中断 200 ms 超时 —— **命令根本没送到线上**。
而 `xfer_prepare` 确实被调用、中断也使能了。

⇒ **破坏点在 msm 重写 MDP 的 CTL/LM/INTF/PP，不在面板初始化。**

---

## 6. 决定性实验：不加载 msm，帧还在跑吗？

```sh
# cmdline 已 blacklist msm，重启后 msm 未加载
modprobe mdppoke
dmesg | grep MDPPOKE | grep frame_cnt
```

结果：**1241 → 1253 → 1278 → 1303**，冷启动复验 **1601 → 1663**。
**LK 留下的流水线一直在以 60 fps 正常扫描。**

同时寄存器对照也全对：

| 寄存器 | LK（可用） | msm（黑屏） |
|---|---|---|
| `ctl_op` | `0x1f20` | `0x00000020` |
| `ctl_layer` | `0x200` (RGB0) | `0x40000` (DMA0@STAGE_BASE) |
| `lm_blend` st0/1/2 | `0x100 / 0x100 / 0x100` | `0 / 0 / 0` |
| `INTF1_CFG` | `0x80000000` | `0x00040000` |

结论：**屏幕、DSI PHY、面板、像素格式从头到尾都是好的。**

---

## 7. 第二个坑：写错了 framebuffer 格式

两个 fb 完全不同：

| | simpledrm（LK/工作路径） | msm fbdev（黑屏路径） |
|---|---|---|
| bpp | **24** | 16 (RG16/RGB565) |
| 分辨率 | 720×1520 | 720×1520 |
| stride/pitch | **2160** | 1472 |
| 总大小 | 3,283,200 B | 2,237,440 B |

之前一直按 16bpp 往 24bpp 的 fb 里写 —— 多轮"黑屏"**至少一半**是这个原因。

正确读法：

```sh
cat /sys/class/graphics/fb0/virtual_size    # 720,1520
cat /sys/class/graphics/fb0/bits_per_pixel  # 24
cat /sys/class/graphics/fb0/stride          # 2160
```

按正确格式写"上白下黑"，用户确认**完全吻合** → 链路彻底确认。

---

## 8. 如果以后要继续攻 msm

正确方向**不是**重建 pipeline，而是：

> diff 出 msm 改写的**全部** MDP 寄存器，让它保留 LK 的值，
> 只更新 SSPP 的 `SRC0_ADDR` / `SRC_YSTRIDE` 去扫描新 buffer（劫持 LK 流水线）。

需要的工具已经在 `drivers/mdppoke/`：

```
modprobe mdppoke                                    # 只观测
modprobe mdppoke pokes="6a804=80000000"             # 写（相对 MDP 基址 0x1a01000）
modprobe mdppoke physpokes="1a947b8=b"              # 写（绝对物理地址，如 PHY）
modprobe mdppoke dumps="1a94400:400"                # dump 任意区域
```

**踩坑**：`dumps=` 传错区域会 oops（`init_module+0x140`），模块卡在 refcnt=1 无法 rmmod，
只能重启。而且 msm 被 fbcon 占用时无法 rmmod，验证新模块一律走重启。
