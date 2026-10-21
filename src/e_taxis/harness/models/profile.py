"""models.profile: a standalone source — the parts a profile wants, each with how it rolls out."""

from msgspec import Struct

from e_taxis.harness.models.catalog import Rollout


##### TYPES #####
class Profile(Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """`house`, `company`, `minimal`: shipped beside the catalog, one YAML file each."""

    id: str
    description: str
    parts: dict[str, Rollout]
