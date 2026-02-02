import pygame
from BASE_components.BASE_ui import BaseUI
from BASE_components.BASE_asset_handler import AssetHandler


class GameUI(BaseUI):
    """MS2 UI: shows health, size, dashes, and abilities."""

    def __init__(self, screen, arena_width, arena_height):
        super().__init__(screen, arena_width, arena_height)
        self.font = AssetHandler.get_font(None, 24)
        self.small_font = AssetHandler.get_font(None, 18)

    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None, local_player_id: str = None, network_stats: dict = None):
        self._draw_stats(characters, local_player_id, network_stats)
        target = self._pick_target_character(characters, local_player_id)
        if target:
            self._draw_health_bar(target)
        if respawn_timers:
            self._draw_respawns(respawn_timers, characters)
        if self._is_help_requested():
            target = self._pick_target_character(characters, local_player_id)
            if target:
                self._draw_ability_help(target)
        if game_over:
            self._draw_game_over(winner)

    def _draw_ability_help(self, character):
        primary_name = getattr(character, "primary_ability_name", None) or "No Primary"
        primary_desc = getattr(character, "primary_description", "") or "No description"
        passive_name = getattr(character, "passive_ability_name", None) or "No Passive"
        passive_desc = getattr(character, "passive_description", "") or "No description"

        lines = [
            "Ability Details (Hold H)",
            f"Primary: {primary_name}",
            f"  {primary_desc}",
            f"Passive: {passive_name}",
            f"  {passive_desc}",
        ]
        surfaces = [
            AssetHandler.render_text(line, None, 24, (255, 255, 255))
            for line in lines
        ]

        pad = 10
        line_height = 20
        width = max(surface.get_width() for surface in surfaces) + pad * 2
        height = line_height * len(lines) + pad * 2
        x = self.arena_width - width - 20
        y = 20

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 160))
        self.screen.blit(panel, (x, y))

        text_y = y + pad
        for surface in surfaces:
            self.screen.blit(surface, (x + pad, text_y))
            text_y += line_height

    def _draw_stats(self, characters, local_player_id: str = None, network_stats: dict = None):
        x = 20
        y = 20
        target = self._pick_target_character(characters, local_player_id)
        if target and not getattr(target, "is_eliminated", False):
            name = getattr(target, "name", "Cow")
            size = int(getattr(target, "size", target.width))
            dashes = getattr(target, "dashes_left", 0)
            ability = getattr(target, "primary_ability_name", None) or "No Primary"
            passive = getattr(target, "passive_ability_name", None) or "No Passive"

            lines = [
                f"{name}",
                f"Size: {size}  Dashes: {dashes}",
                f"Primary: {ability}",
                f"Passive: {passive}",
            ]

            for line in lines:
                text = AssetHandler.render_text(line, None, 24, (255, 255, 255))
                self.screen.blit(text, (x, y))
                y += 20
            y += 10
        
        # Draw network stats below character stats
        if network_stats:
            y += 10  # Add spacing before network stats
            network_lines = [
                f"Network Stats:",
                f"Packets/sec: {network_stats.get('received_last_second', 0)}",
                f"Packets Lost: {network_stats.get('packets_lost', 0)}",
            ]
            
            for line in network_lines:
                text = AssetHandler.render_text(line, None, 18, (200, 200, 255))
                self.screen.blit(text, (x, y))
                y += 18

    def _draw_health_bar(self, character):
        max_health = float(getattr(character, "max_health", 100.0) or 0.0)
        health = float(getattr(character, "health", 0.0) or 0.0)
        if max_health <= 0:
            return

        ratio = max(0.0, min(1.0, health / max_health))
        if ratio > 0.6:
            fill_color = (60, 200, 90)
        elif ratio > 0.3:
            fill_color = (230, 200, 60)
        else:
            fill_color = (220, 70, 70)

        bar_width = 220
        bar_height = 18
        x = 20
        y = self.arena_height - bar_height - 20

        bg_rect = pygame.Rect(x, y, bar_width, bar_height)
        fill_rect = pygame.Rect(x, y, int(bar_width * ratio), bar_height)

        pygame.draw.rect(self.screen, (30, 30, 30), bg_rect)
        pygame.draw.rect(self.screen, fill_color, fill_rect)
        pygame.draw.rect(self.screen, (220, 220, 220), bg_rect, 2)

        label = f"HP {int(health)}/{int(max_health)}"
        text = AssetHandler.render_text(label, None, 18, (255, 255, 255))
        text_rect = text.get_rect(midleft=(x + 8, y + bar_height / 2))
        self.screen.blit(text, text_rect)
