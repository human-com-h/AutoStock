from __future__ import annotations

import run_web


def test_open_browser_when_ready_waits_for_health(monkeypatch):
    states = iter([False, False, True])
    opened: list[bool] = []
    sleeps: list[float] = []
    monkeypatch.setattr(run_web, "_health_ready", lambda: next(states))
    monkeypatch.setattr(run_web, "_open_browser", lambda: opened.append(True))
    monkeypatch.setattr(run_web.time, "sleep", sleeps.append)

    run_web._open_browser_when_ready(attempts=3, interval_seconds=0.1)

    assert opened == [True]
    assert sleeps == [0.1, 0.1]


def test_existing_server_only_opens_browser(monkeypatch):
    opened: list[bool] = []
    monkeypatch.setattr(run_web, "_health_ready", lambda: True)
    monkeypatch.setattr(run_web, "_open_browser", lambda: opened.append(True))
    monkeypatch.setattr(
        run_web,
        "_run_migrations",
        lambda: (_ for _ in ()).throw(AssertionError("不应重复执行迁移")),
    )

    run_web.main()

    assert opened == [True]
