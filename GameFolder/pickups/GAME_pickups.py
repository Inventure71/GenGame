from BASE_components.BASE_pickups import BasePickup
from BASE_components.BASE_asset_handler import AssetHandler
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


class AbilityPickup(BasePickup):
    def __init__(self, ability_name: str, ability_type: str, location: [float, float]):
        super().__init__(location, width=36, height=36, pickup_radius=48)
        self.ability_name = ability_name
        self.ability_type = ability_type
        self.description = self._lookup_description()
        self.asset_image_name = AssetHandler.get_random_asset_from_subcategory(
            "pickups",
            "primary" if self.ability_type == "primary" else "passive",
        )

        if self.ability_type == "primary":
            self.color = (255,255,255)
        else:
            self.color = (255,255,255)

        self._set_network_identity("GameFolder.pickups.GAME_pickups", "AbilityPickup")

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

    def set_ability_name(self, ability_name: str):
        """Update the pickup's ability and refresh any derived fields."""
        self.ability_name = ability_name
        self.description = self._lookup_description()

    def get_label(self) -> str:
        return "P" if self.ability_type == "primary" else "S"
