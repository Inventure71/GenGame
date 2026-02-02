import pygame
from BASE_components.BASE_network import NetworkObject
from BASE_components.BASE_asset_handler import AssetHandler


class BasePickup(NetworkObject):
    """Base pickup with world-space location and simple rendering."""

    def __init__(
        self,
        location: [float, float],
        width: float = 36,
        height: float = 36,
        pickup_radius: float = 48,
    ):
        super().__init__()
        self.location = location
        self.width = width
        self.height = height
        self.pickup_radius = pickup_radius
        self.is_active = True
        self.color = (200, 200, 200)
        self.label = ""
        self.asset_image_name = None
        self.init_graphics()

    def init_graphics(self):
        super().init_graphics()
        try:
            pygame.display.get_surface()
        except Exception:
            return

    def pickup(self):
        self.is_active = False

    def get_pickup_rect(self, arena_height: float) -> pygame.Rect:
        py_x = self.location[0] - self.pickup_radius / 2
        py_y = arena_height - self.location[1] - self.pickup_radius / 2
        return pygame.Rect(py_x, py_y, self.pickup_radius, self.pickup_radius)

    def get_label(self) -> str:
        return str(getattr(self, "label", "") or "")

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        if not self.is_active or not self._graphics_initialized:
            return
        if camera is not None:
            rect = camera.world_center_rect_to_screen(
                self.location[0], self.location[1], self.width, self.height
            )
        else:
            py_x = self.location[0] - self.width / 2
            py_y = arena_height - self.location[1] - self.height / 2
            rect = pygame.Rect(py_x, py_y, self.width, self.height)
        visual_width, visual_height = AssetHandler.get_visual_size(rect.width, rect.height)
        visual_rect = pygame.Rect(0, 0, visual_width, visual_height)
        visual_rect.center = rect.center
        sprite = None
        loaded = False
        if self.asset_image_name:
            sprite, loaded = AssetHandler.get_image(
                self.asset_image_name,
                size=(visual_width, visual_height),
            )

        if sprite is not None and loaded:
            # Apply color tinting to the sprite
            tinted_sprite = sprite.copy()
            # Create a color overlay surface
            color_overlay = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            # Use the pickup's color with moderate alpha for visible tinting
            # If color is the default (200, 200, 200), don't tint (use original sprite)
            default_color = (200, 200, 200)
            if self.color != default_color:
                tint_color = (*self.color, 180)  # ~70% opacity for stronger tinting
                color_overlay.fill(tint_color)
                # Blend the color overlay with the sprite using multiply for tinting
                tinted_sprite.blit(color_overlay, (0, 0), special_flags=pygame.BLEND_MULT)
            sprite_rect = tinted_sprite.get_rect(center=rect.center)
            screen.blit(tinted_sprite, sprite_rect)
        else:
            pygame.draw.rect(screen, self.color, visual_rect, border_radius=6)
            pygame.draw.rect(screen, (20, 20, 20), visual_rect, 2, border_radius=6)

        if sprite is None or not loaded:
            label = self.get_label()
            if label:
                text = AssetHandler.render_text(label, None, 20, (30, 30, 30))
                screen.blit(text, text.get_rect(center=rect.center))
