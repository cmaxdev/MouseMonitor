"""
Mouse Monitor and Auto-Mover

Monitors user activity (keyboard and mouse: clicks, scroll). After 15 seconds
with no user event, generates: mouse scroll every 3–8s (random) and Alt+Tab
every 10–15s (random).
"""

import time
import threading
import random
import ctypes
from ctypes import wintypes
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController

# Work around pynput crash on Python 3.13 / when Alt+Tab generates WM_SYSKEYDOWN:
# _convert raises NotImplementedError; the except block then calls self._handle, but
# threading.Thread has overwritten _handle with the OS thread handle → TypeError.
# Patch the win32 _handler so we never call the buggy fallback.
try:
    import pynput._util.win32 as _pynput_win32
    _orig_handler = _pynput_win32.ListenerMixin._handler
    def _handler_fixed(self, code, msg, lpdata):
        try:
            converted = self._convert(code, msg, lpdata)
            if converted is not None:
                self._message_loop.post(self._WM_PROCESS, *converted)
                if getattr(self, "suppress", False):
                    self.suppress_event()
        except NotImplementedError:
            pass  # Skip unknown messages; do not call self._handle (overwritten by Thread on 3.13)
    _pynput_win32.ListenerMixin._handler = _handler_fixed
except Exception:
    pass


class MouseMonitor:
    def __init__(self):
        self.mouse_controller = MouseController()
        self.last_position = None
        self.last_activity_time = time.time()  # Last user activity (keyboard or mouse click/scroll)
        self.check_interval = 5  # Check for user activity every 5 seconds
        self.idle_threshold = 15  # Start generating only after 15 seconds with no user event
        self.is_auto_moving = False
        self.auto_move_thread = None
        self.running = True
        
        # Scroll: every 3–8 seconds (random). Alt+Tab: every 10–15 seconds (random).
        self.last_scroll_time = 0.0
        self.last_alt_tab_time = 0.0
        self.next_scroll_interval = 0.0  # Set when thread starts
        self.next_alt_tab_interval = 0.0
        # Time of last event we caused (scroll/Alt+Tab); ignore such events in activity detection
        self._last_caused_event_time = 0.0
        self._caused_event_ignore_seconds = 0.5
        
        # Lock for thread-safe operations
        self.lock = threading.Lock()
        
        # Setup Windows API for proper mouse and keyboard input events
        self.setup_windows_api()
    
    def setup_windows_api(self):
        """Setup Windows API for generating proper mouse input events"""
        try:
            # Windows constants
            MOUSEEVENTF_MOVE = 0x0001
            MOUSEEVENTF_ABSOLUTE = 0x8000
            MOUSEEVENTF_WHEEL = 0x0800  # Vertical scroll
            MOUSEEVENTF_HWHEEL = 0x1000  # Horizontal scroll
            WHEEL_DELTA = 120  # Standard scroll unit
            
            # Define INPUT structure
            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("dx", wintypes.LONG),
                    ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
                ]
            
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
                ]
            
            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = [
                    ("uMsg", wintypes.DWORD),
                    ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)
                ]
            
            class INPUT_UNION(ctypes.Union):
                _fields_ = [
                    ("mi", MOUSEINPUT),
                    ("ki", KEYBDINPUT),
                    ("hi", HARDWAREINPUT)
                ]
            
            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("union", INPUT_UNION)
                ]
            
            # Store constants and structures
            self.INPUT_MOUSE = 0
            self.INPUT_KEYBOARD = 1
            self.MOUSEEVENTF_MOVE = MOUSEEVENTF_MOVE
            self.MOUSEEVENTF_ABSOLUTE = MOUSEEVENTF_ABSOLUTE
            self.MOUSEEVENTF_WHEEL = MOUSEEVENTF_WHEEL
            self.MOUSEEVENTF_HWHEEL = MOUSEEVENTF_HWHEEL
            self.WHEEL_DELTA = WHEEL_DELTA
            self.KEYEVENTF_KEYUP = 0x0002
            self.INPUT_STRUCT = INPUT
            self.MOUSEINPUT_STRUCT = MOUSEINPUT
            self.KEYBDINPUT_STRUCT = KEYBDINPUT
            self.INPUT_UNION = INPUT_UNION
            
            # Virtual key codes for arrow keys and modifiers
            self.VK_UP = 0x26
            self.VK_DOWN = 0x28
            self.VK_LEFT = 0x25
            self.VK_RIGHT = 0x27
            self.VK_MENU = 0x12   # Alt
            self.VK_TAB = 0x09    # Tab
            
            # Get user32.dll functions
            self.user32 = ctypes.windll.user32
            
            # Set up SendInput function signature
            self.user32.SendInput.argtypes = [
                ctypes.c_uint,  # nInputs
                ctypes.POINTER(INPUT),  # pInputs
                ctypes.c_int  # cbSize
            ]
            self.user32.SendInput.restype = ctypes.c_uint
            
            # Set up MapVirtualKey for scan code mapping
            self.user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
            self.user32.MapVirtualKeyW.restype = ctypes.c_uint
            
            # Set up GetCursorPos for low-level mouse position retrieval
            # POINT structure: x and y are LONG (signed 32-bit integers)
            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
            
            self.POINT = POINT
            # GetCursorPos expects LPPOINT (pointer to POINT)
            self.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
            self.user32.GetCursorPos.restype = ctypes.c_bool
            
            # Get screen size for absolute coordinate conversion
            self.screen_width = self.user32.GetSystemMetrics(0)  # SM_CXSCREEN
            self.screen_height = self.user32.GetSystemMetrics(1)  # SM_CYSCREEN
            
            self.windows_api_available = True
            
        except Exception as e:
            self.windows_api_available = False
    
    def on_activity(self):
        """Update activity time and stop auto-movement. Ignore events we caused (scroll/Alt+Tab)."""
        current_time = time.time()
        with self.lock:
            # Do not count our own generated events as user activity
            if self._last_caused_event_time and (current_time - self._last_caused_event_time) < self._caused_event_ignore_seconds:
                return
            self.last_activity_time = current_time
            if self.is_auto_moving:
                self.is_auto_moving = False
    
    def on_click(self, x, y, button, pressed):
        """Callback function when mouse is clicked"""
        if pressed:  # Only track button press, not release
            self.on_activity()
    
    def on_scroll(self, x, y, dx, dy):
        """Callback function when mouse wheel is scrolled"""
        self.on_activity()
    
    def on_key_press(self, key):
        """Callback function when a key is pressed"""
        # All keys trigger activity
        self.on_activity()
        return True  # Continue listening
    
    def get_mouse_position(self):
        """Get current mouse position using low-level Windows API GetCursorPos"""
        if not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            # Fallback to pynput only if Windows API unavailable
            try:
                pos = self.mouse_controller.position
                return (pos[0], pos[1])
            except Exception:
                return (0, 0)
        
        try:
            # Use low-level Windows API GetCursorPos
            point = self.POINT()
            # GetCursorPos expects a pointer to POINT structure
            if self.user32.GetCursorPos(ctypes.byref(point)):
                return (point.x, point.y)
            else:
                # If GetCursorPos returns False, return last known position or (0,0)
                if self.last_position:
                    return self.last_position
                return (0, 0)
        except Exception:
            # On error, return last known position or (0,0) - avoid pynput fallback to prevent conflicts
            if self.last_position:
                return self.last_position
            return (0, 0)
    
    def check_activity(self):
        """Check if there has been any user activity"""
        current_time = time.time()
        
        with self.lock:
            if self.last_position is None:
                current_position = self.get_mouse_position()
                self.last_position = current_position
                self.last_activity_time = current_time
                return False
            
            # Check if idle for too long
            idle_time = current_time - self.last_activity_time
            if idle_time >= self.idle_threshold and not self.is_auto_moving:
                return False  # User is idle, should start auto-moving
            elif idle_time < self.idle_threshold:
                return True  # User is active
        
        return False
    
    def send_alt_tab(self):
        """Send Alt+Tab with Tab pressed a random number of times (1 to 9) while Alt is held."""
        if not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            return False
        try:
            null_ptr = ctypes.cast(0, ctypes.POINTER(wintypes.ULONG))
            KEYEVENTF_KEYUP = self.KEYEVENTF_KEYUP
            tab_scan = self.user32.MapVirtualKeyW(self.VK_TAB, 0)
            menu_scan = self.user32.MapVirtualKeyW(self.VK_MENU, 0)
            # Sequence: Alt down, then Tab down/up × random count (1-9), then Alt up
            inputs = [
                self.KEYBDINPUT_STRUCT(self.VK_MENU, menu_scan, 0, 0, null_ptr),
            ]
            tab_count = random.randint(1, 9)
            for _ in range(tab_count):
                inputs.append(self.KEYBDINPUT_STRUCT(self.VK_TAB, tab_scan, 0, 0, null_ptr))
                inputs.append(self.KEYBDINPUT_STRUCT(self.VK_TAB, tab_scan, KEYEVENTF_KEYUP, 0, null_ptr))
            inputs.append(self.KEYBDINPUT_STRUCT(self.VK_MENU, menu_scan, KEYEVENTF_KEYUP, 0, null_ptr))
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
        """Scroll mouse wheel using Windows API SendInput (generates proper input events)"""
        if not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            return False
        
        try:
            # Create proper NULL pointer for dwExtraInfo
            null_ptr = ctypes.cast(0, ctypes.POINTER(wintypes.ULONG))
            
            # Determine scroll direction flag
            scroll_flag = self.MOUSEEVENTF_HWHEEL if horizontal else self.MOUSEEVENTF_WHEEL
            
            # mouseData contains the scroll amount (positive = up/right, negative = down/left)
            # WHEEL_DELTA (120) is one standard scroll unit
            scroll_amount = int(delta * self.WHEEL_DELTA)
            
            # Create mouse scroll input
            mouse_input = self.MOUSEINPUT_STRUCT(
                dx=0,
                dy=0,
                mouseData=scroll_amount,
                dwFlags=scroll_flag,
                time=0,
                dwExtraInfo=null_ptr
            )
            
            # Create input structure with proper union initialization
            input_struct = self.INPUT_STRUCT()
            input_struct.type = self.INPUT_MOUSE
            input_struct.union.mi = mouse_input
            
            # Send the input - this generates proper Windows input events
            result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(self.INPUT_STRUCT))
            return result == 1
        except Exception:
            return False
    
    def auto_move_mouse(self):
        """Generate scroll every 3–8s and Alt+Tab every 10–15s (random) while idle."""
        with self.lock:
            if not self.is_auto_moving:
                return
            self.last_scroll_time = time.time()
            self.last_alt_tab_time = time.time()
            self.next_scroll_interval = random.uniform(3, 8)
            self.next_alt_tab_interval = random.uniform(10, 15)

        while self.is_auto_moving and self.running:
            with self.lock:
                if not self.is_auto_moving:
                    break
            current_time = time.time()

            with self.lock:
                due_scroll = (current_time - self.last_scroll_time) >= self.next_scroll_interval
                due_alt_tab = (current_time - self.last_alt_tab_time) >= self.next_alt_tab_interval

            if due_scroll:
                try:
                    with self.lock:
                        self._last_caused_event_time = time.time()
                    scroll_units = random.choice([1, 2, 3])
                    scroll_direction = random.choice([-1, 1])
                    is_horizontal = random.choice([False, True])
                    self.scroll_mouse(scroll_direction * scroll_units, horizontal=is_horizontal)
                    with self.lock:
                        self.last_scroll_time = time.time()
                        self.next_scroll_interval = random.uniform(3, 8)
                except Exception:
                    pass

            if due_alt_tab:
                try:
                    with self.lock:
                        self._last_caused_event_time = time.time()
                    self.send_alt_tab()
                    with self.lock:
                        self.last_alt_tab_time = time.time()
                        self.next_alt_tab_interval = random.uniform(10, 15)
                except Exception:
                    pass

            # Check again every second so we stay responsive to stop
            if self.is_auto_moving:
                for _ in range(10):
                    if not self.is_auto_moving:
                        break
                    time.sleep(0.1)

    def start_auto_moving(self):
        """Start the auto-move thread"""
        with self.lock:
            if not self.is_auto_moving:
                self.is_auto_moving = True
                if self.auto_move_thread is None or not self.auto_move_thread.is_alive():
                    self.auto_move_thread = threading.Thread(target=self.auto_move_mouse, daemon=True)
                    self.auto_move_thread.start()
    
    def stop_auto_moving(self):
        """Stop the auto-move thread"""
        with self.lock:
            if self.is_auto_moving:
                self.is_auto_moving = False
    
    def monitor_loop(self):
        """Main monitoring loop - checks user activity status periodically"""
        while self.running:
            idle_time = time.time() - self.last_activity_time
            
            # Check if user needs auto-movement (no activity detected)
            if idle_time >= self.idle_threshold:
                if not self.is_auto_moving:
                    self.start_auto_moving()
            else:
                if self.is_auto_moving:
                    self.stop_auto_moving()
            
            # Wait for check interval
            time.sleep(self.check_interval)
    
    def start(self):
        """Start the activity monitor"""
        # Set up mouse listener (scroll and click only; no on_move to avoid movement resetting idle)
        mouse_listener = mouse.Listener(
            on_click=self.on_click,
            on_scroll=self.on_scroll
        )
        mouse_listener.start()
        
        # Set up keyboard listener for all key events
        keyboard_listener = keyboard.Listener(on_press=self.on_key_press, suppress=False)
        keyboard_listener.start()
        self.keyboard_listener = keyboard_listener  # Store reference
        
        # Start monitoring loop in a separate thread
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        
        print("Server Running: http://localhost:9001")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the mouse monitor"""
        self.running = False
        self.stop_auto_moving()


def main():
    monitor = MouseMonitor()
    monitor.start()


if __name__ == "__main__":
    main()

