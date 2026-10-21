from fastapi.testclient import TestClient

from rendercart.core.access import Level
from rendercart.registry.loader import load_builtin_registry, visible_tools


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_public_tool_directory_exposes_public_registry_tools_only(client: TestClient) -> None:
    response = client.get("/api/tools")

    assert response.status_code == 200
    public_slugs = {tool["slug"] for tool in response.json()}
    expected_public_slugs = {
        tool.slug for tool in visible_tools(load_builtin_registry(), Level.GUEST)
    }
    assert public_slugs == expected_public_slugs
    assert not {"url-shortener", "pastebin", "temp-file-share"} & public_slugs
    assert all(tool["category"] != "vault" for tool in response.json())


def test_missing_tool_returns_404(client: TestClient) -> None:
    response = client.get("/api/tools/not-a-tool")

    assert response.status_code == 404


def test_tool_detail_includes_limits_and_options_schema(client: TestClient) -> None:
    response = client.get("/api/tools/merge-pdf")
    payload = response.json()

    assert response.status_code == 200
    assert payload["inputs"]["min_files"] == 2
    assert payload["limits"]["guest"]["count_per_day"] == 2
    assert payload["options_schema"]["title"] == "MergeOptions"
