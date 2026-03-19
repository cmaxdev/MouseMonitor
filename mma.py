"""
Auto input: generates mouse scroll and Alt+Tab at fixed random intervals.

- Mouse scroll: every 2–5 seconds (random interval each time)
- Alt+Tab: every 5–8 seconds (random interval); Tab is pressed several times while Alt is held
"""

import time
import threading
import random
import ctypes
from ctypes import wintypes


class AutoInput:
    def __init__(self):
        self.running = False
        self._worker_thread = None
        self.lock = threading.Lock()

        # Scroll every 2–5 s (random). Alt+Tab every 5–8 s (random).
        self._last_scroll_time = 0.0
        self._last_alt_tab_time = 0.0
        self._next_scroll_interval = 0.0
        self._next_alt_tab_interval = 0.0

        self.setup_windows_api()

    def setup_windows_api(self):
        """Setup Windows API for mouse scroll and keyboard via SendInput."""
        try:
            MOUSEEVENTF_WHEEL = 0x0800
            MOUSEEVENTF_HWHEEL = 0x1000
            WHEEL_DELTA = 120

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("dx", wintypes.LONG),
                    ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
                ]

            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
                ]

            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = [
                    ("uMsg", wintypes.DWORD),
                    ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD),
                ]

            class INPUT_UNION(ctypes.Union):
                _fields_ = [
                    ("mi", MOUSEINPUT),
                    ("ki", KEYBDINPUT),
                    ("hi", HARDWAREINPUT),
                ]

            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("union", INPUT_UNION),
                ]

            self.INPUT_MOUSE = 0
            self.INPUT_KEYBOARD = 1
            self.MOUSEEVENTF_WHEEL = MOUSEEVENTF_WHEEL
            self.MOUSEEVENTF_HWHEEL = MOUSEEVENTF_HWHEEL
            self.WHEEL_DELTA = WHEEL_DELTA
            self.KEYEVENTF_KEYUP = 0x0002
            self.INPUT_STRUCT = INPUT
            self.MOUSEINPUT_STRUCT = MOUSEINPUT
            self.KEYBDINPUT_STRUCT = KEYBDINPUT

            self.VK_MENU = 0x12
            self.VK_TAB = 0x09

            self.user32 = ctypes.windll.user32
            self.user32.SendInput.argtypes = [
                ctypes.c_uint,
                ctypes.POINTER(INPUT),
                ctypes.c_int,
            ]
            self.user32.SendInput.restype = ctypes.c_uint
            self.user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
            self.user32.MapVirtualKeyW.restype = ctypes.c_uint

            self.windows_api_available = True
        except Exception:
            self.windows_api_available = False

    def send_alt_tab(self, tab_presses=None):
        """
        Alt down, Tab down/up repeated several times (default: random 2–7), Alt up.
        """
        if not getattr(self, "windows_api_available", False):
            return False
        if tab_presses is None:
            tab_presses = random.randint(2, 7)
        tab_presses = max(1, int(tab_presses))

        try:
            null_ptr = ctypes.cast(0, ctypes.POINTER(wintypes.ULONG))
            KEYEVENTF_KEYUP = self.KEYEVENTF_KEYUP
            tab_scan = self.user32.MapVirtualKeyW(self.VK_TAB, 0)
            menu_scan = self.user32.MapVirtualKeyW(self.VK_MENU, 0)

            inputs = [
                self.KEYBDINPUT_STRUCT(self.VK_MENU, menu_scan, 0, 0, null_ptr),
            ]
            for _ in range(tab_presses):
                inputs.append(self.KEYBDINPUT_STRUCT(self.VK_TAB, tab_scan, 0, 0, null_ptr))
                inputs.append(
                    self.KEYBDINPUT_STRUCT(self.VK_TAB, tab_scan, KEYEVENTF_KEYUP, 0, null_ptr)
                )
            inputs.append(
                self.KEYBDINPUT_STRUCT(self.VK_MENU, menu_scan, KEYEVENTF_KEYUP, 0, null_ptr)
            )

            n = len(inputs)
            arr = (self.INPUT_STRUCT * n)()
            for i, ki in enumerate(inputs):
                arr[i].type = self.INPUT_KEYBOARD
                arr[i].union.ki = ki
            result = self.user32.SendInput(n, arr, ctypes.sizeof(self.INPUT_STRUCT))
            return result == n
        except Exception:
            return False

    def scroll_mouse(self, delta, horizontal=False):
        if not getattr(self, "windows_api_available", False):
            return False
        try:
            null_ptr = ctypes.cast(0, ctypes.POINTER(wintypes.ULONG))
            scroll_flag = self.MOUSEEVENTF_HWHEEL if horizontal else self.MOUSEEVENTF_WHEEL
            scroll_amount = int(delta * self.WHEEL_DELTA)
            mouse_input = self.MOUSEINPUT_STRUCT(
                dx=0,
                dy=0,
                mouseData=scroll_amount,
                dwFlags=scroll_flag,
                time=0,
                dwExtraInfo=null_ptr,
            )
            input_struct = self.INPUT_STRUCT()
            input_struct.type = self.INPUT_MOUSE
            input_struct.union.mi = mouse_input
            result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(self.INPUT_STRUCT))
            return result == 1
        except Exception:
            return False

    def _do_scroll(self):
        scroll_units = random.choice([1, 2, 3])
        scroll_direction = random.choice([-1, 1])
        is_horizontal = random.choice([False, True])
        return self.scroll_mouse(scroll_direction * scroll_units, horizontal=is_horizontal)

    def generation_loop(self):
        """Emit scroll on 2–5 s schedule and Alt+Tab on 5–8 s schedule (independent timers)."""
        with self.lock:
            now = time.time()
            self._last_scroll_time = now
            self._last_alt_tab_time = now
            self._next_scroll_interval = random.uniform(2, 5)
            self._next_alt_tab_interval = random.uniform(5, 8)

        while self.running:
            current_time = time.time()

            with self.lock:
                due_scroll = (current_time - self._last_scroll_time) >= self._next_scroll_interval
                due_alt = (current_time - self._last_alt_tab_time) >= self._next_alt_tab_interval

            if due_scroll:
                try:
                    self._do_scroll()
                    with self.lock:
                        self._last_scroll_time = time.time()
                        self._next_scroll_interval = random.uniform(2, 5)
                except Exception:
                    pass

            if due_alt:
                try:
                    self.send_alt_tab()
                    with self.lock:
                        self._last_alt_tab_time = time.time()
                        self._next_alt_tab_interval = random.uniform(5, 8)
                except Exception:
                    pass

            # Short sleep so stop() is responsive
            for _ in range(10):
                if not self.running:
                    break
                time.sleep(0.1)

    def start(self):
        if not self.windows_api_available:
            print("Error: Windows input API not available.")
            return
        self.running = True
        self._worker_thread = threading.Thread(target=self.generation_loop, daemon=True)
        self._worker_thread.start()
        print("Auto input running: scroll every 2–5 s, Alt+Tab every 5–8 s (Ctrl+C to stop)")

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)


def main():
    app = AutoInput()
    app.start()


if __name__ == "__main__":
    main()
