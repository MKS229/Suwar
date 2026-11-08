"""Runs the 23 test cases and fills 'Actual Results' and 'Status' of your CSV.

    python test_script/run_all.py

Output: test_script/test_results.csv  (same columns as test_cases.csv, plus the real results)
"""
import csv
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import helpers  # noqa: E402


class Recorder(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.status, self.why = {}, {}

    def _tc(self, test):
        return re.search(r"test_(TC\d+)_", test._testMethodName).group(1)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.status[self._tc(test)] = "Pass"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.status[self._tc(test)] = "Fail"
        self.why[self._tc(test)] = str(err[1]).strip().splitlines()[0]

    def addError(self, test, err):
        super().addError(test, err)
        self.status[self._tc(test)] = "Error"
        self.why[self._tc(test)] = f"{err[0].__name__}: {err[1]}"


def main():
    with open(os.path.join(HERE, "test_cases.csv"), encoding="cp1252", newline="") as f:
        rows = [r for r in csv.reader(f) if r and re.fullmatch(r"TC\d+", r[0])]
    in_csv = [r[0] for r in rows]

    suite = unittest.defaultTestLoader.discover(HERE, pattern="test_*.py", top_level_dir=HERE)
    result = unittest.TextTestRunner(stream=open(os.devnull, "w"), resultclass=Recorder).run(suite)

    print(f"{'TC':<6}{'Result':<8}{'Test scenario'}")
    print("-" * 70)
    for r in rows:
        tc = r[0]
        status = result.status.get(tc, "Not Run")
        actual = helpers.NOTES.get(tc, "")
        if status != "Pass" and tc in result.why:
            actual = (actual + " | " if actual else "") + "Problem: " + result.why[tc]
        r[8], r[10] = actual or "-", status
        print(f"{tc:<6}{status:<8}{r[2]}")
    print("-" * 70)
    passed = sum(r[10] == "Pass" for r in rows)
    print(f"Total {len(rows)}   Pass {passed}   Fail/Error {len(rows) - passed}")
    for tc in sorted(set(result.status) - set(in_csv)):
        print(f"WARNING: test {tc} is not in test_cases.csv")

    out = os.path.join(HERE, "test_results.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["TC ID", "RID", "Test Scenario", "Description", "Pre-condition", "Action", "Test Data",
                    "Expected Results", "Actual Results", "Post-Condition", "Status"])
        w.writerows(rows)
    print("Results saved to", out)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
