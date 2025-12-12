import curses
from curses import wrapper

CHANNEL_VIEW = 1
CHANNEL_ASSIGN = 2

def main(stdscr):
    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(1, curses.COLOR_WHITE, -1)

    stdscr.bkgd(' ', curses.color_pair(1))
    stdscr.clear()

    welcome = "welcome to tinydaw"
    height, width = stdscr.getmaxyx()

    y = height // 2
    x = (width // 2) - (len(welcome) // 2)

    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(y, x, welcome)
    stdscr.attroff(curses.color_pair(1))

    stdscr.refresh()

    # ---- Draw border ----
    stdscr.border()

    # ---- Title at top ----
    title = " tinydaw alpha "
    title_x = (width // 2) - (len(title) // 2)
    stdscr.addstr(0, title_x, title, curses.color_pair(1) | curses.A_BOLD)


    # ---- Center welcome text ----
    welcome = "welcome to tinydaw"
    y = height // 2
    x = (width // 2) - (len(welcome) // 2)
    stdscr.addstr(y, x, welcome, curses.color_pair(1))

    stdscr.refresh()

    # ---- Key loop ----
    while True:
        key = stdscr.getch()

        # Quit on 'q'
        if key == ord('q'):
            break

        # Refresh screen size (in case of resize)
        height, width = stdscr.getmaxyx()

        # Format the key
        if 32 <= key <= 126:
            key_name = chr(key)
        else:
            key_name = f"{key}"

        msg = f"^{key_name}"

        # Draw ABOVE the border → row height - 2

        # Bottom row above border
        y = height - 2

        # Safe right-aligned position
        x = max(1, width - len(msg) - 2)

        # Clear the row (inside borders)
        stdscr.move(y, 1)
        stdscr.clrtoeol()

        stdscr.addstr(y, x, msg, curses.color_pair(1))

        stdscr.refresh()

wrapper(main)
