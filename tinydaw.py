import curses
import os
import time
import logging
from curses import wrapper
from enum import Enum, auto

# Setup logging
logging.basicConfig(filename='tinydaw.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Try importing pygame for audio support
try:
    pygame = __import__('pygame')
    AUDIO_ENABLED = True
except ImportError:
    pygame = None
    AUDIO_ENABLED = False
    logging.warning("Pygame not found, audio disabled.")

MAX_CHANNELS = 8
GATE_THRESHOLD = 0.5  # Seconds without input to consider key released

class Mode(Enum):
    CHANNEL_VIEW = auto()
    CHANNEL_ASSIGN = auto()

class TriggerMode(Enum):
    ONESHOT = auto()
    GATE = auto()
    RETRIGGER = auto()

    def __str__(self):
        return self.name

class Channel:
    def __init__(self, index):
        self.index = index
        self.file_path = None
        self.assigned_key = None  # Integer keycode
        self.assigned_char = "-"  # Display char
        self.sound = None
        self.name = "Empty"
        self.trigger_mode = TriggerMode.ONESHOT
        self.volume = 1.0
        
        # State for Gate mode
        self.last_triggered_time = 0.0
        self.is_gated_playing = False

    def assign_file(self, path):
        if not path:
            return False, "No path provided"
        if not os.path.exists(path):
            return False, "File not found"
        
        # Explicit check for pygame and AUDIO_ENABLED to satisfy linters
        if AUDIO_ENABLED and pygame is not None:
            try:
                self.sound = pygame.mixer.Sound(path)
                self.sound.set_volume(self.volume) # Ensure volume is up
                logging.info(f"Loaded sound for Channel {self.index}: {path}")
            except Exception as e:
                logging.error(f"Error loading sound: {e}")
                return False, f"Audio Error: {str(e)}"
        
        self.file_path = path
        self.name = os.path.basename(path)
        return True, "assigned"

    def assign_key(self, key):
        self.assigned_key = key
        try:
            self.assigned_char = chr(key).upper()
        except ValueError:
            self.assigned_char = "?"
        logging.info(f"Channel {self.index} assigned key {key} ({self.assigned_char})")

    def toggle_mode(self):
        """Cycles through trigger modes."""
        # Reset gate state to prevent persistence bugs when switching back to GATE
        if self.is_gated_playing:
            self.is_gated_playing = False
            # self.sound.stop() # Optional safety

        modes = list(TriggerMode)
        current_idx = modes.index(self.trigger_mode)
        next_idx = (current_idx + 1) % len(modes)
        self.trigger_mode = modes[next_idx]
        logging.info(f"Channel {self.index} switched to {self.trigger_mode}")
        return self.trigger_mode
    
    def adjust_volume(self, delta):
        self.volume = max(0.0, min(1.0, self.volume + delta))
        if self.sound:
            self.sound.set_volume(self.volume)
        logging.debug(f"Channel {self.index} volume: {self.volume:.2f}")

    def trigger(self):
        """Called when the key is pressed (or held)."""
        if not self.sound:
            return

        now = time.time()
        logging.debug(f"Triggering Channel {self.index} in {self.trigger_mode}")

        if self.trigger_mode == TriggerMode.ONESHOT:
            # Standard polyphonic playback
            ch = self.sound.play()
            if ch is None:
                logging.warning(f"Channel {self.index}: No open mixer channels to play sound!")
        
        elif self.trigger_mode == TriggerMode.RETRIGGER:
            # Monophonic playback (restart)
            self.sound.stop()
            self.sound.play()

        elif self.trigger_mode == TriggerMode.GATE:
            self.last_triggered_time = now
            if not self.is_gated_playing:
                # Start playing
                logging.debug("Gate Start")
                self.sound.play() 
                self.is_gated_playing = True

    def update_gate(self):
        """Called periodically to check gate status."""
        if self.trigger_mode == TriggerMode.GATE and self.is_gated_playing:
            if time.time() - self.last_triggered_time > GATE_THRESHOLD:
                if self.sound:
                    self.sound.stop() # Use stop instead of fadeout to avoid potential volume persistence bugs
                self.is_gated_playing = False
                logging.debug(f"Channel {self.index} Gate Stop")

def get_text_input(stdscr, y, x, prompt_text, width=40):
    """Simple text input helper."""
    curses.echo()
    curses.curs_set(1)
    stdscr.addstr(y, x, prompt_text)
    stdscr.refresh()
    
    stdscr.nodelay(False)
    input_bytes = stdscr.getstr(y, x + len(prompt_text), width)
    stdscr.nodelay(True)
    
    curses.noecho()
    curses.curs_set(0)
    return input_bytes.decode('utf-8').strip()

def draw_fader(stdscr, x, y_start, height, value, is_selected):
    """Draws a vertical ASCII fader."""
    # Scale value (0.0-1.0) to height
    # Handle position from bottom (0 to height-1)
    handle_pos = int(value * (height - 1))
    
    # Draw track
    for i in range(height):
        y = y_start + (height - 1) - i # Draw from bottom up
        char = '|'
        
        if i == handle_pos:
            char = '[#]' if is_selected else '[=]'
        elif i < handle_pos:
            char = ' | '
        else:
            char = ' | ' # Above handle
            
        try:
            # Add some color to fader
            attr = curses.A_REVERSE if (i == handle_pos and is_selected) else curses.color_pair(1)
            # Center the char in a 3-wide column
            if char.startswith('['): # handle
                stdscr.addstr(y, x, char, attr)
            else:
                stdscr.addstr(y, x, char, curses.color_pair(1) | curses.A_DIM)
        except curses.error:
            pass
            
    # Draw Value below
    try:
        val_str = f"{int(value*100):3}"
        stdscr.addstr(y_start + height, x, val_str, curses.color_pair(1))
    except curses.error:
        pass

def draw_interface(stdscr, mode: Mode, channels, selected_idx, message=""):
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    # Border
    stdscr.border()

    # Title
    title = " tinydaw alpha "
    if AUDIO_ENABLED:
        title += "(Audio: ON) "
    else:
        title += "(Audio: OFF) "

    if len(title) < width:
        stdscr.addstr(0, (width//2) - (len(title)//2), title, curses.color_pair(1) | curses.A_BOLD)

    content_start_y = 2
    
    if mode == Mode.CHANNEL_VIEW:
        stdscr.addstr(1, 2, "MIXER VIEW - Press keys to play, Arrow Keys to Mix", curses.A_BOLD)
        
        # Calculate Mixer Layout
        # 8 Channels
        # Available width per channel
        
        # Cap column width to keep faders reasonably roughly together on wide screens
        col_width = (width - 4) // MAX_CHANNELS
        if col_width > 14: col_width = 14
        
        fader_height = height - 8 # Dynamic height, leave room for headers/footers
        if fader_height < 5: fader_height = 5 # Min height
        
        # Center the entire block
        total_width = col_width * MAX_CHANNELS
        start_x = (width - total_width) // 2
        start_y = 4
        
        for i, ch in enumerate(channels):
            # Column X start
            col_x = start_x + (i * col_width)
            
            # Center content within the column
            # Content is roughly 3 characters wide (Fader "[=]", Header "CH1")
            content_offset = (col_width - 3) // 2
            draw_x = col_x + content_offset
            
            # Highlight header if selected
            header_attr = curses.A_REVERSE if (i == selected_idx) else curses.A_UNDERLINE
            
            # Header: CH Number
            stdscr.addstr(start_y - 2, draw_x, f"CH{i+1}", header_attr)
            
            # Subheader: Key
            stdscr.addstr(start_y - 1, draw_x, f"[{ch.assigned_char}]", curses.color_pair(1))
            
            # Draw Fader
            draw_fader(stdscr, draw_x, start_y, fader_height, ch.volume, i == selected_idx)
            
            # Footer: Filename (truncated)
            name = ch.name
            # Center text or left align within column?
            # Truncate to col_width to prevent overlap
            if len(name) > col_width - 1:
                name = name[:col_width - 1]
            
            # Center filename visual
            name_x = col_x + max(0, (col_width - len(name)) // 2)
            stdscr.addstr(start_y + fader_height + 1, name_x, name, curses.A_DIM)

    elif mode == Mode.CHANNEL_ASSIGN:
        stdscr.addstr(1, 2, "ASSIGN MODE - Sel. Channel, (F)ile, (K)ey, (T)rigger", curses.A_BOLD)
        
        for i, ch in enumerate(channels):
            y_pos = content_start_y + i
            if y_pos >= height - 2: break
            
            prefix = "> " if i == selected_idx else "  "
            style = curses.A_REVERSE if i == selected_idx else curses.A_NORMAL
            
            # Display full info
            line = f"{prefix}CH {i+1}: Key=[{ch.assigned_char}] Vol={int(ch.volume*100)}% Mode={ch.trigger_mode.name} File={ch.name}"
            # Truncate content for display
            if len(line) > width - 4:
                line = line[:width-4] + "..."
            
            stdscr.addstr(y_pos, 4, line, style)

    # Message/Status Bar
    if message:
        try:
            stdscr.addstr(height-3, 2, f"Use: {message}", curses.color_pair(2))
        except curses.error:
            pass

    # Instructions
    instr = ""
    if mode == Mode.CHANNEL_VIEW:
         instr = "[Arrow Keys: Mix] [F2: Assign] [Q: Quit]"
    elif mode == Mode.CHANNEL_ASSIGN:
        instr = "[Up/Down: Nav] [F: File] [K: Key] [T: Mode] [F1: Mixer]"
    
    try:
        stdscr.addstr(height-2, 2, instr[:width-3], curses.color_pair(1))
    except curses.error:
        pass

    stdscr.refresh()

def main(stdscr):
    logging.info("Starting tinydaw")
    
    # Setup Audio
    if AUDIO_ENABLED and pygame is not None:
        try:
            # Pre-init to ensure standard audio settings
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32) # Increased from MAX*2 to 32 to ensure plenty of polyphony
            logging.info("Audio initialized")
        except Exception as e:
            logging.error(f"Audio init failed: {e}")
            pass

    # Setup Curses
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1) 
    stdscr.bkgd(' ', curses.color_pair(1))
    
    stdscr.nodelay(True)
    
    # App State
    current_mode = Mode.CHANNEL_VIEW
    channels = [Channel(i) for i in range(MAX_CHANNELS)]
    # Use separate selection indices for View and Assign modes? 
    # Or shared? Shared feels natural.
    selected_idx = 0 
    status_msg = ""

    draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)
    
    while True:
        try:
            time.sleep(0.01)
            key = stdscr.getch()
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt")
            break

        should_redraw = False
        
        # Handle Gate Maintenance every loop
        for ch in channels:
            ch.update_gate()

        # Input Handling
        if key != -1:
            status_msg = "" 

            # Global Keys
            if key == curses.KEY_F1:
                current_mode = Mode.CHANNEL_VIEW
                should_redraw = True
            elif key == curses.KEY_F2:
                current_mode = Mode.CHANNEL_ASSIGN
                should_redraw = True
            elif key in (ord('q'), ord('Q')):
                break
            
            # Mode Specific Input
            if current_mode == Mode.CHANNEL_VIEW:
                # Triggers from keys
                for ch in channels:
                    if ch.assigned_key == key:
                        ch.trigger()
                        # Redraw not strictly needed for audio, but maybe visuals later
                
                # Mixer Navigation
                if key == curses.KEY_LEFT:
                    selected_idx = max(0, selected_idx - 1)
                    should_redraw = True
                elif key == curses.KEY_RIGHT:
                    selected_idx = min(MAX_CHANNELS - 1, selected_idx + 1)
                    should_redraw = True
                elif key == curses.KEY_UP:
                    channels[selected_idx].adjust_volume(0.05) # +5%
                    should_redraw = True
                elif key == curses.KEY_DOWN:
                    channels[selected_idx].adjust_volume(-0.05) # -5%
                    should_redraw = True

            elif current_mode == Mode.CHANNEL_ASSIGN:
                if key == curses.KEY_UP:
                    selected_idx = max(0, selected_idx - 1)
                    should_redraw = True
                elif key == curses.KEY_DOWN:
                    selected_idx = min(MAX_CHANNELS - 1, selected_idx + 1)
                    should_redraw = True
                
                # Assign File
                elif key in (ord('f'), ord('F')):
                    path = get_text_input(stdscr, stdscr.getmaxyx()[0]-3, 2, "Path: ")
                    if path:
                        success, msg = channels[selected_idx].assign_file(path)
                        status_msg = msg
                    should_redraw = True

                # Assign Key
                elif key in (ord('k'), ord('K')):
                    status_msg = "Press a key to assign..."
                    stdscr.nodelay(False) 
                    draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)
                    new_key = stdscr.getch()
                    stdscr.nodelay(True) 
                    
                    if new_key not in (curses.KEY_F1, curses.KEY_F2, 27): 
                        channels[selected_idx].assign_key(new_key)
                        status_msg = f"Key assigned to {channels[selected_idx].assigned_char}"
                    else:
                        status_msg = "Cancelled"
                    should_redraw = True
                
                # Toggle Trigger Mode
                elif key in (ord('t'), ord('T')):
                    new_mode = channels[selected_idx].toggle_mode()
                    status_msg = f"Mode set to {new_mode.name}"
                    should_redraw = True

        if should_redraw:
            draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)

if __name__ == "__main__":
    try:
        wrapper(main)
    except Exception as e:
        logging.critical(f"Crash: {e}", exc_info=True)
        print(f"Error: {e}")
