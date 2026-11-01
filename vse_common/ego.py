"""Default ego vehicle blueprint (a stock CARLA vehicle; no custom asset needed).

Scenarios saved with the UT Lexus (``vehicle.lexus.utlexus``) still load on a
stock CARLA install: ``resolve_ego_blueprint_id`` falls back to the default when
the requested blueprint does not exist in the server's blueprint library.
"""

from __future__ import annotations

from typing import Optional

# Not offered in the NPC vehicle list (see EGO_BLUEPRINT_IDS) so NPCs can't be mistaken for the ego.
DEFAULT_EGO_BLUEPRINT = "vehicle.lincoln.mkz_2020"
LEGACY_EGO_BLUEPRINT = "vehicle.lexus.utlexus"
EGO_BLUEPRINT_IDS = (DEFAULT_EGO_BLUEPRINT, LEGACY_EGO_BLUEPRINT)


def resolve_ego_blueprint_id(blueprint_library, requested: Optional[str] = None) -> str:
    """Return a blueprint id that exists in ``blueprint_library``.

    Order: the requested id, the default ego, then any four-wheeled vehicle.
    """
    for candidate in (requested, DEFAULT_EGO_BLUEPRINT):
        if not candidate:
            continue
        try:
            blueprint_library.find(candidate)
            return candidate
        except Exception:
            continue
    fallback = None
    for blueprint in blueprint_library.filter("vehicle.*"):
        try:
            if blueprint.get_attribute("number_of_wheels").as_int() == 4:
                return blueprint.id
        except Exception:
            pass
        fallback = fallback or blueprint.id
    if fallback:
        return fallback
    raise RuntimeError("No vehicle blueprints available for the ego")
