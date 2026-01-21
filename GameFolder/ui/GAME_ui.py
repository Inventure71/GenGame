import pygame
from BASE_components.BASE_ui import BaseUI


class GameUI(BaseUI):
    """MS2 UI: shows health, size, dashes, and abilities."""

    def __init__(self, screen, arena_width, arena_height):
        super().__init__(screen, arena_width, arena_height)
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None, local_player_id: str = None):
        self._draw_stats(characters)
        if respawn_timers:
            self._draw_respawns(respawn_timers, characters)
        if self._is_help_requested():
            target = self._pick_target_character(characters, local_player_id)
            if target:
                self._draw_ability_help(target)
        if game_over:
            self._draw_game_over(winner)

    @staticmethod
    def _is_help_requested() -> bool:
        try:
            keys = pygame.key.get_pressed()
            return keys[pygame.K_h]
        except Exception:
            return False

    @staticmethod
    def _pick_target_character(characters, local_player_id: str = None):
        if local_player_id:
            for char in characters:
                if getattr(char, "network_id", None) == local_player_id:
                    return char
        for char in characters:
            if not getattr(char, "is_eliminated", False):
                return char
        return None

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

        pad = 10
        line_height = 20
        width = max(self.font.size(line)[0] for line in lines) + pad * 2
        height = line_height * len(lines) + pad * 2
        x = self.arena_width - width - 20
        y = 20

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 160))
        self.screen.blit(panel, (x, y))

        text_y = y + pad
        for line in lines:
            text = self.font.render(line, True, (255, 255, 255))
            self.screen.blit(text, (x + pad, text_y))
            text_y += line_height

    def _draw_stats(self, characters):
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
                text = self.font.render(line, True, (255, 255, 255))
                self.screen.blit(text, (x, y))
                y += 20
            y += 10

    def _draw_respawns(self, respawn_timers, characters):
        y = self.arena_height - 60
        for char in characters:
            if char.id in respawn_timers:
                time_left = int(respawn_timers[char.id]) + 1
                text = self.small_font.render(f"{char.name} respawning in {time_left}s", True, (255, 220, 0))
                self.screen.blit(text, (20, y))
                y -= 18

    def _draw_game_over(self, winner):
        width = self.screen.get_width()
        height = self.screen.get_height()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        big_font = pygame.font.Font(None, 72)
        if winner:
            winner_name = winner.id if hasattr(winner, "id") else getattr(winner, "name", "Unknown")
            text = big_font.render(f"{winner_name} WINS!", True, (255, 215, 0))
        else:
            text = big_font.render("GAME OVER", True, (200, 200, 200))

        rect = text.get_rect(center=(width / 2, height / 2))
        self.screen.blit(text, rect)
        instr = self.font.render("Press ESC to Exit", True, (255, 255, 255))
        self.screen.blit(instr, instr.get_rect(center=(width / 2, height / 2 + 50)))
