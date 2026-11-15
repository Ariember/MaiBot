from pathlib import Path

import pytest
import tomlkit

from src.webui.routers import config as config_routes
from src.webui.utils import toml_utils


@pytest.mark.parametrize("raw", [False, True])
def test_config_save_preserves_comments_and_format(tmp_path: Path, monkeypatch, raw: bool) -> None:
    path = tmp_path / "bot_config.toml"
    original = '# bot settings\n[bot]\nnickname = "before" # display name\n'
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(config_routes, "CONFIG_DIR", tmp_path)
    expected = original.replace('"before"', '"after"')

    if raw:
        assert config_routes.update_bot_config_raw(expected)["success"] is True
    else:
        toml_utils.save_toml_with_format({"bot": {"nickname": "after"}}, str(path))

    assert path.read_text(encoding="utf-8") == expected
    assert tomlkit.loads(path.read_text(encoding="utf-8"))["bot"]["nickname"] == "after"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("failure", ["write", "replace"])
def test_failed_config_save_preserves_original(tmp_path: Path, monkeypatch, raw: bool, failure: str) -> None:
    path = tmp_path / "bot_config.toml"
    path.write_text('[bot]\nnickname = "before"\n', encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(config_routes, "CONFIG_DIR", tmp_path)

    if failure == "write":
        create_temporary = toml_utils.NamedTemporaryFile

        def failing_temporary(**kwargs):
            temporary = create_temporary(**kwargs)
            write = temporary.write

            def partial_write(content):
                write(content[:10])
                raise OSError("disk write failed")

            temporary.write = partial_write
            return temporary

        monkeypatch.setattr(toml_utils, "NamedTemporaryFile", failing_temporary)
    else:

        def fail_replace(self, target):
            raise OSError("disk replace failed")

        monkeypatch.setattr(Path, "replace", fail_replace)

    if raw:
        with pytest.raises(config_routes.HTTPException) as error:
            config_routes.update_bot_config_raw('[bot]\nnickname = "after"\n')
        assert error.value.status_code == 500
        assert f"disk {failure} failed" in error.value.detail
    else:
        with pytest.raises(OSError, match=f"disk {failure} failed"):
            toml_utils.save_toml_with_format({"bot": {"nickname": "after"}}, str(path))

    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
