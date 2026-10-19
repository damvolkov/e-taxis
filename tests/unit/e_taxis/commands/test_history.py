"""tests/unit/e_taxis/commands/history: the journal as a user sees it — list newest first, undo one run at a time."""


def test_history_list_empty_says_so(taxis) -> None:
    _, out, _ = taxis("history", "list")
    assert "nothing recorded" in out


def test_history_list_shows_runs_newest_first(taxis, filed) -> None:
    filed("first run", {"k": b"1"})
    filed("second run", {"k": b"2"})
    _, out, _ = taxis("history", "list")
    assert out.index("second run") < out.index("first run")


def test_history_undo_walks_back_one_run_at_a_time(taxis, filed) -> None:
    filed("first run", {"k": b"1"})
    filed("second run", {"k": b"2"})
    assert "undid `second run`" in taxis("history", "undo")[1]
    assert "undid `first run`" in taxis("history", "undo")[1]
    code, _, err = taxis("history", "undo")
    assert code == 4
    assert "nothing to undo" in err
