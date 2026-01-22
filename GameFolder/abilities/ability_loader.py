import importlib
import pkgutil
from typing import List


_PRIMARY_PACKAGE = "GameFolder.abilities.primary"
_PASSIVE_PACKAGE = "GameFolder.abilities.passive"

_cached_primary = None
_cached_passive = None


def _load_abilities(package_name: str) -> List[dict]:
    abilities = []
    package = importlib.import_module(package_name)
    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        module = importlib.import_module(module_info.name)
        ability = getattr(module, "ABILITY", None)
        if not ability:
            continue
        if not ability.get("description"):
            raise ValueError(f"Ability '{ability.get('name', module_info.name)}' missing description")
        abilities.append(ability)
    return abilities

def reload_abilities():
    """Clear the ability cache to force reload on next access."""
    global _cached_primary, _cached_passive
    _cached_primary = None
    _cached_passive = None


def get_primary_abilities() -> List[dict]:
    global _cached_primary
    if _cached_primary is None:
        _cached_primary = _load_abilities(_PRIMARY_PACKAGE)
    return list(_cached_primary)


def get_passive_abilities() -> List[dict]:
    global _cached_passive
    if _cached_passive is None:
        _cached_passive = _load_abilities(_PASSIVE_PACKAGE)
    return list(_cached_passive)
