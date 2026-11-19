import pytest

from rtr_page import parse_progress


@pytest.mark.parametrize("text, expected", [
    ("delay for stabilization:400 RUN 0 ( from 387)", (0, 387)),
    ("RUN 7 ( from 387)", (7, 387)),
    ("RUN 12(from 40)", (12, 40)),
    ("RUN 387 ( from 387 )", (387, 387)),
])
def test_parse_progress(text, expected):
    assert parse_progress(text) == expected


@pytest.mark.parametrize("text", ["", None, "RUN", "400"])
def test_parse_progress_none_when_absent(text):
    assert parse_progress(text) is None


class _PlaywrightLikePage:
    """Mimics Playwright's page.on(): it tags the handler with an attribute, which
    fails for builtin callables such as deque.append."""

    def __init__(self):
        self.handlers = {}

    def on(self, event, handler):
        setattr(handler, "_pw_impl_instance_", object())
        self.handlers[event] = handler


def test_download_handler_is_accepted_by_playwright_and_queues_downloads():
    from rtr_page import RtrPage

    page = _PlaywrightLikePage()
    drv = RtrPage(page, "https://h/p?SID=s")
    page.handlers["download"]("dl-1")
    page.handlers["download"]("dl-2")
    assert drv.drain_downloads() == ["dl-1", "dl-2"]
    assert drv.drain_downloads() == []


class _TimedPage(_PlaywrightLikePage):
    """Fake page whose clock advances in wait_for_timeout and fires scripted console messages."""

    def __init__(self, messages=()):
        super().__init__()
        self.t = 0
        self.messages = list(messages)  # [(at_ms, text)]

    def wait_for_timeout(self, ms):
        self.t += ms
        for item in [m for m in self.messages if m[0] <= self.t]:
            self.messages.remove(item)
            self.handlers["console"](type("Msg", (), {"text": item[1]})())


def test_viewer_ready_once_init_3d_message_arrives():
    from rtr_page import RtrPage

    page = _TimedPage([(3000, "iFrame.3D == post frame_size"), (9000, "iFrame.3D == post init_3d == https://x")])
    drv = RtrPage(page, "https://h/p?SID=s")
    assert drv.wait_viewer_ready(timeout_s=30) is True
    assert 9000 <= page.t < 12000


def test_viewer_not_ready_times_out():
    from rtr_page import RtrPage

    page = _TimedPage([(1000, "video_mp4 module loaded")])
    drv = RtrPage(page, "https://h/p?SID=s")
    assert drv.wait_viewer_ready(timeout_s=5) is False


def test_stale_ready_message_from_the_previous_ring_does_not_count():
    from rtr_page import RtrPage

    page = _TimedPage([(500, "iFrame.3D == post init_3d == old ring")])
    drv = RtrPage(page, "https://h/p?SID=s")
    page.wait_for_timeout(1000)          # old ring finished loading
    drv.reset_viewer_state()             # a new ring is about to be opened
    assert drv.wait_viewer_ready(timeout_s=3) is False


def test_read_progress_treats_a_slow_page_as_no_reading_not_as_a_crash():
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    from rtr_page import RtrPage

    class _Slow(_PlaywrightLikePage):
        def locator(self, sel):
            class _L:
                def inner_text(self, timeout=None):
                    raise PlaywrightTimeout("Locator.inner_text: Timeout 10000ms exceeded.")
            return _L()

    assert RtrPage(_Slow(), "https://h/p?SID=s").read_progress() is None


def test_read_progress_lets_real_crashes_propagate():
    from rtr_page import RtrPage

    class _Crashed(_PlaywrightLikePage):
        def locator(self, sel):
            class _L:
                def inner_text(self, timeout=None):
                    raise RuntimeError("Locator.inner_text: Target crashed")
            return _L()

    with pytest.raises(RuntimeError, match="crashed"):
        RtrPage(_Crashed(), "https://h/p?SID=s").read_progress()
