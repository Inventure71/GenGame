import pygame

class UIComponent:
    """Base class for all UI elements."""
    def __init__(self, x, y, width, height, name=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = True
        self.enabled = True
        self._focused = False
        self.hovered = False
        self.name = name

    @property
    def focused(self):
        return self._focused

    @focused.setter
    def focused(self, value):
        self._focused = value

    def handle_event(self, event):
        """Handle pygame events. Return True if event was consumed."""
        return False

    def update(self, mouse_pos):
        """Update component state based on mouse position."""
        if self.visible and self.enabled:
            self.hovered = self.rect.collidepoint(mouse_pos)

    def render(self, screen):
        """Render the component to the screen."""
        pass

class UIManager:
    """Manages components for a specific menu state."""
    def __init__(self, menu):
        self.menu = menu
        self.components = []
        self.focused_component = None

    def add(self, component):
        """Add a component to the manager."""
        self.components.append(component)
        return component

    def handle_event(self, event):
        """Distribute events to components."""
        # Handle mouse clicks to manage focus
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked_any = False
            # Search in reverse order (topmost first)
            for comp in reversed(self.components):
                if comp.visible and comp.enabled and comp.rect.collidepoint(event.pos):
                    if self.focused_component and self.focused_component != comp:
                        self.focused_component.focused = False

                    self.focused_component = comp
                    comp.focused = True
                    # Pass the click event to the component
                    comp.handle_event(event)
                    clicked_any = True
                    break

            # If clicked outside all components, clear focus
            if not clicked_any and self.focused_component:
                self.focused_component.focused = False
                self.focused_component = None

            return clicked_any

        # Handle scroll wheel events - pass to any component that can handle them
        elif event.type == pygame.MOUSEBUTTONDOWN and (event.button == 4 or event.button == 5):
            # Search in reverse order (topmost first) for components that can handle scroll
            for comp in reversed(self.components):
                if comp.visible and comp.enabled and comp.rect.collidepoint(event.pos):
                    if comp.handle_event(event):
                        return True
            return False

        # For other events (like keys), send to focused component
        if self.focused_component and self.focused_component.enabled:
            return self.focused_component.handle_event(event)

        return False

    def update(self):
        """Update all visible components."""
        mouse_pos = pygame.mouse.get_pos()
        for comp in self.components:
            if comp.visible:
                comp.update(mouse_pos)

    def render(self, screen):
        """Render all visible components."""
        # Render regular components first
        regular_components = [comp for comp in self.components if not isinstance(comp, NotificationOverlay)]
        overlay_components = [comp for comp in self.components if isinstance(comp, NotificationOverlay)]

        # Render regular components
        for comp in regular_components:
            if comp.visible:
                comp.render(screen)

        # Render overlays on top
        for comp in overlay_components:
            if comp.visible:
                comp.render(screen)

# --- TIER 1: PRIMITIVES ---

class Label(UIComponent):
    """Simple text display component."""
    def __init__(self, x, y, text, font, color=(255, 255, 255), center=False, name=None):
        super().__init__(x, y, 0, 0, name=name)
        self.text = text
        self.font = font
        self.color = color
        self.center = center
        # Update rect size based on text
        self._update_rect()

    def _update_rect(self):
        surf = self.font.render(self.text, True, self.color)
        self.rect.width = surf.get_width()
        self.rect.height = surf.get_height()
        if self.center:
            # If centered, x and y are the center point
            self.rect.center = (self.rect.x, self.rect.y)

    def set_text(self, text):
        self.text = text
        self._update_rect()

    def render(self, screen):
        surf = self.font.render(self.text, True, self.color)
        screen.blit(surf, self.rect.topleft)

class Button(UIComponent):
    """Clickable button with hover states and styles."""
    def __init__(self, x, y, width, height, text, font, callback, style="normal", name=None):
        super().__init__(x, y, width, height, name=name)
        self.text = text
        self.font = font
        self.callback = callback
        self.style = style # "normal", "primary", "danger"
        self.border_color = (150, 150, 180)
        self.text_color = (255, 255, 255)

    def get_colors(self):
        """Determine background color based on style and hover state."""
        if self.style == "primary":
            base = (70, 70, 130)
        elif self.style == "danger":
            base = (130, 40, 40)
        else: # normal
            base = (70, 70, 100)
        
        if not self.enabled:
            return (40, 40, 40)
        if self.hovered:
            # Lighten the color when hovered
            return tuple(min(255, c + 30) for c in base)
        return base

    def render(self, screen):
        color = self.get_colors()
        
        # Draw background
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        # Draw border
        pygame.draw.rect(screen, self.border_color, self.rect, 2, border_radius=8)
        
        # Draw text
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered and self.enabled:
                if self.callback:
                    self.callback()
                return True
        return False

class Panel(UIComponent):
    """Background container with border."""
    def __init__(self, x, y, width, height, color=(30, 30, 40), border_color=(100, 100, 120), border_width=2, name=None):
        super().__init__(x, y, width, height, name=name)
        self.color = color
        self.border_color = border_color
        self.border_width = border_width

    def render(self, screen):
        # Draw background
        pygame.draw.rect(screen, self.color, self.rect)
        # Draw border
        if self.border_width > 0:
            pygame.draw.rect(screen, self.border_color, self.rect, self.border_width)

class TextField(UIComponent):
    """Full-featured input with cursor, selection, and clipboard support."""
    def __init__(self, x, y, width, height, font, placeholder="", is_multiline=False, name=None):
        super().__init__(x, y, width, height, name=name)
        self._text = ""
        self.font = font
        self.placeholder = placeholder
        self.is_multiline = is_multiline
        self.cursor_pos = 0
        self.selection_start = 0
        self.selection_end = 0
        self.scroll_offset = 0  # For multiline: vertical scroll in lines
        self.h_scroll_offset = 0  # For horizontal scroll in characters
        self.padding = 10
        self.line_height = 25
        self.char_width = 8 # Approximate, ideally calculated from font
        self.text_color = (255, 255, 255)
        self.placeholder_color = (150, 150, 150)
        self._focused = False  # Initialize the backing field
        self._text_input_enabled = False

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        # When text is set externally, position cursor at the end
        self.cursor_pos = len(value)

    @property
    def focused(self):
        return self._focused

    @focused.setter
    def focused(self, value):
        if value != self._focused:
            self._focused = value
            # Enable/disable pygame text input for better keyboard handling
            if value:
                if hasattr(pygame, 'key') and hasattr(pygame.key, 'start_text_input'):
                    pygame.key.start_text_input()
                self._text_input_enabled = True
            else:
                if hasattr(pygame, 'key') and hasattr(pygame.key, 'stop_text_input'):
                    pygame.key.stop_text_input()
                self._text_input_enabled = False

    def _get_lines(self):
        """Get text as list of lines, with wrapping for multiline."""
        if not self.is_multiline:
            return self._text.split('\n')

        lines = []
        for line in self._text.split('\n'):
            if not line:  # Empty line
                lines.append('')
                continue

            # Word wrap the line if it's too long
            words = line.split(' ')
            current_line = ''
            for word in words:
                # Check if adding this word would exceed the width
                test_line = current_line + (' ' if current_line else '') + word
                if self.font.size(test_line)[0] <= self.rect.width - self.padding * 2:
                    current_line = test_line
                else:
                    # Start a new line
                    if current_line:
                        lines.append(current_line)
                    current_line = word
                    # If a single word is too long, break it at character level
                    if self.font.size(word)[0] > self.rect.width - self.padding * 2:
                        current_line = ''
                        for char in word:
                            if self.font.size(current_line + char)[0] <= self.rect.width - self.padding * 2:
                                current_line += char
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = char
            if current_line:
                lines.append(current_line)
        return lines

    def _get_cursor_line_col(self):
        """Get current cursor position as (line_index, col_index)."""
        lines = self._get_lines()
        pos = 0
        for line_idx, line in enumerate(lines):
            line_len = len(line)
            if pos + line_len >= self.cursor_pos:
                return line_idx, self.cursor_pos - pos
            pos += line_len + 1  # +1 for newline
        return len(lines) - 1, len(lines[-1]) if lines else 0

    def _get_pos_from_line_col(self, line_idx, col_idx):
        """Convert line/column to absolute position."""
        lines = self._get_lines()
        pos = 0
        for i in range(min(line_idx, len(lines))):
            pos += len(lines[i]) + 1
        pos += min(col_idx, len(lines[line_idx]) if line_idx < len(lines) else 0)
        return pos

    def _ensure_cursor_visible(self):
        """Ensure cursor is visible by adjusting scroll offsets."""
        if not self.is_multiline:
            return

        cursor_line, cursor_col = self._get_cursor_line_col()
        visible_lines = (self.rect.height - self.padding * 2) // self.line_height

        # Vertical scrolling
        if cursor_line < self.scroll_offset:
            self.scroll_offset = cursor_line
        elif cursor_line >= self.scroll_offset + visible_lines:
            self.scroll_offset = cursor_line - visible_lines + 1

        # Horizontal scrolling (simplified)
        if cursor_col * self.char_width > self.rect.width - self.padding * 2:
            self.h_scroll_offset = max(0, cursor_col - (self.rect.width - self.padding * 2) // self.char_width)

    def _get_indentation(self, line_idx):
        """Get the indentation of a line."""
        lines = self._get_lines()
        if line_idx < len(lines):
            line = lines[line_idx]
            return len(line) - len(line.lstrip())
        return 0

    def handle_event(self, event):
        if not self.focused or not self.enabled:
            return False

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & pygame.KMOD_CTRL or mods & pygame.KMOD_META # Meta for Mac

            if event.key == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self._text = self._text[:self.cursor_pos-1] + self._text[self.cursor_pos:]
                    self.cursor_pos -= 1
                return True
            elif event.key == pygame.K_DELETE:
                if self.cursor_pos < len(self._text):
                    self._text = self._text[:self.cursor_pos] + self._text[self.cursor_pos+1:]
                return True
            elif event.key == pygame.K_LEFT:
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                    if self.is_multiline:
                        self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_RIGHT:
                if self.cursor_pos < len(self.text):
                    self.cursor_pos += 1
                    if self.is_multiline:
                        self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_HOME:
                self.cursor_pos = 0
                if self.is_multiline:
                    self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_END:
                self.cursor_pos = len(self._text)
                if self.is_multiline:
                    self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_UP and self.is_multiline:
                cursor_line, cursor_col = self._get_cursor_line_col()
                if cursor_line > 0:
                    prev_line_len = len(self._get_lines()[cursor_line - 1])
                    new_col = min(cursor_col, prev_line_len)
                    self.cursor_pos = self._get_pos_from_line_col(cursor_line - 1, new_col)
                    self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_DOWN and self.is_multiline:
                cursor_line, cursor_col = self._get_cursor_line_col()
                lines = self._get_lines()
                if cursor_line < len(lines) - 1:
                    next_line_len = len(lines[cursor_line + 1])
                    new_col = min(cursor_col, next_line_len)
                    self.cursor_pos = self._get_pos_from_line_col(cursor_line + 1, new_col)
                    self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_v and ctrl:
                # Paste
                try:
                    if hasattr(pygame, 'scrap'):
                        if not pygame.scrap.get_init(): pygame.scrap.init()
                        clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                        if clip:
                            paste_text = clip.decode('utf-8').replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
                            self._text = self._text[:self.cursor_pos] + paste_text + self._text[self.cursor_pos:]
                            self.cursor_pos += len(paste_text)
                except:
                    pass
                return True
            elif event.key == pygame.K_c and ctrl:
                # Copy (entire text for now)
                try:
                    if hasattr(pygame, 'scrap'):
                        if not pygame.scrap.get_init(): pygame.scrap.init()
                        pygame.scrap.put(pygame.SCRAP_TEXT, self._text.encode('utf-8'))
                except:
                    pass
                return True
            elif event.key == pygame.K_RETURN:
                if self.is_multiline:
                    # Get current line for indentation
                    cursor_line, _ = self._get_cursor_line_col()
                    indent = self._get_indentation(cursor_line)

                    # Insert newline with automatic indentation
                    indent_str = " " * indent
                    self._text = self._text[:self.cursor_pos] + "\n" + indent_str + self._text[self.cursor_pos:]
                    self.cursor_pos += 1 + indent
                    self._ensure_cursor_visible()
                else:
                    self.focused = False
                return True
            elif event.key == pygame.K_TAB:
                # Insert tab character
                tab_char = "    "  # 4 spaces for tab
                self._text = self._text[:self.cursor_pos] + tab_char + self._text[self.cursor_pos:]
                self.cursor_pos += len(tab_char)
                return True
            else:
                if event.unicode and event.unicode.isprintable():
                    self._text = self._text[:self.cursor_pos] + event.unicode + self._text[self.cursor_pos:]
                    self.cursor_pos += 1
                    if self.is_multiline:
                        self._ensure_cursor_visible()
                return True

        # Handle mouse wheel for scrolling in multiline mode
        if event.type == pygame.MOUSEBUTTONDOWN and self.is_multiline and self.hovered:
            if event.button == 4:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 1)
                return True
            elif event.button == 5:  # Scroll down
                max_scroll = max(0, len(self._get_lines()) - (self.rect.height - self.padding * 2) // self.line_height)
                self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                return True

        return False

    def render(self, screen):
        bg_color = (60, 60, 80) if self.focused else (40, 40, 50)
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (100, 100, 120), self.rect, 2, border_radius=4)

        if not self.is_multiline:
            # Single-line rendering
            display_text = self._text if self._text or not self.placeholder else self.placeholder
            color = self.text_color if self._text else self.placeholder_color

            text_surf = self.font.render(display_text, True, color)

            # Calculate cursor position in text
            text_up_to_cursor = self._text[:self.cursor_pos]
            cursor_text_surf = self.font.render(text_up_to_cursor, True, self.text_color)
            cursor_offset = cursor_text_surf.get_width()

            # Handle text truncation for display
            max_w = self.rect.width - self.padding * 2
            if text_surf.get_width() > max_w:
                # Text is too long, show end portion
                crop_rect = pygame.Rect(text_surf.get_width() - max_w, 0, max_w, text_surf.get_height())
                screen.blit(text_surf, (self.rect.x + self.padding, self.rect.y + (self.rect.height - text_surf.get_height())//2), crop_rect)
                # Adjust cursor offset relative to the cropped display
                cursor_offset = max(0, cursor_offset - (text_surf.get_width() - max_w))
            else:
                # Text fits, display normally
                screen.blit(text_surf, (self.rect.x + self.padding, self.rect.y + (self.rect.height - text_surf.get_height())//2))

            # Cursor for single-line
            if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
                cursor_x = self.rect.x + self.padding + cursor_offset
                pygame.draw.line(screen, (255, 255, 255), (cursor_x, self.rect.y + 10), (cursor_x, self.rect.y + self.rect.height - 10), 2)
        else:
            # Multi-line rendering with proper scrolling
            lines = self._get_lines()
            visible_lines = (self.rect.height - self.padding * 2) // self.line_height
            cursor_line, cursor_col = self._get_cursor_line_col()

            y_offset = self.rect.y + self.padding
            for i in range(visible_lines):
                line_idx = self.scroll_offset + i
                if line_idx >= len(lines):
                    break

                line_text = lines[line_idx]

                # Handle horizontal scrolling
                display_text = line_text
                if self.h_scroll_offset > 0:
                    display_text = line_text[self.h_scroll_offset:]

                # Render each line
                text_surf = self.font.render(display_text, True, self.text_color)
                screen.blit(text_surf, (self.rect.x + self.padding, y_offset))
                y_offset += self.line_height

            # Cursor for multiline
            if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
                cursor_line_visible = cursor_line - self.scroll_offset
                if 0 <= cursor_line_visible < visible_lines:
                    # Calculate actual cursor position based on rendered text width
                    cursor_line_text = lines[cursor_line]
                    # Ensure cursor_col doesn't exceed line length
                    cursor_col = min(cursor_col, len(cursor_line_text))

                    # Account for horizontal scrolling
                    visible_start = self.h_scroll_offset
                    visible_cursor_col = max(0, cursor_col - visible_start)
                    visible_text_up_to_cursor = cursor_line_text[visible_start:cursor_col]
                    cursor_text_surf = self.font.render(visible_text_up_to_cursor, True, self.text_color)
                    cursor_x = self.rect.x + self.padding + cursor_text_surf.get_width()
                    cursor_y = self.rect.y + self.padding + cursor_line_visible * self.line_height
                    pygame.draw.line(screen, (255, 255, 255), (cursor_x, cursor_y), (cursor_x, cursor_y + self.line_height), 2)

class ScrollableList(UIComponent):
    """List with scrollable items."""
    def __init__(self, x, y, width, height, item_height=45, name=None):
        super().__init__(x, y, width, height, name=name)
        self.items = [] # List of dicts: {'text': str, 'data': any, 'selected': bool}
        self.item_height = item_height
        self.scroll_offset = 0
        self.on_item_click = None

    def add_item(self, text, data=None, selected=False):
        self.items.append({'text': text, 'data': data, 'selected': selected})

    def clear_items(self):
        self.items = []
        # Don't reset scroll_offset to preserve scroll position

    def get_visible_count(self):
        return self.rect.height // self.item_height

    def handle_event(self, event):
        if not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4: # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 1)
                return True
            elif event.button == 5: # Scroll down
                max_scroll = max(0, len(self.items) - self.get_visible_count())
                self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                return True
            elif event.button == 1 and self.hovered:
                # Calculate which item was clicked
                rel_y = event.pos[1] - self.rect.y
                idx = self.scroll_offset + (rel_y // self.item_height)
                if idx < len(self.items):
                    if self.on_item_click:
                        self.on_item_click(idx, self.items[idx])
                    return True
        return False

    def render(self, screen):
        visible_count = self.get_visible_count()
        for i in range(min(visible_count, len(self.items) - self.scroll_offset)):
            idx = self.scroll_offset + i
            item = self.items[idx]
            item_rect = pygame.Rect(self.rect.x, self.rect.y + i * self.item_height, self.rect.width, self.item_height - 2)
            
            bg_color = (50, 100, 50) if item.get('selected') else (50, 50, 60)
            if item_rect.collidepoint(pygame.mouse.get_pos()):
                bg_color = tuple(min(255, c + 20) for c in bg_color)
            
            pygame.draw.rect(screen, bg_color, item_rect, border_radius=4)
            pygame.draw.rect(screen, (100, 100, 120), item_rect, 1, border_radius=4)
            
            # Text rendering (using a default font if none provided to the list)
            # This is a bit of a hack, better to pass a font to ScrollableList
            font = pygame.font.Font(None, 24)
            text_surf = font.render(item['text'], True, (255, 255, 255))
            screen.blit(text_surf, (item_rect.x + 10, item_rect.y + (self.item_height - text_surf.get_height())//2))

# --- TIER 2: COMPOSITES ---

class RoomStatusBar(UIComponent):
    """Top-right status info composite."""
    def __init__(self, menu, name=None):
        super().__init__(1100, 10, 280, 100, name=name)
        self.menu = menu

    def render(self, screen):
        code = self.menu.room_code or "NONE"
        status = "CONNECTED" if (self.menu.client and self.menu.client.connected) else "OFFLINE"
        
        # Room Code
        code_text = f"Room Code: {code}"
        surf = self.menu.small_font.render(code_text, True, (100, 200, 255))
        screen.blit(surf, (self.rect.x, self.rect.y))
        
        # Share instruction
        share_surf = self.menu.small_font.render("Share code to let others join", True, (150, 150, 150))
        screen.blit(share_surf, (self.rect.x, self.rect.y + 25))
        
        # Status
        color = (100, 255, 100) if status == "CONNECTED" else (255, 100, 100)
        stat_surf = self.menu.small_font.render(f"Status: {status}", True, color)
        screen.blit(stat_surf, (self.rect.x, self.rect.y + 55))

class PatchBrowser(UIComponent):
    """Combines Panel, Label, and ScrollableList for patch selection."""
    def __init__(self, x, y, width, height, menu, name=None):
        super().__init__(x, y, width, height, name=name)
        self.menu = menu
        self.panel = Panel(x, y, width, height)
        self.list = ScrollableList(x + 10, y + 50, width - 20, height - 60)
        self.list.on_item_click = self._on_item_click
        self.last_patch_count = 0
        self.last_selection_hash = 0

    def _on_item_click(self, idx, item):
        self.menu.patch_manager.toggle_selection(idx)

    def _get_selection_hash(self):
        """Get a hash of the current selection state."""
        return hash(tuple(patch.selected for patch in self.menu.patch_manager.available_patches))

    def reset_cache(self):
        """Reset cached state to force refresh."""
        self.last_patch_count = -1
        self.last_selection_hash = -1

    def update(self, mouse_pos):
        super().update(mouse_pos)
        self.list.update(mouse_pos)

        # Sync patches when count changes or selection state changes
        current_count = len(self.menu.patch_manager.available_patches)
        current_selection_hash = self._get_selection_hash()

        if current_count != self.last_patch_count or current_selection_hash != self.last_selection_hash:
            self._sync_patches()
            self.last_patch_count = current_count
            self.last_selection_hash = current_selection_hash

    def _sync_patches(self):
        """Sync patch items with the patch manager."""
        self.list.clear_items()
        for patch in self.menu.patch_manager.available_patches:
            checkbox = "[X]" if patch.selected else "[ ]"
            text = f"{checkbox} {patch.name} (Base: {patch.base_backup}, Changes: {patch.num_changes})"
            self.list.add_item(text, patch, patch.selected)

    def handle_event(self, event):
        return self.list.handle_event(event)

    def render(self, screen):
        self.panel.render(screen)

        # Header
        count = len(self.menu.patch_manager.selected_patches)
        header_text = f"Select Patch (0-1) - {count}/1 selected"
        surf = self.menu.button_font.render(header_text, True, (255, 255, 255))
        screen.blit(surf, (self.rect.x + 10, self.rect.y + 10))

        self.list.render(screen)

class AgentWorkspace(UIComponent):
    """Composite for agent controls: prompt, buttons, and monitor link."""
    def __init__(self, x, y, width, height, menu, name=None):
        super().__init__(x, y, width, height, name=name)
        self.menu = menu
        self.prompt_field = TextField(x, y + 30, width, 250, menu.button_font, placeholder="Describe features...", is_multiline=True)
        # Reorganized buttons: Paste at center bottom of text field, Start Agent and Stop Agent at corners
        self.paste_button = Button(x + (width-100)//2, y + 290, 100, 45, "Paste", menu.small_font, self._on_paste_click)
        self.run_button = Button(x, y + 290, 200, 45, "Start Agent", menu.button_font, menu.on_agent_send_click, style="primary")
        self.stop_button = Button(x + width - 150, y + 290, 150, 45, "Stop Agent", menu.button_font, menu.on_agent_stop_click, style="danger")
        self._last_focused_state = False

    def update(self, mouse_pos):
        super().update(mouse_pos)
        self.prompt_field.update(mouse_pos)
        self.run_button.update(mouse_pos)
        self.stop_button.update(mouse_pos)
        self.paste_button.update(mouse_pos)

        # Sync focus: when workspace is focused, keep text field focused
        if self.focused:
            self.prompt_field.focused = True
        elif not self.focused and self._last_focused_state:
            self.prompt_field.focused = False
        self._last_focused_state = self.focused

        # Sync state
        self.run_button.text = "Running..." if self.menu.agent_running else "Start Agent"
        self.run_button.enabled = not self.menu.agent_running
        self.stop_button.visible = self.menu.agent_running
        self.menu.agent_prompt = self.prompt_field.text

    def handle_event(self, event):
        # Handle mouse clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check if click is on text field area
            if self.prompt_field.rect.collidepoint(event.pos):
                self.prompt_field.focused = True
                return self.prompt_field.handle_event(event)
            # Check other components
            elif self.run_button.rect.collidepoint(event.pos):
                self.prompt_field.focused = False  # Defocus text field when clicking buttons
                return self.run_button.handle_event(event)
            elif self.stop_button.rect.collidepoint(event.pos) and self.stop_button.visible:
                self.prompt_field.focused = False  # Defocus text field when clicking buttons
                return self.stop_button.handle_event(event)
            elif self.paste_button.rect.collidepoint(event.pos):
                self.prompt_field.focused = False  # Defocus text field when clicking buttons
                return self.paste_button.handle_event(event)
            else:
                # Clicked in workspace area but not on components - focus text field
                self.prompt_field.focused = True
                return True  # Consume the event

        # For keyboard events when workspace is focused, always try the text field first
        if event.type in (pygame.KEYDOWN, pygame.KEYUP) and self.focused:
            if self.prompt_field.handle_event(event): return True

        # For all other events, delegate to focused components
        if self.prompt_field.focused and self.prompt_field.handle_event(event): return True
        if self.run_button.handle_event(event): return True
        if self.paste_button.handle_event(event): return True
        return False

    def _on_paste_click(self):
        text = self.menu.paste_clipboard()
        if text:
            self.prompt_field.text += text
            self.prompt_field.cursor_pos = len(self.prompt_field.text)

    def render(self, screen):
        # Label
        surf = self.menu.button_font.render("Describe features or improvements:", True, (255, 255, 255))
        screen.blit(surf, (self.rect.x, self.rect.y))

        self.prompt_field.render(screen)
        self.run_button.render(screen)
        if self.stop_button.visible:
            self.stop_button.render(screen)
        self.paste_button.render(screen)
        
        # Monitor link
        mon_text = "Live Monitor: http://127.0.0.1:8765"
        mon_surf = self.menu.small_font.render(mon_text, True, (150, 200, 255))
        mon_rect = mon_surf.get_rect(center=(self.rect.centerx, self.rect.y + 370))
        screen.blit(mon_surf, mon_rect)

class TextFieldWithPaste(UIComponent):
    """Composite component with text field and paste button."""
    def __init__(self, x, y, width, height, menu, font, placeholder="", name=None):
        super().__init__(x, y, width, height, name=name)
        self.menu = menu
        self.text_field = TextField(x, y, width - 60, height, font, placeholder=placeholder)
        self.paste_button = Button(x + width - 55, y, 55, height, "Paste", menu.small_font, self._on_paste_click)

    def update(self, mouse_pos):
        super().update(mouse_pos)
        self.text_field.update(mouse_pos)
        self.paste_button.update(mouse_pos)

    def handle_event(self, event):
        # Handle mouse clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.text_field.rect.collidepoint(event.pos):
                self.text_field.focused = True
                return self.text_field.handle_event(event)
            elif self.paste_button.rect.collidepoint(event.pos):
                return self.paste_button.handle_event(event)
            else:
                self.text_field.focused = False
                return True  # Consume event

        # For keyboard events when this component is focused, delegate to text field
        if event.type in (pygame.KEYDOWN, pygame.KEYUP) and self.focused:
            return self.text_field.handle_event(event)

        return False

    def _on_paste_click(self):
        text = self.menu.paste_clipboard()
        if text:
            self.text_field.text += text
            self.text_field.cursor_pos = len(self.text_field.text)

    def render(self, screen):
        self.text_field.render(screen)
        self.paste_button.render(screen)

    @property
    def text(self):
        return self.text_field.text

    @text.setter
    def text(self, value):
        self.text_field.text = value

    @property
    def focused(self):
        return self._focused

    @focused.setter
    def focused(self, value):
        self._focused = value
        if value:
            self.text_field.focused = True

class NotificationOverlay(UIComponent):
    """Global message display component."""
    def __init__(self, menu, name=None):
        super().__init__(0, 50, 1400, 60, name=name)  # Moved to top, larger height for background
        self.menu = menu

    def render(self, screen):
        if self.menu.error_message and pygame.time.get_ticks() - self.menu.error_message_time < 5000:
            # Background panel
            bg_color = (40, 20, 20)  # Dark red background
            border_color = (100, 40, 40)  # Red border
            pygame.draw.rect(screen, bg_color, self.rect)
            pygame.draw.rect(screen, border_color, self.rect, 2)

            # Error message text
            surf = self.menu.small_font.render(self.menu.error_message, True, (255, 150, 150))
            rect = surf.get_rect(center=(700, 80))
            screen.blit(surf, rect)

