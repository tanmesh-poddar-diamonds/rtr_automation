import re
import time
from collections import deque

from playwright.sync_api import TimeoutError as PlaywrightTimeout

_PROGRESS = re.compile(r"(\d+)\s*\(\s*from\s*(\d+)\s*\)")
PANEL = "#user_img_frame"


class PanelError(RuntimeError):
    pass


def parse_progress(text: str | None) -> tuple[int, int] | None:
    m = _PROGRESS.search(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


class RtrPage:
    """The only module that knows the admin panel's selectors."""

    def __init__(self, page, base_url: str):
        self.page = page
        self.base_url = base_url
        self._downloads: deque = deque()
        # Playwright tags handlers with an attribute, so a builtin like deque.append won't do.
        page.on("download", lambda download: self._downloads.append(download))
        self._viewer_ready = False
        page.on("console", lambda msg: self._on_console(msg))

    # -- 3D viewer readiness --------------------------------------------
    def _on_console(self, msg) -> None:
        if "post init_3d" in (msg.text or ""):  # the page logs this when the model has loaded
            self._viewer_ready = True

    def reset_viewer_state(self) -> None:
        self._viewer_ready = False

    def wait_viewer_ready(self, timeout_s: float = 60) -> bool:
        waited = 0
        while not self._viewer_ready and waited < timeout_s * 1000:
            self.page.wait_for_timeout(500)
            waited += 500
        return self._viewer_ready

    # -- ring -----------------------------------------------------------
    def open_ring(self, label: str, timeout_s: int = 30) -> bool:
        self.reset_viewer_state()
        self.page.goto(f"{self.base_url}&ring_id={label}.glb",
                       wait_until="domcontentloaded", timeout=60_000)
        wanted = re.compile(re.escape(label), re.IGNORECASE)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for frame in self.page.frames:  # the title may live in the 3D iframe
                try:
                    if frame.get_by_text(wanted).first.is_visible():
                        return True
                except Exception:  # noqa: BLE001 - frame may be navigating
                    pass
            self.page.wait_for_timeout(500)
        return False

    # -- panel ----------------------------------------------------------
    def open_panel(self) -> None:
        if not self.wait_viewer_ready():
            raise PanelError("3D viewer did not finish loading")
        self.page.wait_for_timeout(1000)  # let the model settle
        self.page.get_by_role("button", name="Script_1", exact=True).click()
        try:
            self.page.locator(PANEL).wait_for(state="visible", timeout=15_000)
            self.page.locator("#user_img_carat").wait_for(state="visible", timeout=15_000)
        except PlaywrightTimeout as exc:
            raise PanelError("Script_1 panel did not open") from exc

    def set_carat(self, value: str) -> None:
        self.page.locator("#user_img_carat").fill(value)

    def select_only_shape(self, shape: str) -> None:
        boxes = self.page.locator(f"{PANEL} input[name=ch_cut_id]")
        names: dict[int, str] = {}
        for i in range(boxes.count()):
            idx = boxes.nth(i).get_attribute("index")
            name = self.page.locator(f"#cut_id_{idx}").get_attribute("value") or ""
            names[i] = name
        targets = [i for i, n in names.items() if n.lower() == shape.lower()]
        if not targets:
            raise PanelError(f"Shape {shape!r} not in panel; available: {sorted(names.values())}")
        for i in names:
            boxes.nth(i).set_checked(i == targets[0])

    def ensure_all_colours(self, shape: str) -> int:
        row = self.page.locator(f"#txt_{shape}")
        if not row.is_visible():
            self.page.locator(
                f"{PANEL} td.pls[onclick*='Show_List_Textures(\"{shape}\"']").click()
        sel = f"#txt_td_{shape} input[type=checkbox]"
        try:
            self.page.locator(sel).first.wait_for(state="visible", timeout=15_000)
        except PlaywrightTimeout as exc:
            raise PanelError(f"Colour list for {shape!r} did not appear") from exc
        return self.page.evaluate(
            """sel => { let n = 0;
                document.querySelectorAll(sel).forEach(c => { if (!c.checked) { c.click(); n++; } });
                return n; }""",
            sel,
        )

    def start_build(self) -> None:
        self.page.locator(PANEL).get_by_role("button", name="BUILD", exact=True).click()

    def stop_build(self) -> None:
        self.page.locator(PANEL).get_by_role("button", name="STOP", exact=True).click()

    # -- progress / downloads ------------------------------------------
    def read_progress(self) -> tuple[int, int] | None:
        """None when the counter is not readable right now (a busy page times out); a crashed
        page or browser raises and is handled by the caller."""
        try:
            return parse_progress(self.page.locator("body").inner_text(timeout=10_000))
        except PlaywrightTimeout:
            return None

    def drain_downloads(self) -> list:
        items = list(self._downloads)
        self._downloads.clear()
        return items

    def pump(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)
