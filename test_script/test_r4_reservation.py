"""R4: Irrigation Scheduling and Time Slot Reservation  -  TC08 ... TC15

Users 1 and 2 are farmers of Al-Khatmeen (slots 1-3); slot 4 belongs to Daris; user 25 is the administrator.
"""
import threading
import unittest

from helpers import make_system, note


class R4Reservation(unittest.TestCase):
    def setUp(self):
        self.ctrl, self.db, self.clock = make_system()
        self.schedule = self.ctrl.schedule_manager

    def owner(self, slot_id):
        return self.db.get_slot(slot_id).reserved_by

    def test_TC08_reserve_available_slot(self):
        result = self.schedule.reserve_time_slot(1, 1)                  # User 1, slot 1
        note("TC08", f"{result.message} Slot 1 reserved_by = {self.owner(1)}")
        self.assertTrue(result)
        self.assertEqual(self.owner(1), 1)

    def test_TC09_reserve_unavailable_slot(self):
        self.schedule.reserve_time_slot(2, 1)                           # pre: slot 1 already reserved (user 2)
        result = self.schedule.reserve_time_slot(1, 1)
        note("TC09", f"{result.message} Slot 1 still reserved_by = {self.owner(1)}")
        self.assertFalse(result)
        self.assertEqual(self.owner(1), 2)                              # existing reservation unchanged

    def test_TC10_reserve_slot_from_another_falaj(self):
        result = self.schedule.reserve_time_slot(1, 4)                  # slot 4 belongs to Daris
        note("TC10", f"{result.message} Reservations of user 1 = {self.db.count_user_slots(1)}")
        self.assertFalse(result)
        self.assertFalse(self.db.get_slot(4).is_reserved)
        self.assertEqual(self.db.count_user_slots(1), 0)

    def test_TC11_exceed_reservation_limit(self):
        self.schedule.reserve_time_slot(1, 1)                           # pre: user 1 already has 2 reservations
        self.schedule.reserve_time_slot(1, 2)
        result = self.schedule.reserve_time_slot(1, 3)
        note("TC11", f"{result.message} Reservations of user 1 = {self.db.count_user_slots(1)}")
        self.assertFalse(result)
        self.assertEqual(self.db.count_user_slots(1), 2)
        self.assertFalse(self.db.get_slot(3).is_reserved)

    def test_TC12_unauthorized_reservation(self):
        result = self.schedule.reserve_time_slot(25, 1)                 # administrator
        note("TC12", f"{result.message} Slot 1 reserved = {self.db.get_slot(1).is_reserved}")
        self.assertFalse(result)
        self.assertEqual(result.message, "Only farmers can reserve slots")
        self.assertFalse(self.db.get_slot(1).is_reserved)

    def test_TC13_simultaneous_reservation(self):
        self.db.slow = True                                             # make both requests overlap
        results, start = {}, threading.Barrier(2)

        def attempt(user_id):
            start.wait()                                                # both users click at the same moment
            results[user_id] = self.schedule.reserve_time_slot(user_id, 1)

        threads = [threading.Thread(target=attempt, args=(u,)) for u in (1, 2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        winners = [u for u, r in results.items() if r]
        note("TC13", f"Successful reservations = {len(winners)} (user {winners}); slot 1 reserved_by = {self.owner(1)}")
        self.assertEqual(len(winners), 1)
        self.assertEqual(self.owner(1), winners[0])
        self.assertEqual(self.db.count_user_slots(1) + self.db.count_user_slots(2), 1)

    def test_TC14_cancel_own_reservation(self):
        self.schedule.reserve_time_slot(1, 1)                           # pre: user 1 has a reservation
        result = self.schedule.cancel_reservation(1, 1)
        note("TC14", f"{result.message} Slot 1 reserved = {self.db.get_slot(1).is_reserved}")
        self.assertTrue(result)
        self.assertFalse(self.db.get_slot(1).is_reserved)

    def test_TC15_cancel_another_farmers_reservation(self):
        self.schedule.reserve_time_slot(2, 1)                           # pre: user 2 owns slot 1
        result = self.schedule.cancel_reservation(1, 1)                 # user 1 tries to cancel it
        note("TC15", f"{result.message} Slot 1 still reserved_by = {self.owner(1)}")
        self.assertFalse(result)
        self.assertEqual(self.owner(1), 2)


if __name__ == "__main__":
    unittest.main()
