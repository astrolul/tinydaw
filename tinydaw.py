import curses
import os
import time
import logging
import random
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
    VIEW_MIXER = auto()
    VIEW_METERS = auto()
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
        
        # State
        self.last_triggered_time = 0.0
        self.is_gated_playing = False
        self.playing_channels = [] # Track pygame channels for visualization
        self.vu_level = 0.0 # 0.0 to 1.0

    def assign_file(self, path):
        if not path:
            return False, "No path provided"
        if not os.path.exists(path):
            return False, "File not found"
        
        if AUDIO_ENABLED and pygame is not None:
            try:
                self.sound = pygame.mixer.Sound(path)
                self.sound.set_volume(self.volume)
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
        if self.is_gated_playing:
            self.is_gated_playing = False
            # self.sound.stop()

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
        if not self.sound:
            return

        now = time.time()
        logging.debug(f"Triggering Channel {self.index} in {self.trigger_mode}")

        ch = None
        if self.trigger_mode == TriggerMode.ONESHOT:
            ch = self.sound.play()
        
        elif self.trigger_mode == TriggerMode.RETRIGGER:
            self.sound.stop()
            ch = self.sound.play()

        elif self.trigger_mode == TriggerMode.GATE:
            self.last_triggered_time = now
            if not self.is_gated_playing:
                self.sound.play() 
                self.is_gated_playing = True
                # Capturing the channel for gate is harder as play() is called once
                # But we can approximate visualizer for gate easily.

        if ch:
            self.playing_channels.append(ch)

    def update(self):
        """Update state, gate logic, and visuals."""
        # 1. Gate Logic
        if self.trigger_mode == TriggerMode.GATE and self.is_gated_playing:
            if time.time() - self.last_triggered_time > GATE_THRESHOLD:
                if self.sound:
                    self.sound.stop()
                self.is_gated_playing = False
                logging.debug(f"Channel {self.index} Gate Stop")

        # 2. Start Visualizer Logic
        is_playing = False
        
        if self.trigger_mode == TriggerMode.GATE:
            is_playing = self.is_gated_playing
        else:
            # Clean up finished channels
            self.playing_channels = [ch for ch in self.playing_channels if ch.get_busy()]
            if self.playing_channels:
                is_playing = True

        target_level = self.volume if is_playing else 0.0
        if is_playing:
            # Add some jitter to look like a real meter
            jitter = random.uniform(0.9, 1.0)
            target_level *= jitter
        
        # Smooth follow
        if target_level > self.vu_level:
            self.vu_level = 0.5 * target_level + 0.5 * self.vu_level # Attack fast
        else:
            self.vu_level = 0.1 * target_level + 0.9 * self.vu_level # Decay slow
            
        if self.vu_level < 0.01: self.vu_level = 0.0

def get_text_input(stdscr, y, x, prompt_text, width=40):
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

def draw_vertical_bar(stdscr, x, y_start, height, value, char_fill, char_empty, color_pair):
    """Generic vertical bar drawer"""
    fill_height = int(value * height)
    for i in range(height):
        y = y_start + (height - 1) - i
        if i < fill_height:
            try:
                stdscr.addstr(y, x, char_fill, color_pair)
            except curses.error: pass
        else:
            try:
                stdscr.addstr(y, x, char_empty, curses.color_pair(1) | curses.A_DIM)
            except curses.error: pass

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
    
    # Common Column Layout Calculation
    col_width = (width - 4) // MAX_CHANNELS
    if col_width > 14: col_width = 14
    total_width = col_width * MAX_CHANNELS
    start_x = (width - total_width) // 2
    bar_height = height - 10
    if bar_height < 5: bar_height = 5
    start_y = 4

    if mode == Mode.VIEW_MIXER:
        stdscr.addstr(1, 2, "MIXER - Faders (Vol)", curses.A_BOLD)
        
        for i, ch in enumerate(channels):
            col_x = start_x + (i * col_width)
            content_offset = (col_width - 3) // 2
            draw_x = col_x + content_offset
            
            header_attr = curses.A_REVERSE if (i == selected_idx) else curses.A_UNDERLINE
            stdscr.addstr(start_y - 2, draw_x, f"CH{i+1}", header_attr)
            stdscr.addstr(start_y - 1, draw_x, f"[{ch.assigned_char}]", curses.color_pair(1))
            
            # Fader Logic
            handle_pos = int(ch.volume * (bar_height - 1))
            for h in range(bar_height):
                y = start_y + (bar_height - 1) - h
                char = ' | '
                attr = curses.color_pair(1) | curses.A_DIM
                if h == handle_pos:
                    char = '[#]' if i == selected_idx else '[=]'
                    attr = curses.A_REVERSE if i == selected_idx else curses.color_pair(1)
                elif h < handle_pos:
                    char = ' | '
                
                try: 
                    stdscr.addstr(y, draw_x, char, attr)
                except: pass

            name = ch.name
            if len(name) > col_width - 1: name = name[:col_width - 1]
            name_x = col_x + max(0, (col_width - len(name)) // 2)
            stdscr.addstr(start_y + bar_height + 1, name_x, name, curses.A_DIM)

    elif mode == Mode.VIEW_METERS:
        stdscr.addstr(1, 2, "METERS - dB Levels (Visual)", curses.A_BOLD)

        for i, ch in enumerate(channels):
            col_x = start_x + (i * col_width)
            content_offset = (col_width - 3) // 2
            draw_x = col_x + content_offset
            
            # Header
            stdscr.addstr(start_y - 2, draw_x, f"CH{i+1}", curses.A_UNDERLINE)
            
            # Meter Logic
            # Use ASCII blocks
            draw_vertical_bar(stdscr, draw_x, start_y, bar_height, ch.vu_level, " █ ", " ░ ", curses.color_pair(2))

            # Value label
            try:
                db_str = f"{int(ch.vu_level * 100)}%"
                stdscr.addstr(start_y + bar_height + 1, draw_x, db_str, curses.color_pair(1))
            except: pass

    elif mode == Mode.CHANNEL_ASSIGN:
        stdscr.addstr(1, 2, "ASSIGN - Setup", curses.A_BOLD)
        
        for i, ch in enumerate(channels):
            y_pos = content_start_y + i
            if y_pos >= height - 2: break
            
            prefix = "> " if i == selected_idx else "  "
            style = curses.A_REVERSE if i == selected_idx else curses.A_NORMAL
            line = f"{prefix}CH{i+1}: [{ch.assigned_char}] Vol={int(ch.volume*100)}% {ch.trigger_mode.name} {ch.name}"
            if len(line) > width - 4: line = line[:width-4] + "..."
            stdscr.addstr(y_pos, 4, line, style)

    # Message
    if message:
        try:
            stdscr.addstr(height-3, 2, f"Use: {message}", curses.color_pair(2))
        except curses.error: pass

    # Footer Instructions
    instr = ""
    if mode == Mode.VIEW_MIXER:
         instr = "[Arrow Keys: Mix] [F2: Meters] [F3: Assign] [Q: Quit]"
    elif mode == Mode.VIEW_METERS:
         instr = "[F1: Mixer] [F3: Assign] [Q: Quit]"
    elif mode == Mode.CHANNEL_ASSIGN:
        instr = "[Up/Down: Nav] [F: File] [K: Key] [T: Mode] [F1: Mixer]"
    
    try:
        stdscr.addstr(height-2, 2, instr[:width-3], curses.color_pair(1))
    except curses.error: pass

    stdscr.refresh()

def main(stdscr):
    logging.info("Starting tinydaw")
    
    if AUDIO_ENABLED and pygame is not None:
        try:
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            logging.info("Audio initialized")
        except Exception as e:
            logging.error(f"Audio init failed: {e}")
            pass

    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1) # Green for meters/messages
    stdscr.bkgd(' ', curses.color_pair(1))
    stdscr.nodelay(True)
    
    current_mode = Mode.VIEW_MIXER
    channels = [Channel(i) for i in range(MAX_CHANNELS)]
    selected_idx = 0
    status_msg = ""

    draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)
    
    while True:
        try:
            time.sleep(0.01) # 100 FPS loop roughly
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        should_redraw = False
        
        # Update channels (Gate + Visuals)
        for ch in channels:
            ch.update()
        
        # Force redraw in metering mode to animate
        if current_mode == Mode.VIEW_METERS:
            should_redraw = True

        if key != -1:
            status_msg = "" 

            # Mode Switching
            if key == curses.KEY_F1:
                current_mode = Mode.VIEW_MIXER
                should_redraw = True
            elif key == curses.KEY_F2:
                current_mode = Mode.VIEW_METERS
                should_redraw = True
            elif key == curses.KEY_F3:
                current_mode = Mode.CHANNEL_ASSIGN
                should_redraw = True
            elif key in (ord('q'), ord('Q')):
                break
            
            # Common Triggering
            if current_mode in (Mode.VIEW_MIXER, Mode.VIEW_METERS):
                for ch in channels:
                    if ch.assigned_key == key:
                        ch.trigger()
            
            # Mixer Controls
            if current_mode == Mode.VIEW_MIXER:
                if key == curses.KEY_LEFT:
                    selected_idx = max(0, selected_idx - 1)
                    should_redraw = True
                elif key == curses.KEY_RIGHT:
                    selected_idx = min(MAX_CHANNELS - 1, selected_idx + 1)
                    should_redraw = True
                elif key == curses.KEY_UP:
                    channels[selected_idx].adjust_volume(0.05)
                    should_redraw = True
                elif key == curses.KEY_DOWN:
                    channels[selected_idx].adjust_volume(-0.05)
                    should_redraw = True

            # Assign Controls
            elif current_mode == Mode.CHANNEL_ASSIGN:
                if key == curses.KEY_UP:
                    selected_idx = max(0, selected_idx - 1)
                    should_redraw = True
                elif key == curses.KEY_DOWN:
                    selected_idx = min(MAX_CHANNELS - 1, selected_idx + 1)
                    should_redraw = True
                elif key in (ord('f'), ord('F')):
                    path = get_text_input(stdscr, stdscr.getmaxyx()[0]-3, 2, "Path: ")
                    if path:
                        success, msg = channels[selected_idx].assign_file(path)
                        status_msg = msg
                    should_redraw = True
                elif key in (ord('k'), ord('K')):
                    status_msg = "Press a key to assign..."
                    stdscr.nodelay(False) 
                    draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)
                    new_key = stdscr.getch()
                    stdscr.nodelay(True) 
                    if new_key not in (curses.KEY_F1, curses.KEY_F2, curses.KEY_F3, 27): 
                        channels[selected_idx].assign_key(new_key)
                        status_msg = f"Key assigned"
                    else:
                        status_msg = "Cancelled"
                    should_redraw = True
                elif key in (ord('t'), ord('T')):
                    new_mode = channels[selected_idx].toggle_mode()
                    status_msg = f"Mode: {new_mode.name}"
                    should_redraw = True

        if should_redraw:
            draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)

if __name__ == "__main__":
    try:
        wrapper(main)
    except Exception as e:
        logging.critical(f"Crash: {e}", exc_info=True)
        print(f"Error: {e}")
