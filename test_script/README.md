# test_script - automated test scripts for the 23 test cases (TC01 - TC23)

Every test is named after its test case in `test_cases.csv`, e.g. `test_TC08_reserve_available_slot`.

## Where to put it
Copy the whole `test_script` folder into the Suwar project folder, next to `suwar/` and `main.py`.

## How to run (from the project folder)
    python test_script/run_all.py
Shows Pass/Fail for TC01-TC23 and saves **test_script/test_results.csv** (your CSV with "Actual Results"
and "Status" filled in). Other ways: `python -m unittest discover -s test_script -v` or `pytest test_script -v`.

## Files
| File | What it does |
|------|--------------|
| `test_cases.csv` | your test cases (unchanged) |
| `helpers.py` | clean in-memory data (instead of MySQL), the real Suwar controller, clock |
| `test_r1_gate_control.py` | TC01, TC02 |
| `test_r2_flow_monitoring.py` | TC03, TC04 |
| `test_r3_leak_alerts.py` | TC05 - TC07 |
| `test_r4_reservation.py` | TC08 - TC15 |
| `test_r5_logging_reports.py` | TC16 - TC18 |
| `test_r6_authentication.py` | TC19 - TC23 |
| `run_all.py` | runs everything and writes `test_results.csv` |

## One edit you may want: TC01 and TC02 (automatic gate control)
The app does not open/close gates by itself yet (only staff can, by hand), so TC01 and TC02 **fail** on the
current app. Either keep them as Fail (a real defect for your report) or add the feature, in
`suwar/controller.py`:

1. In `__init__`, under the line `self._failed: Dict[str, List] = {} ...`, add:

       self._slot_running: Dict[int, bool] = {}

2. In `coordinate_components`, after `self.gates = self.repo.get_gates()`, add:

       self.apply_schedule_to_gates()

3. Add this method right after `coordinate_components` (same indentation as the other methods):

       def apply_schedule_to_gates(self) -> None:
           """Open a gate when a reserved slot of its falaj starts and close it when the slot ends."""
           now = self.now().strftime("%H:%M")
           for gate in self.gates:
               running = any(s.is_reserved and s.start_time <= now < s.end_time
                             for s in self.repo.get_slots(gate.falaj_name))
               was_running = self._slot_running.get(gate.gate_id, False)
               if running and not was_running:
                   gate.open_gate()
               elif was_running and not running:
                   gate.close_gate()
               self._slot_running[gate.gate_id] = running

Run again: all 23 pass.

## Good to know
* The tests use their own clean in-memory data, so they never change your MySQL data. The test password is
  `ValidPass123!` (the one in your CSV); it exists only inside the tests.
* TC16: the app shows the latest 30 readings (no date-range filter). TC18: the report is "Water Flow Summary"
  (average flow per falaj, including Al-Khatmeen) - the app has no report called "Water Usage".
