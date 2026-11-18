from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import json
import pytest

from src.learners import reply_experience_learner as learner_module
from src.learners.reply_experience_learner import ReplyExperienceLearner, ReplyExperienceProbe
from src.learners.reply_experience_store import ReplyExperience, ReplyExperienceStore


@pytest.mark.asyncio
async def test_reflection_updates_a_lesson_and_reuses_it_after_restart(monkeypatch, tmp_path):
    monkeypatch.setattr(
        learner_module.config_module.global_config.chat.reply_style, "enable_reply_experience_learning", True
    )
    scope = ("session", "user", "persona")
    store = ReplyExperienceStore(tmp_path / "experiences.json")
    original = ReplyExperience("询问进度", "先说明状态", "修订先交代了状态")
    store.remember(*scope, original)
    revised = ReplyExperience("询问进度", "先给状态，再说下一步", "修订补充了下一步")
    result = {"cue": revised.cue, "lesson": revised.lesson, "evidence": revised.evidence}
    generate = AsyncMock(return_value=SimpleNamespace(response=f"```json\n{json.dumps(result)}\n```"))
    model = Mock(return_value=SimpleNamespace(generate_response=generate))
    monkeypatch.setattr(learner_module, "LLMServiceClient", model)
    learner = ReplyExperienceLearner(store)
    probe = ReplyExperienceProbe("现在怎样？", "等一下吧", "还在处理，完成后我告诉你", "没有交代状态")

    learner.schedule(scope, probe)
    pending = learner._tasks[scope]
    learner.schedule(scope, probe)
    await pending

    generate.assert_awaited_once()
    request_data = json.loads(generate.call_args.args[0].split("\n\n", 1)[1])
    assert request_data["rejected"] == probe.rejected
    assert request_data["revised"] == probe.revised
    assert request_data["previous_experiences"][0]["lesson"] == original.lesson
    assert store.list_for(*scope) == [revised]
    restarted = ReplyExperienceLearner(ReplyExperienceStore(store.path))
    guidance = await restarted.build_guidance(scope)
    assert revised.cue in guidance and revised.lesson in guidance
    assert revised.evidence not in guidance
    assert await restarted.build_guidance(("session", "other", "persona")) == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["null", '{"cue":"证据不足","lesson":"换个说法"}'])
async def test_reflection_without_complete_evidence_keeps_store_unchanged(monkeypatch, tmp_path, response):
    monkeypatch.setattr(
        learner_module.config_module.global_config.chat.reply_style, "enable_reply_experience_learning", True
    )
    generate = AsyncMock(return_value=SimpleNamespace(response=response))
    monkeypatch.setattr(learner_module, "LLMServiceClient", lambda **_: SimpleNamespace(generate_response=generate))
    store = ReplyExperienceStore(tmp_path / "experiences.json")
    learner = ReplyExperienceLearner(store)
    scope = ("session", "user", "persona")

    learner.schedule(scope, ReplyExperienceProbe("问候", "你好", "早上好", "换个说法"))
    await learner._tasks[scope]

    assert not store.path.exists()
    assert await learner.build_guidance(scope) == ""
