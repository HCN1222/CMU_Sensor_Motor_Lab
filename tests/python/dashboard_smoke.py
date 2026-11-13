"""Offscreen Qt smoke test of the real DashboardWidget.

Uses the real python_qt_binding (as installed with ROS 2 / RoboStack) when it is
importable, otherwise PySide6. Only absent ROS/rqt modules are stubbed. This is
NOT a ROS 2 runtime test; see tests/ros/ros_graph_check.py for that.
Usage: PYTHONPATH=ros2_ws/src/sensor_motor_lab python dashboard_smoke.py [png]
"""
import csv
import io
import os
import sys
import time
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from python_qt_binding import QtWidgets
    binding = 'python_qt_binding'
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    shim = types.ModuleType('python_qt_binding')
    sys.modules['python_qt_binding'] = shim
    for name, module in (('QtCore', QtCore), ('QtGui', QtGui), ('QtWidgets', QtWidgets)):
        sys.modules['python_qt_binding.' + name] = module
    binding = 'PySide6'

from sensor_motor_lab.dashboard import DashboardWidget, csv_columns  # noqa: E402
from sensor_motor_lab.protocol import parse_line  # noqa: E402

CONFIG = 'CONFIG,2,0.0,60.0,1200,1800,30.0,20.0,1080.0,1080.0,200.0,360.0,1,0,1023,0.0,35.0,45.0,1.270,1,0'
STATE = 'STATE,1000,0,-1,50.0,40,39.5,100,3,1,30,45,-12,20,RPM,-90,-90,0,0,0,NONE'

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
commands = []
widget = DashboardWidget(commands.append)
widget.resize(1100, 1000)
widget.show()
app.processEvents()
assert not widget.arm.isEnabled()
assert not any(w.isEnabled() for w in widget.motion_controls)

state = parse_line(STATE).as_dict()
widget.receive_state(state)
assert not widget.arm.isEnabled(), 'ARM must stay disabled until CONFIG says hardware is verified'
config = parse_line(CONFIG).as_dict()
widget.receive_config(config)
assert widget.spins['SERVO'].maximum() == 60 and widget.spins['DC_RPM'].minimum() == -30, 'GUI ranges follow firmware CONFIG'
assert 'PROVISIONAL' in widget.calibration.text()
widget.receive_state(state)
assert widget.arm.isEnabled()
widget.arm.click()
assert commands[-1] == {'verb': 'ARM', 'value': 0.0}
state['armed'] = True
widget.receive_state(state)
assert all(w.isEnabled() for w in widget.motion_controls)
widget.spins['SERVO'].setValue(45)
widget.motion_controls[1].click()
assert commands[-1] == {'verb': 'SERVO', 'value': 45.0}
widget.spins['STEP_MOVE'].setValue(91)
assert '51 whole steps' in widget.step_preview.text() and '91.80' in widget.step_preview.text()
assert 'not calibrated' in widget.values['pot'].text()
state['mode'] = 1
widget.receive_state(state)
assert not any(w.isEnabled() for w in widget.motion_controls)
widget.stop.click()
assert commands[-1] == {'verb': 'STOP', 'value': 0.0}
state['mode'] = 0
state['ir_cm'] = -2.0
state['fault'] = 'ENCODER_STALL'
widget.receive_state(state)
assert 'TOO CLOSE' in widget.values['ir'].text()
assert 'ENCODER_STALL' in widget.fault.text()
state['fault'] = 'NONE'
for index in range(40):
    state['ir_raw_cm'] = 40 + (index % 3 - 1) * 1.5
    state['ir_cm'] = 40 + (index % 3 - 1) * 0.25
    state['sonar_cm'] = 100 + (index % 2)
    widget.receive_state(state)
raw = dict(ms=1000, pot_adc=512, ir_adc=287, sonar_adc=79, slot_blocked=False, button_pressed=False,
           enc_counts=100, step_steps=-50)
widget.receive_raw(raw)
widget.mark_encoder()
widget.receive_raw(dict(raw, enc_counts=460))
assert 'since mark: +360' in widget.encoder_label.text() and '+1.000 rev' in widget.encoder_label.text()
# Log only matching STATE/RAW timestamps, once each; do not mix nearby samples.
log = io.StringIO()
widget.log_file = log
widget.log_writer = csv.DictWriter(log, csv_columns())
widget.log_writer.writeheader()
widget.write_log_row()
widget.write_log_row()
assert len(log.getvalue().splitlines()) == 2
widget.receive_raw(dict(raw, ms=1100, slot_blocked=True))
assert len(log.getvalue().splitlines()) == 2
state['ms'] = 1100
widget.receive_state(state)
assert len(log.getvalue().splitlines()) == 3
header = log.getvalue().splitlines()[0].split(',')
assert 'raw_enc_counts' in header and 'fault' in header and 'step_target_deg' in header
widget.log_file = widget.log_writer = None
# Spread synthetic samples in time for a readable preview without real-time waits.
end = time.monotonic()
for plot in (widget.ir_plot, widget.sonar_plot, widget.dc_plot):
    existing = list(plot.samples)
    plot.samples.clear()
    for index, (_, a, b) in enumerate(existing):
        plot.samples.append((end - (len(existing) - 1 - index) * 0.1, a, b))
widget.event_label.setText('UI PREVIEW — synthetic telemetry. ROS 2 runtime and physical hardware are not tested here.')
app.processEvents()
if len(sys.argv) > 1:
    assert widget.grab().save(sys.argv[1])
widget.last_received -= 2
widget.refresh_enabled()
assert not widget.arm.isEnabled()
assert not any(w.isEnabled() for w in widget.motion_controls)
widget.shutdown()
widget.close()
print(f'Qt offscreen smoke passed ({binding}): CONFIG-driven ranges, ARM gate, interlocks, sentinels, '
      'step rounding preview, encoder CPR helper, stale telemetry, timestamp-matched CSV logging.')
