import pygame
from BASE_components.BASE_asset_handler import AssetHandler


class BaseUI:
    """Low-level UI hook. Override in GameFolder for visuals."""

    def __init__(self, screen: pygame.Surface, arena_width: int, arena_height: int):
        self.screen = screen
        self.arena_width = arena_width
        self.arena_height = arena_height

    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None, local_player_id: str = None, network_stats: dict = None):
        return

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

    def _draw_respawns(self, respawn_timers, characters):
        y = self.arena_height - 60
        for char in characters:
            if char.id in respawn_timers:
                time_left = int(respawn_timers[char.id]) + 1
                text = AssetHandler.render_text(
                    f"{char.name} respawning in {time_left}s",
                    None,
                    18,
                    (255, 220, 0),
                )
                self.screen.blit(text, (20, y))
                y -= 18

    def _draw_game_over(self, winner):
        width = self.screen.get_width()
        height = self.screen.get_height()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        if winner:
            if isinstance(winner, str):
                winner_name = winner
            else:
                winner_name = winner.id if hasattr(winner, "id") else getattr(winner, "name", "Unknown")
            text = AssetHandler.render_text(f"{winner_name} WINS!", None, 72, (255, 215, 0))
        else:
            text = AssetHandler.render_text("GAME OVER", None, 72, (200, 200, 200))

        rect = text.get_rect(center=(width / 2, height / 2))
        self.screen.blit(text, rect)
        instr = AssetHandler.render_text("Press ESC to Exit", None, 24, (255, 255, 255))
        self.screen.blit(instr, instr.get_rect(center=(width / 2, height / 2 + 50)))
