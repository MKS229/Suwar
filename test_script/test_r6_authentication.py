"""R6: User Authentication and Access Control  -  TC19 ... TC23"""
import unittest

from helpers import PASSWORD, make_system, note


class R6Authentication(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.db, self.clock = make_system()

    def test_TC19_valid_login(self):
        result = self.ctrl.login("nasser.harthi", PASSWORD)             # nasser.harthi / ValidPass123!
        note("TC19", result.message)
        self.assertTrue(result)
        self.assertEqual(result.data.username, "nasser.harthi")         # the logged-in user
        self.assertIs(result.data.controller, self.ctrl)                # session is active

    def test_TC20_invalid_username(self):
        result = self.ctrl.login("invalid.user", "AnyPass123!")
        note("TC20", f"Error message: {result.message}")
        self.assertFalse(result)
        self.assertEqual(result.message, "Invalid username or password")
        self.assertIsNone(result.data)                                  # user remains logged out

    def test_TC21_invalid_password(self):
        result = self.ctrl.login("nasser.harthi", "WrongPass123!")
        note("TC21", f"Login rejected: {result.message}")
        self.assertFalse(result)
        self.assertIsNone(result.data)

    def test_TC22_both_invalid_credentials(self):
        result = self.ctrl.login("invalid.user", "WrongPass123!")
        note("TC22", f"Login rejected: {result.message}")
        self.assertFalse(result)
        self.assertIsNone(result.data)

    def test_TC23_account_lockout(self):
        for _ in range(5):                                              # five wrong passwords in a row
            last = self.ctrl.login("nasser.harthi", "WrongPass123!")
        right = self.ctrl.login("nasser.harthi", PASSWORD)              # even the right password is refused
        self.clock.move(seconds=59)
        still_locked = self.ctrl.login("nasser.harthi", PASSWORD)       # still locked during the 60 seconds
        self.clock.move(seconds=2)
        after = self.ctrl.login("nasser.harthi", PASSWORD)              # the lock is temporary
        note("TC23", f"5th failure: '{last.message}'; right password at +0s: refused = {not right}; "
                     f"at +59s: refused = {not still_locked}; at +61s: allowed = {bool(after)}")
        self.assertIn("60 seconds", last.message)
        self.assertFalse(right)
        self.assertFalse(still_locked)
        self.assertTrue(after)


if __name__ == "__main__":
    unittest.main()
