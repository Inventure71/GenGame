import pygame
import math
from BASE_components.BASE_asset_handler import AssetHandler


# --- THEME CONSTANTS ---
THEME = {
    "background": (10, 14, 23),      # Deep Dark Blue
    "surface": (25, 32, 48),         # Lighter Dark Blue
    "surface_hover": (35, 42, 60),   # Highlighted Surface
    "primary": (0, 180, 240),        # Cyan/Electric Blue
    "primary_hover": (50, 200, 255),
    "danger": (220, 40, 80),         # Neon Red
    "danger_hover": (240, 70, 100),
    "text_main": (240, 245, 255),    # Off-white
    "text_dim": (140, 150, 170),     # Grey-blue
    "border": (45, 55, 75),          # Subtle border
    "accent": (100, 255, 218),       # Mint accent (optional)
    "accent_hover": (130, 255, 230), # Lighter Mint
}

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
        regular_components = [comp for comp in self.components if not isinstance(comp, (NotificationOverlay, LoadingOverlay))]
        overlay_components = [comp for comp in self.components if isinstance(comp, (NotificationOverlay, LoadingOverlay))]

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
        surf = AssetHandler.render_text_from_font(self.text, self.font, self.color)
        self.rect.width = surf.get_width()
        self.rect.height = surf.get_height()
        if self.center:
            # If centered, x and y are the center point
            self.rect.center = (self.rect.x, self.rect.y)

    def set_text(self, text):
        self.text = text
        self._update_rect()

    def render(self, screen):
        surf = AssetHandler.render_text_from_font(self.text, self.font, self.color)
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

    def render(self, screen):
        color = self.get_colors()
        
        # Shadow/Glow effect (optional, simple offset)
        # pygame.draw.rect(screen, (0, 0, 0, 50), self.rect.move(2, 2), border_radius=8)

        # Draw background
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        
        # Draw border (thinner, more subtle, or only on hover)
        border_c = THEME["border"]
        if self.style == "primary":
             border_c = THEME["primary"]
        elif self.style == "accent":
             border_c = THEME["accent"]
        
        if self.hovered:
            border_c = THEME["text_main"]
            
        pygame.draw.rect(screen, border_c, self.rect, 1, border_radius=8)
        
        # Draw text
        text_color = THEME["text_main"]
        if self.style == "accent":
            # Accent is bright mint, so use dark text for contrast if needed, 
            # but let's stick to theme for now. Maybe background color is dark enough?
            # Actually mint (100, 255, 218) is quite bright. White text might be hard to read.
            # Let's use the background color for text on accent buttons.
            text_color = THEME["background"]
        elif not self.enabled:
            text_color = THEME["text_dim"]
            
        text_surf = AssetHandler.render_text_from_font(self.text, self.font, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def get_colors(self):
        """Determine background color based on style and hover state."""
        if not self.enabled:
            return (30, 35, 45)

        if self.style == "primary":
            base = THEME["primary"]
            hover = THEME["primary_hover"]
        elif self.style == "danger":
            base = THEME["danger"]
            hover = THEME["danger_hover"]
        elif self.style == "accent":
            base = THEME["accent"]
            hover = THEME["accent_hover"]
        else: # normal
            base = THEME["surface"]
            hover = THEME["surface_hover"]
        
        return hover if self.hovered else base

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered and self.enabled:
                if self.callback:
                    self.callback()
                return True
        return False

class Panel(UIComponent):
    """Background container with optional transparency."""
    def __init__(self, x, y, width, height, color=None, border_color=None, border_width=1, alpha=240, name=None):
        super().__init__(x, y, width, height, name=name)
        self.color = color if color else THEME["surface"]
        self.border_color = border_color if border_color else THEME["border"]
        self.border_width = border_width
        self.alpha = alpha
        
        # Pre-create surface for alpha blending
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def render(self, screen):
        # Clear surface
        self.surface.fill((0,0,0,0))
        
        # Draw background with alpha
        if self.color:
             r, g, b = self.color
             pygame.draw.rect(self.surface, (r, g, b, self.alpha), (0, 0, self.rect.width, self.rect.height), border_radius=6)
        
        # Draw border
        if self.border_width > 0:
            pygame.draw.rect(self.surface, self.border_color, (0, 0, self.rect.width, self.rect.height), self.border_width, border_radius=6)
            
        screen.blit(self.surface, self.rect.topleft)

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
        self.text_color = THEME["text_main"]
        self.placeholder_color = THEME["text_dim"]
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
        # Modern Input Style: Dark background, bottom border highlight on focus
        
        bg_color = (20, 24, 35) # Slightly darker than surface
        border_color = THEME["primary"] if self.focused else THEME["border"]
        
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=4)
        
        # Draw border (full rectangle or just bottom line? Let's do full thin rect)
        pygame.draw.rect(screen, border_color, self.rect, 1 if not self.focused else 2, border_radius=4)

        if not self.is_multiline:
            # Single-line rendering
            display_text = self._text if self._text or not self.placeholder else self.placeholder
            color = THEME["text_main"] if self._text else THEME["text_dim"]

            text_surf = AssetHandler.render_text_from_font(display_text, self.font, color)

            # Calculate cursor position in text
            text_up_to_cursor = self._text[:self.cursor_pos]
            cursor_text_surf = AssetHandler.render_text_from_font(text_up_to_cursor, self.font, THEME["text_main"])
            cursor_offset = cursor_text_surf.get_width()

            # Handle text truncation for display
            max_w = self.rect.width - self.padding * 2
            
            # Simple scrolling logic for single line
            if text_surf.get_width() > max_w:
                # If cursor is near end, show end. If near start, show start.
                # Simplified: Always keep cursor visible.
                
                # Calculate visible window based on cursor
                scroll_x = 0
                if cursor_offset > max_w:
                    scroll_x = cursor_offset - max_w
                
                # Render only the visible part (this is tricky with just blit, easier to re-render visible substring or use subsurface)
                # Fallback to the existing crop logic but updated
                
                crop_rect = pygame.Rect(scroll_x, 0, max_w, text_surf.get_height())
                # Ensure crop rect is within bounds
                if crop_rect.x + crop_rect.width > text_surf.get_width():
                     crop_rect.x = text_surf.get_width() - crop_rect.width
                
                screen.blit(text_surf, (self.rect.x + self.padding, self.rect.y + (self.rect.height - text_surf.get_height())//2), crop_rect)
                
                # Adjust cursor for rendering
                cursor_draw_x = self.rect.x + self.padding + (cursor_offset - crop_rect.x)
            else:
                screen.blit(text_surf, (self.rect.x + self.padding, self.rect.y + (self.rect.height - text_surf.get_height())//2))
                cursor_draw_x = self.rect.x + self.padding + cursor_offset

            # Cursor for single-line
            if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
                # Ensure cursor is within bounds before drawing
                if self.rect.x <= cursor_draw_x <= self.rect.right:
                    pygame.draw.line(screen, THEME["primary"], (cursor_draw_x, self.rect.y + 10), (cursor_draw_x, self.rect.y + self.rect.height - 10), 2)
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
                text_surf = AssetHandler.render_text_from_font(display_text, self.font, THEME["text_main"])
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
                    cursor_text_surf = AssetHandler.render_text_from_font(visible_text_up_to_cursor, self.font, THEME["text_main"])
                    cursor_x = self.rect.x + self.padding + cursor_text_surf.get_width()
                    cursor_y = self.rect.y + self.padding + cursor_line_visible * self.line_height
                    pygame.draw.line(screen, THEME["primary"], (cursor_x, cursor_y), (cursor_x, cursor_y + self.line_height), 2)

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
            
            # Alternate row colors for better readability
            is_hovered = item_rect.collidepoint(pygame.mouse.get_pos())
            is_selected = item.get('selected')
            
            if is_selected:
                bg_color = (40, 60, 90) # Selected blueish
                border_color = THEME["primary"]
            elif is_hovered:
                bg_color = THEME["surface_hover"]
                border_color = THEME["border"]
            else:
                bg_color = THEME["surface"] if idx % 2 == 0 else (20, 25, 40)
                border_color = (0,0,0,0) # No border by default
            
            pygame.draw.rect(screen, bg_color, item_rect, border_radius=4)
            if is_selected or is_hovered:
                 pygame.draw.rect(screen, border_color, item_rect, 1, border_radius=4)
            
            # Text rendering
            font = AssetHandler.get_font(None, 24)
            color = THEME["primary"] if is_selected else THEME["text_main"]
            
            text_surf = AssetHandler.render_text_from_font(item['text'], font, color)
            
            # Clip text if too long
            max_text_width = item_rect.width - 20 # 10px padding each side
            if text_surf.get_width() > max_text_width:
                area = pygame.Rect(0, 0, max_text_width, text_surf.get_height())
                screen.blit(text_surf, (item_rect.x + 10, item_rect.y + (self.item_height - text_surf.get_height())//2), area)
            else:
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
        surf = AssetHandler.render_text_from_font(code_text, self.menu.small_font, THEME["primary"])
        screen.blit(surf, (self.rect.x, self.rect.y))
        
        # Share instruction
        share_surf = AssetHandler.render_text_from_font("Share code to let others join", self.menu.small_font, THEME["text_dim"])
        screen.blit(share_surf, (self.rect.x, self.rect.y + 25))
        
        # Status
        color = THEME["primary"] if status == "CONNECTED" else THEME["danger"]
        stat_surf = AssetHandler.render_text_from_font(f"Status: {status}", self.menu.small_font, color)
        screen.blit(stat_surf, (self.rect.x, self.rect.y + 55))

        # --- Process Visualization ---
        # Game in Progress / Waiting / Syncing states
        process_text = None
        process_color = THEME["text_dim"]

        # 1. Game in Progress (Active)
        if getattr(self.menu, 'game_active', False):
             process_text = "GAME IN PROGRESS"
             process_color = THEME["danger"]
        
        # 2. Waiting for other players (Ready clicked)
        elif self.menu.patches_ready:
            process_text = "Waiting for other players..."
            
            # Check client state if available
            if self.menu.client:
                # Check active downloads
                active_downloads = [t for t in self.menu.client.file_transfers.values() if t.get('received_chunks', 0) < t.get('total_chunks', 1)]
                if active_downloads:
                     total_chunks = sum(t.get('total_chunks', 1) for t in active_downloads)
                     received_chunks = sum(t.get('received_chunks', 0) for t in active_downloads)
                     pct = int((received_chunks / total_chunks) * 100) if total_chunks > 0 else 0
                     process_text = f"Syncing Data: {pct}%"
                     process_color = THEME["accent"]
                # Check uploads (outgoing queue)
                elif len(self.menu.client.outgoing_queue) > 0:
                     process_text = f"Uploading: {len(self.menu.client.outgoing_queue)} items..."
                     process_color = THEME["primary"]
                # Default waiting state
                else:
                     process_text = "Waiting for players / Server..."
                     process_color = THEME["text_dim"]

        if process_text:
            # Draw prominent status background
            font = self.menu.button_font
            text_surf = AssetHandler.render_text_from_font(process_text, font, process_color)
            
            # Center it horizontally on screen if possible, otherwise use local rect
            screen_width = screen.get_width()
            screen_height = screen.get_height()
            
            # Draw a panel at the top center for high visibility
            panel_width = text_surf.get_width() + 60
            panel_height = 60
            panel_x = (screen_width - panel_width) // 2
            panel_y = 100 # Below the title
            
            # Draw semi-transparent background
            bg_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (0, 0, 0, 200), (0, 0, panel_width, panel_height), border_radius=10)
            pygame.draw.rect(bg_surf, process_color, (0, 0, panel_width, panel_height), 2, border_radius=10)
            
            screen.blit(bg_surf, (panel_x, panel_y))
            
            # Draw text centered in panel
            text_rect = text_surf.get_rect(center=(panel_x + panel_width//2, panel_y + panel_height//2))
            screen.blit(text_surf, text_rect)

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
        surf = AssetHandler.render_text_from_font(header_text, self.menu.button_font, THEME["text_main"])
        screen.blit(surf, (self.rect.x + 10, self.rect.y + 10))

        self.list.render(screen)

class ServerPatchBrowser(UIComponent):
    """Patch browser backed by server library pages."""
    def __init__(self, x, y, width, height, menu, name=None):
        super().__init__(x, y, width, height, name=name)
        self.menu = menu
        self.panel = Panel(x, y, width, height)
        self.list = ScrollableList(x + 10, y + 50, width - 20, height - 60)
        self.list.on_item_click = self._on_item_click
        self.last_count = -1
        self.last_selection = -1
        self.last_page = -1
        self.last_items_hash = 0

    def _on_item_click(self, idx, item):
        self.menu.server_patch_selected_index = idx

    def _items_hash(self):
        return hash(tuple(item.get('patch_id', '') for item in self.menu.server_patch_items))

    def update(self, mouse_pos):
        super().update(mouse_pos)
        self.list.update(mouse_pos)

        current_count = len(self.menu.server_patch_items)
        current_selection = self.menu.server_patch_selected_index
        current_page = self.menu.server_patch_page
        current_hash = self._items_hash()

        if (
            current_count != self.last_count
            or current_selection != self.last_selection
            or current_page != self.last_page
            or current_hash != self.last_items_hash
        ):
            self._sync_patches()
            self.last_count = current_count
            self.last_selection = current_selection
            self.last_page = current_page
            self.last_items_hash = current_hash

    def _sync_patches(self):
        self.list.clear_items()
        for idx, patch in enumerate(self.menu.server_patch_items):
            selected = idx == self.menu.server_patch_selected_index
            checkbox = "[X]" if selected else "[ ]"
            name = patch.get('name', 'Unknown')
            owner = patch.get('player_id', 'Unknown')
            base = patch.get('base_backup', 'Unknown')
            changes = patch.get('num_changes', 0)
            text = f"{checkbox} {name} (Owner: {owner}, Base: {base}, Changes: {changes})"
            self.list.add_item(text, patch, selected)

    def handle_event(self, event):
        return self.list.handle_event(event)

    def render(self, screen):
        self.panel.render(screen)

        page_size = max(1, getattr(self.menu, 'server_patch_page_size', 1))
        total = max(0, getattr(self.menu, 'server_patch_total', 0))
        current_page = max(0, getattr(self.menu, 'server_patch_page', 0))
        total_pages = max(1, (total + page_size - 1) // page_size)
        header_text = f"Server Patches - Page {current_page + 1}/{total_pages} (Total: {total})"
        surf = AssetHandler.render_text_from_font(header_text, self.menu.button_font, THEME["text_main"])
        screen.blit(surf, (self.rect.x + 10, self.rect.y + 10))

        self.list.render(screen)

class AgentWorkspace(UIComponent):
    """Composite for agent controls: prompt, buttons, and monitor link."""
    def __init__(self, x, y, width, height, menu, name=None):
        super().__init__(x, y, width, height, name=name)
        self.menu = menu
        self.prompt_field = TextField(x, y + 30, width, 180, menu.button_font, placeholder="Describe features...", is_multiline=True)
        # Reorganized buttons: Paste at center bottom of text field, Start Agent and Stop Agent at corners
        self.paste_button = Button(x + (width-100)//2, y + 220, 100, 45, "Paste", menu.small_font, self._on_paste_click)
        self.run_button = Button(x, y + 220, 200, 45, "Start Agent", menu.button_font, menu.on_agent_send_click, style="primary")
        self.stop_button = Button(x + width - 150, y + 220, 150, 45, "Stop Agent", menu.button_font, menu.on_agent_stop_click, style="danger")
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
        surf = AssetHandler.render_text_from_font("Describe features or improvements:", self.menu.button_font, THEME["text_main"])
        screen.blit(surf, (self.rect.x, self.rect.y))

        self.prompt_field.render(screen)
        self.run_button.render(screen)
        if self.stop_button.visible:
            self.stop_button.render(screen)
        self.paste_button.render(screen)
        
        # Monitor link
        mon_text = "Live Monitor: http://127.0.0.1:8765"
        mon_surf = AssetHandler.render_text_from_font(mon_text, self.menu.small_font, THEME["accent"])
        mon_rect = mon_surf.get_rect(topright=(self.rect.right - 10, self.rect.y + 8))
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
        super().__init__(0, 20, 1400, 60, name=name)  # Moved to top
        self.menu = menu
        self.surface = pygame.Surface((1400, 60), pygame.SRCALPHA)

    def render(self, screen):
        if self.menu.error_message and pygame.time.get_ticks() - self.menu.error_message_time < 5000:
            sw = screen.get_width()
            
            # Resize if screen width changed
            if self.rect.width != sw:
                self.rect.width = sw
                self.surface = pygame.Surface((sw, 60), pygame.SRCALPHA)
            
            # Clear surface
            self.surface.fill((0,0,0,0))
            
            # Draw semi-transparent background
            bg_color = (40, 10, 10, 230) # Dark red, transparent
            pygame.draw.rect(self.surface, bg_color, (0, 0, self.rect.width, self.rect.height), border_radius=6)
            pygame.draw.rect(self.surface, THEME["danger"], (0, 0, self.rect.width, self.rect.height), 2, border_radius=6)
            
            # Error message text - Draw onto surface to center relative to overlay
            surf = AssetHandler.render_text_from_font(self.menu.error_message, self.menu.small_font, (255, 200, 200))
            rect = surf.get_rect(center=(self.rect.width // 2, self.rect.height // 2))
            self.surface.blit(surf, rect)
            
            # Blit surface to screen
            screen.blit(self.surface, (0, self.rect.y))

class LoadingOverlay(UIComponent):
    """Overlay to show blocking operations."""
    def __init__(self, menu, name=None):
        super().__init__(0, 0, 1400, 900, name=name) # Full screen
        self.menu = menu
        self.surface = pygame.Surface((1400, 900), pygame.SRCALPHA)
        self.spinner_angle = 0
    
    def render(self, screen):
        # Check if menu has loading_message attribute and it is set
        msg = getattr(self.menu, 'loading_message', None)
        if msg:
            # Semi-transparent dark background
            self.surface.fill((0,0,0,180))
            screen.blit(self.surface, (0,0))
            
            # Center coordinates
            # Use screen rect if available to handle resizing, else fallback to component rect
            cx, cy = screen.get_rect().centerx, screen.get_rect().centery
            
            # Spinner (simple rotating arc)
            self.spinner_angle = (self.spinner_angle + 15) % 360
            radius = 30
            
            # Define rect for arc
            rect = pygame.Rect(0, 0, radius * 2, radius * 2)
            rect.center = (cx, cy - 30)
            
            # Draw spinning arc
            import math
            start_angle = math.radians(self.spinner_angle)
            end_angle = math.radians(self.spinner_angle + 270)
            
            pygame.draw.arc(screen, THEME["primary"], rect, start_angle, end_angle, 4)
            
            # Text
            font = AssetHandler.get_font(None, 36)
            text_surf = AssetHandler.render_text_from_font(msg, font, THEME["text_main"])
            text_rect = text_surf.get_rect(center=(cx, cy + 30))
            screen.blit(text_surf, text_rect)
