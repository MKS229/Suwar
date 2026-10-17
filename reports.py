"""Report class (class diagram). Saved reports are encrypted with DataSecurity."""
import csv
import json
from datetime import datetime
from typing import Dict, List, Optional

from .repository import Repository
from .security import DataSecurity

REPORT_TYPES = ("Water Flow Summary", "Leak History", "Reservation Summary")


class Report:
    def __init__(self, report_type: str, repo: Repository, security: DataSecurity,
                 report_id: Optional[int] = None, generated_date: Optional[datetime] = None,
                 data: Optional[dict] = None, user_id: Optional[int] = None, now=datetime.now):
        if report_type not in REPORT_TYPES:
            raise ValueError(f"Unknown report type: {report_type}")
        self.report_id = report_id
        self.type = report_type
        self.generated_date = generated_date
        self.data: dict = data or {"rows": [], "analysis": {}}
        self.user_id = user_id
        self.repo = repo
        self.security = security
        self.now = now

    # ---- generateReport()
    def generate_report(self) -> dict:
        """Collect the data from the database, analyse it and store it (encrypted)."""
        builder = {"Water Flow Summary": self._flow_rows,
                   "Leak History": self._leak_rows,
                   "Reservation Summary": self._reservation_rows}[self.type]
        self.data = {"rows": builder(), "analysis": {}}
        self.generated_date = self.now()
        self.analyze_data()
        payload = self.security.encrypt_data(json.dumps(self.data))
        self.report_id = self.repo.add_report(self.type, self.generated_date, payload, self.user_id)
        return self.data

    # ---- analyzeData()
    def analyze_data(self) -> Dict[str, object]:
        rows = self.data["rows"]
        analysis: Dict[str, object] = {}
        if rows:
            if self.type == "Water Flow Summary":
                best = max(rows, key=lambda r: r["Average (L/s)"])
                analysis["Highest average flow"] = f"{best['Falaj']} ({best['Average (L/s)']} L/s)"
                analysis["Sensors currently leaking"] = sum(r["Status"] == "Leak" for r in rows)
                analysis["Overall average (L/s)"] = round(
                    sum(r["Average (L/s)"] for r in rows) / len(rows), 2)
            elif self.type == "Leak History":
                total = sum(r["Total alerts"] for r in rows)
                worst = max(rows, key=lambda r: r["Total alerts"])
                resolved = sum(r["Resolved"] for r in rows)
                analysis["Total alerts"] = total
                analysis["Most affected falaj"] = worst["Falaj"] if total else "-"
                analysis["Resolved (%)"] = round(100 * resolved / total, 1) if total else 0.0
            else:
                reserved = sum(r["Reserved"] for r in rows)
                slots = sum(r["Slots"] for r in rows)
                busiest = max(rows, key=lambda r: r["Utilization (%)"])
                analysis["Overall utilization (%)"] = round(100 * reserved / slots, 1) if slots else 0.0
                analysis["Busiest falaj"] = busiest["Falaj"] if reserved else "-"
        self.data["analysis"] = analysis
        return analysis

    # ---- exportReport()
    def export_report(self, path: str) -> str:
        """Write the report to a CSV file (opens in Excel) and return the path."""
        rows = self.data["rows"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([self.type, f"generated {self.generated_date:%Y-%m-%d %H:%M:%S}"
                             if self.generated_date else ""])
            writer.writerow([])
            if rows:
                writer.writerow(list(rows[0].keys()))
                for row in rows:
                    writer.writerow(list(row.values()))
            writer.writerow([])
            writer.writerow(["Analysis"])
            for key, value in self.data["analysis"].items():
                writer.writerow([key, value])
        return path

    # ---- loading a saved report
    @classmethod
    def from_record(cls, record, repo: Repository, security: DataSecurity) -> "Report":
        data = json.loads(security.decrypt_data(record.payload))
        return cls(record.report_type, repo, security, record.report_id,
                   record.generated_date, data, record.user_id)

    # ---- row builders
    def _flow_rows(self) -> List[dict]:
        rows = []
        for s in self.repo.get_sensors():
            readings = self.repo.get_recent_readings(s.sensor_id, 100)
            rows.append({
                "Falaj": s.falaj_name, "Location": s.location, "Current (L/s)": s.value,
                "Average (L/s)": round(sum(readings) / len(readings), 2) if readings else s.value,
                "Max (L/s)": max(readings) if readings else s.value,
                "Min (L/s)": min(readings) if readings else s.value,
                "Readings": len(readings), "Status": s.report_status()})
        return rows

    def _leak_rows(self) -> List[dict]:
        issues = self.repo.get_maintenance(limit=100000)
        rows = []
        for s in self.repo.get_sensors():
            mine = [m for m in issues if m.sensor_id == s.sensor_id]
            rows.append({"Falaj": s.falaj_name, "Total alerts": len(mine),
                         "Open": sum(m.status == "Open" for m in mine),
                         "Scheduled": sum(m.status in ("Acknowledged", "Scheduled") for m in mine),
                         "Resolved": sum(m.status == "Resolved" for m in mine)})
        return rows

    def _reservation_rows(self) -> List[dict]:
        rows = []
        for s in self.repo.get_sensors():
            slots = self.repo.get_slots(s.falaj_name)
            reserved = sum(sl.is_reserved for sl in slots)
            rows.append({"Falaj": s.falaj_name, "Slots": len(slots), "Reserved": reserved,
                         "Available": len(slots) - reserved,
                         "Utilization (%)": round(100 * reserved / len(slots), 1) if slots else 0.0})
        return rows
