import curses
import os
import sys

def print_centered_bar(text, width = 80, fill_char = '?'):
    # Ensure the text is not longer than the width of the bar
    if len(text) > width:
        text = text[:width]

    # Calculate the padding on either side of the text
    total_padding = width - len(text)
    left_padding = total_padding // 2
    right_padding = total_padding - left_padding

    # Construct the bar with the text centered
    bar = f"{fill_char * left_padding}{text}{fill_char * right_padding}"

    # Print the bar
    print(bar)

def clear_console():
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For macOS and Linux
        os.system('clear')

def display_menu(options, items_per_page=25, ismulti=False, list_only=False):
    def main(stdscr):
        selected_index = 0
        current_page = 0
        total_pages = (len(options) + items_per_page - 1) // items_per_page
        selected_items = []
        clicked_index = -1

        # Enable mouse events
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

        def render_page():
            stdscr.clear()
            # No need to call .keys() since options is now a list
            page_options = options[current_page * items_per_page: (current_page + 1) * items_per_page]

            if current_page > 0:
                page_options.insert(0, "<< Previous Page")
            if current_page < total_pages - 1:
                page_options.append(">> Next Page")
            if list_only:
                page_options.append("Go Back")
            else:
                page_options.append("Submit")

            max_option_length = max(len(option) for option in page_options)
            page_info = f"(Page {current_page + 1} of {total_pages})"
            page_info_position = max_option_length + 5  # 5 spaces padding

            for i, option in enumerate(page_options):
                display_option = option
                if option not in ["<< Previous Page", ">> Next Page", "Submit", "Go Back"]:
                    if option in selected_items:
                        display_option = f"* {option}"
                    else:
                        display_option = f"  {option}"
                if i == selected_index or i == clicked_index:
                    stdscr.addstr(i, 0, display_option, curses.A_REVERSE)
                    if option == ">> Next Page":
                        stdscr.addstr(i, page_info_position, page_info)
                else:
                    stdscr.addstr(i, 0, display_option)
                    if option == ">> Next Page":
                        stdscr.addstr(i, page_info_position, page_info)

            if (ismulti or not list_only) and selected_items:
                selected_ids = ", ".join(selected_items)
                line_length = len(selected_ids)
                padding = " " * (80 - line_length)  # Assuming 80 characters wide terminal
                stdscr.addstr(items_per_page + 3, 0, f"Selected IDs: {selected_ids}{padding}")

            stdscr.refresh()
            return page_options

        def handle_mouse_click(mouse_event):
            nonlocal clicked_index, selected_index, current_page, page_options
            _, mx, my, _, bstate = mouse_event
            if bstate & curses.BUTTON1_CLICKED:
                if 0 <= my < len(page_options):
                    if mx <= len(page_options[my]):  # Limit clickable length to the length of the displayed text
                        clicked_index = my
                        selected_index = my
                        if page_options[selected_index].strip() == ">> Next Page":
                            current_page += 1
                            selected_index = 0
                            clicked_index = -1
                            page_options = render_page()
                        elif page_options[selected_index].strip() == "<< Previous Page":
                            current_page -= 1
                            selected_index = 0
                            clicked_index = -1
                            page_options = render_page()
                        elif list_only and page_options[selected_index].strip() == "Go Back":
                            return None
                        elif page_options[selected_index].strip() == "Submit":
                            if ismulti or not selected_items:
                                return selected_items
                            else:
                                return [selected_items[0]] if selected_items else None
                        else:
                            if ismulti and not list_only and page_options[selected_index].strip() not in ["<< Previous Page", ">> Next Page", "Submit"]:
                                option = page_options[selected_index].strip()
                                if options[option] in selected_items:
                                    selected_items.remove(options[option])
                                else:
                                    selected_items.append(options[option])
                            elif not ismulti and not list_only and page_options[selected_index].strip() not in ["<< Previous Page", ">> Next Page", "Submit"]:
                                selected_items.clear()
                                selected_items.append(options[page_options[selected_index].strip()])
                            render_page()

        page_options = render_page()

        while True:
            key = stdscr.getch()
            if list_only:
                if key == curses.KEY_DOWN:
                    while True:
                        selected_index = (selected_index + 1) % len(page_options)
                        if page_options[selected_index] in ["<< Previous Page", ">> Next Page", "Go Back"]:
                            break
                    render_page()
                elif key == curses.KEY_UP:
                    while True:
                        selected_index = (selected_index - 1) % len(page_options)
                        if page_options[selected_index] in ["<< Previous Page", ">> Next Page", "Go Back"]:
                            break
                    render_page()
                elif key == curses.KEY_ENTER or key in [10, 13]:
                    if page_options[selected_index].strip() == ">> Next Page":
                        current_page += 1
                        selected_index = 0
                        clicked_index = -1
                        page_options = render_page()
                    elif page_options[selected_index].strip() == "<< Previous Page":
                        current_page -= 1
                        selected_index = 0
                        clicked_index = -1
                        page_options = render_page()
                    elif page_options[selected_index].strip() == "Go Back":
                        return None
            else:
                if key == curses.KEY_DOWN:
                    selected_index = (selected_index + 1) % len(page_options)
                    render_page()
                elif key == curses.KEY_UP:
                    selected_index = (selected_index - 1) % len(page_options)
                    render_page()
                elif key == curses.KEY_ENTER or key in [10, 13]:
                    if page_options[selected_index].strip() == ">> Next Page":
                        current_page += 1
                        selected_index = 0
                        clicked_index = -1
                        page_options = render_page()
                    elif page_options[selected_index].strip() == "<< Previous Page":
                        current_page -= 1
                        selected_index = 0
                        clicked_index = -1
                        page_options = render_page()
                    elif page_options[selected_index].strip() == "Submit":
                        if ismulti or not selected_items:
                            return selected_items
                        else:
                            return [selected_items[0]] if selected_items else None
                    else:
                        if ismulti and page_options[selected_index].strip() not in ["<< Previous Page", ">> Next Page", "Submit"]:
                            option = page_options[selected_index].strip()
                            if options[option] in selected_items:
                                selected_items.remove(options[option])
                            else:
                                selected_items.append(options[option])
                        elif not ismulti and page_options[selected_index].strip() not in ["<< Previous Page", ">> Next Page", "Submit"]:
                            selected_items.clear()
                            selected_items.append(page_options[selected_index].strip())
                            print(f"selected index: {selected_index}")
                        render_page()
                elif key == curses.KEY_MOUSE:
                    mouse_event = curses.getmouse()
                    result = handle_mouse_click(mouse_event)
                    if result is not None:
                        return result

    return curses.wrapper(main)


"""# Test Example
if __name__ == "__main__":
    # Example data
    subscriptions = {
        f"Subscription ID: {i}, Subscription Name: SubName{i}": f"SubID{i}" for i in range(1, 61)  # 60 subscriptions
    }

    selected_items = display_menu(subscriptions, items_per_page=10, ismulti=False, list_only=False)
    if selected_items:
        print(f"Selected Subscription IDs: {', '.join(selected_items)}")
    else:
        print("Exited without selection.")"""

class BulletPoints:
    def __init__(self, options, items_per_page):
        self.options = options
        self.items_per_page = items_per_page
        self.selected_index = 0
        self.current_page = 0
        self.total_pages = (len(options) + items_per_page - 1) // items_per_page
        self.selected_option = None

    def display_menu(self):
        def main(stdscr):
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
            self.render_page(stdscr)

            while True:
                key = stdscr.getch()
                if key == curses.KEY_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.page_options)
                    self.render_page(stdscr)
                elif key == curses.KEY_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.page_options)
                    self.render_page(stdscr)
                elif key == curses.KEY_ENTER or key in [10, 13]:
                    self.handle_selection(stdscr)
                    self.render_page(stdscr)
                elif key == curses.KEY_MOUSE:
                    mouse_event = curses.getmouse()
                    self.handle_mouse_click(mouse_event, stdscr)
                    self.render_page(stdscr)

        curses.wrapper(main)

    def render_page(self, stdscr):
        stdscr.clear()
        start_index = self.current_page * self.items_per_page
        end_index = min(start_index + self.items_per_page, len(self.options))
        self.page_options = self.options[start_index:end_index]

        if self.current_page > 0:
            self.page_options.insert(0, "<< Previous Page")
        if self.current_page < self.total_pages - 1:
            self.page_options.append(">> Next Page")

        max_option_length = max(len(option) for option in self.page_options)
        page_info = f"(Page {self.current_page + 1} of {self.total_pages})"
        page_info_position = max_option_length + 5  # 5 spaces padding

        for i, option in enumerate(self.page_options):
            if option not in ["<< Previous Page", ">> Next Page"]:
                bullet = "?"  # Hollow bullet point
                if self.selected_option == option:
                    bullet = "?"  # Filled-in bullet point
                display_text = f"{bullet} {option}"
            else:
                display_text = option

            if i == self.selected_index:
                stdscr.addstr(i, 0, display_text, curses.A_REVERSE)
            else:
                stdscr.addstr(i, 0, display_text)

            if option == ">> Next Page":
                stdscr.addstr(i, page_info_position, page_info)

        stdscr.addstr(len(self.page_options) + 4, 0, f"Selected option: {self.selected_option}")
        stdscr.refresh()

    def handle_selection(self, stdscr):
        selected_option = self.page_options[self.selected_index].strip()
        if selected_option == ">> Next Page":
            self.current_page += 1
            self.selected_index = 0
        elif selected_option == "<< Previous Page":
            self.current_page -= 1
            self.selected_index = 0
        else:
            if self.selected_option == selected_option:
                self.selected_option = None
            else:
                self.selected_option = selected_option

    def handle_mouse_click(self, mouse_event, stdscr):
        _, mx, my, _, bstate = mouse_event
        if bstate & curses.BUTTON1_CLICKED:
            if 0 <= my < len(self.page_options):
                if mx <= len(self.page_options[my]):  # Limit clickable length to the length of the displayed text
                    self.selected_index = my
                    self.handle_selection(stdscr)
"""while True:
# Example usage:
    options = ["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"]
    bullet_points = BulletPoints(options, items_per_page=3)
    bullet_points.display_menu()"""

"""if __name__ == "__main__":
    options = [f"Option {i}" for i in range(1, 101)]
    items_per_page = 10

    # Run the first menu class (Navigation Only)
    nav_menu = MenuNavigationOnly(options, items_per_page)
    nav_menu.run()

    # Run the second menu class (Option Selection)
    option_menu = MenuWithSingleOptionSelection(options, items_per_page)
    selected_option = option_menu.run()
    print(f"Selected option: {selected_option}")"""