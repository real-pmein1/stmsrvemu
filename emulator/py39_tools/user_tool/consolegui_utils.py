import curses
import time
from datetime import datetime


class Window:
    def __init__(self, screen):
        self.screen = screen
        self.initialize_curses()
        self.components = []
        self.current_index = 0

    def add_component(self, component):
        self.components.append(component)
        interactable_components = [c for c in self.components if hasattr(c, 'index')]
        non_interactable_components = [c for c in self.components if not hasattr(c, 'index')]
        interactable_components.sort(key = lambda c:c.index)
        self.components = non_interactable_components + interactable_components
        if interactable_components:
            interactable_components[0].active = True

    def initialize_curses(self):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.curs_set(1)
        self.screen.clear()

    def rgb_to_color_pair(self, fg_r, fg_g, fg_b, bg_r, bg_g, bg_b, pair_id):
        curses.init_color(pair_id, int(fg_r * 1000 / 255), int(fg_g * 1000 / 255), int(fg_b * 1000 / 255))
        bg_color_id = pair_id + 100  # Avoid collision with other color pairs
        curses.init_color(bg_color_id, int(bg_r * 1000 / 255), int(bg_g * 1000 / 255), int(bg_b * 1000 / 255))
        curses.init_pair(pair_id, pair_id, bg_color_id)
        return curses.color_pair(pair_id)

    class Label:
        def __init__(self, parent, y, x, text, max_length, index = 0):
            self.parent = parent
            self.y = y
            self.x = x
            self.text = text
            self.max_length = max_length
            self.index = index
            self.active = False  # Labels are not interactable
            self.label_color = curses.color_pair(2)
            parent.add_component(self)

        def configure_colors(self, label_color):
            self.label_color = label_color

        def draw(self):
            # Word wrapping
            lines = []
            words = self.text.split(' ')
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= self.max_length:
                    current_line += (word + " ")
                else:
                    lines.append(current_line.strip())
                    current_line = word + " "
            lines.append(current_line.strip())

            for i, line in enumerate(lines):
                self.parent.screen.addstr(self.y + i, self.x, line, self.label_color)

    class TextBox:
        def __init__(self, parent, y, x, label, max_length, is_required = False, index = 0):
            self.parent = parent
            self.y = y
            self.x = x
            self.label = label
            self.max_length = max_length
            self.text = ""
            self.is_required = is_required
            self.active = False
            self.index = index
            self.cursor_position = 0  # Track cursor position

            self.label_color = curses.color_pair(4)
            self.label_bg_color = curses.color_pair(4)
            self.textbox_color = curses.color_pair(4)
            self.textbox_bg_color = curses.color_pair(4)
            self.textbox_highlight_color = curses.color_pair(3)
            self.textbox_highlight_bg_color = curses.color_pair(3)
            parent.add_component(self)

        def configure_colors(self, label_color, label_bg_color, textbox_color, textbox_bg_color, textbox_highlight_color, textbox_highlight_bg_color):
            self.label_color = label_color
            self.label_bg_color = label_bg_color
            self.textbox_color = textbox_color
            self.textbox_bg_color = textbox_bg_color
            self.textbox_highlight_color = textbox_highlight_color
            self.textbox_highlight_bg_color = textbox_highlight_bg_color

        def draw(self):
            attr = self.textbox_highlight_color if self.active else self.textbox_color
            bg_attr = self.textbox_highlight_bg_color if self.active else self.textbox_bg_color
            self.parent.screen.addstr(self.y, self.x, self.label, self.label_color | self.label_bg_color)
            self.parent.screen.addstr(self.y, self.x + len(self.label), self.text + ' ' * (self.max_length - len(self.text)), attr | bg_attr)
            if self.active:
                self.parent.screen.move(self.y, self.x + len(self.label) + self.cursor_position)

        def handle_input(self, key):
            if key in [curses.KEY_BACKSPACE, 127, 8]:  # Handling backspace
                if self.cursor_position > 0:
                    self.text = self.text[:self.cursor_position - 1] + self.text[self.cursor_position:]
                    self.cursor_position -= 1
            elif key == curses.KEY_DC:  # Handling delete key
                if self.cursor_position < len(self.text):
                    self.text = self.text[:self.cursor_position] + self.text[self.cursor_position + 1:]
            elif isinstance(key, str) and len(self.text) < self.max_length:
                self.text = self.text[:self.cursor_position] + key + self.text[self.cursor_position:]
                self.cursor_position += 1
            self.draw()

        def move_cursor_left(self):
            if self.cursor_position > 0:
                self.cursor_position -= 1
            self.draw()

        def move_cursor_right(self):
            if self.cursor_position < len(self.text):
                self.cursor_position += 1
            self.draw()

    class Button:
        def __init__(self, parent, y, x, label, action, validate = False, index = 0):
            self.parent = parent
            self.y = y
            self.x = x
            self.label = label
            self.action = action
            self.validate = validate
            self.active = False
            self.index = index

            self.button_color = curses.color_pair(2)
            self.button_highlight_color = curses.color_pair(3)
            parent.add_component(self)

        def configure_colors(self, button_color, button_highlight_color):
            self.button_color = button_color
            self.button_highlight_color = button_highlight_color

        def draw(self):
            attr = self.button_highlight_color if self.active else self.button_color
            self.parent.screen.addstr(self.y, self.x, f"[ {self.label} ]", attr)

        def check_click(self, my, mx):
            if my == self.y and mx >= self.x and mx < self.x + len(f"[ {self.label} ]"):
                self.execute_action()

        def execute_action(self):
            if self.validate:
                errors = []
                for component in self.parent.components:
                    if isinstance(component, Window.TextBox) and component.is_required and not component.text.strip():
                        errors.append(f"Error: '{component.label.strip()}' is required and cannot be empty.")
                if errors:
                    self.parent.screen.addstr(14, 10, "Validation Errors:", curses.color_pair(1))
                    for idx, error in enumerate(errors, start = 1):
                        self.parent.screen.addstr(15 + idx, 10, error, curses.color_pair(1))
                    return
            self.action(**self.parent.get_textbox_values())

    class CheckList:
        def __init__(self, parent, y, x, label, is_checked = False, index = 0):
            self.parent = parent
            self.y = y
            self.x = x
            self.label = label
            self.is_checked = is_checked
            self.active = False
            self.index = index

            self.checkbox_color = curses.color_pair(2)
            self.x_color = curses.color_pair(2)
            self.label_color = curses.color_pair(2)
            self.highlight_color = curses.color_pair(3)
            self.last_toggle_time = 0
            self.debounce_time = 0.3  # Debounce time in seconds
            parent.add_component(self)

        def configure_colors(self, checkbox_color, x_color, label_color, highlight_color):
            self.checkbox_color = checkbox_color
            self.x_color = x_color
            self.label_color = label_color
            self.highlight_color = highlight_color

        def draw(self):
            status = "[ x ]" if self.is_checked else "[   ]"
            attr = self.highlight_color if self.active else self.label_color
            self.parent.screen.addstr(self.y, self.x, status, self.checkbox_color)
            self.parent.screen.addstr(self.y, self.x + 5, self.label, attr)

        def toggle(self):
            current_time = time.time()
            if current_time - self.last_toggle_time > self.debounce_time:
                self.is_checked = not self.is_checked
                self.last_toggle_time = current_time

    class MenuList:
        def __init__(self, parent, y, x, label, action, index = 0):
            self.parent = parent
            self.y = y
            self.x = x
            self.label = label
            self.action = action
            self.active = False
            self.index = index

            self.menu_color = curses.color_pair(2)
            self.menu_highlight_color = curses.color_pair(3)
            parent.add_component(self)

        def configure_colors(self, menu_color, menu_highlight_color):
            self.menu_color = menu_color
            self.menu_highlight_color = menu_highlight_color

        def draw(self):
            attr = self.menu_highlight_color if self.active else self.menu_color
            self.parent.screen.addstr(self.y, self.x, self.label, attr)

        def execute_action(self):
            self.action()

    class TitleBar:
        def __init__(self, parent, text, background_color, text_color):
            self.parent = parent
            self.text = text
            self.background_color = background_color
            self.text_color = text_color
            self.interactable = False
            parent.add_component(self)

        def draw(self):
            height, width = self.parent.screen.getmaxyx()
            self.parent.screen.addstr(0, 0, ' ' * width, curses.color_pair(self.background_color))
            self.parent.screen.addstr(0, 0, self.text, curses.color_pair(self.text_color) | curses.color_pair(self.background_color))

    class Menu:
        def __init__(self, parent, y, x, options, items_per_page, ismulti = False, index = 0):
            self.parent = parent
            self.y = y
            self.x = x
            self.options = options
            self.items_per_page = items_per_page
            self.ismulti = ismulti
            self.selected_index = 0
            self.current_page = 0
            self.total_pages = (len(self.options) + self.items_per_page - 1) // self.items_per_page
            self.selected_items = []
            self.index = index
            self.active = False

            self.menu_color = curses.color_pair(2)
            self.menu_highlight_color = curses.color_pair(3)
            self.menu_selected_color = curses.color_pair(4)
            self.menu_selected_highlight_color = curses.color_pair(3)

            self.longest_option_length = max(len(option) for option in self.options)  # Find the longest option

            self.special_items_offset = 3 if ismulti else 2
            parent.add_component(self)

        def configure_colors(self, menu_color, menu_highlight_color, menu_selected_color, menu_selected_highlight_color):
            self.menu_color = menu_color
            self.menu_highlight_color = menu_highlight_color
            self.menu_selected_color = menu_selected_color
            self.menu_selected_highlight_color = menu_selected_highlight_color

        def draw(self):
            start_index = self.current_page * self.items_per_page
            end_index = min(start_index + self.items_per_page, len(self.options))
            page_options = self.options[start_index:end_index]

            # Clear previous lines to prevent leftover text
            for i in range(self.items_per_page + self.special_items_offset + 1):
                self.parent.screen.addstr(self.y + i, self.x, " " * 80, self.menu_color)

            # Ensure there's a blank line above the first page
            blank_line = self.y - 1
            self.parent.screen.addstr(blank_line, self.x, " " * 80, self.menu_color)

            # Adjust the positioning of special items
            if self.current_page > 0:
                previous_page_line = self.y
                self.parent.screen.addstr(previous_page_line, self.x, "<< Previous Page", self.menu_color if self.selected_index != -1 else self.menu_highlight_color)
            else:
                previous_page_line = None

            if self.current_page < self.total_pages - 1:
                next_page_line = self.y + self.items_per_page + 1
                page_info = f"(Page {self.current_page + 1} of {self.total_pages})"
                page_info_position = self.x + self.longest_option_length + 5  # Position page info at the end of the longest option
                self.parent.screen.addstr(next_page_line, self.x, ">> Next Page", self.menu_color if self.selected_index != len(page_options) else self.menu_highlight_color)
                self.parent.screen.addstr(next_page_line, page_info_position, page_info, self.menu_color)
            else:
                next_page_line = None

            if self.ismulti:
                submit_line = self.y + self.items_per_page + 2
                self.parent.screen.addstr(submit_line, self.x, "Submit", self.menu_color if self.selected_index != len(page_options) + 1 else self.menu_highlight_color)
            else:
                submit_line = None
                exit_line = self.y + self.items_per_page + 2
                self.parent.screen.addstr(exit_line, self.x, "Exit", self.menu_color if self.selected_index != len(page_options) else self.menu_highlight_color)

            # Draw the menu options
            for i, option in enumerate(page_options):
                display_option = f"* {option}" if option.split(',')[0].split(':')[1].strip() in self.selected_items else f"  {option}"
                line = self.y + 1 + i  # Adjusted line position to account for blank line
                if self.selected_index == i:
                    self.parent.screen.addstr(line, self.x, display_option, self.menu_highlight_color)
                else:
                    self.parent.screen.addstr(line, self.x, display_option, self.menu_color)

            if self.ismulti:
                selected_ids = ", ".join(self.selected_items)
                line_length = len(selected_ids)
                padding = " " * (80 - line_length)  # Assuming 80 characters wide terminal
                self.parent.screen.addstr(self.y + self.items_per_page + 4, self.x, f"Selected IDs: {selected_ids}{padding}", self.menu_color)

        def handle_input(self, key):
            page_options = self.get_page_options()
            special_item_offset = self.special_items_offset
            total_options = len(page_options) + special_item_offset

            if key == curses.KEY_DOWN:
                self.selected_index = (self.selected_index + 1) % total_options
                self.draw()
            elif key == curses.KEY_UP:
                self.selected_index = (self.selected_index - 1) % total_options
                self.draw()
            elif key in [curses.KEY_ENTER, 10, 13]:
                if self.selected_index == -1 and self.current_page > 0:
                    self.current_page -= 1
                    self.selected_index = 0
                    self.draw()
                elif self.selected_index == len(page_options):
                    if self.current_page < self.total_pages - 1:
                        self.current_page += 1
                        self.selected_index = 0
                        self.draw()
                elif self.ismulti and self.selected_index == len(page_options) + 1:
                    return self.selected_items
                elif not self.ismulti and self.selected_index == len(page_options) + 1:
                    return None
                else:
                    option = page_options[self.selected_index]
                    sub_id = option.split(',')[0].split(':')[1].strip()
                    if sub_id in self.selected_items:
                        self.selected_items.remove(sub_id)
                    else:
                        self.selected_items.append(sub_id)
                    self.draw()
            elif key in [curses.KEY_TAB, 9]:
                return "NEXT_COMPONENT"

        def get_page_options(self):
            start_index = self.current_page * self.items_per_page
            end_index = min(start_index + self.items_per_page, len(self.options))
            page_options = self.options[start_index:end_index]
            return page_options

        def check_click(self, my, mx):
            if self.y <= my < self.y + self.items_per_page + self.special_items_offset + 1:  # Check if click is within menu boundaries
                if my == self.y and self.current_page > 0:  # Clicked on "<< Previous Page"
                    self.selected_index = -1
                    self.handle_input(curses.KEY_ENTER)
                elif my == self.y + self.items_per_page + 1 and self.current_page < self.total_pages - 1:  # Clicked on ">> Next Page"
                    self.selected_index = len(self.get_page_options())
                    self.handle_input(curses.KEY_ENTER)
                elif my == self.y + self.items_per_page + 2:  # Clicked on "Submit" or "Exit"
                    self.selected_index = len(self.get_page_options()) + 1
                    self.handle_input(curses.KEY_ENTER)
                else:
                    clicked_index = my - (self.y + 1)  # Adjusted for blank line
                    if clicked_index < len(self.get_page_options()):
                        option_text_length = len(self.get_page_options()[clicked_index]) + 2  # Include "* " or "  " prefix
                        if mx < self.x + option_text_length:  # Limit clickable area to the length of the option text
                            self.selected_index = clicked_index
                            self.handle_input(curses.KEY_ENTER)

        def focus(self):
            self.active = True
            self.draw()

        def unfocus(self):
            self.active = False

    def main_loop(self):
        if self.components:
            self.components[self.current_index].draw()

        # Draw the TitleBar
        for component in self.components:
            if isinstance(component, Window.TitleBar):
                component.draw()

        while True:
            for component in self.components:
                component.draw()

            self.place_cursor()
            key = self.screen.getch()

            if key == curses.KEY_MOUSE:
                _, mx, my, _, _ = curses.getmouse()
                for i, component in enumerate(self.components):
                    component.active = False
                    if isinstance(component, Window.TextBox):
                        if my == component.y and mx >= component.x + len(component.label) and mx < component.x + len(component.label) + component.max_length:
                            self.current_index = i
                            component.active = True
                    elif isinstance(component, Window.Button):
                        if my == component.y and mx >= component.x and mx < component.x + len(f"[ {component.label} ]"):
                            self.current_index = i
                            component.active = True
                            component.execute_action()
                    elif isinstance(component, Window.CheckList):
                        if my == component.y and mx >= component.x and mx < component.x + len("[ x ]") + len(component.label):
                            self.current_index = i
                            component.active = True
                            component.toggle()
                    elif isinstance(component, Window.MenuList):
                        if my == component.y and mx >= component.x and mx < component.x + len(component.label):
                            self.current_index = i
                            component.active = True
                            component.execute_action()
                    elif isinstance(component, Window.Menu):
                        if component.y <= my < component.y + component.items_per_page + 5:
                            self.current_index = i
                            component.active = True
                            component.check_click(my, mx)

            elif key in [curses.KEY_BACKSPACE, 127, 8]:
                if isinstance(self.components[self.current_index], Window.TextBox):
                    try:
                        self.components[self.current_index].handle_input(chr(key))
                    except Exception:
                        pass

            elif key in [curses.KEY_UP, 353]:
                self.components[self.current_index].active = False
                self.current_index = (self.current_index - 1) % len(self.components)
                self.components[self.current_index].active = True

            elif key in [curses.KEY_DOWN, 9]:
                self.components[self.current_index].active = False
                self.current_index = (self.current_index + 1) % len(self.components)
                self.components[self.current_index].active = True

            elif key in [curses.KEY_LEFT]:
                if isinstance(self.components[self.current_index], Window.TextBox):
                    self.components[self.current_index].move_cursor_left()

            elif key in [curses.KEY_RIGHT]:
                if isinstance(self.components[self.current_index], Window.TextBox):
                    self.components[self.current_index].move_cursor_right()

            elif key == curses.KEY_DC:  # Handling delete key
                if isinstance(self.components[self.current_index], Window.TextBox):
                    self.components[self.current_index].handle_input(key)

            elif key in [curses.KEY_ENTER, 10, 13]:
                if isinstance(self.components[self.current_index], Window.Button):
                    self.components[self.current_index].execute_action()
                elif isinstance(self.components[self.current_index], Window.CheckList):
                    self.components[self.current_index].toggle()
                elif isinstance(self.components[self.current_index], Window.MenuList):
                    self.components[self.current_index].execute_action()
                elif isinstance(self.components[self.current_index], Window.Menu):
                    result = self.components[self.current_index].handle_input(key)
                    if result is not None:
                        return result
                else:
                    self.components[self.current_index].active = False
                    self.current_index = (self.current_index + 1) % len(self.components)
                    self.components[self.current_index].active = True

            elif key == 9:  # Handling Tab key
                if isinstance(self.components[self.current_index], Window.Menu):
                    result = self.components[self.current_index].handle_input(key)
                    if result == "NEXT_COMPONENT":
                        self.components[self.current_index].active = False
                        self.current_index = (self.current_index + 1) % len(self.components)
                        self.components[self.current_index].active = True
                else:
                    self.components[self.current_index].active = False
                    self.current_index = (self.current_index + 1) % len(self.components)
                    self.components[self.current_index].active = True

            elif 32 <= key <= 126:
                if isinstance(self.components[self.current_index], Window.TextBox):
                    self.components[self.current_index].handle_input(chr(key))

            self.screen.refresh()

    def place_cursor(self):
        if isinstance(self.components[self.current_index], Window.TextBox):
            tb = self.components[self.current_index]
            self.screen.move(tb.y, tb.x + len(tb.label) + tb.cursor_position)

    def submit_form(self, **kwargs):
        self.screen.addstr(9, 10, "Form submitted successfully!", curses.color_pair(1))

    def exit_form(self):
        raise SystemExit("Exiting application")

    def get_textbox_values(self):
        return {component.label.strip().replace(" ", "_").lower():component.text for component in self.components if isinstance(component, Window.TextBox)}