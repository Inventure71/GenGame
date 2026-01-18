import pygame

class BaseUI:
    """
    Modern, minimal UI for GenGame.
    Displays player health indicators in the top-right corner.
    """
    
    def __init__(self, screen: pygame.Surface, arena_width: int, arena_height: int):
        self.screen = screen
        self.arena_width = arena_width
        self.arena_height = arena_height
        
        # Simple minimal design
        self.padding = 15
        self.circle_radius = 35  # Size of health circle
        self.font_size = 22
        self.small_font_size = 16
        self.font = pygame.font.Font(None, self.font_size)
        self.small_font = pygame.font.Font(None, self.small_font_size)
        
    def draw_character_indicator(self, character, player_num: int, position: [int, int]):
        """
        Draw a circular health indicator for a character.
        Color changes based on health percentage.
        """
        x, y = position
        
        # Calculate health percentage and color
        health_pct = max(0, min(1, character.health / character.max_health))
        
        # Color gradient: Green -> Yellow -> Red
        if health_pct > 0.6:
            color = (int(255 * (1 - (health_pct - 0.6) / 0.4)), 255, 0)
        elif health_pct > 0.3:
            color = (255, int(255 * ((health_pct - 0.3) / 0.3)), 0)
        else:
            color = (255, 0, 0)
        
        # Draw background and health circle
        pygame.draw.circle(self.screen, (30, 30, 30), (x, y), self.circle_radius)
        pygame.draw.circle(self.screen, color, (x, y), self.circle_radius - 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (x, y), self.circle_radius, 3)
        
        # Draw player identifier (Name or Number)
        id_text = self.font.render(str(player_num), True, (255, 255, 255))
        id_rect = id_text.get_rect(center=(x, y - 8))
        
        # Text shadow
        shadow = self.font.render(str(player_num), True, (0, 0, 0))
        self.screen.blit(shadow, (id_rect.x + 1, id_rect.y + 1))
        self.screen.blit(id_text, id_rect)
        
        # Draw lives
        lives_y = y + 12
        life_spacing = 10
        life_radius = 4
        start_x = x - ((character.MAX_LIVES - 1) * life_spacing) // 2
        
        for i in range(character.MAX_LIVES):
            life_x = start_x + i * life_spacing
            if i < character.lives:
                pygame.draw.circle(self.screen, (255, 255, 255), (life_x, lives_y), life_radius)
            else:
                pygame.draw.circle(self.screen, (100, 100, 100), (life_x, lives_y), life_radius, 1)
        
        # Draw weapon info
        if character.weapon:
            weapon_name = character.weapon.name[:10]
            ammo_display = f"{character.weapon.ammo}/{character.weapon.max_ammo}"
            weapon_text = self.small_font.render(f"{weapon_name}", True, (255, 255, 255))
            ammo_text = self.small_font.render(ammo_display, True, (255, 200, 0))
            
            # Position weapon name
            weapon_rect = weapon_text.get_rect(center=(x, y + self.circle_radius + 18))
            
            # Position ammo below weapon name
            ammo_rect = ammo_text.get_rect(center=(x, y + self.circle_radius + 32))
            
            # Label background for weapon
            bg_rect = weapon_rect.inflate(8, 4)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (0, 0, 0, 180), (0, 0, bg_rect.width, bg_rect.height), border_radius=4)
            self.screen.blit(bg_surf, bg_rect)
            self.screen.blit(weapon_text, weapon_rect)
            
            # Label background for ammo
            ammo_bg_rect = ammo_rect.inflate(8, 4)
            ammo_bg_surf = pygame.Surface((ammo_bg_rect.width, ammo_bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(ammo_bg_surf, (0, 0, 0, 180), (0, 0, ammo_bg_rect.width, ammo_bg_rect.height), border_radius=4)
            self.screen.blit(ammo_bg_surf, ammo_bg_rect)
            self.screen.blit(ammo_text, ammo_rect)

    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None):
        """Main draw loop for the UI."""
        # Draw player indicators in top-right
        start_x = self.arena_width - self.circle_radius - self.padding
        start_y = self.circle_radius + self.padding
        spacing = self.circle_radius * 3 + 20  # Increased spacing for better separation
        
        for i, char in enumerate(characters):
            if char.is_eliminated:
                continue
            y_pos = start_y + i * spacing
            self.draw_character_indicator(char, i + 1, [start_x, y_pos])
        
        # Draw respawn timers
        if respawn_timers:
            y_offset = 60
            for char in characters:
                if char.id in respawn_timers:
                    time_left = int(respawn_timers[char.id]) + 1
                    text = self.font.render(f"{char.name} respawning in {time_left}s...", True, (255, 255, 0))
                    text_rect = text.get_rect(center=(self.arena_width / 2, y_offset))
                    self.screen.blit(text, text_rect)
                    y_offset += 30
        
        if game_over:
            self.draw_game_over(winner, characters)

    def draw_game_over(self, winner, characters):
        """Standard game over overlay."""
        overlay = pygame.Surface((self.arena_width, self.arena_height), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 200), (0, 0, self.arena_width, self.arena_height))
        self.screen.blit(overlay, (0, 0))
        
        big_font = pygame.font.Font(None, 80)
        if winner:
            # Use the character's ID (which is the username) instead of player index
            winner_name = winner.id if hasattr(winner, 'id') else (winner.name if hasattr(winner, 'name') else "Unknown")
            text_str = f"{winner_name.upper()} WINS!"
            text_color = (255, 215, 0)
        else:
            text_str = "GAME OVER - DRAW"
            text_color = (200, 200, 200)
            
        text = big_font.render(text_str, True, text_color)
        text_rect = text.get_rect(center=(self.arena_width / 2, self.arena_height / 2))
        self.screen.blit(text, text_rect)
        
        instr = self.font.render("Press ESC to Exit", True, (255, 255, 255))
        self.screen.blit(instr, instr.get_rect(center=(self.arena_width / 2, self.arena_height / 2 + 70)))
