"""Regression: FTS5 search must rank by relevance, not by insertion order.

`db.search` ran ``WHERE files_fts MATCH ? LIMIT ?`` with no ``ORDER BY``. FTS5 does
not rank matches unless asked, and it truncates in **rowid order**, so a ``LIMIT``
returned the first-*inserted* match and could drop the better one - the endpoint
behaved like a prefix scan, not a relevance search.

Reproduction of the audit's finding: two rows both matching ``alpha``, the worse
one inserted first, ``LIMIT 1`` -> the worse row came back. With
``ORDER BY rank`` the better row wins. ``rank`` is the FTS5 alias for ``bm25()``
and ascending is better (bm25 is more-negative-is-better).
"""

from dossier.db import FileRecord, open_db, search

# One "alpha" buried in 200 noise tokens: a real match, but a poor one.
_WORSE_BODY = "alpha " + " ".join(f"w{i}" for i in range(200))


def _index(tmp_path, rows):
    """Index rows in the given order, so rowid order == insertion order."""
    connection = open_db(tmp_path / "search-ranking.sqlite")
    for position, (rel, body) in enumerate(rows):
        connection.execute("INSERT INTO files_fts(rel,body) VALUES(?,?)", (rel, body))
        connection.execute(
            "INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (rel, ".txt", 1, position, rel, "file", "", "other", "{}", 0, None),
        )
    connection.commit()
    return connection


def test_limit_returns_the_best_match_not_the_first_inserted(tmp_path):
    """The worse match is rowid 1; a LIMIT of 1 must still return the better one."""
    connection = _index(tmp_path, [("worse.txt", _WORSE_BODY), ("best.txt", "alpha")])
    assert [row["rowid"] for row in connection.execute("SELECT rowid FROM files_fts")] == [1, 2]

    assert [hit["rel"] for hit in search(connection, "alpha", 1)] == ["best.txt"]


def test_every_match_comes_back_best_first(tmp_path):
    """Without `ORDER BY`, the full list comes back in rowid (insertion) order."""
    connection = _index(tmp_path, [("worse.txt", _WORSE_BODY), ("best.txt", "alpha")])

    assert [hit["rel"] for hit in search(connection, "alpha")] == ["best.txt", "worse.txt"]


def test_a_plain_match_still_returns_with_its_snippet(tmp_path):
    """`ORDER BY rank` must not turn a valid match into no result."""
    connection = _index(tmp_path, [("notes.txt", "alpha beta gamma")])

    hits = search(connection, "beta", 10)
    assert [hit["rel"] for hit in hits] == ["notes.txt"]
    assert hits[0]["ext"] == ".txt"
    assert "beta" in hits[0]["snippet"]


def test_the_upsert_path_ranks_too(tmp_path):
    """The same guarantee holds for rows written by `upsert_file`."""
    from dossier.db import upsert_file

    connection = open_db(tmp_path / "search-ranking-upsert.sqlite")
    upsert_file(connection, FileRecord("worse.txt", ".txt", 1, 1, "a"), _WORSE_BODY)
    upsert_file(connection, FileRecord("best.txt", ".txt", 1, 2, "b"), "alpha")
    connection.commit()

    assert [hit["rel"] for hit in search(connection, "alpha", 1)] == ["best.txt"]


# -- a search box is not an FTS5 query -------------------------------------

def test_fragments_a_person_types_never_raise(tmp_path):
    """Every one of these was an unhandled `OperationalError` before the query was
    built from quoted terms: an unmatched quote, a bare operator, a prefix marker,
    a column reference, a lone wildcard and an empty-ish string."""
    connection = _index(tmp_path, [("a.txt", "alpha beta"), ("b.txt", "a:b gamma")])
    for fragment in ['"hello', "hello OR", "*", "a:b", "alpha AND", "  ", "(", "NEAR(",
                     "alpha*", "alpha -beta", '"', "alpha)", "\\"]:
        assert search(connection, fragment) == [] or isinstance(search(connection, fragment), list), fragment


def test_the_words_are_what_is_matched_not_the_operator(tmp_path):
    connection = _index(tmp_path, [("a.txt", "alpha beta"), ("b.txt", "alpha gamma")])
    assert [row["rel"] for row in search(connection, "alpha beta")] == ["a.txt"]
    assert {row["rel"] for row in search(connection, "alpha")} == {"a.txt", "b.txt"}


def test_a_pasted_document_does_not_become_thousands_of_terms(tmp_path):
    from dossier.db import FTS_MAX_TERMS, _fts_tokens

    assert len(_fts_tokens(" ".join(f"word{i}" for i in range(5000)))) == FTS_MAX_TERMS


def test_the_search_route_answers_instead_of_failing(tmp_path):
    from fastapi.testclient import TestClient
    from dossier.api.app import create_app
    from dossier.config import AppConfig

    app = create_app(AppConfig.create(tmp_path, token="search-token"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer search-token"}
    for fragment in ['"hello', "a:b", "*", "alpha OR"]:
        response = client.get("/api/search", params={"q": fragment}, headers=headers)
        assert response.status_code == 200, (fragment, response.status_code, response.text[:200])
        assert isinstance(response.json(), list)
