"""R1: Automated Gate Control  -  TC01, TC02"""
import unittest

from helpers import make_system, note


class R1GateControl(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.db, self.clock = make_system()
        # Pre-condition: a valid irrigation schedule exists - farmer 1 reserved slot 1 (Al-Khatmeen, 06:00-07:00)
        self.ctrl.schedule_manager.reserve_time_slot(1, 1)
        self.gate = self.db.get_gate(1)                      # gate 1 belongs to Al-Khatmeen

    def cycle(self, hour, minute=0):
        """Move the clock and let the system run one monitoring cycle (it runs every few seconds)."""
        self.clock.set(hour, minute)
        self.ctrl.coordinate_components()

    def test_TC01_automatic_gate_opening(self):
        self.cycle(5, 59)
        self.assertFalse(self.gate.is_open)                   # closed before the scheduled time
        self.cycle(6, 0)                                      # Action: the scheduled time (06:00) arrives
        note("TC01", f"At 06:00 gate 1 status = {self.gate.get_gate_status()}")
        self.assertTrue(self.gate.is_open, "Gate 1 did not open automatically at 06:00")

    def test_TC02_automatic_gate_closing(self):
        self.cycle(6, 0)                                      # Pre-condition: gate open, schedule active
        self.assertTrue(self.gate.is_open, "Gate 1 was not open during the irrigation period")
        self.cycle(6, 59)
        self.assertTrue(self.gate.is_open)                    # still open inside the 1-hour period
        self.cycle(7, 0)                                      # Action: the 1-hour period ends
        note("TC02", f"At 07:00 gate 1 status = {self.gate.get_gate_status()}")
        self.assertFalse(self.gate.is_open, "Gate 1 did not close automatically at 07:00")


if __name__ == "__main__":
    unittest.main()
