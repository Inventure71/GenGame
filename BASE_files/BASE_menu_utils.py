import pygame
#from BASE_files.BASE_helpers import base_encode, base_decode, encrypt_code, decrypt_code
from BASE_helpers import base_encode, base_decode, encrypt_code, decrypt_code

class MenuUtils:
    """Utility class for menu drawing and text input handling."""

    def __init__(self, screen, font, button_font, small_font, button_color, button_hover_color, button_text_color):
        self.screen = screen
        self.font = font
        self.button_font = button_font
        self.small_font = small_font
        self.button_color = button_color
        self.button_hover_color = button_hover_color
        self.button_text_color = button_text_color
        self.button_width = 300
        self.button_height = 60

    def draw_button(self, text: str, x: int, y: int, width: int, height: int, hovered: bool = False) -> object:
        """Draw a button and return its rect for collision detection."""
        color = self.button_hover_color if hovered else self.button_color
        rect = pygame.Rect(x, y, width, height)

        # Draw button background
        pygame.draw.rect(self.screen, color, rect, border_radius=8)

        # Draw button border
        pygame.draw.rect(self.screen, (150, 150, 180), rect, 2, border_radius=8)

        # Draw text
        text_surf = self.button_font.render(text, True, self.button_text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

        return rect

    def draw_text(self, text: str, x: int, y: int, font=None, color=None, center=False):
        """Draw text on screen."""
        if font is None:
            font = self.button_font
        if color is None:
            color = (255, 255, 255)

        text_surf = font.render(text, True, color)
        if center:
            text_rect = text_surf.get_rect(center=(x, y))
            self.screen.blit(text_surf, text_rect)
        else:
            self.screen.blit(text_surf, (x, y))

    def draw_text_field(self, text: str, x: int, y: int, width: int, height: int, focused: bool = False, placeholder: str = ""):
        """Draw a text input field."""
        # Draw field background
        field_color = (60, 60, 80) if focused else (40, 40, 50)
        pygame.draw.rect(self.screen, field_color, (x, y, width, height))
        pygame.draw.rect(self.screen, (100, 100, 120), (x, y, width, height), 2)  # Border

        # Draw text or placeholder
        display_text = text if text or not placeholder else placeholder
        text_color = (255, 255, 255) if text else (150, 150, 150)

        # Render text and ensure it fits in the field
        text_surf = self.button_font.render(display_text, True, text_color)
        if text_surf.get_width() > width - 20:  # Leave some padding
            # Truncate text if too long
            while text_surf.get_width() > width - 20 and len(display_text) > 0:
                display_text = display_text[:-1]
                text_surf = self.button_font.render(display_text, True, text_color)

        # Draw the text
        text_y = y + (height - text_surf.get_height()) // 2
        self.screen.blit(text_surf, (x + 10, text_y))

        # Draw cursor if focused
        if focused:
            cursor_x = x + 10 + text_surf.get_width()
            cursor_y = text_y
            pygame.draw.line(self.screen, (255, 255, 255),
                           (cursor_x, cursor_y),
                           (cursor_x, cursor_y + text_surf.get_height()), 2)

        return pygame.Rect(x, y, width, height)

    def check_button_hover(self, x: int, y: int, width: int, height: int, mouse_pos) -> bool:
        """Check if mouse is hovering over a button."""
        button_rect = pygame.Rect(x, y, width, height)
        return button_rect.collidepoint(mouse_pos)

    def check_button_click(self, button_rect, mouse_clicked, mouse_pos) -> bool:
        """Check if a button was clicked."""
        return mouse_clicked and button_rect.collidepoint(mouse_pos)


# Text input handling methods (extracted from BaseMenu)
class TextInputHandler:
    """Handles text input for various text fields in menus."""

    def __init__(self):
        self.agent_cursor_pos = 0
        self.agent_selection_start = 0
        self.agent_selection_end = 0
        self.agent_scroll_offset = 0
        self.patch_cursor_pos = 0
        self.patch_selection_start = 0
        self.patch_selection_end = 0
        self.patch_scroll_offset = 0

    def has_selection(self):
        """Check if there's text selected."""
        return self.agent_selection_start != self.agent_selection_end

    def get_line_col(self, pos, text):
        """Convert absolute position to line and column."""
        lines = text.split('\n')
        current_pos = 0

        for line_idx, line in enumerate(lines):
            line_length = len(line) + 1  # +1 for newline
            if current_pos + line_length > pos:
                col = pos - current_pos
                return line_idx, col
            current_pos += line_length

        # End of text
        return len(lines) - 1, len(lines[-1])

    def get_pos_from_line_col(self, line, col, text):
        """Convert line and column to absolute position."""
        lines = text.split('\n')
        pos = 0

        for i in range(min(line, len(lines))):
            pos += len(lines[i]) + 1  # +1 for newline

        pos += min(col, len(lines[line]) if line < len(lines) else 0)
        return pos

    def update_cursor_from_mouse_click(self, rect, y, mouse_pos, text, char_width=8, line_height=25, padding=10):
        """Update cursor position based on mouse click in wrapped text."""
        # Calculate which display line was clicked
        click_y = mouse_pos[1] - y - padding
        clicked_display_line = max(0, min(int(click_y // line_height), 10))  # Assume up to 10 visible lines

        # Calculate which column was clicked
        click_x = mouse_pos[0] - rect.left - padding
        clicked_col = max(0, int(click_x // char_width))

        # Get display lines to find the actual cursor position
        max_chars_per_line = (rect.width - 2 * padding) // char_width
        display_lines = self.wrap_text_for_display(text, max_chars_per_line)

        if clicked_display_line < len(display_lines):
            display_line = display_lines[clicked_display_line]
            clicked_col = min(clicked_col, len(display_line))

            # Convert display position back to actual text position
            self.agent_cursor_pos = self.get_text_pos_from_display_pos(display_lines, clicked_display_line, clicked_col)
        else:
            # Clicked beyond the text
            self.agent_cursor_pos = len(text)

        self.agent_selection_start = self.agent_cursor_pos
        self.agent_selection_end = self.agent_cursor_pos

    def delete_selection(self, text):
        """Delete the selected text."""
        if not self.has_selection():
            return text

        start = min(self.agent_selection_start, self.agent_selection_end)
        end = max(self.agent_selection_start, self.agent_selection_end)

        result = text[:start] + text[end:]
        self.agent_cursor_pos = start
        self.agent_selection_start = start
        self.agent_selection_end = start
        return result

    def get_selected_text(self, text):
        """Get the currently selected text."""
        if not self.has_selection():
            return ""

        start = min(self.agent_selection_start, self.agent_selection_end)
        end = max(self.agent_selection_start, self.agent_selection_end)
        return text[start:end]

    def insert_text(self, text, new_text):
        """Insert text at cursor position."""
        # Delete selection first if any
        if self.has_selection():
            text = self.delete_selection(text)

        text = text[:self.agent_cursor_pos] + new_text + text[self.agent_cursor_pos:]
        self.agent_cursor_pos += len(new_text)
        self.agent_selection_start = self.agent_cursor_pos
        self.agent_selection_end = self.agent_cursor_pos
        return text

    def select_all(self, text):
        """Select all text."""
        self.agent_selection_start = 0
        self.agent_selection_end = len(text)
        self.agent_cursor_pos = len(text)

    def wrap_text_for_display(self, text, max_chars_per_line):
        """Wrap text to fit within max_chars_per_line and return display lines."""
        if not text:
            return [""]

        display_lines = []
        paragraphs = text.split('\n')

        for paragraph in paragraphs:
            if not paragraph:
                display_lines.append("")
                continue

            words = paragraph.split(' ')
            current_line = ""

            for word in words:
                # Check if adding this word would exceed the line length
                if current_line and len(current_line + ' ' + word) <= max_chars_per_line:
                    current_line += ' ' + word
                elif len(word) <= max_chars_per_line:
                    # Start new line with this word
                    if current_line:
                        display_lines.append(current_line)
                    current_line = word
                else:
                    # Word is too long, split it
                    if current_line:
                        display_lines.append(current_line)
                        current_line = ""
                    # Split long word
                    for i in range(0, len(word), max_chars_per_line):
                        display_lines.append(word[i:i + max_chars_per_line])

            if current_line:
                display_lines.append(current_line)

        return display_lines if display_lines else [""]

    def get_display_line_from_cursor(self, display_lines):
        """Get the display line index where the cursor is located."""
        cursor_pos = self.agent_cursor_pos
        char_count = 0

        for line_idx, line in enumerate(display_lines):
            line_length = len(line) + 1  # +1 for space/newline
            if char_count + line_length > cursor_pos:
                return line_idx
            char_count += line_length

        return len(display_lines) - 1

    def get_cursor_display_position(self, display_lines):
        """Get the cursor position in display coordinates (line, column)."""
        cursor_pos = self.agent_cursor_pos
        char_count = 0

        for line_idx, line in enumerate(display_lines):
            line_length = len(line) + 1  # +1 for space/newline
            if char_count + line_length > cursor_pos:
                col = cursor_pos - char_count
                return line_idx, min(col, len(line))
            char_count += line_length

        # End of text
        last_line_idx = len(display_lines) - 1
        return last_line_idx, len(display_lines[last_line_idx]) if display_lines else 0

    def get_selection_ranges_for_display_line(self, display_lines, display_line_idx):
        """Get selection ranges for a specific display line."""
        if not self.has_selection():
            return []

        sel_start = min(self.agent_selection_start, self.agent_selection_end)
        sel_end = max(self.agent_selection_start, self.agent_selection_end)

        # Find the character ranges for this display line
        char_start = 0
        for i in range(display_line_idx):
            char_start += len(display_lines[i]) + 1

        char_end = char_start + len(display_lines[display_line_idx])

        # Check if selection intersects with this line
        line_sel_start = max(sel_start, char_start)
        line_sel_end = min(sel_end, char_end)

        if line_sel_start < line_sel_end:
            start_col = line_sel_start - char_start
            end_col = line_sel_end - char_start
            return [(start_col, end_col)]

        return []

    def get_text_pos_from_display_pos(self, display_lines, display_line_idx, display_col):
        """Convert display position back to actual text position."""
        pos = 0

        for i in range(display_line_idx):
            if i < len(display_lines):
                # Add the length of this display line plus space/newline
                pos += len(display_lines[i]) + 1

        # Add the column position within the current display line
        if display_line_idx < len(display_lines):
            pos += min(display_col, len(display_lines[display_line_idx]))

        return pos

    def draw_text_input(self, rect, y, width, height, text, screen, button_font, menu_text_color, frame_count):
        """Draw the text input field with word wrapping, scrolling, cursor and selection."""
        line_height = 25
        char_width = 8
        padding = 10
        max_chars_per_line = (width - 2 * padding) // char_width
        visible_lines = (height - 2 * padding) // line_height

        # Wrap text into display lines
        display_lines = self.wrap_text_for_display(text, max_chars_per_line)

        # Calculate scrolling
        cursor_line_idx = self.get_display_line_from_cursor(display_lines)
        if cursor_line_idx < self.agent_scroll_offset:
            self.agent_scroll_offset = cursor_line_idx
        elif cursor_line_idx >= self.agent_scroll_offset + visible_lines:
            self.agent_scroll_offset = cursor_line_idx - visible_lines + 1

        # Ensure scroll offset is valid
        max_scroll = max(0, len(display_lines) - visible_lines)
        self.agent_scroll_offset = max(0, min(self.agent_scroll_offset, max_scroll))

        # Draw visible lines
        for i in range(visible_lines):
            line_idx = self.agent_scroll_offset + i
            if line_idx >= len(display_lines):
                break

            line_y = y + padding + i * line_height
            display_line = display_lines[line_idx]

            # Draw selection background if there's a selection
            if self.has_selection():
                sel_ranges = self.get_selection_ranges_for_display_line(display_lines, line_idx)
                for start_col, end_col in sel_ranges:
                    if start_col < end_col:
                        sel_x = rect.left + padding + start_col * char_width
                        sel_width = (end_col - start_col) * char_width
                        pygame.draw.rect(screen, (100, 150, 200),
                                       (sel_x, line_y, sel_width, line_height))

            # Draw the line text
            text_surf = button_font.render(display_line, True, menu_text_color)
            screen.blit(text_surf, (rect.left + padding, line_y))

            # Draw cursor if focused and on this line
            if frame_count % 60 < 30:  # Blinking cursor
                cursor_display_line, cursor_col = self.get_cursor_display_position(display_lines)
                if cursor_display_line == line_idx:
                    cursor_x = rect.left + padding + cursor_col * char_width
                    pygame.draw.line(screen, menu_text_color,
                                   (cursor_x, line_y),
                                   (cursor_x, line_y + line_height), 2)

        # Draw scroll indicators
        if self.agent_scroll_offset > 0:
            arrow_up = button_font.render("▲", True, (200, 200, 255))
            screen.blit(arrow_up, (rect.right - 20, y + padding))
        if self.agent_scroll_offset + visible_lines < len(display_lines):
            arrow_down = button_font.render("▼", True, (200, 200, 255))
            screen.blit(arrow_down, (rect.right - 20, y + height - padding - line_height))

    def draw_patch_text_input(self, rect, y, width, height, text, screen, button_font, menu_text_color, focused):
        """Draw the patch name text input field (simplified single-line version)."""
        padding = 10
        char_width = 8
        line_height = 25

        # Draw the text
        text_x = rect.left + padding
        text_y = y + (height - line_height) // 2 + 5
        display_text = text

        # Draw selection background if there's a selection
        if self.patch_selection_start != self.patch_selection_end:
            sel_start = min(self.patch_selection_start, self.patch_selection_end)
            sel_end = max(self.patch_selection_start, self.patch_selection_end)
            sel_x = text_x + sel_start * char_width
            sel_width = (sel_end - sel_start) * char_width
            pygame.draw.rect(screen, (100, 150, 200),
                           (sel_x, text_y - 2, sel_width, line_height))

        # Draw the text
        text_surf = button_font.render(display_text, True, menu_text_color)
        screen.blit(text_surf, (text_x, text_y))

        # Draw cursor if focused
        if focused:
            cursor_x = text_x + self.patch_cursor_pos * char_width
            pygame.draw.line(screen, menu_text_color,
                           (cursor_x, text_y - 2), (cursor_x, text_y + line_height - 2), 2)

    def update_patch_cursor_from_mouse_click(self, rect, y, mouse_pos, text):
        """Update cursor position based on mouse click in patch name field."""
        if not rect.collidepoint(mouse_pos):
            return

        # Calculate relative x position
        relative_x = mouse_pos[0] - rect.left - 10  # 10 is padding
        char_width = 8

        # Calculate character position
        char_pos = relative_x // char_width
        self.patch_cursor_pos = max(0, min(char_pos, len(text)))
        self.patch_selection_start = self.patch_cursor_pos
        self.patch_selection_end = self.patch_cursor_pos


# Note: pygame should be imported in the main menu file to avoid circular imports
if __name__ == "__main__":
    code = encrypt_code("192.168.9.1", 555, "REMOTE")
    print(code)
    print(decrypt_code(code))
