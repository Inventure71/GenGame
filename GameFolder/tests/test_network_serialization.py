"""
Network serialization tests for MS2 pickups and effects.
"""

from BASE_files.BASE_network import NetworkObject
from GameFolder.pickups.GAME_pickups import AbilityPickup
from GameFolder.effects.obstacleeffect import ObstacleEffect


def test_ability_pickup_network_roundtrip():
    """AbilityPickup should serialize and deserialize with required fields."""
    pickup = AbilityPickup("Milk Splash", "primary", [200.0, 150.0])

    state = pickup.__getstate__()
    assert state["module_path"] == "GameFolder.pickups.GAME_pickups"
    assert state["class_name"] == "AbilityPickup"
    assert state["ability_name"] == "Milk Splash"
    assert state["ability_type"] == "primary"
    assert state["location"] == [200.0, 150.0]

    recreated = AbilityPickup.create_from_network_data(state)
    assert recreated is not None
    assert recreated.ability_name == pickup.ability_name
    assert recreated.ability_type == pickup.ability_type
    assert recreated.location == pickup.location


def test_effect_network_roundtrip():
    """ObstacleEffect should serialize and recreate via NetworkObject."""
    effect = ObstacleEffect([100.0, 100.0], size=20.0, owner_id="cow", mine=True, wall=False)

    state = effect.__getstate__()
    assert state["class_name"] == "ObstacleEffect"
    assert state["location"] == [100.0, 100.0]
    assert state["size"] == 20.0

    recreated = NetworkObject.create_from_network_data(state)
    assert recreated is not None
    assert recreated.location == effect.location
    assert recreated.size == effect.size
    assert recreated.mine is True
