"""
Mouse Monitor and Auto-Mover

This script monitors mouse movement and automatically moves the mouse
if it remains idle for more than 30 seconds.
"""

import time
import threading
import random
import logging
import os
import math
import ctypes
from ctypes import wintypes
from datetime import datetime
from pynput import mouse
from pynput.mouse import Controller as MouseController


class MouseMonitor:
    def __init__(self):
        self.mouse_controller = MouseController()
        self.last_position = None
        self.last_move_time = time.time()
        self.check_interval = 5  # Check every 10 seconds
        self.idle_threshold = 20  # 30 seconds of no movement
        self.auto_move_interval = 5  # Auto-move every 5 seconds
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
        
        # Setup logging first (needed for Windows API setup logging)
        self.setup_logging()
        
        # Setup Windows API for proper mouse input events
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
            self.MOUSEEVENTF_MOVE = MOUSEEVENTF_MOVE
            self.MOUSEEVENTF_ABSOLUTE = MOUSEEVENTF_ABSOLUTE
            self.INPUT_STRUCT = INPUT
            self.MOUSEINPUT_STRUCT = MOUSEINPUT
            self.INPUT_UNION = INPUT_UNION
            
            # Get user32.dll functions
            self.user32 = ctypes.windll.user32
            
            # Get screen size for absolute coordinate conversion
            self.screen_width = self.user32.GetSystemMetrics(0)  # SM_CXSCREEN
            self.screen_height = self.user32.GetSystemMetrics(1)  # SM_CYSCREEN
            
            self.windows_api_available = True
            if hasattr(self, 'logger'):
                self.logger.info("Windows API initialized for proper mouse input events")
            
        except Exception as e:
            self.windows_api_available = False
            if hasattr(self, 'logger'):
                self.logger.warning(f"Windows API initialization failed, will use fallback method: {e}")
            else:
                self._windows_api_error = str(e)
    
    def setup_logging(self):
        """Setup logging to both file and console"""
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create log file with timestamp
        log_filename = os.path.join(log_dir, f"mouse_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # Configure logging format
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Setup logger
        self.logger = logging.getLogger('MouseMonitor')
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(log_format, date_format)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"Logging initialized. Log file: {log_filename}")
        
        # Log Windows API initialization error if any
        if hasattr(self, '_windows_api_error'):
            self.logger.warning(f"Windows API initialization error: {self._windows_api_error}")
        elif not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            self.logger.warning("Windows API not available, mouse movements may not be detected by all applications")
    
    def on_move(self, x, y):
        """Callback function when mouse moves - distinguishes manual from automatic movements"""
        current_time = time.time()
        
        with self.lock:
            # First check: if auto-move is currently in progress, ignore all movements
            if self.is_auto_move_in_progress:
                self.logger.debug(f"Ignoring movement during auto-move: ({x}, {y})")
                return
            
            # Second check: if movement happened very recently after auto-move, verify it's not auto-generated
            is_auto_movement = False
            if self.last_auto_move_time and (current_time - self.last_auto_move_time) < 1.0:
                if self.last_auto_position:
                    distance = math.sqrt((x - self.last_auto_position[0])**2 + 
                                       (y - self.last_auto_position[1])**2)
                    # If very close to auto-move position and recent, likely auto-generated
                    if distance < 10:
                        is_auto_movement = True
                        self.logger.debug(f"Ignoring auto-generated movement at ({x}, {y}), distance: {distance:.1f}px")
            
            if not is_auto_movement:
                # This is a REAL manual movement
                self.last_position = (x, y)
                self.last_move_time = current_time
                
                # If auto-moving, stop it immediately (real user movement detected)
                if self.is_auto_moving:
                    self.logger.info(f"MANUAL mouse movement detected at ({x}, {y}). Stopping AUTO-movement.")
                    self.is_auto_moving = False
                else:
                    self.logger.debug(f"Manual mouse moved to ({x}, {y})")
    
    def check_mouse_position(self):
        """Check if mouse position has changed"""
        current_position = self.mouse_controller.position
        current_time = time.time()
        
        with self.lock:
            if self.last_position is None:
                self.last_position = current_position
                self.last_move_time = current_time
                return False
            
            # Check if position changed
            if current_position != self.last_position:
                self.last_position = current_position
                self.last_move_time = current_time
                return True
            
            # Check if idle for too long
            idle_time = current_time - self.last_move_time
            if idle_time >= self.idle_threshold and not self.is_auto_moving:
                return False  # Mouse is idle, should start auto-moving
            elif idle_time < self.idle_threshold:
                return True  # Mouse is active
        
        return False
    
    def move_mouse_relative(self, dx, dy):
        """Move mouse using Windows API SendInput with relative movement (generates proper input events)"""
        if not hasattr(self, 'windows_api_available') or not self.windows_api_available:
            return False
            
        try:
            # Create NULL pointer for dwExtraInfo
            null_ptr = ctypes.POINTER(wintypes.ULONG)()
            
            # Use relative movement which generates proper WM_MOUSEMOVE messages
            # This creates actual Windows input events that applications like ManicTime can detect
            mouse_input = self.MOUSEINPUT_STRUCT(
                dx=int(round(dx)),
                dy=int(round(dy)),
                mouseData=0,
                dwFlags=self.MOUSEEVENTF_MOVE,  # Relative movement flag (not absolute)
                time=0,
                dwExtraInfo=null_ptr  # NULL pointer
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
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error in move_mouse_relative: {e}", exc_info=True)
            return False
    
    def natural_move(self, start_x, start_y, end_x, end_y):
        """Move mouse with natural human-like acceleration and deceleration using Windows API"""
        # Set flag to indicate auto-move in progress
        with self.lock:
            self.is_auto_move_in_progress = True
        
        try:
            # Get current position first (might differ from start_x, start_y)
            current_pos = self.mouse_controller.position
            current_x, current_y = current_pos[0], current_pos[1]
            
            # Calculate total distance to move
            total_dx = end_x - current_x
            total_dy = end_y - current_y
            distance = math.sqrt(total_dx**2 + total_dy**2)
            
            # Adjust steps based on distance for natural movement
            base_steps = max(20, int(distance / 6))
            
            # Add some randomness to make it more human-like
            steps = base_steps + random.randint(-4, 4)
            steps = max(15, min(steps, 40))
            
            dx_per_step = total_dx / steps
            dy_per_step = total_dy / steps
            
            for i in range(1, steps + 1):
                if not self.is_auto_moving:
                    break
                
                # Calculate relative movement for this step
                step_dx = dx_per_step
                step_dy = dy_per_step
                
                # Add tiny random micro-movements for more natural feel
                step_dx += random.uniform(-0.5, 0.5)
                step_dy += random.uniform(-0.5, 0.5)
                
                try:
                    # Use Windows API for proper input events
                    success = self.move_mouse_relative(step_dx, step_dy)
                    
                    if not success:
                        # Fallback to pynput if Windows API fails
                        new_x = current_x + (dx_per_step * i)
                        new_y = current_y + (dy_per_step * i)
                        self.mouse_controller.position = (int(new_x), int(new_y))
                    
                    # Update current position estimate
                    current_x += step_dx
                    current_y += step_dy
                    
                    # Vary speed like a human would - faster in middle, slower at start/end
                    if i < steps * 0.15 or i > steps * 0.85:
                        time.sleep(0.010)  # Slower at start/end
                    else:
                        time.sleep(0.006)  # Faster in middle
                        
                except Exception as e:
                    self.logger.error(f"Error in natural move: {e}", exc_info=True)
                    break
        finally:
            # Clear flag when done
            with self.lock:
                self.is_auto_move_in_progress = False
    
    def auto_move_mouse(self):
        """Automatically move mouse with random distances and directions"""
        # Get starting position
        with self.lock:
            if not self.is_auto_moving:
                return
            start_pos = self.mouse_controller.position
        
        # Random distance range (in pixels)
        min_distance = 100  # Minimum movement distance
        max_distance = 600  # Maximum movement distance
        
        move_count = 0
        
        self.logger.info(f"Starting AUTO-movement from ({start_pos[0]}, {start_pos[1]})")
        self.logger.info(f"Random distance range: {min_distance}-{max_distance} pixels")
        
        while self.is_auto_moving and self.running:
            # Check if we should continue
            with self.lock:
                if not self.is_auto_moving:
                    break
            
            try:
                # Get current position before moving
                current_pos = self.mouse_controller.position
                current_x, current_y = current_pos[0], current_pos[1]
                
                # Generate completely random distance for this movement
                distance = random.randint(min_distance, max_distance)
                
                # Generate completely random direction (0 to 2π radians)
                angle = random.uniform(0, 2 * math.pi)
                
                # Calculate new position with random distance and direction
                new_x = current_x + distance * math.cos(angle)
                new_y = current_y + distance * math.sin(angle)
                
                # Get screen dimensions to ensure we stay within bounds (optional safety check)
                # For now, we'll just use the calculated position
                
                # Add small random offset for even more natural variation
                new_x += random.randint(-10, 10)
                new_y += random.randint(-10, 10)
                
                # Natural smooth movement to new position
                self.natural_move(current_x, current_y, new_x, new_y)
                
                move_count += 1
                
                # Update tracking variables for manual movement detection
                with self.lock:
                    final_pos = self.mouse_controller.position
                    self.last_auto_position = (final_pos[0], final_pos[1])
                    self.last_auto_move_time = time.time()
                    self.last_position = self.last_auto_position
                    self.last_move_time = self.last_auto_move_time
                
                # Log movement details
                actual_distance = math.sqrt((final_pos[0] - current_x)**2 + (final_pos[1] - current_y)**2)
                if move_count % 3 == 0:  # Log every 3rd move
                    self.logger.info(f"AUTO-moved: distance={actual_distance:.0f}px, angle={math.degrees(angle):.0f}°, to ({self.last_auto_position[0]:.0f}, {self.last_auto_position[1]:.0f})")
                
            except Exception as e:
                self.logger.error(f"Error in auto-move: {e}", exc_info=True)
            
            # Wait for auto-move interval before next movement
            if self.is_auto_moving:
                # Add slight randomness to timing for more natural feel
                sleep_time = self.auto_move_interval + random.uniform(-0.5, 0.5)
                time.sleep(max(2.0, sleep_time))
    
    def start_auto_moving(self):
        """Start the auto-move thread"""
        with self.lock:
            if not self.is_auto_moving:
                self.is_auto_moving = True
                idle_time = time.time() - self.last_move_time
                # Initialize tracking variables
                self.last_auto_position = None
                self.last_auto_move_time = None
                self.logger.warning(f"Starting AUTO-movement (mouse idle for {idle_time:.1f} seconds, threshold: {self.idle_threshold}s)")
                
                if self.auto_move_thread is None or not self.auto_move_thread.is_alive():
                    self.auto_move_thread = threading.Thread(target=self.auto_move_mouse, daemon=True)
                    self.auto_move_thread.start()
                    self.logger.debug("Auto-move thread started")
                else:
                    self.logger.debug("Auto-move thread already running")
    
    def stop_auto_moving(self):
        """Stop the auto-move thread"""
        with self.lock:
            if self.is_auto_moving:
                self.is_auto_moving = False
                self.is_auto_move_in_progress = False
                self.last_auto_position = None
                self.last_auto_move_time = None
                self.logger.info("Stopping AUTO-movement")
    
    def monitor_loop(self):
        """Main monitoring loop - checks mouse status every 10 seconds"""
        self.logger.info("Mouse monitor started. Checking mouse position every 10 seconds...")
        self.logger.info(f"Auto-movement will start if mouse is idle for {self.idle_threshold} seconds.")
        
        check_count = 0
        while self.running:
            check_count += 1
            idle_time = time.time() - self.last_move_time
            
            self.logger.debug(f"Check #{check_count}: Mouse idle for {idle_time:.1f} seconds")
            
            # Check if mouse needs auto-movement
            if idle_time >= self.idle_threshold:
                if not self.is_auto_moving:
                    self.start_auto_moving()
            else:
                if self.is_auto_moving:
                    self.stop_auto_moving()
            
            # Wait for check interval
            time.sleep(self.check_interval)
    
    def start(self):
        """Start the mouse monitor"""
        self.logger.info("=" * 50)
        self.logger.info("Initializing Mouse Monitor")
        self.logger.info("=" * 50)
        
        # Set up mouse listener for real-time movement detection
        listener = mouse.Listener(on_move=self.on_move)
        listener.start()
        self.logger.debug("Mouse listener started")
        
        # Start monitoring loop in a separate thread
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        self.logger.debug("Monitor thread started")
        
        self.logger.info("\nMouse monitor is running. Press Ctrl+C to stop.\n")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("\n\nKeyboard interrupt received. Stopping mouse monitor...")
            self.stop()
    
    def stop(self):
        """Stop the mouse monitor"""
        self.logger.info("Stopping mouse monitor...")
        self.running = False
        self.stop_auto_moving()
        self.logger.info("Mouse monitor stopped.")
        self.logger.info("=" * 50)


def main():
    monitor = MouseMonitor()
    monitor.start()


if __name__ == "__main__":
    main()

