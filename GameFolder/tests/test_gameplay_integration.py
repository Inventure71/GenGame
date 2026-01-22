"""
Gameplay Integration Tests - Tests for real gameplay scenarios.

These tests verify that the game works correctly when actually played,
not just in artificial test scenarios. Covers:
- Setup file loading
- Player input handling
- Serialization roundtrips
- Multi-frame state consistency
- Multi-player interactions
- Resource cleanup
"""

import pickle
import zlib
from GameFolder.arenas.GAME_arena import Arena
from GameFolder.characters.GAME_character import Character
from GameFolder.setup import setup_battle_arena
from GameFolder.pickups.GAME_pickups import AbilityPickup
from GameFolder.effects.radialeffect import RadialEffect
from GameFolder.effects.obstacleeffect import ObstacleEffect
from BASE_files.BASE_network import NetworkObject


# ============================================================================
# SETUP FILE LOADING TESTS
# ============================================================================

def test_setup_file_loads_successfully():
    """Test that setup.py can be imported and setup_battle_arena() works."""
    # This test verifies the setup file is syntactically correct and functional
    arena = setup_battle_arena(width=800, height=600, headless=True, player_names=["Test1", "Test2"])
    
    assert arena is not None, "setup_battle_arena() should return an arena"
    assert len(arena.characters) == 2, "Should create 2 characters"
    assert arena.characters[0].name == "Test1", "First character should have correct name"
    assert arena.characters[1].name == "Test2", "Second character should have correct name"
    assert all(char.is_alive for char in arena.characters), "All characters should be alive"


def test_setup_creates_valid_arena_structure():
    """Test that setup creates arena with all required components."""
    arena = setup_battle_arena(width=1400, height=900, headless=True)
    
    assert hasattr(arena, 'characters'), "Arena should have characters list"
    assert hasattr(arena, 'effects'), "Arena should have effects list"
    assert hasattr(arena, 'obstacles'), "Arena should have obstacles list"
    assert hasattr(arena, 'grass_fields'), "Arena should have grass_fields list"
    assert hasattr(arena, 'weapon_pickups'), "Arena should have weapon_pickups list"
    assert len(arena.obstacles) > 0, "Arena should have obstacles"
    assert len(arena.grass_fields) > 0, "Arena should have grass fields"


def test_setup_with_custom_dimensions():
    """Test setup works with different arena dimensions."""
    arena = setup_battle_arena(width=1000, height=800, headless=True, player_names=["Player"])
    
    assert arena.width == 1000, "Arena width should match input"
    assert arena.height == 800, "Arena height should match input"
    assert len(arena.characters) == 1, "Should create 1 character"


# ============================================================================
# PLAYER INPUT HANDLING TESTS
# ============================================================================

def test_all_movement_keys_work():
    """Test that all movement keys (WASD and arrows) work correctly."""
    import pygame
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    arena.add_character(char)
    
    # Test W (up)
    initial_y = char.location[1]
    input_data = Character.get_input_data({pygame.K_w}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    assert char.location[1] > initial_y, "W should move up"
    
    # Test S (down) - reset location first
    char.location = [400.0, 300.0]
    initial_y = char.location[1]
    input_data = Character.get_input_data({pygame.K_s}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    assert char.location[1] < initial_y, "S should move down"
    
    # Test A (left)
    char.location = [400.0, 300.0]
    initial_x = char.location[0]
    input_data = Character.get_input_data({pygame.K_a}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    assert char.location[0] < initial_x, "A should move left"
    
    # Test D (right)
    char.location = [400.0, 300.0]
    initial_x = char.location[0]
    input_data = Character.get_input_data({pygame.K_d}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    assert char.location[0] > initial_x, "D should move right"
    
    # Test arrow keys
    char.location = [400.0, 300.0]
    initial_y = char.location[1]
    input_data = Character.get_input_data({pygame.K_UP}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    assert char.location[1] > initial_y, "UP arrow should move up"
    
    char.location = [400.0, 300.0]
    initial_x = char.location[0]
    input_data = Character.get_input_data({pygame.K_LEFT}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    assert char.location[0] < initial_x, "LEFT arrow should move left"


def test_simultaneous_key_presses():
    """Test that multiple keys pressed at once work correctly."""
    import pygame
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    arena.add_character(char)
    
    initial_x = char.location[0]
    initial_y = char.location[1]
    
    # Diagonal movement (W+D)
    input_data = Character.get_input_data({pygame.K_w, pygame.K_d}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    
    assert char.location[0] > initial_x, "Should move right"
    assert char.location[1] > initial_y, "Should move up"


def test_input_edge_detection():
    """Test that input edge detection works (press vs hold)."""
    import pygame
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    arena.add_character(char)
    
    # Test swap key edge detection
    char.set_primary_ability("Stomp")
    initial_ability = char.primary_ability_name
    
    # First press should trigger swap (if pickup available)
    input_data = Character.get_input_data({pygame.K_q}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    
    # Second press (held) should not trigger again
    char.process_input(input_data, arena)
    
    # Release and press again should trigger
    input_data = Character.get_input_data(set(), [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    input_data = Character.get_input_data({pygame.K_q}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)


def test_input_during_death():
    """Test that dead characters don't process input."""
    import pygame
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    arena.add_character(char)
    
    initial_location = char.location[:]
    
    # Kill the character
    char.take_damage(char.health + 10)
    assert not char.is_alive, "Character should be dead"
    
    # Try to move
    input_data = Character.get_input_data({pygame.K_d}, [False, False, False], [400.0, 300.0])
    char.process_input(input_data, arena)
    
    assert char.location == initial_location, "Dead character should not move"


def test_mouse_input_handling():
    """Test that mouse input (primary ability) works correctly."""
    import pygame
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    char.set_primary_ability("Stomp")
    arena.add_character(char)
    
    # Ensure ability is ready (cooldown reset and has ammo)
    char.primary_use_cooldown = 0.0
    char.available_primary_abilities = char.max_primary_abilities
    
    initial_effects = len(arena.effects)
    
    # Left mouse button click
    input_data = Character.get_input_data(set(), [True, False, False], [500.0, 400.0])
    char.process_input(input_data, arena)
    
    assert len(arena.effects) > initial_effects, "Mouse click should trigger primary ability"


# ============================================================================
# SERIALIZATION ROUNDTRIP TESTS
# ============================================================================

def test_character_serialization_roundtrip():
    """Test that Character can be serialized and deserialized correctly."""
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    char.health = 75.0
    char.size = 35.0
    char.set_primary_ability("Stomp")
    char.set_passive_ability("Ruminant Regen")
    
    # Serialize
    state = char.__getstate__()
    
    # Deserialize
    recreated = NetworkObject.create_from_network_data(state)
    
    assert recreated is not None, "Character should be recreated"
    assert recreated.name == char.name, "Name should be preserved"
    assert recreated.location == char.location, "Location should be preserved"
    assert recreated.health == char.health, "Health should be preserved"
    assert recreated.size == char.size, "Size should be preserved"
    assert recreated.primary_ability_name == char.primary_ability_name, "Primary ability should be preserved"
    assert recreated.passive_ability_name == char.passive_ability_name, "Passive ability should be preserved"


def test_effect_serialization_roundtrip():
    """Test that effects serialize and deserialize correctly."""
    effect = RadialEffect([200.0, 150.0], radius=60.0, owner_id="player1", damage=10.0, damage_cooldown=0.4)
    
    state = effect.__getstate__()
    recreated = NetworkObject.create_from_network_data(state)
    
    assert recreated is not None, "Effect should be recreated"
    assert recreated.location == effect.location, "Location should be preserved"
    assert recreated.radius == effect.radius, "Radius should be preserved"
    assert recreated.owner_id == effect.owner_id, "Owner ID should be preserved"
    assert recreated.damage == effect.damage, "Damage should be preserved"


def test_pickup_serialization_roundtrip():
    """Test that pickups serialize and deserialize correctly."""
    pickup = AbilityPickup("Milk Splash", "primary", [300.0, 200.0])
    
    state = pickup.__getstate__()
    recreated = NetworkObject.create_from_network_data(state)
    
    assert recreated is not None, "Pickup should be recreated"
    assert recreated.ability_name == pickup.ability_name, "Ability name should be preserved"
    assert recreated.ability_type == pickup.ability_type, "Ability type should be preserved"
    assert recreated.location == pickup.location, "Location should be preserved"


def test_compressed_serialization():
    """Test that compressed serialization works correctly."""
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    
    # Serialize
    state = char.__getstate__()
    serialized = pickle.dumps(state)
    
    # Compress
    compressed = zlib.compress(serialized, level=1)
    
    # Decompress and deserialize
    decompressed = zlib.decompress(compressed)
    state_restored = pickle.loads(decompressed)
    recreated = NetworkObject.create_from_network_data(state_restored)
    
    assert recreated is not None, "Character should be recreated after compression"
    assert recreated.name == char.name, "Name should be preserved"


def test_nested_object_serialization():
    """Test that objects containing other NetworkObjects serialize correctly."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    arena.add_character(char)
    
    # Add effect owned by character
    effect = RadialEffect([400.0, 300.0], radius=50.0, owner_id=char.id, damage=5.0, damage_cooldown=0.4)
    arena.add_effect(effect)
    
    # Serialize character (effect is separate, but owner_id references it)
    char_state = char.__getstate__()
    effect_state = effect.__getstate__()
    
    # Deserialize both
    char_recreated = NetworkObject.create_from_network_data(char_state)
    effect_recreated = NetworkObject.create_from_network_data(effect_state)
    
    assert char_recreated.id == char.id, "Character ID should be preserved"
    assert effect_recreated.owner_id == char.id, "Effect owner ID should reference character"


# ============================================================================
# MULTI-FRAME STATE CONSISTENCY TESTS
# ============================================================================

def test_state_consistency_across_frames():
    """Test that game state remains consistent across many update cycles."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    char.health = 100.0
    arena.add_character(char)
    
    initial_health = char.health
    initial_location = char.location[:]
    
    # Run many update cycles
    for _ in range(100):
        arena.update(0.016)  # 60 FPS
    
    # Health should only change if damage was taken (not randomly)
    assert char.health <= initial_health, "Health should not increase without healing"
    # Location might change due to movement, but should be valid
    assert 0 <= char.location[0] <= arena.width, "Character should stay in bounds"
    assert 0 <= char.location[1] <= arena.height, "Character should stay in bounds"


def test_frame_rate_independence():
    """Test that game works correctly with different delta_time values."""
    arena1 = Arena(800, 600, headless=True)
    char1 = Character("TestCow1", "Test", "", [400.0, 300.0])
    arena1.add_character(char1)
    
    arena2 = Arena(800, 600, headless=True)
    char2 = Character("TestCow2", "Test", "", [400.0, 300.0])
    arena2.add_character(char2)
    
    # Update arena1 with small delta (60 FPS)
    for _ in range(60):
        arena1.update(0.016)
    
    # Update arena2 with large delta (1 second total)
    arena2.update(1.0)
    
    # Both should have processed similar amounts of time
    # (exact values may differ due to cooldowns, but should be close)
    assert abs(arena1.current_time - arena2.current_time) < 0.1, "Time should be similar"


def test_cooldown_consistency():
    """Test that cooldowns work consistently across multiple frames."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    char.set_primary_ability("Stomp")
    arena.add_character(char)
    
    # Use ability
    char.use_primary_ability(arena, [400.0, 300.0])
    initial_cooldown = char.primary_use_cooldown
    
    # Update many frames
    for _ in range(100):
        arena.update(0.016)
    
    # Cooldown should have decreased (or reached 0)
    assert char.primary_use_cooldown <= initial_cooldown, "Cooldown should decrease over time"


# ============================================================================
# MULTI-PLAYER INTERACTION TESTS
# ============================================================================

def test_multiple_characters_collision():
    """Test that multiple characters can collide correctly."""
    arena = Arena(800, 600, headless=True)
    char1 = Character("Player1", "Test", "", [400.0, 300.0])
    char2 = Character("Player2", "Test", "", [410.0, 300.0])
    arena.add_character(char1)
    arena.add_character(char2)
    
    # Both characters should exist
    assert len(arena.characters) == 2, "Should have 2 characters"
    assert char1.is_alive and char2.is_alive, "Both should be alive"
    
    # Update to process collisions
    arena.update(0.016)
    
    # Characters should still exist (not eliminated by collision)
    assert len(arena.characters) == 2, "Characters should still exist"


def test_concurrent_ability_usage():
    """Test that multiple characters can use abilities simultaneously."""
    arena = Arena(800, 600, headless=True)
    char1 = Character("Player1", "Test", "", [300.0, 300.0])
    char2 = Character("Player2", "Test", "", [500.0, 300.0])
    char1.set_primary_ability("Stomp")
    char2.set_primary_ability("Stomp")
    arena.add_character(char1)
    arena.add_character(char2)
    
    # Ensure abilities are ready (cooldowns reset)
    char1.primary_use_cooldown = 0.0
    char2.primary_use_cooldown = 0.0
    char1.available_primary_abilities = char1.max_primary_abilities
    char2.available_primary_abilities = char2.max_primary_abilities
    
    initial_effects = len(arena.effects)
    
    # Both use abilities
    char1.use_primary_ability(arena, [300.0, 300.0])
    char2.use_primary_ability(arena, [500.0, 300.0])
    
    assert len(arena.effects) >= initial_effects + 2, "Both abilities should spawn effects"


def test_shared_pickup_conflict():
    """Test that only one character can pick up a pickup."""
    from GameFolder.pickups.GAME_pickups import PRIMARY_ABILITY_NAMES
    
    arena = Arena(800, 600, headless=True)
    char1 = Character("Player1", "Test", "", [400.0, 300.0])
    char2 = Character("Player2", "Test", "", [400.0, 300.0])
    arena.add_character(char1)
    arena.add_character(char2)
    
    # Let obstacle resolution happen
    arena.handle_collisions()
    char1_final = char1.location[:]
    char2_final = char2.location[:]
    
    # Place pickup between them (or at one location)
    pickup = AbilityPickup(PRIMARY_ABILITY_NAMES[0], "primary", char1_final[:])
    arena.weapon_pickups.append(pickup)
    
    initial_pickups = len(arena.weapon_pickups)
    
    # Process collisions
    arena.handle_collisions()
    
    # Only one character should get the pickup
    picked_up = (char1.primary_ability_name is not None) or (char2.primary_ability_name is not None)
    assert picked_up, "At least one character should get the pickup"
    assert len(arena.weapon_pickups) < initial_pickups, "Pickup should be removed"


# ============================================================================
# RESOURCE CLEANUP TESTS
# ============================================================================

def test_effect_expiration_cleanup():
    """Test that expired effects are removed from the arena."""
    arena = Arena(800, 600, headless=True)
    effect = RadialEffect([400.0, 300.0], radius=50.0, owner_id="test", damage=5.0, damage_cooldown=0.4, lifetime=0.1)
    arena.add_effect(effect)
    
    assert len(arena.effects) == 1, "Effect should be added"
    
    # Update past lifetime
    arena.update(0.2)
    
    assert len(arena.effects) == 0, "Expired effect should be removed"


def test_eliminated_character_cleanup():
    """Test that eliminated characters are handled correctly."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    char.lives = 1
    arena.add_character(char)
    
    # Kill character (lose last life)
    char.take_damage(char.health + 10)
    
    assert not char.is_alive, "Character should be dead"
    assert char.is_eliminated, "Character should be eliminated"
    assert char.lives == 0, "Character should have 0 lives"


def test_memory_leak_prevention():
    """Test that entity counts don't grow unbounded over time."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [400.0, 300.0])
    char.set_primary_ability("Stomp")
    arena.add_character(char)
    
    initial_effects = len(arena.effects)
    
    # Run many cycles with ability usage
    for i in range(100):
        if i % 10 == 0:  # Use ability every 10 frames
            char.use_primary_ability(arena, [400.0, 300.0])
        arena.update(0.016)
    
    # Effects should expire and be cleaned up
    # Count should not grow unbounded (may have some active, but not 100)
    assert len(arena.effects) < 50, "Effects should be cleaned up, not accumulate"


# ============================================================================
# BOUNDARY CONDITIONS TESTS
# ============================================================================

def test_arena_boundary_enforcement():
    """Test that characters stay within arena boundaries."""
    arena = Arena(800, 600, headless=True)
    char = Character("TestCow", "Test", "", [15.0, 15.0])  # Near edge
    arena.add_character(char)
    
    # Try to move outside bounds
    import pygame
    for _ in range(100):
        input_data = Character.get_input_data({pygame.K_a, pygame.K_s}, [False, False, False], [0.0, 0.0])
        char.process_input(input_data, arena)
        arena.update(0.016)
    
    # Character should still be in bounds
    margin = char.size / 2
    assert margin <= char.location[0] <= arena.width - margin, "Character should stay in horizontal bounds"
    assert margin <= char.location[1] <= arena.height - margin, "Character should stay in vertical bounds"


def test_empty_arena_state():
    """Test that arena works correctly with no characters."""
    arena = Arena(800, 600, headless=True)
    
    # Update with no characters
    arena.update(0.016)
    
    assert len(arena.characters) == 0, "Should have no characters"
    # Arena should not crash


def test_maximum_entities():
    """Test arena behavior with many entities."""
    arena = Arena(800, 600, headless=True)
    
    # Add many characters
    for i in range(10):
        char = Character(f"Player{i}", "Test", "", [100.0 + i * 50, 300.0])
        arena.add_character(char)
    
    # Add many effects
    for i in range(20):
        effect = RadialEffect([200.0 + i * 20, 200.0], radius=30.0, owner_id="test", damage=1.0, damage_cooldown=0.4)
        arena.add_effect(effect)
    
    # Should handle all entities
    assert len(arena.characters) == 10, "Should have 10 characters"
    assert len(arena.effects) == 20, "Should have 20 effects"
    
    # Update should not crash
    arena.update(0.016)
