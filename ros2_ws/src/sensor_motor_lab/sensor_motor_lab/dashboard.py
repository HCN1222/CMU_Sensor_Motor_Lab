"""rqt plugin: real ROS topics, explicit commands, and Qt-native live plots."""
from collections import deque
import csv
import json
import time

from python_qt_binding.QtCore import QPointF, QTimer, Signal
from python_qt_binding.QtGui import QColor, QPainter, QPen
from python_qt_binding.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .protocol import CALIBRATION_BITS, LIMITS, TOO_CLOSE, Config, Raw, State, validate_command

STALE_S = 1.5
MOTION = (
    # verb, label, initial value
    ('SERVO', 'Servo target — commanded angle (deg)', None),
    ('DC_RPM', 'DC speed — signed RPM (encoder closed loop)', 10),
    ('DC_MOVE', 'DC relative move — signed deg (encoder closed loop)', 90),
    ('STEP_MOVE', 'Stepper relative move — signed deg (open loop)', 90),
)


def distance_text(value):
    if value == TOO_CLOSE:
        return 'TOO CLOSE (below min range)'
    if value < 0:
        return 'NO VALID READING'
    return f'{value:.1f} cm'


def plot_value(value):
    return value if value >= 0 else None


class TracePlot(QWidget):
    def __init__(self, title, first, second=None, parent=None):
        super().__init__(parent)
        self.title, self.first, self.second = title, first, second
        self.samples = deque(maxlen=300)
        self.setMinimumSize(300, 170)

    def add(self, first, second=None):
        self.samples.append((time.monotonic(), first, second))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#ffffff'))
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor('#1f2937'))
        painter.drawText(12, 20, self.title)
        painter.setPen(QColor('#d97706'))
        painter.drawText(12, 38, self.first)
        if self.second:
            painter.setPen(QColor('#2563eb'))
            painter.drawText(160, 38, self.second)
        left, top = 48.0, 52.0
        width, height = max(1, self.width() - 62.0), max(1, self.height() - 78.0)
        painter.setPen(QColor('#9ca3af'))
        painter.drawLine(QPointF(left, top), QPointF(left, top + height))
        painter.drawLine(QPointF(left, top + height), QPointF(left + width, top + height))
        if len(self.samples) < 2:
            painter.drawText(65, 90, 'Waiting for live telemetry')
            return
        end = self.samples[-1][0]
        start = max(self.samples[0][0], end - 20.0)
        samples = [row for row in self.samples if row[0] >= start]
        values = [v for _, a, b in samples for v in (a, b) if v is not None]
        if not values:
            painter.drawText(65, 90, 'No valid readings in the last 20 s')
            return
        low, high = min(values), max(values)
        margin = max((high - low) * 0.12, 0.5)
        low -= margin
        high += margin
        painter.drawText(2, int(top + 5), f'{high:.1f}')
        painter.drawText(2, int(top + height), f'{low:.1f}')
        painter.drawText(int(left), self.height() - 7, f'{start - end:.1f} s')
        painter.drawText(int(left + width - 25), self.height() - 7, '0 s')
        span = max(end - start, 0.1)
        for column, color in ((1, '#d97706'), (2, '#2563eb')):
            painter.setPen(QPen(QColor(color), 2))
            previous = None
            for row in samples:
                value = row[column]
                if value is None:
                    previous = None
                    continue
                point = QPointF(left + width * (row[0] - start) / span,
                                top + height * (high - value) / (high - low))
                if previous is not None:
                    painter.drawLine(previous, point)
                previous = point


class DashboardWidget(QWidget):
    state_signal = Signal(object)
    raw_signal = Signal(object)
    event_signal = Signal(object)
    config_signal = Signal(object)

    def __init__(self, publish):
        super().__init__()
        self.publish = publish
        self.state = None
        self.raw = {}
        self.config = None
        self.last_received = 0.0
        self.log_file = None
        self.log_writer = None
        self.last_logged_ms = None
        self.encoder_mark = None
        self.motion_controls = []
        self.spins = {}
        self.setWindowTitle('Sensors & Motor Control Lab')
        root = QVBoxLayout(self)
        self.connection = QLabel('Waiting for /lab/state — outputs start disarmed')
        self.connection.setStyleSheet('font-weight: bold;')
        self.calibration = QLabel('Waiting for firmware CONFIG (limits and calibration status)')
        self.calibration.setWordWrap(True)
        self.calibration.setStyleSheet('color: #92400e; font-weight: bold;')
        self.fault = QLabel('')
        self.fault.setStyleSheet('color: #b91c1c; font-weight: bold;')
        for label in (self.connection, self.calibration, self.fault):
            root.addWidget(label)

        toolbar = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['GUI control', 'Sensor control'])
        self.mode.activated.connect(lambda index: self.send('MODE', index))
        self.arm = QPushButton('ARM outputs')
        self.arm.clicked.connect(lambda: self.send('ARM', 0))
        self.stop = QPushButton('STOP / DISARM')
        self.stop.setStyleSheet('background: #b91c1c; color: white; font-weight: bold;')
        self.stop.clicked.connect(lambda: self.send('STOP', 0))
        self.zero = QPushButton('Zero motor coordinates')
        self.zero.clicked.connect(lambda: self.send('ZERO', 0))
        for control in (self.mode, self.arm, self.stop, self.zero):
            toolbar.addWidget(control)
        root.addLayout(toolbar)

        controls = QGroupBox('GUI commands — each click sends exactly one command')
        grid = QGridLayout(controls)
        for row, (verb, title, initial) in enumerate(MOTION):
            self.add_command(grid, row, title, verb, initial)
        self.step_preview = QLabel('')
        grid.addWidget(self.step_preview, len(MOTION), 0, 1, 3)
        self.spins['STEP_MOVE'].valueChanged.connect(self.update_step_preview)
        self.range_note = QLabel('Ranges come from the firmware CONFIG frame; controls stay disabled until it arrives.')
        self.range_note.setWordWrap(True)
        root.addWidget(controls)
        root.addWidget(self.range_note)

        sensors = QGroupBox('Live sensors and motors')
        grid = QGridLayout(sensors)
        rows = (
            ('pot', 'Potentiometer (A0)'),
            ('ir', 'Sharp IR GP2Y0A02 (A1): raw → filtered'),
            ('sonar', 'MaxSonar EZ0 AN (A2), median filtered'),
            ('slot', 'Slot sensor EE-SX1042 (A3)'),
            ('servo', 'Servo — COMMANDED angle (no feedback)'),
            ('dc', 'DC motor — encoder MEASURED'),
            ('dc_target', 'DC target'),
            ('step', 'Stepper — from STEP pulses sent (open loop)'),
        )
        self.values = {}
        for row, (key, title) in enumerate(rows):
            grid.addWidget(QLabel(title), row, 0)
            self.values[key] = QLabel('—')
            grid.addWidget(self.values[key], row, 1)
        root.addWidget(sensors)

        encoder = QGroupBox('Encoder CPR helper — while DISARMED: Mark, turn the output shaft exactly one turn '
                            'by hand, |since mark| = counts/rev')
        row = QHBoxLayout(encoder)
        self.encoder_label = QLabel('Raw x4 count: —')
        self.mark = QPushButton('Mark count')
        self.mark.clicked.connect(self.mark_encoder)
        row.addWidget(self.encoder_label)
        row.addWidget(self.mark)
        root.addWidget(encoder)
        self.raw_label = QLabel('Raw inputs: waiting for /lab/raw')
        root.addWidget(self.raw_label)

        plots = QHBoxLayout()
        self.ir_plot = TracePlot('IR distance (cm)', 'Before filter', 'After filter')
        self.sonar_plot = TracePlot('Ultrasonic distance (cm)', 'Median filtered')
        self.dc_plot = TracePlot('DC speed (RPM)', 'Encoder measured', 'Target (RPM mode)')
        for plot in (self.ir_plot, self.sonar_plot, self.dc_plot):
            plots.addWidget(plot)
        root.addLayout(plots)
        self.log = QPushButton('Record telemetry CSV…')
        self.log.clicked.connect(self.toggle_log)
        root.addWidget(self.log)
        self.event_label = QLabel('Connect bridge, choose mode, then ARM. ZERO requires disarmed outputs.')
        self.event_label.setWordWrap(True)
        root.addWidget(self.event_label)
        self.state_signal.connect(self.receive_state)
        self.raw_signal.connect(self.receive_raw)
        self.event_signal.connect(self.receive_event)
        self.config_signal.connect(self.receive_config)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_enabled)
        self.timer.start(100)
        self.refresh_enabled()

    # ---- commands -------------------------------------------------------------
    def add_command(self, grid, row, title, verb, initial):
        spin = QDoubleSpinBox()
        spin.setRange(*LIMITS[verb])
        spin.setDecimals(1)
        if initial is not None:
            spin.setValue(initial)
        button = QPushButton('Send')
        button.clicked.connect(lambda: self.send(verb, spin.value()))
        grid.addWidget(QLabel(title), row, 0)
        grid.addWidget(spin, row, 1)
        grid.addWidget(button, row, 2)
        self.spins[verb] = spin
        self.motion_controls.extend([spin, button])

    def send(self, verb, value):
        try:
            limits = Config(**self.config).limits() if self.config else None
            verb, value = validate_command(verb, value, limits)
            self.publish(dict(verb=verb, value=value))
            self.event_label.setText(f'Sent request {verb} {value:g}; waiting for controller ACK.')
        except ValueError as exc:
            self.event_label.setText(str(exc))

    def update_step_preview(self):
        if not self.config:
            self.step_preview.setText('')
            return
        per_step = 360.0 / self.config['steps_per_rev']
        requested = self.spins['STEP_MOVE'].value()
        steps = int(requested / per_step + (0.5 if requested >= 0 else -0.5))
        self.step_preview.setText(
            f'Stepper: {requested:g}° → {steps} whole steps → {steps * per_step:.2f}° actually commanded '
            f'({per_step:g}°/step). Busy stepper rejects new moves (BUSY_OR_LIMIT).')

    def mark_encoder(self):
        if self.raw:
            self.encoder_mark = self.raw['enc_counts']
            self.receive_raw(self.raw)

    # ---- incoming data ----------------------------------------------------------
    def receive_config(self, config):
        self.config = config
        for verb, (low, high) in Config(**config).limits().items():
            spin = self.spins[verb]
            spin.setRange(low, high)
        if self.spins['SERVO'].value() == self.spins['SERVO'].minimum() and self.state is None:
            self.spins['SERVO'].setValue((config['servo_min_deg'] + config['servo_max_deg']) / 2)
        self.range_note.setText(
            f"Firmware limits: servo {config['servo_min_deg']:g}–{config['servo_max_deg']:g}° "
            f"({config['servo_min_us']}–{config['servo_max_us']} µs), DC ±{config['max_rpm']:g} RPM, "
            f"DC move ±{config['dc_move_max_deg']:g}°, stepper ±{config['step_move_max_deg']:g}°. "
            f"Sensor rule: IR stop < {config['ir_stop_cm']:g} cm, restart > {config['ir_start_cm']:g} cm, "
            f"{config['sensor_rpm']:g} RPM.")
        missing = [name for name, bit in CALIBRATION_BITS.items() if not config['cal_mask'] & bit]
        lines = []
        if not config['hw_verified']:
            lines.append('ARM DISABLED: hardware_config.h has HARDWARE_CONFIG_VERIFIED = false.')
        lines.append('All subsystems calibrated with measured data.' if not missing else
                     'PROVISIONAL (not measured): ' + ', '.join(missing) + '.')
        self.calibration.setText(' '.join(lines))
        self.calibration.setStyleSheet('color: %s; font-weight: bold;' % ('#065f46' if not missing and config['hw_verified'] else '#92400e'))
        self.update_step_preview()
        self.refresh_enabled()

    def receive_state(self, state):
        self.state = state
        self.last_received = time.monotonic()
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(int(state['mode']))
        self.mode.blockSignals(False)
        pot = f"{state['pot_pct']:.1f} % of ADC span"
        pot = (f"{state['pot_deg']:.1f}° ({pot})" if state['pot_deg'] >= 0
               else f'{pot} — angle not calibrated (POT_TRAVEL_DEG = 0)')
        self.values['pot'].setText(pot)
        self.values['ir'].setText(f"{distance_text(state['ir_raw_cm'])} → {distance_text(state['ir_cm'])}")
        self.values['sonar'].setText(distance_text(state['sonar_cm']))
        blocked = self.raw.get('slot_blocked') if self.raw else None
        self.values['slot'].setText(
            f"{state['slot_count']} obstruction events, {state['slot_ignored']} ignored (stepper busy)"
            + ('' if blocked is None else f" · now {'BLOCKED' if blocked else 'clear'}"))
        self.values['servo'].setText(f"{state['servo_cmd_deg']:.1f}°")
        self.values['dc'].setText(f"{state['dc_deg']:.1f}°, {state['dc_rpm']:.1f} RPM")
        if state['dc_control'] == 'RPM':
            self.values['dc_target'].setText(f"{state['dc_target']:.1f} RPM (speed mode)")
        else:
            remaining = state['dc_target'] - state['dc_deg']
            self.values['dc_target'].setText(
                f"{state['dc_target']:.1f}° absolute target, {remaining:+.1f}° remaining (position mode)")
        self.values['step'].setText(
            f"{state['step_deg']:.2f}° done → target {state['step_target_deg']:.2f}°"
            + (' · MOVING' if state['step_busy'] else ' · idle'))
        self.fault.setText('' if state['fault'] == 'NONE' else
                           f"Last automatic stop: {state['fault']} — check the motor/encoder, then ARM again.")
        self.ir_plot.add(plot_value(state['ir_raw_cm']), plot_value(state['ir_cm']))
        self.sonar_plot.add(plot_value(state['sonar_cm']))
        self.dc_plot.add(state['dc_rpm'], state['dc_target'] if state['dc_control'] == 'RPM' else None)
        self.write_log_row()
        self.refresh_enabled()

    def receive_raw(self, raw):
        self.raw = raw
        self.raw_label.setText(
            f"Raw inputs · Pot ADC {raw['pot_adc']} · IR ADC {raw['ir_adc']} · Sonar ADC {raw['sonar_adc']}"
            f" · Slot {'BLOCKED' if raw['slot_blocked'] else 'clear'}"
            f" · Button {'pressed' if raw['button_pressed'] else 'released'}"
            f" · Stepper {raw['step_steps']} steps")
        text = f"Raw x4 count: {raw['enc_counts']}"
        if self.encoder_mark is not None:
            delta = raw['enc_counts'] - self.encoder_mark
            text += f" · since mark: {delta:+d}"
            if self.config:
                text += (f" (= {delta / self.config['enc_cpr']:+.3f} rev at configured "
                         f"{self.config['enc_cpr']:g} counts/rev)")
        self.encoder_label.setText(text)
        self.write_log_row()

    def write_log_row(self):
        # Pair data by the controller timestamp, never silently mix adjacent samples.
        if (self.log_writer and self.state and self.raw
                and self.state['ms'] == self.raw['ms']
                and self.state['ms'] != self.last_logged_ms):
            self.log_writer.writerow(dict(host_monotonic_s=self.last_received, **self.state,
                **{('raw_' + key): value for key, value in self.raw.items()}))
            self.log_file.flush()
            self.last_logged_ms = self.state['ms']

    def receive_event(self, event):
        kind = event.get('kind', '')
        if kind == 'ack':
            self.event_label.setText(
                f"{event['verb']} #{event['seq']}: {'OK' if event['ok'] else 'REJECTED'} — {event['reason']}"
                + (f" ({ACK_HELP[event['reason']]})" if event['reason'] in ACK_HELP else ''))
        elif kind == 'disconnected':
            self.config = None
            self.event_label.setText(f"disconnected: {event.get('detail', '')}")
        elif kind not in ('sent', 'config'):
            self.event_label.setText(f"{kind}: {event.get('detail', '')}")

    def refresh_enabled(self):
        fresh = self.state is not None and time.monotonic() - self.last_received < STALE_S
        armed = fresh and self.state['armed']
        gui = fresh and self.state['mode'] == 0
        verified = bool(self.config and self.config['hw_verified'])
        self.mode.setEnabled(fresh)
        self.arm.setEnabled(fresh and not armed and verified)
        self.zero.setEnabled(fresh and not armed)
        self.mark.setEnabled(fresh and bool(self.raw))
        for widget in self.motion_controls:
            widget.setEnabled(bool(fresh and armed and gui and self.config))
        if fresh:
            self.connection.setText(
                f"LIVE · {'ARMED' if armed else 'DISARMED'} · {'GUI' if gui else 'SENSOR'} control")
        else:
            self.connection.setText('NO FRESH TELEMETRY — controls disabled; check bridge and serial connection')

    def toggle_log(self):
        if self.log_file:
            self.log_file.close()
            self.log_file = self.log_writer = None
            self.log.setText('Record telemetry CSV…')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Record telemetry', 'lab_telemetry.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            self.log_file = open(path, 'w', newline='', encoding='utf-8')
            self.log_writer = csv.DictWriter(self.log_file, csv_columns())
            self.log_writer.writeheader()
            self.last_logged_ms = None
        except OSError as exc:
            self.event_label.setText(f'Cannot open log: {exc}')
            self.log_file = self.log_writer = None
            return
        self.log.setText('Stop recording telemetry')

    def shutdown(self):
        self.timer.stop()
        if self.log_file:
            self.log_file.close()


ACK_HELP = {
    'CONFIG_REQUIRED': 'set HARDWARE_CONFIG_VERIFIED in firmware/hardware_config.h after checking wiring',
    'CONFIG_INVALID': 'hardware_config.h values are inconsistent; see the INFO line at boot',
    'DISARMED': 'press ARM first',
    'SENSOR_MODE': 'switch to GUI mode for manual motion',
    'BUSY_OR_LIMIT': 'stepper still moving; wait or STOP',
    'RANGE': 'outside the firmware limits',
    'DISARM_FIRST': 'STOP before zeroing',
    'STALE_SEQ': 'restart the bridge or reset the Uno',
}


def csv_columns():
    return ['host_monotonic_s', *State.__dataclass_fields__, *['raw_' + key for key in Raw.__dataclass_fields__]]


try:  # rqt is only needed for the plugin wrapper; DashboardWidget works without it.
    from rqt_gui_py.plugin import Plugin
except ImportError:  # pragma: no cover - exercised only on machines without rqt
    Plugin = object


class LabDashboard(Plugin):
    def __init__(self, context):
        super().__init__(context)
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from std_msgs.msg import String
        self.String = String
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        self.setObjectName('LabDashboard')
        self.node = context.node
        self.publisher = self.node.create_publisher(String, '/lab/command', 10)
        self.alive_publisher = self.node.create_publisher(String, '/lab/operator_alive', 10)
        self.widget = DashboardWidget(self.publish_command)
        self.alive_timer = QTimer(self.widget)
        self.alive_timer.timeout.connect(self.send_alive)
        self.alive_timer.start(500)
        self.subs = [
            self.node.create_subscription(String, '/lab/state', self.on_state, 10),
            self.node.create_subscription(String, '/lab/raw', self.on_raw, 10),
            self.node.create_subscription(String, '/lab/event', self.on_event, 10),
            self.node.create_subscription(String, '/lab/config', self.on_config, latched),
        ]
        if context.serial_number() > 1:
            self.widget.setWindowTitle(self.widget.windowTitle() + f' ({context.serial_number()})')
        context.add_widget(self.widget)

    def publish_command(self, command):
        self.publisher.publish(self.String(data=json.dumps(command, allow_nan=False)))

    def send_alive(self):
        if self.widget.state is not None and time.monotonic() - self.widget.last_received < STALE_S:
            self.alive_publisher.publish(self.String(data='alive'))

    def _emit(self, message, fields, signal, kind):
        try:
            data = json.loads(message.data)
            if not isinstance(data, dict) or set(data) != set(fields):
                raise ValueError(f'{kind} fields do not match the protocol; rebuild bridge and GUI together')
            signal.emit(data)
        except (ValueError, TypeError) as exc:
            self.widget.event_signal.emit(dict(kind='invalid_' + kind, detail=str(exc)))

    def on_state(self, message):
        self._emit(message, State.__dataclass_fields__, self.widget.state_signal, 'state')

    def on_raw(self, message):
        self._emit(message, Raw.__dataclass_fields__, self.widget.raw_signal, 'raw')

    def on_config(self, message):
        self._emit(message, Config.__dataclass_fields__, self.widget.config_signal, 'config')

    def on_event(self, message):
        try:
            self.widget.event_signal.emit(json.loads(message.data))
        except ValueError:
            pass

    def shutdown_plugin(self):
        # rqt unload requests STOP; the firmware watchdog is the fallback if ROS is gone.
        self.publish_command(dict(verb='STOP', value=0))
        self.alive_timer.stop()
        self.widget.shutdown()
        for sub in self.subs:
            self.node.destroy_subscription(sub)
        self.node.destroy_publisher(self.publisher)
        self.node.destroy_publisher(self.alive_publisher)
