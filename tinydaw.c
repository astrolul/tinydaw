#include <ncurses.h>
#include <stdio.h>
#include <string.h>

int main() {
    // Initialize ncurses
    initscr();
    
    // Disable line buffering
    cbreak();
    
    // Don't echo user input
    noecho();
    
    // Enable function key recognition
    keypad(stdscr, TRUE);
    
    // Set color support
    start_color();
    use_default_colors();
    init_pair(1, COLOR_GREEN, -1);
    init_pair(2, COLOR_CYAN, -1);
    
    int ch;
    const char *current_text = "Channel View";
    int text_color = 1;
    
    int max_x, max_y;
    getmaxyx(stdscr, max_y, max_x);
    
    // Clear screen and display initial content
    clear();
    mvprintw(0, 0, "tinydaw alpha");
    int text_x = (max_x - strlen(current_text)) / 2;
    int text_y = max_y / 2;
    attron(COLOR_PAIR(text_color));
    mvprintw(text_y, text_x, "%s", current_text);
    attroff(COLOR_PAIR(text_color));
    mvprintw(max_y - 1, 0, "F1: Channel View | F2: Channel Assign | q: quit");
    refresh();
    
    // Event loop
    while ((ch = getch()) != 'q') {
        if (ch == KEY_F(1)) {
            current_text = "Channel View";
            text_color = 1;
        } else if (ch == KEY_F(2)) {
            current_text = "Channel Assign";
            text_color = 2;
        }
        
        // Clear and redraw
        clear();
        
        // Display title at top left
        mvprintw(0, 0, "tinydaw alpha");
        
        // Get screen dimensions
        getmaxyx(stdscr, max_y, max_x);
        
        // Display the current text centered
        if (strlen(current_text) > 0) {
            int text_x = (max_x - strlen(current_text)) / 2;
            int text_y = max_y / 2;
            attron(COLOR_PAIR(text_color));
            mvprintw(text_y, text_x, "%s", current_text);
            attroff(COLOR_PAIR(text_color));
        }
        
        // Display keybind message at bottom left
        mvprintw(max_y - 1, 0, "F1: Channel View | F2: Channel Assign | q: quit");
        
        refresh();
    }
    
    // Cleanup
    endwin();
    
    return 0;
}
