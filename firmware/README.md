# Uno 固件

## 文件

| 文件 | 内容 | 能否直接编辑 |
|---|---|---|
| `controller_core.h` | 与硬件无关的控制逻辑：转换、滤波、消抖、模式、PID、保护、协议解析、帧格式化 | ✅（主机测试也用它） |
| `hardware_config.h` | **所有实物参数**的唯一位置（编码器、PID、舵机、电位器、IR 表、超声波、去抖、安全开关） | ✅ 最常改的文件 |
| `arduino_adapter.inc` | Uno 引脚、中断、PWM/STEP 输出、Servo、非阻塞串口 | ✅ |
| `generate_sketches.py` | 把上面三个文件拼接成可上传的单文件 sketch | — |
| `hardware_controller/hardware_controller.ino` | **生成的**上传文件 | ❌ 会被覆盖 |
| `legacy_tinkercad/` | 旧浏览器演示程序 | ❌ 不要上传 |
| `legacy_bench_sensor_test/` | 早期单传感器台架测试（MaxSonar PW→D2、开关→D4，与正式接线不同） | ❌ 完整接线时不要上传 |

改完源文件后：

```bash
python firmware/generate_sketches.py           # 重新生成
python firmware/generate_sketches.py --check   # 确认已同步（测试脚本也会检查）
```

上传：VS Code（Arduino Community Edition 扩展）或 Arduino IDE 打开 `hardware_controller/hardware_controller.ino`，板子选 Arduino Uno，端口选 COM5（或 `/dev/ttyACM0`）；或用命令行：

```bash
arduino-cli lib install Servo
arduino-cli compile --fqbn arduino:avr:uno firmware/hardware_controller
arduino-cli upload  --fqbn arduino:avr:uno -p COM5 firmware/hardware_controller
```

2026-11-09 编译结果（arduino:avr 1.8.8，Servo 1.3.0）：Flash 21 030 / 32 256 B（65%），全局 RAM 1 202 / 2 048 B（58%，余 846 B 给栈）。

## 运行时行为

| 周期 | 工作 |
|---|---|
| 每次 loop | 读串口命令（每次最多 48 字节）、DC 控制、PWM、舵机、STEP 脉冲、清空发送队列 |
| 20 ms | 读 A0/A1/A2（每路丢弃首次转换）、A3 槽型、A4 按钮 |
| 100 ms | 发送 `STATE` + `RAW`（同一时间戳） |
| 1000 ms | 发送 `CONFIG` |

- **非阻塞串口**：`Serial.print` 在 64 字节硬件缓冲满时会阻塞，影响 STEP 周期和 STOP 响应。现在所有输出先进 256 字节队列，按 `Serial.availableForWrite()` 逐步发送。队列不够时丢弃遥测帧（启动时和每秒一次以 `INFO,TELEMETRY_DROPPED` 报告），ACK 永不丢弃。
- **字符串放在 Flash**（`LAB_STR`/`PSTR`）以节省 RAM。
- **上电即 DISARMED**：步进 ENABLE 高、DC PWM 0、舵机不发脉冲。

## 安全与保护

| 条件 | 结果 | `fault` |
|---|---|---|
| `HARDWARE_CONFIG_VERIFIED = false` | ARM 被拒绝（`CONFIG_REQUIRED`） | — |
| 配置不自洽（如 IR 表不单调、滞回反向） | ARM 被拒绝（`CONFIG_INVALID`），启动时 INFO 报告具体项 | `CONFIG_INVALID` |
| 1.5 s 没有被接受的命令（ROS 每 0.5 s 发 PING） | STOP + 解除使能 | `WATCHDOG` |
| \|PWM\| ≥ 120 且编码器 1 s 无变化 | STOP + 解除使能 | `ENCODER_STALL` |
| \|PWM\| ≥ 120 且实测转向与输出相反 1 s | STOP + 解除使能 | `ENCODER_DIRECTION` |
| DC_MOVE 15 s 未到位 | DC 停止，仍保持使能 | `POSITION_TIMEOUT` |
| 模式切换（按钮或命令） | 取消 DC 运动和剩余步数，保持使能状态 | — |
| STOP | DC PWM 0、取消剩余步数、步进禁用、舵机停脉冲、解除使能 | — |

`fault` 显示自上次 ARM 以来最后一次**自动**停机的原因，再次 ARM 后清为 `NONE`。STOP 是软件停机，不切断电源。

## 传感器处理

| 传感器 | 转换 | 无效值 |
|---|---|---|
| 电位器 | `pot_pct` = ADC 在 [`POT_ADC_MIN`, `POT_ADC_MAX`] 中的比例；`pot_deg` = 比例 × `POT_TRAVEL_DEG` | `POT_TRAVEL_DEG = 0`（未测）时 `pot_deg = -1` |
| Sharp GP2Y0A02 | 分段线性插值表 → `ir_raw_cm`；连续 5 个有效样本滑动平均 → `ir_cm` | 高于 20 cm 点：`-2`（太近）；低于 150 cm 点：`-1`。无效样本清空滤波器，窗口未满时 `ir_cm = -1` |
| MaxSonar AN | 9 样本中值 × 1.27 cm/ADC | ≤ 约 16.5 cm：`-2`；ADC < 4（断线）或 > 645 cm：`-1` |
| 槽型 | 10 ms 去抖后的**新遮挡**计数一次 | — |
| 模式按钮 | 30 ms 去抖后的**按下沿**切换一次；按住不重复 | — |

传感器模式规则：电位器比例 → 舵机命令角度；IR 滤波值 < `IR_STOP_CM` 停、> `IR_START_CM` 以 `DC_SENSOR_RPM` 转，之间保持（无效/太近/滤波未满一律视为停）；新遮挡 → 步进转 90°，步进忙时该事件计入 `slot_ignored`，不排队。

**GP2Y0A02 的限制**：约 15 cm 以内输出电压会折返，与较远距离的电压相同，单个 ADC 值无法识别。固件只能识别「高于 20 cm 标定点的电压」为太近。

## 串口协议 v2（115200 baud，ASCII，LF 结尾）

```text
CMD,<seq>,<verb>,<value>
ACK,<seq>,OK|ERR,<reason>
STATE,ms,mode,pot_deg,pot_pct,ir_raw_cm,ir_cm,sonar_cm,slot_count,slot_ignored,servo_cmd_deg,
      dc_deg,dc_rpm,dc_target,dc_control,step_deg,step_target_deg,step_busy,armed,calibrated,fault   (21 字段)
RAW,ms,pot_adc,ir_adc,sonar_adc,slot_blocked,button_pressed,enc_counts,step_steps                 (9 字段)
CONFIG,protocol,servo_min_deg,servo_max_deg,servo_min_us,servo_max_us,max_rpm,sensor_rpm,
       dc_move_max_deg,step_move_max_deg,steps_per_rev,enc_cpr,enc_sign,pot_adc_min,pot_adc_max,
       pot_travel_deg,ir_stop_cm,ir_start_cm,sonar_cm_per_adc,hw_verified,cal_mask              (21 字段)
INFO,<detail>
```

- 命令：`ARM` `STOP` `MODE`(0=GUI, 1=SENSOR) `SERVO`(度) `DC_RPM` `DC_MOVE`(相对度) `STEP_MOVE`(相对度) `ZERO`(仅 DISARMED) `PING`。
- 序号必须递增；重复的最后一个序号只回原 ACK、不再执行（防止相对运动重复）；更旧的回 `STALE_SEQ`。
- `servo_cmd_deg` 是**命令值**；`step_deg` 是**已发步数推算**；`dc_deg`/`dc_rpm` 是**编码器实测**。位置模式下 `dc_target` 是内部绝对目标坐标。
- `enc_counts` 是原始 x4 计数，不受 CPR、符号、ZERO 影响，用于测 CPR。
- `cal_mask` 位：1 电位器、2 IR、4 超声波、8 编码器、16 舵机。`calibrated` = 全部位都置位。
- 手动调试（Serial Monitor，选 LF 结尾）：`CMD,1,PING,0`。注意 1.5 s 看门狗只在 ARM 后起作用。

协议字段改动必须同时改：`controller_core.h` 格式化函数、`protocol.py`、GUI、`tests/`，并把 `LAB_PROTOCOL_VERSION` 和 `PROTOCOL_VERSION` 一起加 1。
