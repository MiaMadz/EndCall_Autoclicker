from collections import deque


class TriggerRule:
    """Decides when to end the call from the sequence of counts read off the screen.

    A reading is trusted when it fits the sequence:
      - it's the same as, or a small step from, the last count (like 41 -> 40), or
      - it's a big jump that shows up twice in a row (a real mass exit, not a misread).
    So a count ticking down every second is followed live, while a one-off
    misread like 12 -> 2 is ignored.
    """

    def __init__(self, min_count, drop_amount, drop_window):
        self.min_count = min_count
        self.drop_amount = drop_amount
        self.drop_window = drop_window
        self.history = deque()  # (time, trusted count)
        self.last_raw = None
        self.armed = False

    @property
    def recent_peak(self):
        return max((c for _, c in self.history), default=None)

    @property
    def last_trusted(self):
        return self.history[-1][1] if self.history else None

    @staticmethod
    def max_step(count):
        """Biggest change between two reads that's treated as normal."""
        return max(2, count // 10)

    def _close(self, a, b):
        return a is not None and abs(a - b) <= self.max_step(a)

    def _fits_sequence(self, count):
        previous_read = self.last_raw
        self.last_raw = count
        # Close to the last trusted count, or to the read just before it
        # (two back-to-back reads like 30 then 29 back each other up).
        return self._close(self.last_trusted, count) or self._close(previous_read, count)

    def update(self, count, now):
        """Feed one reading taken at time `now` (seconds).

        Returns a reason string when the call should end, otherwise None.
        """
        if not self._fits_sequence(count):
            return None

        self.history.append((now, count))
        while now - self.history[0][0] > self.drop_window:
            self.history.popleft()

        # The "reaches" rule only starts once the count has been above it,
        # so joining a near-empty call early doesn't end it right away.
        if count > self.min_count:
            self.armed = True

        if self.armed and count <= self.min_count:
            return f"count reached {count}"
        peak = self.recent_peak
        if peak - count >= self.drop_amount:
            return f"count dropped {peak} → {count}"
        return None
