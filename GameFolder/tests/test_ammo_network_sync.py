"""
Tests for ammo system network synchronization.
Verifies ammo attributes are properly synchronized between client and server.
"""

from BASE_components.BASE_weapon import BaseWeapon
from BASE_components.BASE_ammo import BaseAmmoPickup
from BASE_files.network_client import EntityManager


def test_weapon_ammo_network_serialization():
    """Test that weapon ammo attributes are serialized correctly."""
    weapon = BaseWeapon('Test Gun', 10, 0.5, 20.0, max_ammo=30, ammo_per_shot=2)
    weapon.ammo = 15

    # Serialize
    state = weapon.__getstate__()

    # Verify ammo attributes are included
    assert 'max_ammo' in state
    assert 'ammo' in state
    assert 'ammo_per_shot' in state

    assert state['max_ammo'] == 30
    assert state['ammo'] == 15
    assert state['ammo_per_shot'] == 2

    # Deserialize
    new_weapon = BaseWeapon.create_from_network_data(state)
    assert new_weapon is not None
    assert new_weapon.max_ammo == 30
    assert new_weapon.ammo == 15
    assert new_weapon.ammo_per_shot == 2


def test_ammo_pickup_network_serialization():
    """Test that ammo pickups are serialized correctly."""
    ammo = BaseAmmoPickup([200, 150], ammo_amount=20)

    # Serialize
    state = ammo.__getstate__()

    # Verify key attributes
    assert state['module_path'] == 'BASE_components.BASE_ammo'
    assert state['class_name'] == 'BaseAmmoPickup'
    assert state['ammo_amount'] == 20
    assert state['location'] == [200, 150]
    assert state['is_active'] == True

    # Deserialize
    new_ammo = BaseAmmoPickup.create_from_network_data(state)
    assert new_ammo is not None
    assert new_ammo.ammo_amount == 20
    assert new_ammo.location == [200, 150]
    assert new_ammo.is_active == True


def test_entity_manager_handles_ammo_pickups():
    """Test that EntityManager can create and update ammo pickups."""
    manager = EntityManager()

    # Create ammo pickup data as it would come from server
    ammo_data = {
        'network_id': 'test-ammo-123',
        'module_path': 'BASE_components.BASE_ammo',
        'class_name': 'BaseAmmoPickup',
        'location': [300, 200],
        'ammo_amount': 15,
        'is_active': True
    }

    # Simulate receiving from server
    manager._create_entity('test-ammo-123', ammo_data)

    # Verify ammo pickup was created
    assert 'test-ammo-123' in manager.entities
    ammo = manager.entities['test-ammo-123']
    assert isinstance(ammo, BaseAmmoPickup)
    assert ammo.location == [300, 200]
    assert ammo.ammo_amount == 15
    assert ammo.is_active == True

    # Test updating
    updated_data = ammo_data.copy()
    updated_data['is_active'] = False
    manager._update_entity('test-ammo-123', updated_data)

    # Verify update worked
    updated_ammo = manager.entities['test-ammo-123']
    assert updated_ammo.is_active == False


def test_ammo_pickup_removal():
    """Test that ammo pickups are properly removed when they no longer exist on server."""
    manager = EntityManager()

    # Create ammo pickup
    ammo_data = {
        'network_id': 'test-ammo-456',
        'module_path': 'BASE_components.BASE_ammo',
        'class_name': 'BaseAmmoPickup',
        'location': [100, 100],
        'ammo_amount': 10,
        'is_active': True
    }

    manager._create_entity('test-ammo-456', ammo_data)
    assert 'test-ammo-456' in manager.entities

    # Simulate server update that doesn't include this ammo pickup
    game_state = {
        'characters': [],
        'projectiles': [],
        'weapons': [],
        'ammo_pickups': [],  # Empty - ammo pickup should be removed
        'platforms': []
    }

    manager.update_from_server(game_state)

    # Verify ammo pickup was removed
    assert 'test-ammo-456' not in manager.entities


def test_weapon_ammo_persistence_across_network():
    """Test that weapon ammo state persists correctly in network updates."""
    manager = EntityManager()

    # Create weapon with partial ammo
    weapon_data = {
        'network_id': 'test-weapon-789',
        'module_path': 'BASE_components.BASE_weapon',
        'class_name': 'BaseWeapon',
        'name': 'Network Gun',
        'damage': 15,
        'cooldown': 0.4,
        'projectile_speed': 25.0,
        'max_ammo': 25,
        'ammo': 12,  # Partial ammo
        'ammo_per_shot': 1,
        'location': [150, 150],
        'is_equipped': False
    }

    # Create weapon
    manager._create_entity('test-weapon-789', weapon_data)
    weapon = manager.entities['test-weapon-789']

    assert weapon.ammo == 12
    assert weapon.max_ammo == 25

    # Update with new ammo count (simulating ammo consumption on server)
    updated_weapon_data = weapon_data.copy()
    updated_weapon_data['ammo'] = 10

    manager._update_entity('test-weapon-789', updated_weapon_data)

    # Verify ammo was updated
    updated_weapon = manager.entities['test-weapon-789']
    assert updated_weapon.ammo == 10
