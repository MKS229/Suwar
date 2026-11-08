"""R3: Leak Detection and Maintenance Alerts  -  TC05, TC06, TC07"""
import unittest

from helpers import FixedFlow, PASSWORD, make_system, note


class R3LeakAlerts(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.db, self.clock = make_system()

    def test_TC05_detect_water_leakage(self):
        self.db.sensors[2].value = 8.5                        # Sensor 3 reads 8.5 L/s (above 8.0)
        leak = self.ctrl.sensor_manager.detect_leak()
        alerts = self.ctrl.generate_alerts()
        mine = [a for a in alerts if a.sensor_id == 3]
        note("TC05", f"Leak detected = {leak}; alert created for sensor 3: "
                     f"{mine[0].send_maintenance_alert() if mine else 'none'}")
        self.assertTrue(leak)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].issue_type, "WATER_LEAK")
        self.assertIn(mine[0].maintenance_id, [m.maintenance_id for m in self.ctrl.get_open_alerts()])  # recorded

    def test_TC06_flow_at_detection_threshold(self):
        self.ctrl.sensor_manager.rng = FixedFlow(8.0)         # sensors read exactly 8.0 L/s
        alerts = self.ctrl.coordinate_components()
        note("TC06", f"Sensor 2 flow {self.db.sensors[1].value}, status {self.db.sensors[1].report_status()}, "
                     f"alerts created = {len(alerts)}")
        self.assertEqual(self.db.sensors[1].value, 8.0)
        self.assertEqual(self.db.sensors[1].report_status(), "Normal")
        self.assertEqual(alerts, [])                                    # no leak alert
        self.assertEqual(self.ctrl.get_open_alerts(), [])
        self.assertEqual(self.ctrl.get_flow_history(2)[-1], 8.0)        # post: reading is recorded

    def test_TC07_acknowledge_leak_alert(self):
        user = self.ctrl.login("nasser.harthi", PASSWORD).data          # pre: authenticated user
        self.db.sensors[0].value = 12.0
        alert = self.ctrl.generate_alerts()[0]                          # pre: a leak alert exists
        result = self.ctrl.acknowledge_alert(user, alert.maintenance_id)
        status = self.db.get_maintenance_by_id(alert.maintenance_id).status
        note("TC07", f"{result.message}; alert status = {status}")
        self.assertTrue(result)
        self.assertEqual(status, "Acknowledged")
        self.assertNotIn(alert.maintenance_id, [m.maintenance_id for m in self.ctrl.get_open_alerts()])


if __name__ == "__main__":
    unittest.main()
