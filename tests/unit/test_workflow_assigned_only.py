"""assigned_only: a token takes only the Queue cards a human assigned to it, so several
identities can split one board by role (e.g. one bot for code, one for graphics)."""
import pytest

from tests.unit.fakes import FakeAPI
from vikunja_mcp.config import load_config
from vikunja_mcp.workflow import STAGES, Workflow, WorkflowError


@pytest.fixture
def env():
    api = FakeAPI(buckets=STAGES)
    return api, Workflow(api, project_id=3, assigned_only=True)


def _me(api):
    return api.me()


def test_unassigned_queue_card_is_not_offered(env):
    api, wf = env
    api.add_task("free", "Queue", priority=5)
    res = wf.next_task()
    assert res["task"] is None
    assert "assigned_only" in res["note"]


def test_card_assigned_to_someone_else_is_not_offered(env):
    api, wf = env
    api.add_task("theirs", "Queue", assignee={"id": 9, "username": "codex-bot"})
    assert wf.next_task()["task"] is None


def test_card_assigned_to_me_is_offered_and_claimable(env):
    api, wf = env
    api.add_task("free", "Queue", priority=9)
    mine = api.add_task("mine", "Queue", priority=1, assignee=_me(api))
    res = wf.next_task()
    assert res["task"]["id"] == mine["id"]
    assert wf.claim(mine["id"])["claimed"] is True


def test_claim_refuses_unassigned_card(env):
    api, wf = env
    free = api.add_task("free", "Queue")
    with pytest.raises(WorkflowError, match="assigned_only"):
        wf.claim(free["id"])
    assert not api.tasks[free["id"]].get("assignees")


def test_review_offers_are_unaffected(env):
    """Cross-review between identities still works: Review cards are offered to anyone."""
    api, wf = env
    api.add_task("built", "Review", assignee={"id": 9, "username": "codex-bot"})
    t = next(iter(api.tasks.values()))
    api.add_comment(t["id"], "[worklog] done")
    assert wf.next_task().get("review") is True


def test_default_off_keeps_free_queue(env):
    api, _ = env
    free = api.add_task("free", "Queue")
    assert Workflow(api, project_id=3).next_task()["task"]["id"] == free["id"]


def test_toml_key_reaches_config(tmp_path):
    (tmp_path / ".vikunja-mcp.toml").write_text(
        '[tracker]\nurl = "http://x"\nproject_id = 3\nassigned_only = true\n'
    )
    assert load_config(cwd=tmp_path, environ={"VIKUNJA_TOKEN": "t"}).assigned_only is True
