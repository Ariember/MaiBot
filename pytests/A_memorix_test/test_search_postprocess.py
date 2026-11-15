from types import SimpleNamespace

import pytest

from src.A_memorix.core.utils.search_postprocess import apply_safe_content_dedup


@pytest.mark.parametrize("reverse", [False, True])
def test_content_dedup_preserves_additional_facts(reverse):
    results = [
        SimpleNamespace(hash_value="short", content="小明喜欢绿茶。"),
        SimpleNamespace(hash_value="long", content="小明喜欢绿茶。小红喜欢咖啡。"),
    ]
    if reverse:
        results.reverse()

    unique, removed = apply_safe_content_dedup(results)

    assert unique == results
    assert removed == 0


def test_content_dedup_removes_same_hash_and_equal_text():
    first = SimpleNamespace(hash_value="one", content="小明喜欢绿茶。")
    results = [
        first,
        SimpleNamespace(hash_value="one", content="小明喜欢绿茶。小红喜欢咖啡。"),
        SimpleNamespace(hash_value="two", content=" 小明喜欢绿茶。 "),
    ]

    unique, removed = apply_safe_content_dedup(results)

    assert unique == [first]
    assert removed == 2


def test_content_dedup_preserves_one_result_when_all_contents_are_empty():
    results = [SimpleNamespace(hash_value="one", content=""), SimpleNamespace(hash_value="two", content=" ")]

    assert apply_safe_content_dedup([]) == ([], 0)
    assert apply_safe_content_dedup(results) == ([results[0]], 1)
