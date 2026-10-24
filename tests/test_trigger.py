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


    def test_follows_a_count_ticking_down_every_read(self):
        self.assertEqual(run(list(range(30, 15, -1)), min_count=20, drop_amount=99),
                         (10, "count reached 20"))

    def test_steady_drop_within_window_ends(self):
        self.assertEqual(run([40, 40, 40, 40, 39, 38, 37, 36, 35], min_count=0),
                         (8, "count dropped 40 → 35"))

    def test_misread_near_jump_is_ignored(self):
        # 21 misread as 27 once: too big a jump to trust without a repeat
        self.assertIsNone(run([21, 21, 27, 21, 21], min_count=0, drop_amount=5))

    def test_mass_exit_needs_one_confirming_read(self):
        self.assertEqual(run([30, 30, 30, 12, 12], min_count=0, drop_amount=5),
                         (4, "count dropped 30 → 12"))


if __name__ == "__main__":
    unittest.main()
