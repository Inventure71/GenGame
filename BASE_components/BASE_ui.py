import pygame

class BaseUI:
    """
    Base UI class for displaying game information.
    Designed to be easily extended and customized by children.
    """
    
    def __init__(self, screen: pygame.Surface, arena_width: int, arena_height: int):
        self.screen = screen
        self.arena_width = arena_width
        self.arena_height = arena_height
        
        # Font settings (can be customized by children)
        self.font_size = 24
        self.small_font_size = 18
        self.font = pygame.font.Font(None, self.font_size)
        self.small_font = pygame.font.Font(None, self.small_font_size)
        
        # Colors (can be customized by children)
        self.text_color = (255, 255, 255)  # White
        self.bg_color = (0, 0, 0, 128)  # Semi-transparent black
        self.health_color = (0, 255, 0)  # Green
        self.health_bg_color = (255, 0, 0)  # Red background
        self.life_color = (255, 215, 0)  # Gold
        
        # Layout settings (can be customized by children)
        self.padding = 10
        self.bar_height = 20
        self.bar_width = 150
        
    def draw_character_info(self, character, position: [int, int]):
        """
        Draw a single character's info panel.
        
        Args:
            character: The character to display info for
            position: [x, y] position for the top-left of the info panel
        """
        x, y = position
        
        # Draw background panel
        panel_width = self.bar_width + self.padding * 2
        panel_height = 100
        self.draw_panel(x, y, panel_width, panel_height)
        
        # Draw character name
        name_text = self.font.render(character.name, True, self.text_color)
        self.screen.blit(name_text, (x + self.padding, y + self.padding))
        
        y_offset = y + self.padding + 30
        
        # Draw health bar
        self.draw_health_bar(character, x + self.padding, y_offset)
        y_offset += self.bar_height + 5
        
        # Draw lives
        self.draw_lives(character, x + self.padding, y_offset)
        y_offset += 25
        
        # Draw weapon name
        weapon_name = character.weapon.name if character.weapon else "No Weapon"
        weapon_text = self.small_font.render(f"Weapon: {weapon_name}", True, self.text_color)
        self.screen.blit(weapon_text, (x + self.padding, y_offset))
        
    def draw_panel(self, x: int, y: int, width: int, height: int):
        """
        Draw a semi-transparent background panel.
        Can be customized by children for different styling.
        """
        panel_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, self.bg_color, (0, 0, width, height))
        pygame.draw.rect(panel_surface, (255, 255, 255, 100), (0, 0, width, height), 2)
        self.screen.blit(panel_surface, (x, y))
        
    def draw_health_bar(self, character, x: int, y: int):
        """
        Draw a health bar for a character.
        Can be customized by children for different styling.
        """
        # Background (red)
        pygame.draw.rect(self.screen, self.health_bg_color, (x, y, self.bar_width, self.bar_height))
        
        # Foreground (green) - based on health percentage
        health_percentage = character.health / character.max_health
        health_width = int(self.bar_width * health_percentage)
        pygame.draw.rect(self.screen, self.health_color, (x, y, health_width, self.bar_height))
        
        # Border
        pygame.draw.rect(self.screen, (255, 255, 255), (x, y, self.bar_width, self.bar_height), 2)
        
        # Health text
        health_text = self.small_font.render(f"{int(character.health)}/{int(character.max_health)}", True, self.text_color)
        text_rect = health_text.get_rect(center=(x + self.bar_width/2, y + self.bar_height/2))
        self.screen.blit(health_text, text_rect)
        
    def draw_lives(self, character, x: int, y: int):
        """
        Draw life indicators (hearts/circles) for a character.
        Can be customized by children for different styling.
        """
        life_text = self.small_font.render("Lives:", True, self.text_color)
        self.screen.blit(life_text, (x, y))
        
        # Draw life icons
        icon_x = x + 50
        icon_size = 15
        spacing = 20
        
        for i in range(character.MAX_LIVES):
            if i < character.lives:
                # Filled circle for remaining lives
                pygame.draw.circle(self.screen, self.life_color, (icon_x + i * spacing, y + 8), icon_size // 2)
            else:
                # Empty circle for lost lives
                pygame.draw.circle(self.screen, (100, 100, 100), (icon_x + i * spacing, y + 8), icon_size // 2, 2)
                
    def draw_game_state(self, game_over: bool, winner=None):
        """
        Draw game over screen or winner announcement.
        Can be customized by children for different styling.
        """
        if not game_over:
            return
        
        # Semi-transparent overlay
        overlay = pygame.Surface((self.arena_width, self.arena_height), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 180), (0, 0, self.arena_width, self.arena_height))
        self.screen.blit(overlay, (0, 0))
        
        # Game Over text
        big_font = pygame.font.Font(None, 72)
        if winner:
            text = big_font.render(f"{winner.name} WINS!", True, (255, 215, 0))
        else:
            text = big_font.render("GAME OVER", True, (255, 0, 0))
        
        text_rect = text.get_rect(center=(self.arena_width / 2, self.arena_height / 2))
        self.screen.blit(text, text_rect)
        
        # Instructions
        instruction_text = self.font.render("Press ESC to quit", True, (255, 255, 255))
        instruction_rect = instruction_text.get_rect(center=(self.arena_width / 2, self.arena_height / 2 + 60))
        self.screen.blit(instruction_text, instruction_rect)
        
    def draw_respawn_timer(self, character, time_remaining: float):
        """
        Draw respawn countdown for a dead character.
        Can be customized by children.
        """
        text = self.font.render(f"{character.name} respawning in {int(time_remaining) + 1}...", True, (255, 255, 0))
        text_rect = text.get_rect(center=(self.arena_width / 2, 50))
        self.screen.blit(text, text_rect)
        
    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None):
        """
        Main draw method - draws all UI elements.
        
        Args:
            characters: List of characters to display info for
            game_over: Whether the game is over
            winner: The winning character (if any)
            respawn_timers: Dict of {character_id: time_remaining} for respawning characters
        """
        # Draw character info panels
        for i, char in enumerate(characters):
            if char.is_eliminated:
                continue  # Don't show UI for eliminated players
            
            # Position panels in top corners
            if i == 0:
                position = [self.padding, self.padding]
            else:
                panel_width = self.bar_width + self.padding * 2
                position = [self.arena_width - panel_width - self.padding, self.padding + i * 120]
            
            self.draw_character_info(char, position)
        
        # Draw respawn timers
        if respawn_timers:
            for char in characters:
                if char.id in respawn_timers:
                    self.draw_respawn_timer(char, respawn_timers[char.id])
        
        # Draw game over screen
        self.draw_game_state(game_over, winner)

