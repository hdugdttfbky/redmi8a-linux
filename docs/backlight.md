# 背光：KTD3137（不是 DT 里写的 LM3697）

## 决定性发现

设备树里 `blsp2_i2c1` 那段写的是 `ti,lm3697`，`enable-gpios = <&pm8953_gpios 4>`。
但实测 0x36 上的芯片**不是 LM3697**：

- `0x00` 读回 **`0x18`**
- 寄存器只有 `0x00`–`0x0A`，LM3697 的 `0x10/0x20/0x21/0x24` 在这颗芯片上根本不存在（写入不生效）
- 对照 Kinetic 数据手册：**Device ID `0x18` = KTD3137（DEV_ID_B）**

DT 里那句被忽略的注释 `/* ktd3137@36 */` 其实早就写明了。

## 寄存器表

| 寄存器 | 含义 |
|---|---|
| `0x00` | DEV_ID，KTD3137 = `0x18` |
| `0x01` | SW_RESET |
| `0x02` | MODE：bit0 = **BL_EN**，bit[7:3] = 满量程电流档 |
| `0x03` | CONTROL |
| `0x04` | 亮度 ratio LSB（低 3 位） |
| `0x05` | 亮度 ratio MSB（高 8 位） |
| `0x0A` | STATUS |

- 亮度是 **11 位**（`0`–`2047`）：`value = (msb << 3) | (lsb & 0x07)`
- **必须先写 `0x04`（LSB）再写 `0x05`（MSB）**
- 电流档 `10011` = 20.2 mA → `0x02 = 0x99`（BL_EN=1）或 `0x98`（BL_EN=0，保留电流档）

出厂默认 `0x02 = 0x98`，即 **BL_EN=0，背光从未使能** —— 这就是"全链路正常、屏幕全黑"的真正原因。

## 供电前提：PM8953 GPIO4 (HWEN)

KTD3137 的硬件使能挂在 PM8953 GPIO4 上，由 `bl_lm3697` 驱动拉高。
那个驱动唯一的用处就是这个（它写 LM3697 寄存器是无效的）。

### ⚠️ 绝对不要做的事

```sh
rmmod bl_lm3697              # lm3697_remove 会把 HWEN 拉低 → 芯片断电 → 0x36 直接 NACK
echo 1-0036 > .../lm3697/unbind   # 同上
```

一旦断电，`i2cget` 立刻 `Read failed`，`0x02` 复位回 `0x98`，屏幕瞬灭。
抢救方法：重新 bind 回 `1-0036`，再跑 `ktd3137-bl <亮度>`。

（早期一版 `screen-toggle.py` 正是用 unbind 关屏的，结果每次按键都在冒险，
最后停在"驱动绑着、BL_EN=0"的假开机态 → 黑屏。现在的实现只读写寄存器。）

## 工具

```sh
/usr/local/bin/ktd3137-bl 1400     # 0..2047
```

脚本会**自动探测 0x36 在哪条 i2c 总线**（原因见下）。

## 为什么必须自动探测总线

把 `spi@78b7000` 从 i2c 切成 spi 之后，i2c 控制器编号会重排：`1-0036` → `0-0036`。
所有硬编码 `BUS=1` 的脚本（`ktd3137-bl`、`bl-guard.sh`、`screen-toggle.py`）当场失效，
表现为"背光服务全部失败"。

现在三个脚本都改成遍历 `/dev/i2c-0..5`，谁在 0x36 应答就用谁 —— **新旧 DTB 都兼容**。

## 守护层：bl-guard

`bl-guard.sh` 由 `bl-guard.timer` 每 15 秒触发一次，检查 `0x00` 是否为 `0x18`：

- 是 → 直接 `exit 0`，开销可忽略
- 否 → 重绑 `<bus>-0036`（只拉高 HWEN，绝不 unbind）→ 再不行 `modprobe bl_lm3697`
  → 最后按 `/run/screen-toggle.power` 恢复原状态（该亮就亮、该灭保持灭）

恢复亮度取 `/run/screen-toggle.brightness`，非法值回落 1400。

## 电源键 = 开关屏

链路由 `pm8941_pwrkey` → `event0`（`KEY_POWER=116`）→ `screen-toggle.py --daemon`：

- 关屏：`0x02 = 0x98`（保留电流档）
- 开屏：先恢复 `0x04/0x05`，再 `0x02 = 0x99`
- **不碰 framebuffer**，所以开屏后画面原样恢复

另外 `/etc/systemd/logind.conf.d/10-powerkey.conf` 把
`HandlePowerKey/SuspendKey/HibernateKey/LidSwitch/PowerKeyLongPress` 全设为 `ignore`，
否则短按会走 logind 的关机/挂起流程。

长按约 10 秒是 **PMIC PON 硬件复位**，绕开 OS，软件无法也不应该禁用。

## 关于"屏幕慢慢变暗"

静态纯白画面下屏幕会逐渐变暗，这是面板的 **CABC（内容自适应背光）** 在降电流，
属正常行为，不是背光掉了也不是信号断了。init 序列里有 `0x55 0x80`、`0x53 0x2c` 与之相关。
