"""The optional board-wide WIP pool shared by every tracker identity."""
from contextlib import contextmanager

import pytest

from tests.unit.fakes import FakeAPI
from vikunja_mcp.config import ConfigError, load_config
from vikunja_mcp.workflow import STAGES, Workflow, WorkflowError


def _env(*, username="claude-developer", **kwargs):
    api = FakeAPI(me_id=20, me_username=username, buckets=STAGES)
    return api, Workflow(api, project_id=3, **kwargs)


def _other(username="codex-artist", user_id=10):
    return {"id": user_id, "username": username}


def test_config_reads_the_shared_limit_from_toml_only(tmp_path):
    tmp_path.joinpath(".vikunja-mcp.toml").write_text(
        '[tracker]\nurl = "http://vikunja"\nproject_id = 6\nshared_wip_limit = 3\n'
    )

    config = load_config(
        cwd=tmp_path,
        environ={"VIKUNJA_TOKEN": "secret", "VIKUNJA_SHARED_WIP_LIMIT": "99"},
    )

    assert config.shared_wip_limit == 3


@pytest.mark.parametrize("value", [0, -1, '"many"', True])
def test_config_refuses_an_invalid_shared_limit(tmp_path, value):
    rendered = str(value).lower() if isinstance(value, bool) else str(value)
    tmp_path.joinpath(".vikunja-mcp.toml").write_text(
        f'[tracker]\nurl = "http://vikunja"\nproject_id = 6\n'
        f"shared_wip_limit = {rendered}\n"
    )

    with pytest.raises(ConfigError, match="shared_wip_limit"):
        load_config(cwd=tmp_path, environ={"VIKUNJA_TOKEN": "secret"})


def test_two_codex_cards_leave_exactly_one_shared_slot_for_claude():
    api, wf = _env(
        wip_limit=3,
        wip_limits={"codex-artist": 2, "claude-developer": 3},
        shared_wip_limit=3,
    )
    api.add_task("artist one", "Design", assignee=_other())
    api.add_task("artist two", "Build", assignee=_other())
    first = api.add_task("developer one", "Queue")
    second = api.add_task("developer two", "Queue")

    assert wf.claim(first["id"])["claimed"] is True
    with pytest.raises(WorkflowError, match=r"Shared WIP limit reached \(3/3\)"):
        wf.claim(second["id"])


def test_review_cards_consume_the_shared_pool_and_remain_reviewable():
    api, wf = _env(shared_wip_limit=3)
    api.add_task("artist design", "Design", assignee=_other())
    api.add_task("artist build", "Build", assignee=_other())
    review = api.add_task("artist review", "Review", assignee=_other())
    api.add_comment(review["id"], "[worklog] ready for review")
    queued = api.add_task("developer queue", "Queue")

    offered = wf.next_task()
    assert offered["review"] is True
    assert offered["task"]["id"] == review["id"]
    assert offered["wip"]["shared"] == {
        "active": 3,
        "limit": 3,
        "free": 0,
        "stages": ["Design", "Build", "Review"],
    }
    assert offered["wip"]["free"] == 0
    with pytest.raises(WorkflowError, match=r"Shared WIP limit reached \(3/3\)"):
        wf.claim(queued["id"])


def test_effective_free_is_the_smaller_of_personal_and_shared_capacity():
    api, wf = _env(wip_limit=3, shared_wip_limit=3)
    api.add_task("other design", "Design", assignee=_other())
    api.add_task("other review", "Review", assignee=_other())
    api.add_task("available", "Queue")

    wip = wf.next_task()["wip"]

    assert wip["active"] == 0
    assert wip["limit"] == 3
    assert wip["free"] == 1
    assert wip["shared"]["free"] == 1


def test_shared_claims_enter_the_cross_process_lock(monkeypatch):
    api, wf = _env(shared_wip_limit=3)
    task = api.add_task("available", "Queue")
    entered = []

    @contextmanager
    def recording_lock(project_id):
        entered.append(project_id)
        yield

    monkeypatch.setattr("vikunja_mcp.workflow._project_claim_lock", recording_lock)

    assert wf.claim(task["id"])["claimed"] is True
    assert entered == [3]


def test_unconfigured_projects_keep_the_original_payload_shape():
    api, wf = _env(wip_limit=2)
    api.add_task("available", "Queue")

    assert wf.next_task()["wip"] == {"active": 0, "limit": 2, "free": 2}
