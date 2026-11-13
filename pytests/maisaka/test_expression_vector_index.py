from copy import deepcopy

import pytest


@pytest.fixture(scope="module")
def expression_index_class(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MAIBOT_INSTANCE_DIR", str(tmp_path_factory.mktemp("expression-index-instance")))
        from src.chat.replyer.expression_vector_index import ExpressionVectorIndex

        yield ExpressionVectorIndex


def test_cluster_summaries_empty(expression_index_class):
    assert expression_index_class._build_cluster_summaries([]) == []


def test_cluster_summaries_normalize_keys_and_members(expression_index_class):
    expressions = [
        {},
        {"embedding_profile_marker": None, "cluster_id": None, "id": None, "count": None},
        {"embedding_profile_marker": " \t", "cluster_id": "0", "situation": None, "style": None},
        {
            "embedding_profile_marker": " profile\n a ", "cluster_id": "2", "id": "7",
            "situation": " 开心\n 时 ", "style": " 好\t 耶 ", "count": "3",
        },
        {"embedding_profile_marker": "profile a", "cluster_id": 2, "id": 8, "count": 0},
    ]
    original = deepcopy(expressions)

    summaries = expression_index_class._build_cluster_summaries(expressions)

    assert summaries == [
        {
            "embedding_profile_marker": "", "cluster_id": 0, "size": 3,
            "members": [{"id": 0, "situation": "", "style": "", "count": 0}] * 3,
        },
        {
            "embedding_profile_marker": "profile a", "cluster_id": 2, "size": 2,
            "members": [
                {"id": 7, "situation": "开心 时", "style": "好 耶", "count": 3},
                {"id": 8, "situation": "", "style": "", "count": 0},
            ],
        },
    ]
    assert expressions == original


def test_cluster_summaries_preserve_first_eight_and_tie_order(expression_index_class):
    groups = [("b", 2), ("a", 10), ("a", 2), ("z", 0)]
    expressions = [
        {
            "embedding_profile_marker": marker, "cluster_id": cluster_id,
            "id": 100 - index, "situation": f"{marker}/{cluster_id} 情景 {index}",
            "style": f"表达 {index}", "count": index,
        }
        for index in range(10)
        for marker, cluster_id in groups
    ]
    expressions.extend([
        {"embedding_profile_marker": "z", "cluster_id": 0, "id": 200 + index}
        for index in range(2)
    ])
    original = deepcopy(expressions)

    summaries = expression_index_class._build_cluster_summaries(expressions)

    assert summaries == [
        {
            "embedding_profile_marker": marker, "cluster_id": cluster_id, "size": size,
            "members": [
                {
                    "id": 100 - index, "situation": f"{marker}/{cluster_id} 情景 {index}",
                    "style": f"表达 {index}", "count": index,
                }
                for index in range(8)
            ],
        }
        for marker, cluster_id, size in [("z", 0, 12), ("a", 2, 10), ("a", 10, 10), ("b", 2, 10)]
    ]
    assert expressions == original
