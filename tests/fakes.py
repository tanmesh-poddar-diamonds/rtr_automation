from pathlib import Path


class FakeDownload:
    def __init__(self, name, data=b"0123456789", failure=None):
        self.suggested_filename = name
        self._data = data
        self._failure = failure

    def failure(self):
        return self._failure

    def save_as(self, path):
        Path(path).write_bytes(self._data)


from contextlib import contextmanager


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeDriver:
    """Scripted driver. `steps` = [((n, total), [downloads]), ...]; each read_progress()
    consumes one step. When steps run out the last progress repeats (a stall)."""

    def __init__(self, clock, steps=None, found=True, open_failures=0, build_raises=None):
        self.clock = clock
        self.steps = list(steps or [])
        self.found = found
        self.open_failures = open_failures
        self.build_raises = build_raises
        self.calls = []
        self._pending = []
        self._last = None

    def open_ring(self, label):
        self.calls.append(("open_ring", label))
        return self.found

    def open_panel(self):
        self.calls.append(("open_panel",))
        if self.open_failures > 0:
            self.open_failures -= 1
            raise RuntimeError("panel did not open")

    def set_carat(self, v):
        self.calls.append(("set_carat", v))

    def select_only_shape(self, s):
        self.calls.append(("select_only_shape", s))

    def ensure_all_colours(self, s):
        self.calls.append(("ensure_all_colours", s))
        return 0

    def start_build(self):
        self.calls.append(("start_build",))
        if self.build_raises:
            raise self.build_raises

    def stop_build(self):
        self.calls.append(("stop_build",))

    def read_progress(self):
        if self.steps:
            progress, downloads = self.steps.pop(0)
            self._last = progress
            self._pending.extend(downloads)
        return self._last

    def drain_downloads(self):
        items, self._pending = self._pending, []
        return items

    def pump(self, ms):
        self.clock.t += ms / 1000


@contextmanager
def driver_factory(driver):
    yield driver
