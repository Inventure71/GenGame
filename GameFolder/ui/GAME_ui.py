from BASE_components.BASE_ui import BaseUI
import pygame

class GameUI(BaseUI):
    """
    Simple, minimal UI with colored circles showing health.
    Players shown in top-right corner as numbered circles.
    """
    
    def __init__(self, screen: pygame.Surface, arena_width: int, arena_height: int):
        super().__init__(screen, arena_width, arena_height)
        
        # Simple minimal design
        self.padding = 10
        self.circle_radius = 30  # Size of health circle
        self.font_size = 20
        self.small_font_size = 14
        self.font = pygame.font.Font(None, self.font_size)
        self.small_font = pygame.font.Font(None, self.small_font_size)
        
    def draw_character_indicator(self, character, player_num: int, position: [int, int]):
        """
        Draw a simple circular health indicator for a character.
        Color changes based on health percentage.
        """
        x, y = position
        
        # Calculate health percentage and color
        health_pct = character.health / character.max_health
        
        # Color gradient from red (low) to yellow (mid) to green (high)
        if health_pct > 0.6:
            # Green to yellow
            color = (int(255 * (1 - (health_pct - 0.6) / 0.4)), 
                    255, 
                    0)
        elif health_pct > 0.3:
            # Yellow to red
            color = (255, 
                    int(255 * ((health_pct - 0.3) / 0.3)), 
                    0)
        else:
            # Red
            color = (255, 0, 0)
        
        # Draw filled circle with health color
        pygame.draw.circle(self.screen, color, (x, y), self.circle_radius)
        
        # Draw black border
        pygame.draw.circle(self.screen, (0, 0, 0), (x, y), self.circle_radius, 3)
        
        # Draw player number in center
        num_text = self.font.render(str(player_num), True, (255, 255, 255))
        num_rect = num_text.get_rect(center=(x, y - 8))
        
        # Text shadow for readability
        shadow = self.font.render(str(player_num), True, (0, 0, 0))
        shadow_rect = num_rect.copy()
        shadow_rect.x += 1
        shadow_rect.y += 1
        self.screen.blit(shadow, shadow_rect)
        self.screen.blit(num_text, num_rect)
        
        # Draw lives as small circles below number
        lives_y = y + 12
        life_spacing = 8
        life_radius = 3
        start_x = x - ((character.MAX_LIVES - 1) * life_spacing) // 2
        
        for i in range(character.MAX_LIVES):
            life_x = start_x + i * life_spacing
            if i < character.lives:
                pygame.draw.circle(self.screen, (255, 255, 255), (life_x, lives_y), life_radius)
            else:
                pygame.draw.circle(self.screen, (100, 100, 100), (life_x, lives_y), life_radius, 1)
        
        # Draw weapon name below circle (if has weapon)
        if character.weapon:
            weapon_text = self.small_font.render(character.weapon.name[:8], True, (255, 255, 255))
            weapon_rect = weapon_text.get_rect(center=(x, y + self.circle_radius + 15))
            
            # Semi-transparent background
            bg_rect = weapon_rect.inflate(6, 2)
            bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(bg_surface, (0, 0, 0, 150), (0, 0, bg_rect.width, bg_rect.height))
            self.screen.blit(bg_surface, bg_rect)
            
            self.screen.blit(weapon_text, weapon_rect)
        
    
    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None):
        """
        Simple UI: Draw all player indicators in top-right corner.
        """
        # Draw player indicators in top-right corner
        start_x = self.arena_width - self.circle_radius - self.padding
        start_y = self.circle_radius + self.padding
        spacing = self.circle_radius * 2 + 20  # Space between circles
        
        for i, char in enumerate(characters):
            if char.is_eliminated:
                continue  # Don't show eliminated players
            
            y_pos = start_y + i * spacing
            self.draw_character_indicator(char, i + 1, [start_x, y_pos])
        
        # Draw respawn timers (center of screen)
        if respawn_timers:
            y_offset = 50
            for char in characters:
                if char.id in respawn_timers:
                    time_left = int(respawn_timers[char.id]) + 1
                    text = self.font.render(f"P{characters.index(char) + 1} respawning in {time_left}...", True, (255, 255, 0))
                    text_rect = text.get_rect(center=(self.arena_width / 2, y_offset))
                    self.screen.blit(text, text_rect)
                    y_offset += 30
        
        # Draw game over screen
        if game_over:
            self.draw_game_over(winner, characters)
    
    def draw_game_over(self, winner, characters):
        """
        Simple game over screen.
        """
        # Semi-transparent overlay
        overlay = pygame.Surface((self.arena_width, self.arena_height), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 180), (0, 0, self.arena_width, self.arena_height))
        self.screen.blit(overlay, (0, 0))
        
        # Game Over text
        big_font = pygame.font.Font(None, 72)
        if winner:
            player_num = characters.index(winner) + 1
            text_str = f"PLAYER {player_num} WINS!"
            text_color = (255, 215, 0)  # Gold
        else:
            text_str = "DRAW"
            text_color = (200, 200, 200)
        
        text = big_font.render(text_str, True, text_color)
        text_rect = text.get_rect(center=(self.arena_width / 2, self.arena_height / 2))
        self.screen.blit(text, text_rect)
        
        # Instructions
        instruction = self.font.render("Press ESC to quit", True, (200, 200, 200))
        instruction_rect = instruction.get_rect(center=(self.arena_width / 2, self.arena_height / 2 + 60))
        self.screen.blit(instruction, instruction_rect)

