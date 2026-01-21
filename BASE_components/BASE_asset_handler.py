import os
from typing import Callable, Optional, Tuple, List

import pygame


class AssetHandler:
    """Shared asset loader with caching and graceful fallbacks."""

    _image_cache = {}
    _fallback_cache = {}
    _animation_cache = {}

    @staticmethod
    def _asset_root() -> str:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_dir, "GameFolder", "assets")

    @staticmethod
    def _normalize_size(size: Optional[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        if size is None:
            return None
        return (max(1, int(size[0])), max(1, int(size[1])))

    @classmethod
    def _load_image(cls, asset_name: str, size: Optional[Tuple[int, int]]) -> Tuple[Optional[pygame.Surface], bool]:
        asset_root = cls._asset_root()
        path = os.path.join(asset_root, asset_name)
        if not os.path.isfile(path):
            return None, False
        try:
            surface = pygame.image.load(path).convert_alpha()
            if size is not None:
                surface = pygame.transform.smoothscale(surface, size)
            return surface, True
        except Exception:
            return None, False

    @classmethod
    def get_image(
        cls,
        asset_name: str,
        size: Optional[Tuple[int, int]] = None,
        fallback_draw: Optional[Callable[[pygame.Surface], None]] = None,
        fallback_tag: Optional[str] = None,
    ) -> Tuple[Optional[pygame.Surface], bool]:
        size = cls._normalize_size(size)
        image_key = (asset_name, size)
        if image_key not in cls._image_cache:
            cls._image_cache[image_key] = cls._load_image(asset_name, size)

        surface, loaded = cls._image_cache[image_key]
        if loaded or fallback_draw is None or size is None:
            return surface, loaded

        fallback_key = (asset_name, size, fallback_tag)
        if fallback_key not in cls._fallback_cache:
            fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
            fallback_draw(fallback_surface)
            cls._fallback_cache[fallback_key] = fallback_surface
        return cls._fallback_cache[fallback_key], False

    @classmethod
    def get_animation(
        cls,
        base_name: str,
        frame_count: int,
        size: Optional[Tuple[int, int]] = None,
        fallback_draw: Optional[Callable[[pygame.Surface], None]] = None,
        fallback_tag: Optional[str] = None,
    ) -> Tuple[List[pygame.Surface], bool]:
        size = cls._normalize_size(size)
        anim_key = (base_name, frame_count, size)
        if anim_key in cls._animation_cache:
            return cls._animation_cache[anim_key]

        frames = []
        all_loaded = True
        for i in range(frame_count):
            frame_name = f"{base_name}{i}.png"
            frame, loaded = cls.get_image(frame_name, size=size, fallback_draw=None)
            if not loaded or frame is None:
                all_loaded = False
                frames = []
                break
            frames.append(frame)

        if not all_loaded and fallback_draw is not None and size is not None:
            fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
            fallback_draw(fallback_surface)
            frames = [fallback_surface for _ in range(max(1, frame_count))]

        cls._animation_cache[anim_key] = (frames, all_loaded)
        return frames, all_loaded
