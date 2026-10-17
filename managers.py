"""SensorManager and ScheduleManager (class diagram)."""
import random
import re
from datetime import datetime, timedelta
from typing import List, Optional

from . import config
from .models import Maintenance, Result, TimeSlot, User, OPEN
from .repository import Repository


class SensorManager:
    """Owns the sensors (composition): collects readings, detects leaks, raises alerts."""

    def __init__(self, repo: Repository, rng=None, now=datetime.now,
                 manager_id: str = "SM-1", sensor_type: str = "Water flow"):
        self.repo = repo
        self.rng = rng or random
        self.now = now
        self.sensor_id = manager_id
        self.type = sensor_type
        self.reading = 0.0          # latest average flow of all sensors (L/s)

    @property
    def sensors(self):
        return self.repo.get_sensors()

    @property
    def last_calibrated(self) -> Optional[datetime]:
        dates = [s.last_calibrated for s in self.sensors if s.last_calibrated]
        return max(dates) if dates else None

    def collect_data(self) -> float:
        """collectData(): read every sensor, store the readings, return the average flow."""
        sensors = self.sensors
        for sensor in sensors:
            sensor.read_value(self.rng)
            self.repo.update_sensor(sensor)
            self.repo.add_reading(sensor.sensor_id, sensor.value, self.now())
        self.reading = round(sum(s.value for s in sensors) / len(sensors), 2) if sensors else 0.0
        return self.reading

    def calibrate_sensor(self, sensor_id: int) -> bool:
        """calibrateSensor(): record that a sensor was calibrated now."""
        return self.repo.set_sensor_calibrated(sensor_id, self.now())

    def can_alert(self, sensor_id: int) -> bool:
        """At most MAX_ALERTS_PER_HOUR alerts per sensor in the last 60 minutes."""
        since = self.now() - timedelta(hours=1)
        return self.repo.count_recent_alerts(sensor_id, since) < config.MAX_ALERTS_PER_HOUR

    def leaking_sensors(self, threshold: float = config.LEAK_THRESHOLD):
        return [s for s in self.sensors if s.value > threshold and self.can_alert(s.sensor_id)]

    def detect_leak(self, threshold: float = config.LEAK_THRESHOLD) -> bool:
        """detectLeak(): True if any sensor is above the threshold (and may still alert)."""
        return bool(self.leaking_sensors(threshold))

    def send_alert(self) -> List[Maintenance]:
        """sendAlert(): log a maintenance issue for every leaking sensor; returns the new ones."""
        created = []
        for sensor in self.leaking_sensors():
            issue = Maintenance(None, "WATER_LEAK", self.now(), OPEN, sensor.sensor_id,
                                f"{sensor.falaj_name} - {sensor.location}", repo=self.repo)
            issue.log_issue()
            created.append(issue)
        return created


class ScheduleManager:
    """Irrigation schedule: creates / updates / reserves time slots inside a daily window."""

    TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")

    def __init__(self, repo: Repository, schedule_id: str = "SCH-1",
                 start_time: str = config.SCHEDULE_START, end_time: str = config.SCHEDULE_END,
                 priority: int = 1):
        self.repo = repo
        self.schedule_id = schedule_id
        self.start_time = start_time
        self.end_time = end_time
        self.priority = priority

    # ---- helpers
    def get_slots(self, falaj_name: Optional[str] = None) -> List[TimeSlot]:
        return self.repo.get_slots(falaj_name)

    def _normalise_time(self, value) -> Optional[str]:
        """Return 'HH:MM' if value is a valid time inside the schedule window, else None."""
        if not isinstance(value, str) or not self.TIME_RE.match(value.strip()):
            return None
        try:
            start = datetime.strptime(value.strip(), "%H:%M")
        except ValueError:
            return None
        lo = datetime.strptime(self.start_time, "%H:%M")
        hi = datetime.strptime(self.end_time, "%H:%M")
        if start < lo or start + timedelta(minutes=config.SLOT_DURATION_MINUTES) > hi:
            return None
        return start.strftime("%H:%M")

    @staticmethod
    def _to_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # ---- createSchedule / updateSchedule
    def create_schedule(self, falaj_name: str, start_time: str) -> Result:
        if self.repo.get_sensor_by_falaj(falaj_name) is None:
            return Result(False, "Unknown falaj")
        t = self._normalise_time(start_time)
        if t is None:
            return Result(False, f"Time must be HH:MM between {self.start_time} and {self.end_time}")
        if any(s.start_time == t for s in self.repo.get_slots(falaj_name)):
            return Result(False, "A slot already exists at this time")
        return Result(True, "Time slot created", self.repo.add_slot(falaj_name, t))

    def update_schedule(self, slot_id, new_start_time: str) -> Result:
        slot = self.repo.get_slot(self._to_int(slot_id)) if self._to_int(slot_id) is not None else None
        if slot is None:
            return Result(False, "Invalid slot ID")
        if slot.is_reserved:
            return Result(False, "A reserved slot cannot be changed")
        t = self._normalise_time(new_start_time)
        if t is None:
            return Result(False, f"Time must be HH:MM between {self.start_time} and {self.end_time}")
        if any(s.start_time == t and s.slot_id != slot.slot_id for s in self.repo.get_slots(slot.falaj_name)):
            return Result(False, "A slot already exists at this time")
        return Result(True, "Time slot updated") if self.repo.update_slot_time(slot.slot_id, t) \
            else Result(False, "Slot could not be updated")

    # ---- reservation rules
    def max_slots_for(self, user: User) -> int:
        sensor = self.repo.get_sensor_by_falaj(user.farm.falaj_name) if user.farm else None
        if sensor is not None and sensor.value > config.HIGH_FLOW_THRESHOLD:
            return config.MAX_SLOTS_HIGH_FLOW
        return config.MAX_SLOTS_NORMAL

    def can_reserve_more(self, user: User) -> bool:
        if not user.is_farmer or user.farm is None:
            return False
        if self.repo.get_sensor_by_falaj(user.farm.falaj_name) is None:
            return False
        return self.repo.count_user_slots(user.user_id) < self.max_slots_for(user)

    def reserve_time_slot(self, user_id, slot_id) -> Result:
        """reserveTimeSlot(userID, slot)."""
        slot_id, user_id = self._to_int(slot_id), self._to_int(user_id)
        slot = self.repo.get_slot(slot_id) if slot_id is not None else None
        user = self.repo.get_user(user_id) if user_id is not None else None

        if not slot or not user:
            return Result(False, "Invalid slot or user ID")
        if not user.is_farmer or user.farm is None:
            return Result(False, "Only farmers can reserve slots")
        if slot.is_reserved:
            return Result(False, "Slot already reserved")
        if user.farm.falaj_name != slot.falaj_name:
            return Result(False, f"You can only reserve slots for {user.farm.falaj_name}")
        if not self.can_reserve_more(user):
            limit = self.max_slots_for(user)
            reason = " (high flow rate)" if limit == config.MAX_SLOTS_HIGH_FLOW else ""
            return Result(False, f"Maximum {limit} slot{'s' if limit > 1 else ''} allowed{reason}")
        if not self.repo.reserve_slot(slot.slot_id, user.user_id):     # lost a race
            return Result(False, "Slot already reserved")
        return Result(True, "Slot reserved successfully!")

    def cancel_reservation(self, user_id, slot_id) -> Result:
        slot_id, user_id = self._to_int(slot_id), self._to_int(user_id)
        if slot_id is None or user_id is None:
            return Result(False, "Invalid slot or user ID")
        if self.repo.release_slot(slot_id, user_id):
            return Result(True, "Reservation cancelled")
        return Result(False, "You have no reservation on this slot")

    def optimize_schedule(self) -> List[TimeSlot]:
        """optimizeSchedule(): the reserved slots in running order (earliest first)."""
        reserved = [s for s in self.repo.get_slots() if s.is_reserved]
        return sorted(reserved, key=lambda s: (s.start_time, s.falaj_name))
