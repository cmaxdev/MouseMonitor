"""
Mouse Monitor and Auto-Mover

This script monitors mouse movement and automatically moves the mouse
if it remains idle for more than 30 seconds.
"""

import time
import threading
import random
import ctypes
from ctypes import wintypes
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController


class MouseMonitor:
    def __init__(self):
        self.mouse_controller = MouseController()
        self.last_position = None
        self.last_activity_time = time.time()  # Track last user activity (mouse or keyboard)
        self.check_interval = 5  # Check manual events every 5 seconds
        self.idle_threshold = 5  # 5 seconds of no activity before starting auto-movement
        self.auto_move_interval = 5  # Generate automatic events every 5 seconds
        self.is_auto_moving = False
        self.auto_move_thread = None
        self.running = True
        self.auto_move_event_ids = set()  # Track auto-generated movement event IDs
        self.auto_move_counter = 0  # Counter for unique auto-move IDs
        self.last_auto_position = None  # Track last auto-move position for detection
        self.last_auto_move_time = None  # Track when last auto-move occurred
        self.is_auto_move_in_progress = False  # Flag set during auto-movement
        
        # Mode switching for periodic frequent events
        self.frequent_mode = False  # When True, next event will wait 1 minute
        self.last_mode_switch_time = time.time()  # Track when mode was last switched
        self.next_mode_switch_interval = random.randint(30 * 60, 50 * 60)  # Next switch in 30-50 minutes (in seconds)
        
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
            self.KEYEVENTF_KEYUP = 0x0002
            self.INPUT_STRUCT = INPUT
            self.MOUSEINPUT_STRUCT = MOUSEINPUT
            self.KEYBDINPUT_STRUCT = KEYBDINPUT
            self.INPUT_UNION = INPUT_UNION
            
            # Virtual key codes for arrow keys
            self.VK_UP = 0x26
            self.VK_DOWN = 0x28
            self.VK_LEFT = 0x25
            self.VK_RIGHT = 0x27
            
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
        """Update activity time and stop auto-movement"""
        current_time = time.time()
        with self.lock:
            self.last_activity_time = current_time
            if self.is_auto_moving:
                self.is_auto_moving = False
    
    def on_move(self, x, y):
        """Callback function when mouse moves - distinguishes manual from automatic movements"""
        # Fast check without lock first
        if self.is_auto_move_in_progress:
            return
        
        current_time = time.time()
        
        # Quick check without lock for recent auto-move
        if self.last_auto_move_time and (current_time - self.last_auto_move_time) < 1.0:
            if self.last_auto_position:
                # Fast distance check without lock
                dx = x - self.last_auto_position[0]
                dy = y - self.last_auto_position[1]
                distance_sq = dx * dx + dy * dy
                # If very close to auto-move position and recent, likely auto-generated
                if distance_sq < 100:  # 10^2 = 100, avoiding sqrt for speed
                    return
        
        # Only acquire lock for real manual movements
        with self.lock:
            # Double-check auto-move flag (might have changed)
            if self.is_auto_move_in_progress:
                return
            
            # This is a REAL manual movement
            self.last_position = (x, y)
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
    
    def move_mouse_relative(self, dx, dy):
        """Move mouse using Windows API SendInput with relative movement (generates proper input events)"""
        if not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            return False
            
        try:
            # Create proper NULL pointer for dwExtraInfo
            null_ptr = ctypes.cast(0, ctypes.POINTER(wintypes.ULONG))
            
            # Use relative movement which generates proper WM_MOUSEMOVE messages
            # This creates actual Windows input events that applications like ManicTime can detect
            mouse_input = self.MOUSEINPUT_STRUCT(
                dx=int(round(dx)),
                dy=int(round(dy)),
                mouseData=0,
                dwFlags=self.MOUSEEVENTF_MOVE,  # Relative movement flag (not absolute)
                time=0,
                dwExtraInfo=null_ptr
            )
            
            # Create input structure with proper union initialization
            input_struct = self.INPUT_STRUCT()
            input_struct.type = self.INPUT_MOUSE
            input_struct.union.mi = mouse_input
            
            # Send the input - this generates proper Windows input events that system-wide hooks can detect
            # SendInput injects input at a low level, similar to physical mouse movement
            # This is what applications like ManicTime monitor to detect user activity
            result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(self.INPUT_STRUCT))
            return result == 1
        except Exception:
            return False
    
    def auto_move_mouse(self):
        """Automatically generate 1-pixel relative mouse movement via Windows SendInput (no wheel)."""
        with self.lock:
            if not self.is_auto_moving:
                return
        
        # Exactly one screen pixel per tick; cardinal directions only.
        pixel_directions = ((1, 0), (-1, 0), (0, 1), (0, -1))
        
        while self.is_auto_moving and self.running:
            # Check if we should continue
            with self.lock:
                if not self.is_auto_moving:
                    break
            
            # Check and update mode switching logic
            current_time = time.time()
            time_since_last_switch = current_time - self.last_mode_switch_time
            
            with self.lock:
                # Check if we need to switch to frequent mode (30-50 minutes passed)
                if not self.frequent_mode:
                    if time_since_last_switch >= self.next_mode_switch_interval:
                        # Time to switch to frequent mode for one event
                        self.frequent_mode = True
                        self.last_mode_switch_time = current_time
                        # Set next switch interval (will be reset after frequent mode event)
                        self.next_mode_switch_interval = random.randint(30 * 60, 50 * 60)
                
                # Determine current interval based on mode
                if self.frequent_mode:
                    wait_interval = 60  # 1 minute wait in frequent mode (only once)
                else:
                    wait_interval = self.auto_move_interval  # 5 seconds in normal mode
                
            try:
                dx, dy = random.choice(pixel_directions)
                self.is_auto_move_in_progress = True
                try:
                    success = self.move_mouse_relative(dx, dy)
                finally:
                    self.is_auto_move_in_progress = False
                
                if success:
                    final_pos = self.get_mouse_position()
                    event_time = time.time()
                    with self.lock:
                        self.last_auto_position = (final_pos[0], final_pos[1])
                        self.last_auto_move_time = event_time
                        self.last_position = self.last_auto_position
            except Exception:
                pass
            
            # If we just executed a frequent mode event, switch back to normal mode immediately
            with self.lock:
                if self.frequent_mode:
                    # Switch back to normal mode after the frequent mode event
                    self.frequent_mode = False
                    self.last_mode_switch_time = time.time()
                    # Set next switch interval
                    self.next_mode_switch_interval = random.randint(30 * 60, 50 * 60)  # Next switch in 30-50 minutes
            
            # Wait for the determined interval before next movement
            if self.is_auto_moving:
                # Sleep in small increments to allow for quick interruption
                elapsed = 0
                sleep_chunk = min(5, wait_interval)  # Check every 5 seconds max
                while elapsed < wait_interval and self.is_auto_moving:
                    time.sleep(sleep_chunk)
                    elapsed += sleep_chunk
                    if elapsed >= wait_interval:
                        break
    
    def start_auto_moving(self):
        """Start the auto-move thread"""
        with self.lock:
            if not self.is_auto_moving:
                self.is_auto_moving = True
                # Initialize tracking variables
                self.last_auto_position = None
                self.last_auto_move_time = None
                # Reset mode switching to start fresh
                self.frequent_mode = False
                self.last_mode_switch_time = time.time()
                self.next_mode_switch_interval = random.randint(30 * 60, 50 * 60)  # Next switch in 30-50 minutes
                
                if self.auto_move_thread is None or not self.auto_move_thread.is_alive():
                    self.auto_move_thread = threading.Thread(target=self.auto_move_mouse, daemon=True)
                    self.auto_move_thread.start()
    
    def stop_auto_moving(self):
        """Stop the auto-move thread"""
        with self.lock:
            if self.is_auto_moving:
                self.is_auto_moving = False
                self.is_auto_move_in_progress = False
                self.last_auto_position = None
                self.last_auto_move_time = None
    
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
        # Set up mouse listener for all mouse events
        mouse_listener = mouse.Listener(
            on_move=self.on_move,
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

