import pygame
import random
from BASE_components.BASE_platform import BaseWorldPlatform
from BASE_components.BASE_asset_handler import AssetHandler

class WorldObstacle(BaseWorldPlatform):
    def __init__(self, center_x: float, center_y: float, size: float, obstacle_type: str, arena_height: float):
        self.world_center = [center_x, center_y]
        self.size = size
        self.obstacle_type = obstacle_type
        self._anim_offset = random.randint(0, 1000)
        
        # Random animation speed per obstacle (milliseconds per frame)
        # Range: 160-400ms per frame (slower animations - at least half as slow as before)
        self._anim_speed = random.uniform(160, 400)

        # Determine size category for blocking obstacles (small, medium, big)
        # Based on size ranges: small (50-70), medium (71-95), big (96-200)
        if obstacle_type == "blocking":
            if size <= 70:
                self.obstacle_size_category = "small"
            elif size <= 95:
                self.obstacle_size_category = "medium"
            else:
                self.obstacle_size_category = "big"
        else:
            self.obstacle_size_category = None

        # Pick and store variant for consistency (so same obstacle always uses same variant)
        if obstacle_type == "slowing":
            self.obstacle_variant = AssetHandler.get_random_variant("slowObstacles")
        elif obstacle_type == "blocking":
            self.obstacle_variant = AssetHandler.get_random_variant("blockObstacles", self.obstacle_size_category)
        else:
            self.obstacle_variant = None

        color = (80, 80, 80) if obstacle_type == "blocking" else (60, 120, 160)
        super().__init__(center_x, center_y, size, size, arena_height, color=color)
        self._set_network_identity("GameFolder.world.GAME_world_objects", "WorldObstacle")

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        rect = self.get_draw_rect(arena_height, camera)
        visual_width, visual_height = AssetHandler.get_visual_size(rect.width, rect.height)
        visual_rect = pygame.Rect(0, 0, visual_width, visual_height)
        visual_rect.center = rect.center

        if self.obstacle_type == "slowing":
            def fallback(surface):
                center = (surface.get_width() // 2, surface.get_height() // 2)
                radius = min(center[0], center[1])
                pygame.draw.circle(surface, (70, 140, 180), center, radius)
                pygame.draw.circle(surface, (30, 60, 80), center, radius, 2)

            frames, _, variant = AssetHandler.get_animation_from_category(
                "slowObstacles",
                variant=self.obstacle_variant,  # Use stored variant
                size=(visual_width, visual_height),
                fallback_draw=fallback,
            )
            if frames:
                tick = pygame.time.get_ticks() if pygame.get_init() else 0
                # Use per-obstacle animation speed instead of fixed 120ms
                frame_index = int((tick / self._anim_speed) + self._anim_offset) % len(frames)
                screen.blit(frames[frame_index], visual_rect)
            return

        elif self.obstacle_type == "blocking":
            def fallback(surface):
                center = (surface.get_width() // 2, surface.get_height() // 2)
                radius = min(center[0], center[1])
                pygame.draw.circle(surface, (90, 90, 90), center, radius)
                pygame.draw.circle(surface, (30, 30, 30), center, radius, 2)

            # Try to load image from blockObstacles category with size-based subcategory
            sprite, loaded, variant = AssetHandler.get_image_from_category(
                "blockObstacles",
                variant=self.obstacle_variant,  # Use stored variant
                frame=0,
                size=(visual_width, visual_height),
                fallback_draw=fallback,
                subcategory=self.obstacle_size_category,  # Use size category (big/medium/small)
            )
            if sprite is not None:
                screen.blit(sprite, visual_rect)
            elif not loaded:
                # Fallback to colored circle if asset not found
                center = (visual_rect.centerx, visual_rect.centery)
                radius = min(visual_rect.width, visual_rect.height) // 2
                pygame.draw.circle(screen, (90, 90, 90), center, radius)
                pygame.draw.circle(screen, (30, 30, 30), center, radius, 2)
            return

        # Default fallback for unknown obstacle types
        center = (visual_rect.centerx, visual_rect.centery)
        radius = min(visual_rect.width, visual_rect.height) // 2
        pygame.draw.circle(screen, (90, 90, 90), center, radius)
        pygame.draw.circle(screen, (30, 30, 30), center, radius, 2)


class GrassField(BaseWorldPlatform):
    def __init__(self, center_x: float, center_y: float, radius: float, max_food: float, arena_height: float):
        self.world_center = [center_x, center_y]
        self.radius = radius
        self.max_food = max_food
        self.current_food = max_food
        
        # Pick and store variant for consistency
        self.grass_variant = AssetHandler.get_random_variant("grass")

        super().__init__(center_x, center_y, radius * 2, radius * 2, arena_height, color=(40, 160, 40))
        self._set_network_identity("GameFolder.world.GAME_world_objects", "GrassField")

    def can_eat(self, cow_x: float, cow_y: float, cow_radius: float) -> bool:
        dx = cow_x - self.world_center[0]
        dy = cow_y - self.world_center[1]
        return (dx * dx + dy * dy) <= (self.radius + cow_radius) ** 2

    def eat(self) -> bool:
        if self.current_food > 0:
            self.current_food -= 1
            return True
        return False

    def regrow(self, delta_time: float, rate: float = 0.2):
        if self.current_food < self.max_food:
            self.current_food = min(self.max_food, self.current_food + rate * delta_time)

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if self.is_destroyed or not self._graphics_initialized:
            return
        fullness = self.current_food / max(1.0, self.max_food)
        bucket = max(0, min(10, int(fullness * 10)))

        rect = self.get_draw_rect(arena_height, camera)
        visual_width, visual_height = AssetHandler.get_visual_size(rect.width, rect.height)
        visual_rect = pygame.Rect(0, 0, visual_width, visual_height)
        visual_rect.center = rect.center
        def fallback(surface):
            center = (surface.get_width() // 2, surface.get_height() // 2)
            radius = min(center[0], center[1])
            color = (40, int(120 + 100 * fullness), 40)
            pygame.draw.circle(surface, color, center, radius)
            pygame.draw.circle(surface, (20, 60, 20), center, radius, 2)

        # Try to load from grass category first
        grass_surface, loaded, variant = AssetHandler.get_image_from_category(
            "grass",
            variant=self.grass_variant,  # Use stored variant
            frame=0,
            size=(visual_width, visual_height),
            fallback_draw=fallback,
            fallback_tag=f"fullness_{bucket}",
        )
        
        # Store variant if it was randomly selected
        if variant is not None and self.grass_variant is None:
            self.grass_variant = variant
        
        # If category system didn't work, fall back to old flat file system
        if not loaded and grass_surface is None:
            grass_surface, loaded = AssetHandler.get_image(
                "ERBA.png",
                size=(visual_width, visual_height),
                fallback_draw=fallback,
                fallback_tag=f"fullness_{bucket}",
            )
        
        if grass_surface is None:
            return
            
        # Apply alpha based on fullness if asset was loaded and not at full
        if loaded and fullness < 1.0:
            # Create a copy to avoid modifying cached surface
            grass_surface = grass_surface.copy()
            grass_surface.set_alpha(int(120 + 120 * (bucket / 10.0)))
        
        screen.blit(grass_surface, visual_rect)
