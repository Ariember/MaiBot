"""离线验证主动私聊工作时段与旧配置迁移。"""

from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncio
import importlib
import pytest


@pytest.fixture
def modules(plugin_module):

    names = ("config", "life.rest_gate", "core.llm_service")

    return SimpleNamespace(
        **{name.rsplit(".", 1)[-1]: importlib.import_module(f"src.plugins.built_in.mylife.{name}") for name in names}
    )


@pytest.fixture
def setup_runtime(modules):

    config = modules.config.MaiLifeSettings()

    store = SimpleNamespace()

    now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone(timedelta(hours=8)))

    return config, store, now


@pytest.mark.parametrize(
    "start,end,current,expected",
    [
        ("09:00", "18:00", "08:59", False),
        ("09:00", "18:00", "09:00", True),
        ("09:00", "18:00", "17:59", True),
        ("09:00", "18:00", "18:00", False),
        ("22:00", "06:00", "22:00", True),
        ("22:00", "06:00", "05:59", True),
        ("22:00", "06:00", "06:00", False),
        ("22:00", "06:00", "12:00", False),
        ("00:00", "00:00", "23:59", True),
        ("09:00", "09:00", "00:00", True),
    ],
)
def test_work_window(modules, start, end, current, expected):

    assert modules.rest_gate.RestGate.in_work_window(start, end, current) is expected


@pytest.mark.parametrize(
    "field,value", [("work_start", "9:00"), ("work_end", "24:00"), ("work_start", "12:60"), ("work_end", None)]
)
def test_invalid_config_rejected(modules, field, value):

    with pytest.raises(ValidationError):
        modules.config.MaiLifeSettings(proactive={field: value})


def test_legacy_enabled_config_migrates_hours(modules):

    config = modules.config.MaiLifeSettings(
        rest_gate={
            "enabled": True,
            "mode": "llm",
            "wake_probability": 0.4,
            "night_start": "23:00",
            "night_end": "07:00",
            "awake_grace_minutes": 45,
        },
    )

    assert (config.proactive.work_start, config.proactive.work_end) == ("07:00", "23:00")

    assert "state" not in config.model_dump()

    assert "rest_gate" not in config.model_dump()

    assert "rest_wakeup_task" not in config.models.model_dump()


def test_legacy_disabled_and_schedule_modes(modules):

    config = modules.config.MaiLifeSettings(
        rest_gate={"enabled": False, "wake_probability": 0.18, "gate_mode": "time_window"},
    )

    assert config.proactive.work_start == config.proactive.work_end == "00:00"

    schedule = modules.config.MaiLifeSettings(
        rest_gate={"enabled": True, "gate_mode": "schedule", "wake_probability": 0.3}
    ).proactive

    assert schedule.work_start == schedule.work_end == "00:00"

    assert "reply_probability" not in schedule.model_dump()


def test_explicit_new_settings_win_over_old_fields(modules):

    config = modules.config.MaiLifeSettings(
        rest_gate={
            "enabled": True,
            "work_start": "09:00",
            "wake_probability": 0.2,
            "night_start": "21:00",
            "awake_grace_minutes": 50,
        },
        proactive={"work_start": "10:00", "work_end": "20:00"},
        state={"awake_grace_minutes": 10},
    )

    assert (config.proactive.work_start, config.proactive.work_end) == ("10:00", "20:00")

    assert "state" not in config.model_dump()


@pytest.mark.parametrize("enabled,expected", [(True, ("22:00", "07:00")), (False, ("00:00", "00:00"))])
def test_private_hours_move_to_proactive_without_changing_input(modules, enabled, expected):

    legacy = {"enabled": enabled, "work_start": "22:00", "work_end": "07:00"}

    data = {"rest_gate": dict(legacy), "proactive": {"enabled": False}}

    config = modules.config.MaiLifeSettings.model_validate(data)

    assert (config.proactive.work_start, config.proactive.work_end) == expected

    assert not config.proactive.enabled

    assert "rest_gate" not in config.model_dump()

    assert data == {"rest_gate": legacy, "proactive": {"enabled": False}}

    reloaded = modules.config.MaiLifeSettings.model_validate(config.model_dump())

    assert reloaded.proactive == config.proactive


def test_llm_usage_and_daily_counts_use_injected_time(setup_runtime, modules):

    config, store, now = setup_runtime

    store.record_llm_usage = AsyncMock()

    service = modules.llm_service.LLMService(SimpleNamespace(logger=Mock()), config, store, now=lambda: now)

    service._count_json_failure("schedule")

    assert service.json_failure_snapshot()["day"] == "2026-11-05"

    assert "rest_wakeup" not in service._active_task_kinds()

    assert "dream" not in service._active_task_kinds()

    asyncio.run(
        service.record_observed(
            source="host",
            task_name="replyer",
            request_type="replyer",
            model_name="",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        )
    )

    assert store.record_llm_usage.await_args.kwargs["created_at"] == now.timestamp()
