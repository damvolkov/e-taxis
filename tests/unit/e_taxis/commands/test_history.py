"""tests/unit/e_taxis/commands/history: the journal as a user sees it — list, undo in order, failed runs never filed."""

TOKEN = ("--token", "tk-test-0001")


def test_history_list_empty_says_so(taxis) -> None:
    _, out, _ = taxis("history", "list")
    assert "nothing recorded" in out


def test_history_list_shows_runs_newest_first(taxis) -> None:
    taxis(*TOKEN, "project", "create", "demo")
    taxis(*TOKEN, "project", "env", "set", "demo", "KEY", "v")
    _, out, _ = taxis("history", "list")
    assert out.index("project env set") < out.index("project create")


def test_history_undo_walks_back_one_run_at_a_time(taxis) -> None:
    taxis(*TOKEN, "project", "create", "demo")
    taxis(*TOKEN, "project", "env", "set", "demo", "KEY", "v")
    assert "undid `project env set`" in taxis("history", "undo")[1]
    assert "no variables" in taxis("project", "env", "list", "demo")[1]
    assert "undid `project create`" in taxis("history", "undo")[1]
    code, _, err = taxis("history", "undo")
    assert code == 4
    assert "nothing to undo" in err


def test_history_failed_run_is_never_filed(taxis) -> None:
    taxis(*TOKEN, "project", "create", "demo")
    taxis(*TOKEN, "project", "create", "demo")
    _, out, _ = taxis("history", "list")
    assert out.count("project create") == 1
