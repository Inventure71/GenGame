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
        self._draw_stats(characters, network_stats)
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

    def _draw_stats(self, characters, network_stats: dict = None):
        x = 20
        y = 20
        for idx, char in enumerate(characters):
            if char.is_eliminated:
                continue
            name = getattr(char, "name", f"Cow {idx+1}")
            health = int(char.health)
            size = int(getattr(char, "size", char.width))
            dashes = getattr(char, "dashes_left", 0)
            ability = getattr(char, "primary_ability_name", None) or "No Primary"
            passive = getattr(char, "passive_ability_name", None) or "No Passive"

            lines = [
                f"{name}",
                f"HP: {health}  Size: {size}  Dashes: {dashes}",
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
