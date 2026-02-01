import pygame
from BASE_components.BASE_effects import TimedEffect


class RadialEffect(TimedEffect):
    def __init__(
        self,
        location,
        radius,
        owner_id,
        damage,
        damage_cooldown,
        knockback_distance: float = 0.0,
        lifetime: float = 0.5,
    ):
        super().__init__(location, lifetime)
        self.radius = radius
        self.owner_id = owner_id
        self.damage = damage
        self.damage_cooldown = damage_cooldown
        self.knockback_distance = knockback_distance

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self._graphics_initialized:
            return
        if camera is not None:
            center = camera.world_to_screen_point(self.location[0], self.location[1])
            center = (int(center[0]), int(center[1]))
        else:
            center = (int(self.location[0]), int(arena_height - self.location[1]))
        pygame.draw.circle(screen, (255, 255, 255), center, int(self.radius), 2)

