"""R2: Real-Time Water Flow Monitoring  -  TC03, TC04"""
import unittest

from helpers import FixedFlow, make_system, note


class R2FlowMonitoring(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.db, self.clock = make_system()

    def read_sensor(self, sensor_id, flow):
        """Make the sensors read `flow` L/s, collect the reading, return that sensor as the screen shows it."""
        self.ctrl.sensor_manager.rng = FixedFlow(flow)
        self.ctrl.sensor_manager.collect_data()
        return next(s for s in self.ctrl.get_sensors() if s.sensor_id == sensor_id)

    def test_TC03_normal_water_flow(self):
        sensor = self.read_sensor(1, 5.0)                     # Sensor 1, flow 5.0 L/s
        shown = f"{sensor.value:.1f} L/s"
        note("TC03", f"Sensor 1 shows {shown}, status {sensor.report_status()}; latest stored reading "
                     f"{self.ctrl.get_flow_history(1)[-1]}")
        self.assertEqual(sensor.value, 5.0)
        self.assertEqual(sensor.report_status(), "Normal")
        self.assertEqual(self.ctrl.get_flow_history(1)[-1], 5.0)      # post: latest reading is available

    def test_TC04_zero_water_flow(self):
        sensor = self.read_sensor(4, 0.0)                     # Sensor 4, flow 0.0 L/s
        shown = f"{sensor.value:.1f} L/s"
        note("TC04", f"Sensor 4 shows {shown}, status {sensor.report_status()}")
        self.assertEqual(shown, "0.0 L/s")
        self.assertEqual(sensor.report_status(), "Normal")
        self.assertEqual(self.ctrl.get_flow_history(4)[-1], 0.0)      # post: latest reading is updated


if __name__ == "__main__":
    unittest.main()
