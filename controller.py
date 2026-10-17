"""SystemController (class diagram): the hub that coordinates every other component.

The GUI only talks to this class (and to the objects it hands out).
"""
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config
from .managers import ScheduleManager, SensorManager
from .models import (ACKNOWLEDGED, GateController, Maintenance, OPEN, RESOLVED, SCHEDULED,
                     Result, Sensor, TimeSlot, User)
from .reports import REPORT_TYPES, Report
from .repository import Repository
from .security import DataSecurity


class SystemController:
    def __init__(self, repo: Repository, rng=None, now=datetime.now,
                 security: Optional[DataSecurity] = None):
        self.repo = repo
        self.now = now
        self.system_id = "SYS-1"
        self.status = "Stopped"
        self.last_updated: Optional[datetime] = None
        self.security = security or DataSecurity(repo, now=now)
        self.sensor_manager = SensorManager(repo, rng or random, now)
        self.schedule_manager = ScheduleManager(repo)
        self.gates: List[GateController] = []                 # aggregation: 0..* gates
        self._failed: Dict[str, List] = {}                    # username -> [count, locked_until]

    # ------------------------------------------------------------------ lifecycle
    def initialize_system(self) -> bool:
        """initializeSystem(): check the database, load the gates, start running."""
        self.repo.check_connection()
        self.gates = self.repo.get_gates()
        self.update_system_status()
        return True

    def update_system_status(self) -> str:
        """updateSystemStatus(): 'Alert' while there are unacknowledged leaks, else 'Running'."""
        open_alerts = self.repo.get_maintenance(statuses=[OPEN], limit=1)
        self.status = "Alert" if open_alerts else "Running"
        self.last_updated = self.now()
        return self.status

    def generate_alerts(self) -> List[Maintenance]:
        """generateAlerts(): ask the SensorManager to log every new leak."""
        return self.sensor_manager.send_alert()

    def coordinate_components(self) -> List[Maintenance]:
        """coordinateComponents(): one monitoring cycle. Returns the new alerts."""
        self.sensor_manager.collect_data()
        new_alerts = self.generate_alerts() if self.sensor_manager.detect_leak() else []
        self.gates = self.repo.get_gates()
        self.update_system_status()
        return new_alerts

    # ------------------------------------------------------------------ login
    def login(self, username: str, password: str) -> Result:
        username = (username or "").strip().lower()
        if not username or not password:
            return Result(False, "Please enter your username and password")
        record = self._failed.setdefault(username, [0, None])
        if record[1] and self.now() < record[1]:
            seconds = int((record[1] - self.now()).total_seconds()) + 1
            return Result(False, f"Too many failed attempts. Try again in {seconds} seconds")
        if record[1] and self.now() >= record[1]:
            record[0], record[1] = 0, None

        user = self.repo.get_user_by_username(username)
        if user is not None and user.login(password):
            self._failed.pop(username, None)
            user.controller = self
            return Result(True, f"Welcome, {user.name}", user)

        record[0] += 1
        if record[0] >= config.MAX_LOGIN_ATTEMPTS:
            record[1] = self.now() + timedelta(seconds=config.LOCKOUT_SECONDS)
            return Result(False, f"Too many failed attempts. Try again in {config.LOCKOUT_SECONDS} seconds")
        return Result(False, "Invalid username or password")

    def change_password(self, user: User, new_password: str) -> Result:
        if len(new_password) < config.MIN_PASSWORD_LENGTH:
            return Result(False, f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters")
        if not self.repo.update_password(user.user_id, self.security.hash_password(new_password)):
            return Result(False, "Password could not be changed")
        return Result(True, "Password changed")

    # ------------------------------------------------------------------ permissions
    @staticmethod
    def _require(user: User, level: int):
        if user is None or user.access_level < level:
            raise PermissionError("You do not have permission to do this")

    # ------------------------------------------------------------------ read access
    def get_sensors(self) -> List[Sensor]:
        return self.sensor_manager.sensors

    def get_flow_history(self, sensor_id: int, limit: int = 30) -> List[float]:
        return self.repo.get_recent_readings(sensor_id, limit)

    def get_slots(self, falaj_name: Optional[str] = None) -> List[TimeSlot]:
        return self.schedule_manager.get_slots(falaj_name)

    def get_gates(self) -> List[GateController]:
        self.gates = self.repo.get_gates()
        return self.gates

    def get_system_overview(self) -> dict:
        """Used by User.monitor_system()."""
        sensors = self.get_sensors()
        return {"system_id": self.system_id, "status": self.status, "last_updated": self.last_updated,
                "sensors": sensors, "leaking": [s for s in sensors if s.is_leaking()],
                "open_alerts": len(self.repo.get_maintenance(statuses=[OPEN]))}

    def get_users(self, requesting_user: User) -> List[User]:
        """Only an administrator may list the users (enforced by DataSecurity)."""
        if requesting_user is None or not self.security.enforce_access_control(requesting_user.user_id):
            raise PermissionError("Only administrators can view the users list")
        return self.repo.get_users()

    def describe_reservation(self, slot: TimeSlot, viewer: User) -> str:
        """Who holds a slot. Farmers see only 'you' / 'reserved'; staff see names."""
        if not slot.is_reserved:
            return "Available"
        if slot.reserved_by == viewer.user_id:
            return "Reserved by you"
        if viewer.is_staff:
            owner = self.repo.get_user(slot.reserved_by)
            return f"Reserved by {owner.name}" if owner else "Reserved"
        return "Reserved"

    def user_slot_count(self, user: User) -> int:
        return self.repo.count_user_slots(user.user_id)

    # ------------------------------------------------------------------ maintenance
    def get_open_alerts(self) -> List[Maintenance]:
        return self.repo.get_maintenance(statuses=[OPEN])

    def get_active_maintenance(self) -> List[Maintenance]:
        return self.repo.get_maintenance(statuses=[OPEN, ACKNOWLEDGED, SCHEDULED])

    def get_maintenance_history(self, limit: int = 50) -> List[Maintenance]:
        return self.repo.get_maintenance(limit=limit)

    def _issue(self, maintenance_id) -> Optional[Maintenance]:
        try:
            return self.repo.get_maintenance_by_id(int(maintenance_id))
        except (TypeError, ValueError):
            return None

    def acknowledge_alert(self, user: User, maintenance_id) -> Result:
        self._require(user, config.ACCESS_FARMER)
        issue = self._issue(maintenance_id)
        if issue is None:
            return Result(False, "Alert not found")
        return Result(True, "Alert acknowledged") if issue.acknowledge() \
            else Result(False, "This alert was already acknowledged")

    def schedule_maintenance(self, user: User, maintenance_id, when: date) -> Result:
        self._require(user, config.ACCESS_STAFF)
        issue = self._issue(maintenance_id)
        if issue is None:
            return Result(False, "Alert not found")
        if issue.schedule_maintenance(when):
            return Result(True, f"Maintenance scheduled for {when:%Y-%m-%d}")
        return Result(False, "Cannot schedule (already resolved, or the date is in the past)")

    def resolve_issue(self, user: User, maintenance_id) -> Result:
        self._require(user, config.ACCESS_STAFF)
        issue = self._issue(maintenance_id)
        if issue is None:
            return Result(False, "Alert not found")
        return Result(True, "Issue marked as resolved") if issue.resolve_issue() \
            else Result(False, "Already resolved")

    # ------------------------------------------------------------------ gates / sensors (staff)
    def operate_gate(self, user: User, gate_id, action: str, rate: Optional[float] = None) -> Result:
        self._require(user, config.ACCESS_STAFF)
        try:
            gate = self.repo.get_gate(int(gate_id))
        except (TypeError, ValueError):
            gate = None
        if gate is None:
            return Result(False, "Gate not found")
        if action == "open":
            gate.open_gate()
        elif action == "close":
            gate.close_gate()
        elif action == "adjust":
            if rate is None or not gate.adjust_flow(rate):
                return Result(False, f"Flow must be 0-{config.MAX_GATE_FLOW:g} L/s and the gate must be open")
        else:
            return Result(False, "Unknown action")
        return Result(True, f"Gate {gate.gate_id}: {gate.get_gate_status()}")

    def calibrate_sensor(self, user: User, sensor_id) -> Result:
        self._require(user, config.ACCESS_STAFF)
        try:
            ok = self.sensor_manager.calibrate_sensor(int(sensor_id))
        except (TypeError, ValueError):
            ok = False
        return Result(ok, "Sensor calibrated" if ok else "Sensor not found")

    # ------------------------------------------------------------------ reports (staff)
    def generate_report(self, user: User, report_type: str) -> Report:
        self._require(user, config.ACCESS_STAFF)
        report = Report(report_type, self.repo, self.security, user_id=user.user_id, now=self.now)
        report.generate_report()
        return report

    def get_saved_reports(self, user: User, limit: int = 20) -> List[Report]:
        self._require(user, config.ACCESS_STAFF)
        reports = []
        for record in self.repo.get_reports(limit):
            try:
                reports.append(Report.from_record(record, self.repo, self.security))
            except ValueError:
                continue            # unreadable (e.g. key changed): skip instead of crashing
        return reports

    def run_security_audit(self, user: User) -> List[str]:
        self._require(user, config.ACCESS_ADMIN)
        return self.security.perform_audit()
