import pygame


class BaseUI:
    """Low-level UI hook. Override in GameFolder for visuals."""

    def __init__(self, screen: pygame.Surface, arena_width: int, arena_height: int):
        self.screen = screen
        self.arena_width = arena_width
        self.arena_height = arena_height

    def draw(self, characters: list, game_over: bool = False, winner=None, respawn_timers: dict = None, local_player_id: str = None, network_stats: dict = None):
        return
