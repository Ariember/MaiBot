"""离线验证工作时段、固定概率与旧配置迁移。"""

from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncio
import importlib
import pytest


@pytest.fixture
def modules(plugin_module):

    names = ("config", "life.rest_gate", "social.group_observer", "core.llm_service")

    return SimpleNamespace(
        **{name.rsplit(".", 1)[-1]: importlib.import_module(f"src.plugins.built_in.mylife.{name}") for name in names}
    )


@pytest.fixture
def setup_gate(modules):

    config = modules.config.MaiLifeSettings()

    store = SimpleNamespace()

    gate = modules.rest_gate.RestGate(config)

    now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone(timedelta(hours=8)))

    return gate, config, store, now


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
    "probability,sample,expected", [(0, 0, False), (1, 0.999999, True), (0.18, 0.18, False), (0.18, 0.179, True)]
)
@pytest.mark.parametrize("text", ["普通消息", "救命，醒醒", "别回，继续睡", ""])
def test_content_does_not_override_probability(setup_gate, monkeypatch, modules, probability, sample, expected, text):

    gate, config, store, now = setup_gate

    config.group.reply_probability = probability

    monkeypatch.setattr(modules.rest_gate.random, "random", lambda: sample)

    assert gate.decide_group(text, now)[0] is expected


def test_work_hours_override_probability_but_commands_pass(setup_gate, monkeypatch, modules):

    gate, config, store, now = setup_gate

    config.group.work_start = "13:00"

    config.group.work_end = "18:00"

    config.group.reply_probability = 1

    random = Mock(side_effect=AssertionError("outside hours must not sample"))

    monkeypatch.setattr(modules.rest_gate.random, "random", random)

    assert gate.decide_group("醒醒", now)[0] is False

    assert gate.decide_group("/麦麦帮助", now)[0] is True


def test_disabled_policy_and_hot_update(setup_gate, modules):

    gate, config, store, now = setup_gate

    replacement = modules.config.MaiLifeSettings(group={"gate_enabled": False, "reply_probability": 0})

    gate.update_config(replacement)

    assert gate.decide_group("消息", now)[0] is True

    replacement.group.gate_enabled = True

    assert gate.decide_group("消息", now)[0] is False


@pytest.mark.parametrize("section", ["proactive", "group"])
@pytest.mark.parametrize(
    "field,value", [("work_start", "9:00"), ("work_end", "24:00"), ("work_start", "12:60"), ("work_end", None)]
)
def test_invalid_config_rejected(modules, section, field, value):

    with pytest.raises(ValidationError):
        modules.config.MaiLifeSettings(**{section: {field: value}})


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_invalid_group_probability_rejected(modules, value):

    with pytest.raises(ValidationError):
        modules.config.GroupChatSettings(reply_probability=value)


def test_legacy_enabled_config_migrates_hours_and_probability(modules):

    config = modules.config.MaiLifeSettings(
        rest_gate={
            "enabled": True,
            "mode": "llm",
            "wake_probability": 0.4,
            "night_start": "23:00",
            "night_end": "07:00",
            "awake_grace_minutes": 45,
        },
        group={"gate_enabled": True, "gate_mode": "time_window", "night_start": "00:30", "night_end": "08:00"},
    )

    assert (config.proactive.work_start, config.proactive.work_end) == ("07:00", "23:00")

    assert (config.group.work_start, config.group.work_end, config.group.reply_probability) == ("08:00", "00:30", 0.18)

    assert "state" not in config.model_dump()

    assert "rest_gate" not in config.model_dump()

    assert "force_wake_terms" not in config.group.model_dump()

    assert "rest_wakeup_task" not in config.models.model_dump()


def test_legacy_disabled_and_schedule_modes(modules):

    config = modules.config.MaiLifeSettings(
        rest_gate={"enabled": False, "wake_probability": 0.18, "gate_mode": "time_window"},
        group={"gate_enabled": False, "gate_mode": "schedule"},
    )

    assert config.group.gate_enabled and config.group.reply_probability == 0.18

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


def test_group_observation_uses_window_without_random(setup_gate, modules, monkeypatch):

    gate, config, store, now = setup_gate

    config.group.work_start = "13:00"

    config.group.work_end = "18:00"

    observer = modules.group_observer.GroupObserver(store, config, Mock(), Mock())

    monkeypatch.setattr(modules.rest_gate.random, "random", Mock(side_effect=AssertionError("second sample")))

    assert asyncio.run(observer._group_quiet_now(now))

    config.group.work_start = "12:00"

    assert not asyncio.run(observer._group_quiet_now(now))


def test_llm_usage_and_daily_counts_use_injected_time(setup_gate, modules):

    gate, config, store, now = setup_gate

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
