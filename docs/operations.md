# 运维：备份、回滚、灾难恢复

这套配置是十几轮试错换来的，散落在 systemd unit、`/usr/local/bin`、内核模块和 DTB 里。
一次 `apt upgrade` 或误改就可能全部白费 —— 所以先建立回退能力，再动任何东西。

---

## 1. 全量配置备份

```sh
backup-redmi8a.sh
```

产出 `/root/redmi8a-backup/redmi8a-config-<时间戳>.tar.gz` + `.sha256`，自动保留最近 5 份。

打包内容：

- `/etc/systemd/system`（含 `.d` 覆盖）
- `/etc/modprobe.d`、`/etc/nftables.conf`、`/etc/X11`、apt 源
- `/usr/local/bin` 全部脚本、`/root/vnc-terminal.sh`、`/root/.vnc`
- `wcn36xx` 模块备份、`msm.ko.zst`、olive 面板模块
- `MANIFEST.txt`：内核 cmdline、显示链路说明、VNC 结论、dpkg 包列表、nft ruleset、
  fb0/X 状态、完整文件清单

**注意**：归档里含 `/root/.vnc`（VNC 密码）—— 如果要上传或分享，记得先剔除。

## 2. 恢复

```sh
restore-redmi8a.sh /root/redmi8a-backup/redmi8a-config-XXXX.tar.gz
```

流程：校验 sha256 → 解包覆盖 → `daemon-reload` → 重新 enable → 重启显示栈。
内核版本与备份不一致时会告警（模块路径可能对不上）。

恢复后**建议重启**，因为 LK 遗留的显示流水线只有重启才能重新建立。

---

## 3. DTB 实验的安全网

改 DTB 是唯一可能让设备直接起不来的操作。三层保护：

### ① 改之前备份原文件

```sh
/root/dtb-backup/sdm439-xiaomi-olive.dtb.pre-<时间戳>
/root/dtb-backup/extlinux.conf.pre-<时间戳>
/root/dtb-backup/INFO-<时间戳>.txt     # 校验和
```

### ② 一键回退

```sh
rollback-dtb.sh            # 只恢复文件
rollback-dtb.sh --reboot   # 恢复并重启
```

恢复后会打印新旧 sha256 供核对。

### ③ 自动守卫（防"改了起不来又没法远程回滚"）

```sh
systemctl enable --now dtb-guard.service    # 只应在实验期间启用
```

启动后 600 秒内如果没有：

```sh
touch /root/.dtb-confirmed
```

就自动 `rollback-dtb.sh` + 重启。**实验确认成功后务必停用它并留下确认标记**，否则
以后每次重启 10 分钟后都会被回滚一次。

---

## 4. 灾难恢复顺序

设备完全不响应时，按这个顺序试：

| 症状 | 处理 |
|---|---|
| SSH 不通，但屏幕有画面 | 接 USB 键盘，本地 console 登录；或拔电重启 |
| 屏幕全黑，SSH 通 | 检查 `bl_lm3697` 是否被卸载/解绑 → 重新 bind + `ktd3137-bl 1400` |
| 屏幕全黑，SSH 不通 | 长按电源键 ~10 s（PMIC PON 硬件复位，绕开 OS） |
| 重启后卡住不进系统 | 串口 console（`add-serial-console.sh` 可加），或从 `resin` 键进 bootloader 换 DTB |
| DTB 改坏了 | 用 `dtb-guard` 自动回滚；或从 bootloader 用备份文件覆盖 `/boot/*.dtb` |

---

## 5. 不要做的事（重复强调）

| 操作 | 后果 |
|---|---|
| `modprobe msm` | 改写 MDP 寄存器 → 屏幕黑，只能重启 |
| `rmmod bl_lm3697` / unbind `<bus>-0036` | HWEN 拉低 → 背光芯片断电 → 黑屏 |
| `echo 1 > /sys/class/graphics/fb0/blank` 再回 0 | DSI 链路被破坏，`prepare()` 报 `-22`，随后 oops |
| 给触控 IC 发 `0x69` | 复位整颗 TDDI，连带 LCD 黑屏 |
| 手动 `rmmod msm` | msm 被 fbcon 占用，会拆到一半卡死（`Used by -1`），只能重启 |

---

## 6. 健康自检

一条命令看全状态：

```sh
bash scripts/display/check-mirror.py     # fb0 与 X 画面是否一致
systemctl --failed                       # 失败单元应为 0
cat /sys/class/graphics/fb0/blank        # 应为 0
i2cget -y -f <bus> 0x36 0x02             # 应为 0x99（背光使能）
DISPLAY=:1 xdpyinfo | grep dimensions    # 应为 1520x720 pixels
```

正常时的参考值：

```
冷启动          ~11 s
服务            8 个 active，失败单元 0
fbmirror CPU    9~10%（静止更低）
fb0 一致性      差异 < 0.1%（采样瞬间光标/时钟刷新）
```
