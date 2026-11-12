# 旧的单传感器台架测试（历史资料）

`legacy_bench_sensor_test.ino` 是 2026-11-09 在接入完整固件之前，用来单独检查传感器的测试程序（原来放在 `Arduino/motor_sensor_lab/`，已并入本工程）。它每秒在 Serial Monitor 打印一次可读的文字报告：

- MaxSonar **PW（脉宽）输出 → D2**，每秒 10 个样本取中值
- Sharp GP2Y0A02 → A1，表格插值和平均
- Omron D3C 微动开关 → **D4**（COM 接 GND，内部上拉，20 ms 去抖）

## ⚠️ 引脚和正式接线不同

| | 本测试程序 | 正式接线（[hardware/WIRING.md](../../hardware/WIRING.md)） |
|---|---|---|
| MaxSonar | PW → D2 | **AN → A2** |
| D3C 开关 | D4 | **A4** |
| D2 / D4 | 传感器输入 | 编码器 A 相 / DC 驱动方向脚 |

**不要在完整接线（尤其是电机驱动已接上、台式电源打开）时上传这个程序**：它不会控制 D5/D7 等电机引脚，驱动板输入可能处于悬空状态。只在面包板上只接这三个传感器时使用。

正式固件已经通过 `RAW` 帧提供所有传感器的原始量，`calibration/capture.py` 可以直接采集，一般不再需要这个程序。
