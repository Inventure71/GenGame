import os
import random
from typing import Callable, Optional, Tuple, List

import pygame


class AssetHandler:
    """
    Shared asset loader with caching and graceful fallbacks.
    
    Supports both legacy flat file structure and new category/variant structure:
    - Legacy: Flat files in assets/ (e.g., "ERBA.png", "mucca0.png")
    - New: Category/variant/frame structure (e.g., "cows/Brown/0.png")
    
    Features:
    - Automatic caching of all loaded assets
    - Random variant selection with consistency (variants stored per object)
    - Automatic frame counting for animations
    - Alpha channel preservation for transparency
    - Fallback drawing functions for missing assets
    - Backward compatibility with legacy asset structure
    """

    _image_cache = {}
    _fallback_cache = {}
    _animation_cache = {}
    _alpha_cache = {}
    _font_cache = {}
    _text_cache = {}
    _text_cache_max = 512
    _variant_cache = {}  # Cache for available variants per category

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
            # Load image - always try to preserve alpha channel
            surface = pygame.image.load(path)
            # Always use convert_alpha() to ensure proper alpha channel support
            # This will preserve transparency if the image has it
            surface = surface.convert_alpha()
            
            if size is not None:
                # smoothscale preserves alpha channel automatically
                surface = pygame.transform.smoothscale(surface, size)
                # Ensure alpha is still present after scaling
                if not (surface.get_flags() & pygame.SRCALPHA):
                    # Recreate with alpha if it was lost (shouldn't happen with smoothscale)
                    new_surface = pygame.Surface(size, pygame.SRCALPHA)
                    new_surface.blit(surface, (0, 0))
                    surface = new_surface
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
    def get_image_with_alpha(
        cls,
        asset_name: str,
        size: Optional[Tuple[int, int]] = None,
        alpha: int = 255,
        fallback_draw: Optional[Callable[[pygame.Surface], None]] = None,
        fallback_tag: Optional[str] = None,
    ) -> Tuple[Optional[pygame.Surface], bool]:
        size = cls._normalize_size(size)
        surface, loaded = cls.get_image(
            asset_name,
            size=size,
            fallback_draw=fallback_draw,
            fallback_tag=fallback_tag,
        )
        if surface is None:
            return None, loaded
        alpha = int(max(0, min(255, alpha)))
        if alpha >= 255:
            return surface, loaded
        alpha_key = (asset_name, size, fallback_tag, alpha, loaded)
        if alpha_key not in cls._alpha_cache:
            alpha_surface = surface.copy()
            alpha_surface.set_alpha(alpha)
            cls._alpha_cache[alpha_key] = alpha_surface
        return cls._alpha_cache[alpha_key], loaded

    @classmethod
    def get_font(
        cls,
        font_name: Optional[str],
        size: int,
        bold: bool = False,
        italic: bool = False,
    ) -> pygame.font.Font:
        font_key = (font_name, int(size), bool(bold), bool(italic))
        font = cls._font_cache.get(font_key)
        if font is not None:
            return font
        if font_name:
            font = pygame.font.Font(font_name, int(size))
        else:
            font = pygame.font.Font(None, int(size))
        if bold:
            font.set_bold(True)
        if italic:
            font.set_italic(True)
        cls._font_cache[font_key] = font
        return font

    @classmethod
    def get_sys_font(
        cls,
        font_name: str,
        size: int,
        bold: bool = False,
        italic: bool = False,
    ) -> pygame.font.Font:
        font_key = ("sys", font_name, int(size), bool(bold), bool(italic))
        font = cls._font_cache.get(font_key)
        if font is not None:
            return font
        font = pygame.font.SysFont(font_name, int(size), bold=bold, italic=italic)
        cls._font_cache[font_key] = font
        return font

    @classmethod
    def render_text(
        cls,
        text: str,
        font_name: Optional[str],
        size: int,
        color: Tuple[int, int, int],
        antialias: bool = True,
        bold: bool = False,
        italic: bool = False,
    ) -> pygame.Surface:
        text = "" if text is None else str(text)
        color_key = tuple(int(c) for c in color)
        text_key = (
            text,
            font_name,
            int(size),
            color_key,
            bool(antialias),
            bool(bold),
            bool(italic),
        )
        surface = cls._text_cache.get(text_key)
        if surface is not None:
            return surface
        font = cls.get_font(font_name, size, bold=bold, italic=italic)
        surface = font.render(text, antialias, color_key)
        cls._text_cache[text_key] = surface
        if len(cls._text_cache) > cls._text_cache_max:
            # Drop an arbitrary cached item to bound memory use.
            cls._text_cache.pop(next(iter(cls._text_cache)))
        return surface

    @classmethod
    def render_text_from_font(
        cls,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        antialias: bool = True,
    ) -> pygame.Surface:
        text = "" if text is None else str(text)
        color_key = tuple(int(c) for c in color)
        text_key = ("font_obj", id(font), text, color_key, bool(antialias))
        surface = cls._text_cache.get(text_key)
        if surface is not None:
            return surface
        surface = font.render(text, antialias, color_key)
        cls._text_cache[text_key] = surface
        if len(cls._text_cache) > cls._text_cache_max:
            cls._text_cache.pop(next(iter(cls._text_cache)))
        return surface

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

    @classmethod
    def _get_category_variants(cls, category: str) -> List[str]:
        """Get all available variants for a category."""
        if category in cls._variant_cache:
            return cls._variant_cache[category]
        
        asset_root = cls._asset_root()
        category_path = os.path.join(asset_root, category)
        
        if not os.path.isdir(category_path):
            cls._variant_cache[category] = []
            return []
        
        variants = []
        for item in os.listdir(category_path):
            variant_path = os.path.join(category_path, item)
            if os.path.isdir(variant_path):
                variants.append(item)
        
        cls._variant_cache[category] = variants
        return variants

    @classmethod
    def get_random_variant(cls, category: str) -> Optional[str]:
        """Get a random variant from a category."""
        variants = cls._get_category_variants(category)
        if not variants:
            return None
        return random.choice(variants)

    @classmethod
    def _count_frames(cls, category: str, variant: str) -> int:
        """Count how many frames exist for a variant (0.png, 1.png, ...)."""
        asset_root = cls._asset_root()
        variant_path = os.path.join(asset_root, category, variant)
        
        if not os.path.isdir(variant_path):
            return 0
        
        frame_count = 0
        while True:
            frame_path = os.path.join(variant_path, f"{frame_count}.png")
            if not os.path.isfile(frame_path):
                break
            frame_count += 1
        
        return frame_count

    @classmethod
    def get_animation_from_category(
        cls,
        category: str,
        variant: Optional[str] = None,
        size: Optional[Tuple[int, int]] = None,
        fallback_draw: Optional[Callable[[pygame.Surface], None]] = None,
        fallback_tag: Optional[str] = None,
    ) -> Tuple[List[pygame.Surface], bool, Optional[str]]:
        """
        Load animation from category/variant structure.
        Returns: (frames, all_loaded, variant_used)
        """
        size = cls._normalize_size(size)
        
        # Get variant (random if not specified)
        if variant is None:
            variant = cls.get_random_variant(category)
            if variant is None:
                # No variants found, use fallback if provided
                if fallback_draw is not None and size is not None:
                    fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
                    fallback_draw(fallback_surface)
                    return [fallback_surface], False, None
                return [], False, None
        
        # Count frames automatically
        frame_count = cls._count_frames(category, variant)
        if frame_count == 0:
            # No frames found, use fallback if provided
            if fallback_draw is not None and size is not None:
                fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
                fallback_draw(fallback_surface)
                return [fallback_surface], False, variant
            return [], False, variant
        
        # Check cache
        anim_key = (category, variant, frame_count, size)
        if anim_key in cls._animation_cache:
            frames, loaded = cls._animation_cache[anim_key]
            return frames, loaded, variant
        
        # Load frames
        frames = []
        all_loaded = True
        asset_root = cls._asset_root()
        
        for i in range(frame_count):
            frame_path = os.path.join(asset_root, category, variant, f"{i}.png")
            if not os.path.isfile(frame_path):
                all_loaded = False
                frames = []
                break
            
            try:
                surface = pygame.image.load(frame_path).convert_alpha()
                if size is not None:
                    surface = pygame.transform.smoothscale(surface, size)
                frames.append(surface)
            except Exception:
                all_loaded = False
                frames = []
                break
        
        # Use fallback if loading failed
        if not all_loaded and fallback_draw is not None and size is not None:
            fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
            fallback_draw(fallback_surface)
            frames = [fallback_surface for _ in range(max(1, frame_count))]
        
        cls._animation_cache[anim_key] = (frames, all_loaded)
        return frames, all_loaded, variant

    @classmethod
    def get_image_from_category(
        cls,
        category: str,
        variant: Optional[str] = None,
        frame: int = 0,
        size: Optional[Tuple[int, int]] = None,
        fallback_draw: Optional[Callable[[pygame.Surface], None]] = None,
        fallback_tag: Optional[str] = None,
    ) -> Tuple[Optional[pygame.Surface], bool, Optional[str]]:
        """
        Load a single image from category/variant/frame structure.
        Returns: (surface, loaded, variant_used)
        """
        size = cls._normalize_size(size)
        
        # Get variant (random if not specified)
        if variant is None:
            variant = cls.get_random_variant(category)
            if variant is None:
                if fallback_draw is not None and size is not None:
                    fallback_key = (category, size, fallback_tag)
                    if fallback_key not in cls._fallback_cache:
                        fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
                        fallback_draw(fallback_surface)
                        cls._fallback_cache[fallback_key] = fallback_surface
                    return cls._fallback_cache[fallback_key], False, None
                return None, False, None
        
        # Build path
        asset_root = cls._asset_root()
        frame_path = os.path.join(asset_root, category, variant, f"{frame}.png")
        
        # Check cache
        image_key = (category, variant, frame, size)
        if image_key in cls._image_cache:
            surface, loaded = cls._image_cache[image_key]
            return surface, loaded, variant
        
        # Load image
        if not os.path.isfile(frame_path):
            if fallback_draw is not None and size is not None:
                fallback_key = (category, variant, size, fallback_tag)
                if fallback_key not in cls._fallback_cache:
                    fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
                    fallback_draw(fallback_surface)
                    cls._fallback_cache[fallback_key] = fallback_surface
                return cls._fallback_cache[fallback_key], False, variant
            return None, False, variant
        
        try:
            # Load image - always try to preserve alpha channel
            surface = pygame.image.load(frame_path)
            # Always use convert_alpha() to ensure proper alpha channel support
            # This will preserve transparency if the image has it
            surface = surface.convert_alpha()
            
            if size is not None:
                # smoothscale preserves alpha channel automatically
                surface = pygame.transform.smoothscale(surface, size)
                # Ensure alpha is still present after scaling
                if not (surface.get_flags() & pygame.SRCALPHA):
                    # Recreate with alpha if it was lost (shouldn't happen with smoothscale)
                    new_surface = pygame.Surface(size, pygame.SRCALPHA)
                    new_surface.blit(surface, (0, 0))
                    surface = new_surface
            cls._image_cache[image_key] = (surface, True)
            return surface, True, variant
        except Exception:
            if fallback_draw is not None and size is not None:
                fallback_key = (category, variant, size, fallback_tag)
                if fallback_key not in cls._fallback_cache:
                    fallback_surface = pygame.Surface(size, pygame.SRCALPHA)
                    fallback_draw(fallback_surface)
                    cls._fallback_cache[fallback_key] = fallback_surface
                return cls._fallback_cache[fallback_key], False, variant
            return None, False, variant
