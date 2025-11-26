"""
Mouse Monitor and Auto-Mover

This script monitors mouse movement and automatically moves the mouse
if it remains idle for more than 30 seconds.
"""

import time
import threading
import random
import math
import ctypes
from ctypes import wintypes
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController


class MouseMonitor:
    def __init__(self):
        self.mouse_controller = MouseController()
        self.last_position = None
        self.last_activity_time = time.time()  # Track last user activity (mouse or keyboard)
        self.check_interval = 10  # Check manual events every 10 seconds
        self.idle_threshold = 20  # 20 seconds of no activity
        self.auto_move_interval = 5  # Generate automatic events every 5 seconds
        self.is_auto_moving = False
        self.auto_move_thread = None
        self.running = True
        self.auto_move_event_ids = set()  # Track auto-generated movement event IDs
        self.auto_move_counter = 0  # Counter for unique auto-move IDs
        self.last_auto_position = None  # Track last auto-move position for detection
        self.last_auto_move_time = None  # Track when last auto-move occurred
        self.is_auto_move_in_progress = False  # Flag set during auto-movement
        
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
    
    def check_activity(self):
        """Check if there has been any user activity"""
        current_time = time.time()
        
        with self.lock:
            if self.last_position is None:
                current_position = self.mouse_controller.position
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
            # Create NULL pointer for dwExtraInfo (reuse to avoid recreation)
            if not hasattr(self, '_null_ptr'):
                self._null_ptr = ctypes.POINTER(wintypes.ULONG)()
            
            # Use relative movement which generates proper WM_MOUSEMOVE messages
            # This creates actual Windows input events that applications like ManicTime can detect
            mouse_input = self.MOUSEINPUT_STRUCT(
                dx=int(round(dx)),
                dy=int(round(dy)),
                mouseData=0,
                dwFlags=self.MOUSEEVENTF_MOVE,  # Relative movement flag (not absolute)
                time=0,
                dwExtraInfo=self._null_ptr  # NULL pointer
            )
            
            input_union = self.INPUT_UNION(mi=mouse_input)
            input_struct = self.INPUT_STRUCT(
                type=self.INPUT_MOUSE,
                union=input_union
            )
            
            # Send the input - this generates proper Windows input events that system-wide hooks can detect
            # SendInput injects input at a low level, similar to physical mouse movement
            # This is what applications like ManicTime monitor to detect user activity
            result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(self.INPUT_STRUCT))
            return result == 1
        except Exception:
            return False
    
    def press_key(self, vk_code):
        """Press and release a key using Windows API SendInput (generates proper input events)"""
        if not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            return False
        
        try:
            # Create NULL pointer for dwExtraInfo
            null_ptr = ctypes.cast(None, ctypes.POINTER(wintypes.ULONG))
            
            # Create key press input
            key_press = self.KEYBDINPUT_STRUCT()
            key_press.wVk = vk_code
            key_press.wScan = 0
            key_press.dwFlags = 0  # Key press (not release)
            key_press.time = 0
            key_press.dwExtraInfo = null_ptr
            
            # Create key release input
            key_release = self.KEYBDINPUT_STRUCT()
            key_release.wVk = vk_code
            key_release.wScan = 0
            key_release.dwFlags = self.KEYEVENTF_KEYUP  # Key release
            key_release.time = 0
            key_release.dwExtraInfo = null_ptr
            
            # Create input structures
            input_press = self.INPUT_STRUCT()
            input_press.type = self.INPUT_KEYBOARD
            input_press.union.ki = key_press
            
            input_release = self.INPUT_STRUCT()
            input_release.type = self.INPUT_KEYBOARD
            input_release.union.ki = key_release
            
            # Send press first
            result1 = self.user32.SendInput(1, ctypes.byref(input_press), ctypes.sizeof(self.INPUT_STRUCT))
            if result1 != 1:
                return False
            
            time.sleep(0.02)  # Small delay between press and release
            
            # Send release
            result2 = self.user32.SendInput(1, ctypes.byref(input_release), ctypes.sizeof(self.INPUT_STRUCT))
            
            return result2 == 1
        except Exception as e:
            return False
    
    def press_arrow_key(self):
        """Press a random arrow key (up, down, left, right)"""
        arrow_keys = [self.VK_UP, self.VK_DOWN, self.VK_LEFT, self.VK_RIGHT]
        selected_key = random.choice(arrow_keys)
        return self.press_key(selected_key)
    
    def natural_move(self, start_x, start_y, end_x, end_y):
        """Move mouse smoothly using Windows API with smooth interpolation"""
        # Set flag atomically (boolean assignment is atomic in Python)
        self.is_auto_move_in_progress = True
        
        try:
            # Get current position first (might differ from start_x, start_y)
            current_pos = self.mouse_controller.position
            current_x, current_y = current_pos[0], current_pos[1]
            
            # Calculate total distance to move
            total_dx = end_x - current_x
            total_dy = end_y - current_y
            distance = math.sqrt(total_dx * total_dx + total_dy * total_dy)
            
            if distance < 1:
                # Already at target, skip
                return
            
            # Calculate optimal number of steps for smooth movement
            # More steps for smoother movement
            if distance < 50:
                steps = 8
            elif distance < 150:
                steps = 12
            elif distance < 300:
                steps = 18
            else:
                steps = 25
            
            # Smooth interpolation using ease-in-out curve
            prev_t = 0.0
            for i in range(1, steps + 1):
                if not self.is_auto_moving:
                    break
                
                # Ease-in-out interpolation (smooth start and end)
                t = i / steps
                # Cubic ease-in-out: t^2 * (3 - 2*t)
                eased_t = t * t * (3.0 - 2.0 * t)
                
                # Calculate the portion of movement for this step
                step_portion = eased_t - prev_t
                prev_t = eased_t
                
                # Calculate relative movement for this step
                step_dx = total_dx * step_portion
                step_dy = total_dy * step_portion
                
                # Skip if movement is too small
                if abs(step_dx) < 0.1 and abs(step_dy) < 0.1:
                    continue
                
                try:
                    # Use Windows API for proper input events
                    success = self.move_mouse_relative(step_dx, step_dy)
                    
                    if not success:
                        # Fallback to pynput if Windows API fails
                        new_x = current_x + step_dx
                        new_y = current_y + step_dy
                        self.mouse_controller.position = (int(new_x), int(new_y))
                    
                    # Update current position estimate
                    current_x += step_dx
                    current_y += step_dy
                    
                    # Small delay for smooth rendering
                    if i < steps:
                        time.sleep(0.003)  # 3ms delay for smoother movement
                        
                except Exception:
                    break
        finally:
            # Clear flag atomically when done
            self.is_auto_move_in_progress = False
    
    def auto_move_mouse(self):
        """Automatically generate complex events (mouse and/or keyboard randomly)"""
        # Get starting position
        with self.lock:
            if not self.is_auto_moving:
                return
            start_pos = self.mouse_controller.position
        
        # Random distance range (in pixels) - reduced for smaller, more subtle movements
        min_distance = 30  # Minimum movement distance
        max_distance = 120  # Maximum movement distance
        
        move_count = 0
        
        while self.is_auto_moving and self.running:
            # Check if we should continue
            with self.lock:
                if not self.is_auto_moving:
                    break
            
            try:
                # Always use complex events: randomly decide between both, mouse only, or keyboard only
                choice = random.choice(['both', 'mouse', 'keyboard'])
                do_mouse = False
                do_keyboard = False
                
                if choice == 'both':
                    do_mouse = True
                    do_keyboard = True
                elif choice == 'mouse':
                    do_mouse = True
                else:
                    do_keyboard = True
                
                # Perform mouse movement if needed
                if do_mouse:
                    current_pos = self.mouse_controller.position
                    current_x, current_y = current_pos[0], current_pos[1]
                    
                    # Generate random distance - reduced range for smaller movements
                    distance = random.randint(min_distance, max_distance)
                    
                    # Generate completely random direction (0 to 2π radians)
                    angle = random.uniform(0, 2 * math.pi)
                    
                    # Calculate new position with random distance and direction
                    new_x = current_x + distance * math.cos(angle)
                    new_y = current_y + distance * math.sin(angle)
                    
                    # Add small random offset for even more natural variation
                    new_x += random.randint(-5, 5)
                    new_y += random.randint(-5, 5)
                    
                    # Natural smooth movement to new position
                    self.natural_move(current_x, current_y, new_x, new_y)
                    
                    # Update tracking variables for manual movement detection (minimal lock time)
                    final_pos = self.mouse_controller.position
                    current_time = time.time()
                    with self.lock:
                        self.last_auto_position = (final_pos[0], final_pos[1])
                        self.last_auto_move_time = current_time
                        self.last_position = self.last_auto_position
                
                # Perform keyboard press if needed
                if do_keyboard:
                    # Small delay if both actions to make it more natural
                    if do_mouse:
                        time.sleep(0.05)  # Reduced from 0.1 to 0.05
                    success = self.press_arrow_key()
                
                move_count += 1
                
            except Exception:
                pass
            
            # Wait for auto-move interval before next movement (exactly 5 seconds)
            if self.is_auto_moving:
                time.sleep(self.auto_move_interval)
    
    def start_auto_moving(self):
        """Start the auto-move thread"""
        with self.lock:
            if not self.is_auto_moving:
                self.is_auto_moving = True
                # Initialize tracking variables
                self.last_auto_position = None
                self.last_auto_move_time = None
                
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

