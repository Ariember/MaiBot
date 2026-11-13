"""插件市场隔离无效发布条目，保留可用插件与索引校验。"""

from types import SimpleNamespace
from typing import Any, Dict
import json

import pytest

from src.plugin_market import service
from src.plugin_market.releases import parse_release_index

REPOSITORY_URL = "https://github.com/example/plugin"


def _manifest(plugin_id: str, repository_url: str = REPOSITORY_URL) -> Dict[str, Any]:
    return {
        "manifest_version": 2,
        "id": plugin_id,
        "name": "Test",
        "version": "1.0.0",
        "repository_url": repository_url,
    }


def _release(plugin_id: str) -> Dict[str, Any]:
    return {
        "version": "1.0.0",
        "tag": "v1.0.0",
        "commit": "a" * 40,
        "prerelease": False,
        "manifest": _manifest(plugin_id),
    }


def _index_entry(plugin_id: str) -> Dict[str, Any]:
    return {
        "id": plugin_id,
        "manifest_id": plugin_id,
        "repositoryUrl": REPOSITORY_URL,
        "mode": "releases",
        "versions": [_release(plugin_id)],
    }


def _official_item(plugin_id: str) -> Dict[str, Any]:
    return {
        "id": plugin_id,
        "marketplace_id": plugin_id,
        "repository_url": REPOSITORY_URL,
        "install_mode": "releases",
        "manifest": _manifest(plugin_id),
        "release": _release(plugin_id),
    }


@pytest.mark.parametrize("field,value", [("manifest", _manifest("github.example.old")), ("commit", "deadbeef")])
def test_release_index_skips_invalid_entry(field, value):
    broken = _index_entry("github.example.broken")
    broken["versions"][0][field] = value
    content = json.dumps({"schema_version": 1, "plugins": [_index_entry("github.example.valid"), broken]})

    parsed = parse_release_index(content)

    assert [entry.id for entry in parsed.plugins] == ["github.example.valid"]


def test_release_index_still_rejects_conflicting_ids():
    first = _index_entry("github.example.first")
    second = {**_index_entry("github.example.second"), "manifest_id": first["id"], "versions": []}

    with pytest.raises(ValueError, match="插件 ID 冲突"):
        parse_release_index(json.dumps({"schema_version": 1, "plugins": [first, second]}))


@pytest.mark.parametrize("content", [{"schema_version": 2, "plugins": []}, {"schema_version": 1, "plugins": {}}])
def test_release_index_still_rejects_invalid_envelope(content):
    with pytest.raises(ValueError):
        parse_release_index(json.dumps(content))


@pytest.mark.parametrize("field,value", [("manifest", _manifest("github.example.old")), ("commit", "deadbeef")])
def test_official_catalog_preserves_plugin_with_invalid_release(monkeypatch, field, value):
    monkeypatch.setattr(service, "download_source", lambda: SimpleNamespace(id="github"))
    broken = _official_item("github.example.broken")
    broken["release"][field] = value

    plugins = service._catalog([_official_item("github.example.valid"), broken], "official")

    assert [plugin["id"] for plugin in plugins] == ["github.example.valid", "github.example.broken"]
    assert len(plugins[0]["releases"]["versions"]) == 1
    assert plugins[1]["releases"]["versions"] == []
    assert plugins[1]["releases"]["recommended_version"] is None
    assert plugins[1]["releases"]["sync_error"]


@pytest.mark.parametrize(
    "official_url,manifest_url,expected_url",
    [
        (REPOSITORY_URL, "", REPOSITORY_URL),
        (REPOSITORY_URL, "https://github.com/example/other", REPOSITORY_URL),
        ("https://gitlab.com/example/plugin", REPOSITORY_URL, REPOSITORY_URL),
        ("", "", None),
    ],
)
def test_official_catalog_uses_valid_repository_url(monkeypatch, official_url, manifest_url, expected_url):
    monkeypatch.setattr(service, "download_source", lambda: SimpleNamespace(id="github"))
    broken = _official_item("github.example.broken")
    broken["release"]["manifest"]["id"] = "github.example.old"
    broken["repository_url"] = official_url
    broken["manifest"]["repository_url"] = manifest_url

    plugins = service._catalog([_official_item("github.example.valid"), broken], "official")

    assert plugins[0]["id"] == "github.example.valid"
    if expected_url is None:
        assert len(plugins) == 1
    else:
        assert len(plugins) == 2
        assert plugins[1]["releases"]["repositoryUrl"] == expected_url
        assert plugins[1]["repository_url"] == expected_url
