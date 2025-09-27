from __future__ import annotations

from typing import Any, Dict

from src.utils import paper_workflows as workflows


class _StubResponse:
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.status_code = 200
        self.content = b"<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'></feed>"

    def raise_for_status(self) -> None:
        return


class _StubSession:
    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    def get(self, url: str, *, params: Dict[str, Any], timeout: int) -> _StubResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return _StubResponse(params)


def test_quote_term_escapes_double_quotes() -> None:
    quoted = workflows._quote_term('multi "quote" value')
    assert quoted == "\"multi \\\"quote\\\" value\""


def test_build_semantic_scholar_query_quotes_all_terms() -> None:
    query = workflows.build_semantic_scholar_query(
        ["large language models", "LLM"],
        ["systematic review"],
    )
    assert query == '("large language models" OR "LLM") AND ("systematic review")'


def test_search_arxiv_for_topic_quotes_search_terms() -> None:
    session = _StubSession()
    workflows.search_arxiv_for_topic(
        session,
        anchor_terms=["graph neural networks"],
        search_terms=["contrastive learning"],
    )
    assert len(session.calls) == 1
    params = session.calls[0]["params"]
    assert params["search_query"] == '(ti:"graph neural networks") AND (ti:"contrastive learning")'
