"""Challenge policy: what is configured, what is applied, and what is recorded.

The gate changed from "a challenge is a blocker" to "a challenge is answered only by
the policy the workspace declares, and the answer is recorded". These tests hold the
line that made that a *safe* change:

* the default policy is still `auto`, and `auto` still ends in an honest blocker;
* a policy can come from the workspace file, a recipe or an argument, in that order;
* a visible window is never opened unless the caller or the workspace allowed it;
* the solver is never called without a key, and never called by `auto` unless a key
  is present;
* a page that clears itself is captured, with the wait recorded.
"""

from __future__ import annotations

import json

import pytest

from dossier.scrape import challenge


def _config(root, payload):
    (root / ".dossier").mkdir(parents=True, exist_ok=True)
    (root / ".dossier" / "scrape.json").write_text(json.dumps(payload), encoding="utf-8")


# -- policy resolution -----------------------------------------------------

def test_the_default_policy_is_auto(tmp_path):
    assert challenge.effective_policy(tmp_path) == "auto"
    assert challenge.describe(tmp_path)["configured"] == "auto"


def test_a_workspace_can_declare_a_global_and_a_per_board_policy(tmp_path):
    _config(tmp_path, {"challenge": "stealth", "sources": {"linkedin": {"challenge": "solve"}}})
    assert challenge.effective_policy(tmp_path) == "stealth"
    assert challenge.effective_policy(tmp_path, "linkedin") == "solve"
    assert challenge.effective_policy(tmp_path, "seek") == "stealth"


def test_an_argument_beats_a_recipe_which_beats_the_workspace(tmp_path):
    _config(tmp_path, {"challenge": "block"})
    assert challenge.effective_policy(tmp_path, "", override="await") == "await"
    assert challenge.effective_policy(tmp_path, "", recipe_policy="solve") == "solve"
    assert challenge.effective_policy(tmp_path, "") == "block"


def test_an_unknown_policy_is_refused_by_name(tmp_path):
    with pytest.raises(challenge.ChallengePolicyError) as caught:
        challenge.effective_policy(tmp_path, "", override="bypass")
    assert "bypass" in str(caught.value)


def test_a_malformed_config_falls_back_to_the_default(tmp_path):
    (tmp_path / ".dossier").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".dossier" / "scrape.json").write_text("{not json", encoding="utf-8")
    assert challenge.effective_policy(tmp_path) == "auto"


def test_a_visible_window_is_off_unless_asked_for(tmp_path):
    assert challenge.allow_visible(tmp_path) is False
    _config(tmp_path, {"visible": True})
    assert challenge.allow_visible(tmp_path) is True
    _config(tmp_path, {"visible": "yes"})  # a string is not a boolean
    assert challenge.allow_visible(tmp_path) is False


# -- the solver ------------------------------------------------------------

def test_the_solver_reports_unconfigured_without_a_key(monkeypatch):
    monkeypatch.delenv(challenge.ENV_SOLVER_KEY, raising=False)
    config = challenge.solver_config()
    assert config["configured"] is False
    assert "DOSSIER_SOLVER_KEY" in json.dumps(config)


def test_the_solver_never_returns_the_key(monkeypatch):
    monkeypatch.setenv(challenge.ENV_SOLVER_KEY, "super-secret-key")
    config = challenge.solver_config()
    assert config["configured"] is True
    assert "super-secret-key" not in json.dumps(config)


def test_solve_refuses_early_without_a_key(monkeypatch):
    monkeypatch.delenv(challenge.ENV_SOLVER_KEY, raising=False)
    result = challenge.solve(_FakePage(), url="https://example.com/jobs")
    assert result["solved"] is False
    assert "DOSSIER_SOLVER_KEY" in result["reason"]


class _FakePage:
    """Just enough of a Playwright page for the pieces that read it."""

    def __init__(self, *, sitekey="0x4AAAA-test", insert_ok=True, cleared_after=1):
        self.sitekey = sitekey
        self.insert_ok = insert_ok
        self.cleared_after = cleared_after
        self.polls = 0
        self.evaluations: list[str] = []

    def evaluate(self, script, arg=None):
        self.evaluations.append(script)
        if "data-sitekey" in script:
            return self.sitekey
        return self.insert_ok

    def title(self):
        return "Just a moment..." if self.polls < self.cleared_after else "Open roles"

    def content(self):
        self.polls += 1
        return ("<html><body><h1>Just a moment...</h1><p>Checking your browser</p></body></html>"
                if self.polls < self.cleared_after else
                "<html><body><h1>Open roles</h1><p>Senior Engineer</p></body></html>")

    def query_selector(self, selector):
        return None

    def wait_for_timeout(self, milliseconds):
        return None


def test_a_page_that_clears_itself_reports_cleared():
    page = _FakePage(cleared_after=2)
    cleared, waited, reason = challenge.clear_waiter(page, seconds=5, poll=0)
    assert cleared is True
    assert "cleared" in reason
    assert waited >= 0


def test_a_page_that_never_clears_reports_the_timeout():
    page = _FakePage(cleared_after=10_000)
    cleared, waited, reason = challenge.clear_waiter(page, seconds=0.5, poll=0)
    assert cleared is False
    assert "never cleared" in reason


def test_solve_injects_a_token_into_the_named_field():
    page = _FakePage()
    assert challenge.inject_token(page, "token-value", "turnstile") is True
    assert any("cf-turnstile-response" in script for script in page.evaluations)


def test_a_page_with_no_sitekey_is_reported_not_guessed(monkeypatch):
    monkeypatch.setenv(challenge.ENV_SOLVER_KEY, "key")
    page = _FakePage(sitekey="")
    result = challenge.solve(page, url="https://example.com/jobs")
    assert result["solved"] is False
    assert "site key" in result["reason"]
