"""Domain classes from the Suwar class diagram.

UML name -> Python name:  readValue() -> read_value(), isOpen -> is_open, userID -> user_id, ...
SensorManager, ScheduleManager, SystemController, Report and DataSecurity live in
their own modules (managers.py, controller.py, reports.py, security.py).
"""
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from . import config
from .security import DataSecurity


class Result:
    """Outcome of an action: truthy when it succeeded, always carries a message."""

    def __init__(self, success: bool, message: str = "", data=None):
        self.success = success
        self.message = message
        self.data = data

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self):
        return f"Result({self.success}, {self.message!r})"


@dataclass
class Farm:
    farm_id: int
    location: str
    falaj_name: str
    size: float  # hectares


@dataclass
class TimeSlot:
    slot_id: int
    start_time: str            # "HH:MM"
    falaj_name: str
    reserved_by: Optional[int] = None

    @property
    def is_reserved(self) -> bool:
        return self.reserved_by is not None

    @property
    def end_time(self) -> str:
        start = datetime.strptime(self.start_time, "%H:%M")
        return (start + timedelta(minutes=config.SLOT_DURATION_MINUTES)).strftime("%H:%M")


# ------------------------------------------------------------------ Sensor
@dataclass
class Sensor:
    sensor_id: int
    location: str
    falaj_name: str
    value: float = 0.0
    status: str = "Normal"
    last_calibrated: Optional[datetime] = None

    def is_leaking(self, threshold: float = config.LEAK_THRESHOLD) -> bool:
        return self.value > threshold

    def read_value(self, rng=random) -> float:
        """readValue(): take a (simulated) flow reading in L/s, with occasional spikes."""
        base_flow = rng.uniform(0, 8)
        spike = rng.random() < 0.2
        spike_value = rng.uniform(5, 10) if spike else 0
        self.value = round(base_flow + spike_value, 1)
        self.report_status()
        return self.value

    def report_status(self) -> str:
        """reportStatus(): 'Leak' above the threshold, otherwise 'Normal'."""
        self.status = "Leak" if self.is_leaking() else "Normal"
        return self.status


# ------------------------------------------------------------------ User
@dataclass
class User:
    user_id: int
    name: str
    role: str
    farm: Optional[Farm] = None
    username: str = ""
    password_hash: str = ""
    access_level: int = config.ACCESS_FARMER
    controller: object = field(default=None, repr=False, compare=False)   # set by SystemController.login

    @property
    def farm_id(self) -> Optional[int]:
        return self.farm.farm_id if self.farm else None

    @property
    def is_farmer(self) -> bool:
        return self.role == "farmer"

    @property
    def is_admin(self) -> bool:
        return self.access_level >= config.ACCESS_ADMIN

    @property
    def is_staff(self) -> bool:
        return self.access_level >= config.ACCESS_STAFF

    def login(self, credentials: str) -> bool:
        """login(credentials): True if the password matches the stored hash."""
        return DataSecurity.verify_password(credentials, self.password_hash)

    def monitor_system(self) -> dict:
        """monitorSystem(): current system status, sensors and open alerts."""
        if self.controller is None:
            raise RuntimeError("User is not logged in")
        return self.controller.get_system_overview()

    def adjust_settings(self, new_password: Optional[str] = None) -> Result:
        """adjustSettings(): currently lets a user change their own password."""
        if self.controller is None:
            return Result(False, "User is not logged in")
        if new_password is None:
            return Result(False, "Nothing to change")
        return self.controller.change_password(self, new_password)

    def reserve_time_slot(self, slot_id) -> Result:
        """reserveTimeSlot(): ask the ScheduleManager for a slot."""
        if self.controller is None:
            return Result(False, "User is not logged in")
        return self.controller.schedule_manager.reserve_time_slot(self.user_id, slot_id)


# ------------------------------------------------------------------ Maintenance
OPEN, ACKNOWLEDGED, SCHEDULED, RESOLVED = "Open", "Acknowledged", "Scheduled", "Resolved"


@dataclass
class Maintenance:
    maintenance_id: Optional[int]
    issue_type: str
    reported_date: datetime
    status: str = OPEN
    sensor_id: Optional[int] = None
    location: str = ""
    scheduled_date: Optional[date] = None
    repo: object = field(default=None, repr=False, compare=False)

    def _save(self):
        if self.repo is not None and self.maintenance_id is not None:
            self.repo.update_maintenance(self)

    def log_issue(self) -> int:
        """logIssue(): store this issue in the database and return its id."""
        self.maintenance_id = self.repo.add_maintenance(self)
        return self.maintenance_id

    def send_maintenance_alert(self) -> str:
        """sendMaintenanceAlert(): the notification text shown to users."""
        return f"LEAK DETECTED at {self.location}" if self.issue_type == "WATER_LEAK" \
            else f"{self.issue_type} at {self.location}"

    def acknowledge(self) -> bool:
        if self.status != OPEN:
            return False
        self.status = ACKNOWLEDGED
        self._save()
        return True

    def schedule_maintenance(self, when: date) -> bool:
        """scheduleMaintenance(): plan the repair for a date (today or later)."""
        if self.status == RESOLVED or when < date.today():
            return False
        self.scheduled_date = when
        self.status = SCHEDULED
        self._save()
        return True

    def resolve_issue(self) -> bool:
        """resolveIssue(): mark the problem as fixed."""
        if self.status == RESOLVED:
            return False
        self.status = RESOLVED
        self._save()
        return True


# ------------------------------------------------------------------ GateController
@dataclass
class GateController:
    gate_id: int
    location: str
    falaj_name: str
    is_open: bool = False
    flow_rate: float = 0.0
    repo: object = field(default=None, repr=False, compare=False)

    def _save(self):
        if self.repo is not None:
            self.repo.update_gate(self)

    def open_gate(self) -> None:
        self.is_open = True
        if self.flow_rate <= 0:
            self.flow_rate = config.DEFAULT_GATE_FLOW
        self._save()

    def close_gate(self) -> None:
        self.is_open = False
        self.flow_rate = 0.0
        self._save()

    def adjust_flow(self, rate: float) -> bool:
        """adjustFlow(rate): only an open gate can be adjusted, within 0..MAX_GATE_FLOW."""
        if not self.is_open or not (0 <= rate <= config.MAX_GATE_FLOW):
            return False
        self.flow_rate = round(float(rate), 1)
        self._save()
        return True

    def get_gate_status(self) -> str:
        return f"OPEN - {self.flow_rate:.1f} L/s" if self.is_open else "CLOSED"
