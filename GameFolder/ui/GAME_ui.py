from BASE_components.BASE_ui import BaseUI
import pygame

class GameUI(BaseUI):
    """
    Game specific UI. Currently uses all features from the modernized BaseUI.
    Enhanced with shield visualization.
    """
    def __init__(self, screen, arena_width, arena_height):
        super().__init__(screen, arena_width, arena_height)

    def draw_character_indicator(self, character, player_num: int, position: [int, int]):
        """
        Override to add shield visualization around the health circle.
        """
        x, y = position

        # Calculate health percentage and color (same as base)
        health_pct = max(0, min(1, character.health / character.max_health))

        # Color gradient: Green -> Yellow -> Red
        if health_pct > 0.6:
            color = (int(255 * (1 - (health_pct - 0.6) / 0.4)), 255, 0)
        elif health_pct > 0.3:
            color = (255, int(255 * ((health_pct - 0.3) / 0.3)), 0)
        else:
            color = (255, 0, 0)

        # Draw invulnerability effect (outermost glow) if character is invulnerable
        if hasattr(character, 'is_invulnerable') and character.is_invulnerable:
            # Simple glow effect - multiple concentric circles with decreasing alpha
            timer_pct = max(0, min(1, character.invulnerability_timer / 8.0))  # Max 8.0 seconds
            glow_intensity = int(150 * timer_pct) + 50  # Fade from 200 to 50

            # Create glow surface once
            glow_size = self.circle_radius * 2 + 16
            glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)

            # Draw multiple glow circles with decreasing alpha
            for i in range(3):
                radius = self.circle_radius + 4 + i * 2
                alpha = int(80 * timer_pct * (1 - i * 0.3))  # Fade with timer and distance
                if alpha > 0:
                    glow_color = (glow_intensity, glow_intensity, 255, alpha)
                    pygame.draw.circle(glow_surf, glow_color,
                                     (glow_size // 2, glow_size // 2), radius)

            # Blit the glow surface
            self.screen.blit(glow_surf, (x - glow_size // 2, y - glow_size // 2))

            # Invulnerability border
            border_color = (100, 100, min(255, glow_intensity))
            pygame.draw.circle(self.screen, border_color, (x, y), self.circle_radius + 8, 2)

        # Draw shield ring (outer circle) if character has shield
        if hasattr(character, 'shield') and character.shield > 0:
            shield_pct = character.shield / character.max_shield
            shield_color = (0, int(255 * shield_pct), int(255 * shield_pct))  # Cyan gradient

            # Shield background (gray when depleted)
            pygame.draw.circle(self.screen, (60, 60, 60), (x, y), self.circle_radius + 6)
            # Active shield
            shield_angle = 360 * shield_pct
            pygame.draw.arc(self.screen, shield_color, (x - self.circle_radius - 6, y - self.circle_radius - 6,
                                                       (self.circle_radius + 6) * 2, (self.circle_radius + 6) * 2),
                          0, shield_angle * 3.14159 / 180, 4)
            # Shield border
            pygame.draw.circle(self.screen, (0, 255, 255), (x, y), self.circle_radius + 6, 2)

        # Draw background and health circle (same as base)
        pygame.draw.circle(self.screen, (30, 30, 30), (x, y), self.circle_radius)
        pygame.draw.circle(self.screen, color, (x, y), self.circle_radius - 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (x, y), self.circle_radius, 3)

        # Draw player identifier (Name or Number) - same as base
        id_text = self.font.render(str(player_num), True, (255, 255, 255))
        id_rect = id_text.get_rect(center=(x, y - 8))

        # Text shadow
        shadow = self.font.render(str(player_num), True, (0, 0, 0))
        self.screen.blit(shadow, (id_rect.x + 1, id_rect.y + 1))
        self.screen.blit(id_text, id_rect)

        # Draw lives - same as base
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

        # Draw weapon info - same as base
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
