from collections import deque


class TriggerRule:
    def __init__(self, min_count, drop_amount, drop_window):
        self.min_count = min_count
        self.drop_amount = drop_amount
        self.drop_window = drop_window
        self.history = deque()  # (time, stable count)
        self.last_raw = None
        self.armed = False

    @property
    def recent_peak(self):
        return max((c for _, c in self.history), default=None)

    def update(self, count, now):
        stable = count == self.last_raw
        self.last_raw = count
        if not stable:
            return None

        self.history.append((now, count))
        while now - self.history[0][0] > self.drop_window:
            self.history.popleft()

        if count > self.min_count:
            self.armed = True

        if self.armed and count <= self.min_count:
            return f"count reached {count}"
        peak = self.recent_peak
        if peak - count >= self.drop_amount:
            return f"count dropped {peak} → {count}"
        return None
