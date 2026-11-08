"""Shared helpers for the Suwar test scripts.

* MemoryDB    : a small in-memory database used instead of MySQL, so every test starts from the
                same clean data (same IDs as database/schema.sql: users 1, 2, 3, 22, 25 ...).
* make_system : builds the real Suwar controller on top of MemoryDB.
* note(...)   : the test writes what really happened -> it becomes the 'Actual Results' column.
"""
import os
import sys
import threading
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # project folder (has suwar/)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from suwar.controller import SystemController            # noqa: E402
from suwar.models import Farm, GateController, Sensor, TimeSlot, User   # noqa: E402
from suwar.repository import Repository, ReportRecord    # noqa: E402
from suwar.security import DataSecurity                  # noqa: E402

PASSWORD = "ValidPass123!"          # password of every test user (the one used in your CSV)
NOTES = {}                          # TC id -> actual result text


def note(tc_id, text):
    NOTES[tc_id] = text


# ----------------------------------------------------------------------------- readings and clock
class FixedFlow:
    """Makes every sensor read exactly `value` L/s (no spikes)."""
    def __init__(self, value):
        self.value = value

    def uniform(self, a, b):
        return self.value

    def random(self):
        return 0.9


class Clock:
    """System time that the test can move: clock.set(6, 0) = 06:00."""
    def __init__(self):
        self.time = datetime(2026, 3, 2, 5, 0, 0)

    def now(self):
        return self.time

    def set(self, hour, minute=0):
        self.time = self.time.replace(hour=hour, minute=minute, second=0)

    def move(self, **kwargs):
        self.time += timedelta(**kwargs)


# ----------------------------------------------------------------------------- the data
FALAJ = ["Al-Khatmeen", "Daris", "Al-Muyasser", "Al-Jeela", "Al-Malaki",
         "Al-Ayn", "Al-Ghail", "Al-Hamra", "Al-Thuwaibah", "Al-Gantaq"]


class MemoryDB(Repository):
    def __init__(self):
        hasher = DataSecurity(iterations=1000)          # fast hashing for tests
        h = lambda: hasher.hash_password(PASSWORD)
        self.lock = threading.Lock()                    # makes reserve_slot atomic, like the MySQL UPDATE
        self.slow = False                               # True = small delay so two users really overlap (TC13)
        self.sensors = [Sensor(i, f"Location {i}", f) for i, f in enumerate(FALAJ, 1)]
        self.gates = [GateController(i, f"Gate {i}", f, repo=self) for i, f in enumerate(FALAJ, 1)]
        self.users = [
            User(1, "Nasser Al-Harthi", "farmer", Farm(11, "Farm 1-1", FALAJ[0], 5.0), "nasser.harthi", h(), 1),
            User(2, "Salim Al-Balushi", "farmer", Farm(12, "Farm 1-2", FALAJ[0], 7.5), "salim.balushi", h(), 1),
            User(3, "Khalid Al-Siyabi", "farmer", Farm(21, "Farm 2-1", FALAJ[1], 5.0), "khalid.siyabi", h(), 1),
            User(22, "Khalifa Al-Kindi", "engineer", None, "khalifa.kindi", h(), 2),
            User(25, "Maryam Al Harthi", "admin", None, "mks.harthi", h(), 5),
        ]
        self.slots = [TimeSlot(n * 3 + k + 1, t, f) for n, f in enumerate(FALAJ)
                      for k, t in enumerate(("06:00", "12:00", "18:00"))]
        self.readings = {}                              # sensor id -> [(value, time), ...]
        self.maintenance, self.reports, self._next_id, self._next_report = [], [], 1000, 0

    def check_connection(self): pass

    # sensors
    def get_sensors(self): return list(self.sensors)
    def get_sensor_by_falaj(self, falaj_name): return next((s for s in self.sensors if s.falaj_name == falaj_name), None)

    def update_sensor(self, sensor):
        stored = next(s for s in self.sensors if s.sensor_id == sensor.sensor_id)
        stored.value, stored.status = sensor.value, sensor.status

    def set_sensor_calibrated(self, sensor_id, when):
        sensor = next((s for s in self.sensors if s.sensor_id == sensor_id), None)
        if sensor:
            sensor.last_calibrated = when
        return sensor is not None

    def add_reading(self, sensor_id, value, recorded_at):
        self.readings.setdefault(sensor_id, []).append((value, recorded_at))

    def get_recent_readings(self, sensor_id, limit=30):
        return [v for v, _ in self.readings.get(sensor_id, [])][-limit:]

    # gates
    def get_gates(self): return list(self.gates)
    def get_gate(self, gate_id): return next((g for g in self.gates if g.gate_id == gate_id), None)
    def update_gate(self, gate): pass

    # users
    def get_users(self): return list(self.users)
    def get_user(self, user_id): return next((u for u in self.users if u.user_id == user_id), None)
    def get_user_by_username(self, username): return next((u for u in self.users if u.username == username), None)

    def update_password(self, user_id, password_hash):
        user = self.get_user(user_id)
        if user:
            user.password_hash = password_hash
        return user is not None

    # time slots
    def get_slots(self, falaj_name=None):
        return [s for s in self.slots if falaj_name is None or s.falaj_name == falaj_name]

    def get_slot(self, slot_id): return next((s for s in self.slots if s.slot_id == slot_id), None)

    def add_slot(self, falaj_name, start_time):
        slot = TimeSlot(max(s.slot_id for s in self.slots) + 1, start_time, falaj_name)
        self.slots.append(slot)
        return slot.slot_id

    def update_slot_time(self, slot_id, start_time):
        slot = self.get_slot(slot_id)
        if slot is None or slot.is_reserved:
            return False
        slot.start_time = start_time
        return True

    def count_user_slots(self, user_id):
        if self.slow:
            time.sleep(0.05)                                # both users have passed the 'is it free?' check by now
        return sum(s.reserved_by == user_id for s in self.slots)

    def reserve_slot(self, slot_id, user_id):
        with self.lock:
            slot = self.get_slot(slot_id)
            if slot is None or slot.is_reserved:
                return False
            slot.reserved_by = user_id
            return True

    def release_slot(self, slot_id, user_id):
        with self.lock:
            slot = self.get_slot(slot_id)
            if slot is None or slot.reserved_by != user_id:
                return False
            slot.reserved_by = None
            return True

    # maintenance (leak alerts)
    def add_maintenance(self, m):
        self._next_id += 1
        m.maintenance_id, m.repo = self._next_id, self
        self.maintenance.append(m)
        return m.maintenance_id

    def update_maintenance(self, m): pass
    def get_maintenance_by_id(self, maintenance_id): return next((m for m in self.maintenance if m.maintenance_id == maintenance_id), None)

    def count_recent_alerts(self, sensor_id, since):
        return sum(m.sensor_id == sensor_id and m.reported_date >= since for m in self.maintenance)

    def get_maintenance(self, statuses=None, sensor_id=None, limit=50):
        rows = [m for m in self.maintenance if (not statuses or m.status in statuses)
                and (sensor_id is None or m.sensor_id == sensor_id)]
        return sorted(rows, key=lambda m: (m.reported_date, m.maintenance_id), reverse=True)[:limit]

    # reports
    def add_report(self, report_type, generated_date, payload, user_id):
        self._next_report += 1
        self.reports.append(ReportRecord(self._next_report, report_type, generated_date, payload, user_id))
        return self._next_report

    def get_reports(self, limit=20):
        return sorted(self.reports, key=lambda r: r.report_id, reverse=True)[:limit]


def make_system():
    """Return (controller, db, clock): the real Suwar controller running on clean in-memory data."""
    db, clock = MemoryDB(), Clock()
    controller = SystemController(db, FixedFlow(1.0), clock.now, DataSecurity(db, iterations=1000))
    controller.initialize_system()
    return controller, db, clock
