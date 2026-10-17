"""MySQL implementation of the Repository interface."""
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

try:
    import mysql.connector as mysql_connector
except ImportError:          # lets the rest of the code (and unit tests) import without the driver
    mysql_connector = None

from .models import Farm, GateController, Maintenance, Sensor, TimeSlot, User
from .repository import Repository, ReportRecord


class DatabaseError(Exception):
    """Raised when the database cannot be reached or a query fails."""


class MySQLRepository(Repository):
    def __init__(self, config: dict):
        self.config = config

    # ------------------------------------------------------------------ helpers
    @contextmanager
    def _cursor(self, commit: bool = False):
        if mysql_connector is None:
            raise DatabaseError("mysql-connector-python is not installed "
                                "(run: pip install mysql-connector-python)")
        try:
            conn = mysql_connector.connect(**self.config)
        except mysql_connector.Error as exc:
            raise DatabaseError(f"Cannot connect to MySQL: {exc}") from exc
        try:
            cur = conn.cursor(dictionary=True)
            try:
                yield cur
                if commit:
                    conn.commit()
            finally:
                cur.close()
        except mysql_connector.Error as exc:
            raise DatabaseError(f"Database error: {exc}") from exc
        finally:
            conn.close()

    def _query(self, sql: str, params: tuple = ()) -> list:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _execute(self, sql: str, params: tuple = ()) -> int:
        """Run a write statement and return the number of affected rows."""
        with self._cursor(commit=True) as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def check_connection(self) -> None:
        self._query("SELECT 1 AS ok")

    # ------------------------------------------------------------------ sensors
    @staticmethod
    def _sensor(row) -> Sensor:
        return Sensor(row["sensor_id"], row["location"], row["falaj_name"], float(row["value"]),
                      row["status"], row["last_calibrated"])

    def get_sensors(self) -> List[Sensor]:
        return [self._sensor(r) for r in self._query("SELECT * FROM Sensors ORDER BY sensor_id")]

    def get_sensor_by_falaj(self, falaj_name: str) -> Optional[Sensor]:
        rows = self._query("SELECT * FROM Sensors WHERE falaj_name = %s LIMIT 1", (falaj_name,))
        return self._sensor(rows[0]) if rows else None

    def update_sensor(self, sensor: Sensor) -> None:
        self._execute("UPDATE Sensors SET value = %s, status = %s WHERE sensor_id = %s",
                      (sensor.value, sensor.status, sensor.sensor_id))

    def set_sensor_calibrated(self, sensor_id: int, when: datetime) -> bool:
        return self._execute("UPDATE Sensors SET last_calibrated = %s WHERE sensor_id = %s",
                             (when, sensor_id)) == 1

    def add_reading(self, sensor_id: int, value: float, recorded_at: datetime) -> None:
        self._execute("INSERT INTO SensorReadings (sensor_id, value, recorded_at) VALUES (%s, %s, %s)",
                      (sensor_id, value, recorded_at))

    def get_recent_readings(self, sensor_id: int, limit: int = 30) -> List[float]:
        rows = self._query("SELECT value FROM SensorReadings WHERE sensor_id = %s "
                           "ORDER BY reading_id DESC LIMIT %s", (sensor_id, limit))
        return [float(r["value"]) for r in reversed(rows)]

    # ------------------------------------------------------------------ gates
    def _gate(self, row) -> GateController:
        return GateController(row["gate_id"], row["location"], row["falaj_name"],
                              bool(row["is_open"]), float(row["flow_rate"]), repo=self)

    def get_gates(self) -> List[GateController]:
        return [self._gate(r) for r in self._query("SELECT * FROM Gates ORDER BY gate_id")]

    def get_gate(self, gate_id: int) -> Optional[GateController]:
        rows = self._query("SELECT * FROM Gates WHERE gate_id = %s", (gate_id,))
        return self._gate(rows[0]) if rows else None

    def update_gate(self, gate: GateController) -> None:
        self._execute("UPDATE Gates SET is_open = %s, flow_rate = %s WHERE gate_id = %s",
                      (int(gate.is_open), gate.flow_rate, gate.gate_id))

    # ------------------------------------------------------------------ users
    _USER_SQL = ("SELECT u.user_id, u.username, u.password_hash, u.name, u.role, u.access_level, "
                 "f.farm_id, f.location AS farm_location, f.falaj_name AS farm_falaj, f.size AS farm_size "
                 "FROM Users u LEFT JOIN Farms f ON u.farm_id = f.farm_id")

    @staticmethod
    def _user(row) -> User:
        farm = None
        if row["farm_id"] is not None:
            farm = Farm(row["farm_id"], row["farm_location"], row["farm_falaj"], float(row["farm_size"]))
        return User(row["user_id"], row["name"], row["role"], farm, row["username"],
                    row["password_hash"], row["access_level"])

    def get_users(self) -> List[User]:
        return [self._user(r) for r in self._query(self._USER_SQL + " ORDER BY u.user_id")]

    def get_user(self, user_id: int) -> Optional[User]:
        rows = self._query(self._USER_SQL + " WHERE u.user_id = %s", (user_id,))
        return self._user(rows[0]) if rows else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        rows = self._query(self._USER_SQL + " WHERE u.username = %s", (username,))
        return self._user(rows[0]) if rows else None

    def update_password(self, user_id: int, password_hash: str) -> bool:
        return self._execute("UPDATE Users SET password_hash = %s WHERE user_id = %s",
                             (password_hash, user_id)) == 1

    # ------------------------------------------------------------------ time slots
    @staticmethod
    def _slot(row) -> TimeSlot:
        return TimeSlot(row["slot_id"], row["start_time"], row["falaj_name"], row["reserved_by"])

    def get_slots(self, falaj_name: Optional[str] = None) -> List[TimeSlot]:
        if falaj_name:
            rows = self._query("SELECT * FROM TimeSlots WHERE falaj_name = %s "
                               "ORDER BY start_time, slot_id", (falaj_name,))
        else:
            rows = self._query("SELECT * FROM TimeSlots ORDER BY slot_id")
        return [self._slot(r) for r in rows]

    def get_slot(self, slot_id: int) -> Optional[TimeSlot]:
        rows = self._query("SELECT * FROM TimeSlots WHERE slot_id = %s", (slot_id,))
        return self._slot(rows[0]) if rows else None

    def add_slot(self, falaj_name: str, start_time: str) -> int:
        with self._cursor(commit=True) as cur:
            cur.execute("INSERT INTO TimeSlots (slot_id, start_time, falaj_name) "
                        "SELECT COALESCE(MAX(slot_id), 0) + 1, %s, %s FROM TimeSlots",
                        (start_time, falaj_name))
            cur.execute("SELECT MAX(slot_id) AS id FROM TimeSlots")
            return cur.fetchone()["id"]

    def update_slot_time(self, slot_id: int, start_time: str) -> bool:
        return self._execute("UPDATE TimeSlots SET start_time = %s "
                             "WHERE slot_id = %s AND reserved_by IS NULL", (start_time, slot_id)) == 1

    def count_user_slots(self, user_id: int) -> int:
        rows = self._query("SELECT COUNT(*) AS c FROM TimeSlots WHERE reserved_by = %s", (user_id,))
        return int(rows[0]["c"])

    def reserve_slot(self, slot_id: int, user_id: int) -> bool:
        # The WHERE clause makes this atomic: two users can never both win the same slot.
        return self._execute("UPDATE TimeSlots SET reserved_by = %s "
                             "WHERE slot_id = %s AND reserved_by IS NULL", (user_id, slot_id)) == 1

    def release_slot(self, slot_id: int, user_id: int) -> bool:
        return self._execute("UPDATE TimeSlots SET reserved_by = NULL "
                             "WHERE slot_id = %s AND reserved_by = %s", (slot_id, user_id)) == 1

    # ------------------------------------------------------------------ maintenance
    def _maintenance(self, row) -> Maintenance:
        return Maintenance(row["maintenance_id"], row["issue_type"], row["reported_date"], row["status"],
                           row["sensor_id"], row["location"], row["scheduled_date"], repo=self)

    def add_maintenance(self, m: Maintenance) -> int:
        with self._cursor(commit=True) as cur:
            cur.execute("INSERT INTO Maintenance (sensor_id, issue_type, reported_date, status, location, "
                        "scheduled_date) VALUES (%s, %s, %s, %s, %s, %s)",
                        (m.sensor_id, m.issue_type, m.reported_date, m.status, m.location, m.scheduled_date))
            return cur.lastrowid

    def update_maintenance(self, m: Maintenance) -> None:
        self._execute("UPDATE Maintenance SET status = %s, scheduled_date = %s WHERE maintenance_id = %s",
                      (m.status, m.scheduled_date, m.maintenance_id))

    def get_maintenance_by_id(self, maintenance_id: int) -> Optional[Maintenance]:
        rows = self._query("SELECT * FROM Maintenance WHERE maintenance_id = %s", (maintenance_id,))
        return self._maintenance(rows[0]) if rows else None

    def count_recent_alerts(self, sensor_id: int, since: datetime) -> int:
        rows = self._query("SELECT COUNT(*) AS c FROM Maintenance "
                           "WHERE sensor_id = %s AND reported_date >= %s", (sensor_id, since))
        return int(rows[0]["c"])

    def get_maintenance(self, statuses: Optional[List[str]] = None,
                        sensor_id: Optional[int] = None, limit: int = 50) -> List[Maintenance]:
        where, params = [], []
        if statuses:
            where.append("status IN (" + ", ".join(["%s"] * len(statuses)) + ")")
            params.extend(statuses)
        if sensor_id is not None:
            where.append("sensor_id = %s")
            params.append(sensor_id)
        sql = "SELECT * FROM Maintenance"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY reported_date DESC, maintenance_id DESC LIMIT %s"
        params.append(limit)
        return [self._maintenance(r) for r in self._query(sql, tuple(params))]

    # ------------------------------------------------------------------ reports
    def add_report(self, report_type: str, generated_date: datetime, payload: str,
                   user_id: Optional[int]) -> int:
        with self._cursor(commit=True) as cur:
            cur.execute("INSERT INTO Reports (report_type, generated_date, payload, user_id) "
                        "VALUES (%s, %s, %s, %s)", (report_type, generated_date, payload, user_id))
            return cur.lastrowid

    def get_reports(self, limit: int = 20) -> List[ReportRecord]:
        rows = self._query("SELECT * FROM Reports ORDER BY generated_date DESC, report_id DESC LIMIT %s",
                           (limit,))
        return [ReportRecord(r["report_id"], r["report_type"], r["generated_date"], r["payload"],
                             r["user_id"]) for r in rows]
