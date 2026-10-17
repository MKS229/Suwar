"""Abstract data-access layer.

The business classes only talk to this interface, so they can be unit-tested with a
fake repository (no MySQL needed) and run in production with MySQLRepository.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

from .models import GateController, Maintenance, Sensor, TimeSlot, User


@dataclass
class ReportRecord:
    report_id: int
    report_type: str
    generated_date: datetime
    payload: str            # encrypted JSON
    user_id: Optional[int]


class Repository(ABC):
    @abstractmethod
    def check_connection(self) -> None: ...

    # ---- sensors
    @abstractmethod
    def get_sensors(self) -> List[Sensor]: ...

    @abstractmethod
    def get_sensor_by_falaj(self, falaj_name: str) -> Optional[Sensor]: ...

    @abstractmethod
    def update_sensor(self, sensor: Sensor) -> None:
        """Save value and status."""

    @abstractmethod
    def set_sensor_calibrated(self, sensor_id: int, when: datetime) -> bool: ...

    @abstractmethod
    def add_reading(self, sensor_id: int, value: float, recorded_at: datetime) -> None: ...

    @abstractmethod
    def get_recent_readings(self, sensor_id: int, limit: int = 30) -> List[float]:
        """Oldest first."""

    # ---- gates
    @abstractmethod
    def get_gates(self) -> List[GateController]: ...

    @abstractmethod
    def get_gate(self, gate_id: int) -> Optional[GateController]: ...

    @abstractmethod
    def update_gate(self, gate: GateController) -> None: ...

    # ---- users
    @abstractmethod
    def get_users(self) -> List[User]: ...

    @abstractmethod
    def get_user(self, user_id: int) -> Optional[User]: ...

    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[User]: ...

    @abstractmethod
    def update_password(self, user_id: int, password_hash: str) -> bool: ...

    # ---- time slots
    @abstractmethod
    def get_slots(self, falaj_name: Optional[str] = None) -> List[TimeSlot]: ...

    @abstractmethod
    def get_slot(self, slot_id: int) -> Optional[TimeSlot]: ...

    @abstractmethod
    def add_slot(self, falaj_name: str, start_time: str) -> int: ...

    @abstractmethod
    def update_slot_time(self, slot_id: int, start_time: str) -> bool:
        """Only changes a slot that is not reserved."""

    @abstractmethod
    def count_user_slots(self, user_id: int) -> int: ...

    @abstractmethod
    def reserve_slot(self, slot_id: int, user_id: int) -> bool:
        """Atomically reserve; return False if the slot was already taken."""

    @abstractmethod
    def release_slot(self, slot_id: int, user_id: int) -> bool:
        """Free a slot held by user_id; return False if it wasn't theirs."""

    # ---- maintenance / alerts
    @abstractmethod
    def add_maintenance(self, m: Maintenance) -> int: ...

    @abstractmethod
    def update_maintenance(self, m: Maintenance) -> None: ...

    @abstractmethod
    def get_maintenance_by_id(self, maintenance_id: int) -> Optional[Maintenance]: ...

    @abstractmethod
    def count_recent_alerts(self, sensor_id: int, since: datetime) -> int: ...

    @abstractmethod
    def get_maintenance(self, statuses: Optional[List[str]] = None,
                        sensor_id: Optional[int] = None, limit: int = 50) -> List[Maintenance]:
        """Newest first."""

    # ---- reports
    @abstractmethod
    def add_report(self, report_type: str, generated_date: datetime, payload: str,
                   user_id: Optional[int]) -> int: ...

    @abstractmethod
    def get_reports(self, limit: int = 20) -> List[ReportRecord]:
        """Newest first."""
