import pygame
from BASE_files.BASE_network import NetworkObject
from GameFolder.abilities.ability_loader import get_primary_abilities, get_passive_abilities, reload_abilities


def _get_primary_names():
    return [ability["name"] for ability in get_primary_abilities()]


def _get_passive_names():
    return [ability["name"] for ability in get_passive_abilities()]


PRIMARY_ABILITY_NAMES = _get_primary_names()
PASSIVE_ABILITY_NAMES = _get_passive_names()

def reload_ability_names():
    """Reload abilities and update the name constants."""
    global PRIMARY_ABILITY_NAMES, PASSIVE_ABILITY_NAMES
    reload_abilities()
    PRIMARY_ABILITY_NAMES = _get_primary_names()
    PASSIVE_ABILITY_NAMES = _get_passive_names()


class AbilityPickup(NetworkObject):
    def __init__(self, ability_name: str, ability_type: str, location: [float, float]):
        super().__init__()
        self.ability_name = ability_name
        self.ability_type = ability_type
        self.location = location
        self.width = 36
        self.height = 36
        self.pickup_radius = 48
        self.is_active = True
        self.description = self._lookup_description()

        if self.ability_type == "primary":
            self.color = (255, 170, 80)
        else:
            self.color = (100, 160, 255)

        self._set_network_identity("GameFolder.pickups.GAME_pickups", "AbilityPickup")
        self.init_graphics()

    def _lookup_description(self) -> str:
        ability_def = None
        if self.ability_type == "primary":
            for ability in get_primary_abilities():
                if ability["name"] == self.ability_name:
                    ability_def = ability
                    break
        else:
            for ability in get_passive_abilities():
                if ability["name"] == self.ability_name:
                    ability_def = ability
                    break
        if not ability_def:
            raise ValueError(f"AbilityPickup missing description for '{self.ability_name}' ({self.ability_type})")
        return ability_def["description"]

    def init_graphics(self):
        super().init_graphics()
        try:
            pygame.display.get_surface()
        except Exception:
            return

    def pickup(self):
        self.is_active = False

    def set_ability_name(self, ability_name: str):
        """Update the pickup's ability and refresh any derived fields."""
        self.ability_name = ability_name
        self.description = self._lookup_description()

    def get_pickup_rect(self, arena_height: float) -> pygame.Rect:
        py_x = self.location[0] - self.pickup_radius / 2
        py_y = arena_height - self.location[1] - self.pickup_radius / 2
        return pygame.Rect(py_x, py_y, self.pickup_radius, self.pickup_radius)

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self.is_active or not self._graphics_initialized:
            return
        if camera is not None:
            rect = camera.world_center_rect_to_screen(self.location[0], self.location[1], self.width, self.height)
        else:
            py_x = self.location[0] - self.width / 2
            py_y = arena_height - self.location[1] - self.height / 2
            rect = pygame.Rect(py_x, py_y, self.width, self.height)
        pygame.draw.rect(screen, self.color, rect, border_radius=6)
        pygame.draw.rect(screen, (20, 20, 20), rect, 2, border_radius=6)

        label = "P" if self.ability_type == "primary" else "S"
        font = pygame.font.Font(None, 20)
        text = font.render(label, True, (30, 30, 30))
        screen.blit(text, text.get_rect(center=rect.center))
