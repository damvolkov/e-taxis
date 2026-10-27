"""tests/unit/e_taxis/workflow/models/endpoint: an endpoint never says its key."""

from e_taxis.workflow.models.endpoint import Endpoint


async def test_endpoint_repr_hides_the_key() -> None:
    endpoint = Endpoint(base_url="https://api/v1", key="sk-secret", model="m")
    assert "sk-secret" not in repr(endpoint)
