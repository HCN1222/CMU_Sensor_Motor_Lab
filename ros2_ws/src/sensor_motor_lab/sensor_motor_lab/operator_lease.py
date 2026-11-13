"""Local receipt-time lease for the control panel's ROS heartbeat."""


class OperatorLease:
    def __init__(self, clock, timeout=1.5):
        self.clock = clock
        self.timeout = timeout
        self.last_seen = None

    def heartbeat(self):
        self.last_seen = self.clock()

    @property
    def fresh(self):
        return self.last_seen is not None and 0 <= self.clock() - self.last_seen < self.timeout

    def permits(self, verb):
        return verb not in {'ARM', 'SERVO', 'DC_RPM', 'DC_MOVE', 'STEP_MOVE'} or self.fresh
