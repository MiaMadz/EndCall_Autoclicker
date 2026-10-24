import queue
import threading
import time

from .ocr import Reader, read_count, save_unreadable

SAVE_EVERY = 5  # seconds between saving unreadable captures


class Monitor:
    def __init__(self, root, on_reading):
        self.root = root
        self.on_reading = on_reading
        self.readings = queue.Queue()
        self.stop_event = threading.Event()
        self.session = 0
        self.running = False
        self.reader = Reader()
        self.reader_region = None
        root.after(100, self._drain)

    def start(self, region, interval):
        self.stop()
        # Keep learned digits between starts, but relearn if the box moved.
        if tuple(region) != self.reader_region:
            self.reader = Reader()
            self.reader_region = tuple(region)
        self.session += 1
        self.stop_event = threading.Event()
        self.running = True
        threading.Thread(target=self._work, daemon=True,
                         args=(self.session, tuple(region), interval, self.stop_event)).start()

    def stop(self):
        # Bumping the session makes any readings still in the queue get ignored.
        self.stop_event.set()
        self.session += 1
        self.running = False

    def _work(self, session, region, interval, stop):
        last_saved = 0
        while not stop.is_set():
            try:
                count, img = read_count(region, self.reader)
                if count is None and time.monotonic() - last_saved > SAVE_EVERY:
                    save_unreadable(img)
                    last_saved = time.monotonic()
            except Exception as e:
                count = e
            self.readings.put((session, time.monotonic(), count))
            stop.wait(interval)

    def _drain(self):
        try:
            while True:
                session, now, count = self.readings.get_nowait()
                if self.running and session == self.session:
                    self.on_reading(now, count)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)
