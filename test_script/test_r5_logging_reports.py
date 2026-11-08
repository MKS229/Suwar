"""R5: Data Logging and Reporting  -  TC16, TC17, TC18"""
import unittest
from datetime import timedelta

from helpers import FixedFlow, PASSWORD, make_system, note


class R5LoggingReports(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.db, self.clock = make_system()

    def store_history(self, sensor_id, values):
        for n, value in enumerate(values):                              # pre: historical readings in the database
            self.db.add_reading(sensor_id, value, self.clock.now() - timedelta(hours=len(values) - n))

    def test_TC16_view_historical_readings(self):
        self.store_history(1, [4.0, 5.5, 6.0, 7.2])
        history = self.ctrl.get_flow_history(1)                         # Action: open the history of sensor 1
        note("TC16", f"Sensor 1 history = {history}")
        self.assertEqual(history, [4.0, 5.5, 6.0, 7.2])                 # oldest first
        self.assertEqual(self.ctrl.get_flow_history(1), history)        # readings remain stored

    def test_TC17_store_sensor_readings(self):
        self.ctrl.sensor_manager.rng = FixedFlow(5.0)
        self.ctrl.sensor_manager.collect_data()                         # Action: collect a new reading
        value, stamp = self.db.readings[1][-1]
        note("TC17", f"Stored sensor 1 reading {value} L/s at {stamp:%Y-%m-%d %H:%M:%S}")
        self.assertEqual(value, 5.0)
        self.assertEqual(stamp, self.clock.now())                       # stored with its timestamp
        self.assertEqual(self.ctrl.get_flow_history(1)[-1], 5.0)        # available in historical records

    def test_TC18_generate_analytical_report(self):
        self.store_history(1, [4.0, 6.0, 8.0])                          # Al-Khatmeen = sensor 1
        engineer = self.ctrl.login("khalifa.kindi", PASSWORD).data      # authorised user
        report = self.ctrl.generate_report(engineer, "Water Flow Summary")
        row = next(r for r in report.data["rows"] if r["Falaj"] == "Al-Khatmeen")
        saved = [r.report_id for r in self.ctrl.get_saved_reports(engineer)]
        note("TC18", f"Report #{report.report_id} generated; Al-Khatmeen average = {row['Average (L/s)']} L/s "
                     f"from {row['Readings']} stored readings")
        self.assertEqual(row["Readings"], 3)
        self.assertEqual(row["Average (L/s)"], 6.0)                     # calculated from the stored data
        self.assertIn(report.report_id, saved)                          # available to authorised users
        farmer = self.ctrl.login("nasser.harthi", PASSWORD).data
        with self.assertRaises(PermissionError):                        # ... and only to them
            self.ctrl.get_saved_reports(farmer)


if __name__ == "__main__":
    unittest.main()
