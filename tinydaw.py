import curses
import os
from curses import wrapper
from enum import Enum, auto

# Try importing pygame for audio support
try:
    pygame = __import__('pygame')
    AUDIO_ENABLED = True
except ImportError:
    pygame = None
    AUDIO_ENABLED = False

MAX_CHANNELS = 8

class Mode(Enum):
    CHANNEL_VIEW = auto()
    CHANNEL_ASSIGN = auto()

class Channel:
    def __init__(self, index):
        self.index = index
        self.file_path = None
        self.assigned_key = None  # Integer keycode
        self.assigned_char = "-"  # Display char
        self.sound = None
        self.name = "Empty"

    def assign_file(self, path):
        if not path:
            return False, "No path provided"
        if not os.path.exists(path):
            return False, "File not found"
        
        # Explicit check for pygame and AUDIO_ENABLED to satisfy linters
        if AUDIO_ENABLED and pygame is not None:
            try:
                self.sound = pygame.mixer.Sound(path)
            except Exception as e:
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

    def play(self):
        if self.sound:
            self.sound.play()

def get_text_input(stdscr, y, x, prompt_text, width=40):
    """Simple text input helper."""
    curses.echo()
    curses.curs_set(1)
    stdscr.addstr(y, x, prompt_text)
    stdscr.refresh()
    
    input_bytes = stdscr.getstr(y, x + len(prompt_text), width)
    
    curses.noecho()
    curses.curs_set(0)
    return input_bytes.decode('utf-8').strip()

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

    # Content Area
    content_start_y = 2
    
    if mode == Mode.CHANNEL_VIEW:
        stdscr.addstr(1, 2, "VIEW MODE - Press assigned keys to play", curses.A_BOLD)
        
        # Draw grid of channels
        # Valid area: y=2 to height-3
        for i, ch in enumerate(channels):
            y_pos = content_start_y + i
            if y_pos >= height - 2: break
            
            line = f"CH {i+1}: [{ch.assigned_char}] {ch.name}"
            stdscr.addstr(y_pos, 4, line)

    elif mode == Mode.CHANNEL_ASSIGN:
        stdscr.addstr(1, 2, "ASSIGN MODE - Select Channel, (F)ile, (K)ey", curses.A_BOLD)
        
        for i, ch in enumerate(channels):
            y_pos = content_start_y + i
            if y_pos >= height - 2: break
            
            prefix = "> " if i == selected_idx else "  "
            style = curses.A_REVERSE if i == selected_idx else curses.A_NORMAL
            
            line = f"{prefix}CH {i+1}: Key=[{ch.assigned_char}] File={ch.name}"
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
    instr = "[F1: View] [F2: Assign] [Q: Quit] "
    if mode == Mode.CHANNEL_ASSIGN:
        instr += "[Up/Down: Select] [F: File] [K: Key]"
    
    try:
        stdscr.addstr(height-2, 2, instr[:width-3], curses.color_pair(1))
    except curses.error:
        pass

    stdscr.refresh()

def main(stdscr):
    # Setup Audio
    if AUDIO_ENABLED and pygame is not None:
        try:
            pygame.mixer.init()
            # Optional: set some channels
            pygame.mixer.set_num_channels(MAX_CHANNELS)
        except Exception:
            # If init fails (e.g. no audio device), disable audio
            pass

    # Setup Curses
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1) # Messages
    stdscr.bkgd(' ', curses.color_pair(1))

    # App State
    current_mode = Mode.CHANNEL_VIEW
    channels = [Channel(i) for i in range(MAX_CHANNELS)]
    selected_idx = 0
    status_msg = ""

    draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)

    while True:
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        should_redraw = False
        status_msg = "" # Clear message on new input

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
            # Check for assigned keys to trigger audio
            for ch in channels:
                if ch.assigned_key == key:
                    ch.play()
                    status_msg = f"Playing {ch.name}..."
                    should_redraw = True # Update message
        
        elif current_mode == Mode.CHANNEL_ASSIGN:
            if key == curses.KEY_UP:
                selected_idx = max(0, selected_idx - 1)
                should_redraw = True
            elif key == curses.KEY_DOWN:
                selected_idx = min(MAX_CHANNELS - 1, selected_idx + 1)
                should_redraw = True
            
            # Assign File
            elif key in (ord('f'), ord('F')):
                # Prompt for file
                path = get_text_input(stdscr, stdscr.getmaxyx()[0]-3, 2, "Path: ")
                if path:
                    success, msg = channels[selected_idx].assign_file(path)
                    status_msg = msg
                should_redraw = True

            # Assign Key
            elif key in (ord('k'), ord('K')):
                status_msg = "Press a key to assign..."
                draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)
                new_key = stdscr.getch()
                if new_key not in (curses.KEY_F1, curses.KEY_F2, 27): # Ignore Function keys/Esc
                    channels[selected_idx].assign_key(new_key)
                    status_msg = f"Key assigned to {channels[selected_idx].assigned_char}"
                else:
                    status_msg = "Cancelled"
                should_redraw = True

        if should_redraw:
            draw_interface(stdscr, current_mode, channels, selected_idx, status_msg)

if __name__ == "__main__":
    wrapper(main)
