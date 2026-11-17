"""回复断句保留中英混排词组，并在引号外识别消息边界。"""

from types import SimpleNamespace

import pytest

from src.chat.utils import utils
from src.config.official_configs import ResponsePostProcessConfig


@pytest.mark.parametrize(
    "text",
    [
        "SpaceX 的星舰这次试飞",
        "刚看了 SpaceX 的 Starship 试飞",
        "升级到 Python 3.12 后再试",
        "今天跑了 5 km 感觉不错",
        "中文 排版 空格",
        "hello  world 和 AI   助手",
    ],
)
def test_spaces_do_not_split_phrases(monkeypatch, text: str) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)

    assert utils._split_into_sentence_segments(text) == [(text, "")]


@pytest.mark.parametrize("text", ["AI", "OK", "好的"])
def test_short_replies_are_not_split_into_characters(monkeypatch, text: str) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.0)

    assert utils._split_into_sentence_segments(text) == [(text, "")]


def test_punctuation_and_newlines_remain_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)

    assert utils._split_into_sentence_segments("第一段，第二段,第三段。第四段;第五段\n第六段") == [
        ("第一段", "，"),
        ("第二段", ","),
        ("第三段", "。"),
        ("第四段", ";"),
        ("第五段", "\n"),
        ("第六段", ""),
    ]


@pytest.mark.parametrize(
    "opening,closing", [("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"), ('"', '"'), ("'", "'")]
)
def test_quotes_protect_content_and_end_at_matching_quote(monkeypatch, opening: str, closing: str) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)
    quoted = f"他说{opening}SpaceX, 试飞。完成{closing}以后再聊"

    assert utils._split_into_sentence_segments(f"{quoted}，下一句。结束") == [
        (quoted, "，"),
        ("下一句", "。"),
        ("结束", ""),
    ]


@pytest.mark.parametrize("word", ["don't", "I'm", "it's", "don’t", "SpaceX’s", "1990's"])
def test_apostrophes_do_not_open_quotes(monkeypatch, word: str) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)
    sentence = f"他说 {word} 很常见"

    assert utils._split_into_sentence_segments(f"{sentence}，下一句。结束") == [
        (sentence, "，"),
        ("下一句", "。"),
        ("结束", ""),
    ]


def test_apostrophe_does_not_close_double_quote(monkeypatch) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)
    quoted = '他说"don\'t stop, keep going"'

    assert utils._split_into_sentence_segments(f"{quoted}，继续。") == [(quoted, "，"), ("继续", "。")]


@pytest.mark.asyncio
async def test_mixed_reply_keeps_phrases_and_punctuation_when_compressed(monkeypatch) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)
    monkeypatch.setattr(
        utils,
        "global_config",
        SimpleNamespace(
            response_post_process=SimpleNamespace(enable_response_post_process=True, remove_bracket_content=True),
            response_splitter=SimpleNamespace(
                mode="rule",
                enable=True,
                enable_kaomoji_protection=True,
                enable_overflow_return_all=False,
                max_length=512,
                max_sentence_num=8,
                max_split_num=3,
            ),
            chinese_typo=SimpleNamespace(enable=False),
        ),
    )
    text = "刚看到个挺酷的事，SpaceX 的星舰这次试飞，居然用发射塔的“筷子”机械臂把飞船半空夹住了，跟夹娃娃一样。你下午在忙什么呢？"

    segments = await utils.process_llm_response_segments_async(text)

    assert [segment.text for segment in segments] == [
        "刚看到个挺酷的事，SpaceX 的星舰这次试飞",
        "居然用发射塔的“筷子”机械臂把飞船半空夹住了，跟夹娃娃一样",
        "你下午在忙什么呢？",
    ]
    assert "".join(segment.text + segment.separator for segment in segments) == text


@pytest.mark.parametrize("remove_bracket_content", [True, False])
@pytest.mark.parametrize("opening,closing", [("(", ")"), ("[", "]"), ("（", "）")])
def test_bracket_cleanup_keeps_sentence_splitting_and_kaomoji(
    monkeypatch, remove_bracket_content: bool, opening: str, closing: str,
) -> None:
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)
    monkeypatch.setattr(
        utils,
        "global_config",
        SimpleNamespace(
            response_post_process=ResponsePostProcessConfig(remove_bracket_content=remove_bracket_content),
            response_splitter=SimpleNamespace(
                enable=True,
                enable_kaomoji_protection=True,
                enable_overflow_return_all=False,
                max_length=512,
                max_sentence_num=8,
                max_split_num=8,
            ),
            chinese_typo=SimpleNamespace(enable=False),
        ),
    )
    action = f"{opening}挥手{closing}"
    text = f"你好{action}，下次见(^_^)"

    segments = utils.process_llm_response_segments(text)

    assert [segment.text for segment in segments] == [
        "你好" if remove_bracket_content else f"你好{action}",
        "下次见(^_^)",
    ]


@pytest.mark.parametrize("opening,closing", [("(", ")"), ("[", "]"), ("（", "）")])
def test_default_cleanup_preserves_english_brackets_before_chinese(monkeypatch, opening: str, closing: str) -> None:
    monkeypatch.setattr(
        utils,
        "global_config",
        SimpleNamespace(
            response_post_process=ResponsePostProcessConfig(),
            response_splitter=utils.global_config.response_splitter,
            chinese_typo=SimpleNamespace(enable=False),
        ),
    )
    text = f"使用 {opening}API{closing} 请求中文模型{opening}点头{closing}"

    segments = utils.process_llm_response_segments(text, enable_splitter=False, enable_chinese_typo=False)

    assert [segment.text for segment in segments] == [f"使用 {opening}API{closing} 请求中文模型"]
