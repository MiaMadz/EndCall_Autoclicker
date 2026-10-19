import unittest

from endcall.trigger import TriggerRule


def run(counts, min_count=2, drop_amount=5, drop_window=10):
    rule = TriggerRule(min_count, drop_amount, drop_window)
    for second, count in enumerate(counts):
        reason = rule.update(count, float(second))
        if reason:
            return second, reason
    return None


class TriggerRuleTests(unittest.TestCase):
    def test_single_misread_is_ignored(self):
        self.assertIsNone(run([12, 12, 2, 12, 12]))

    def test_joining_an_empty_call_does_not_end_it(self):
        self.assertIsNone(run([1, 1, 1, 1]))

    def test_ends_when_count_falls_to_minimum(self):
        self.assertEqual(run([1, 1, 5, 5, 6, 6, 2, 2]), (7, "count reached 2"))

    def test_ends_on_sudden_drop(self):
        self.assertEqual(run([15, 15, 15, 9, 9]), (4, "count dropped 15 → 9"))

    def test_small_drift_does_not_end(self):
        self.assertIsNone(run([15, 15, 14, 14, 13, 13, 12, 12]))

    def test_slow_drop_outside_window_does_not_end(self):
        counts = [20, 20] + [18] * 15 + [16] * 15 + [14] * 15
        self.assertIsNone(run(counts, drop_window=10))


if __name__ == "__main__":
    unittest.main()
