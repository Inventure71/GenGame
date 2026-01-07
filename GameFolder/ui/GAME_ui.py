from BASE_components.BASE_ui import BaseUI

class GameUI(BaseUI):
    """
    Game specific UI. Currently uses all features from the modernized BaseUI.
    """
    def __init__(self, screen, arena_width, arena_height):
        super().__init__(screen, arena_width, arena_height)
