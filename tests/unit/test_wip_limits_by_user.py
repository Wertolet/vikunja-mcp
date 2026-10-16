from vikunja_mcp.config import ConfigError, load_config
from vikunja_mcp.workflow import Workflow


class IdentityAPI:
    def __init__(self, username: str):
        self.username = username

    def me(self):
        return {"id": 1, "username": self.username}


def test_identity_limit_overrides_project_default():
    artist = Workflow(
        IdentityAPI("codex-artist"), 6, wip_limit=3,
        wip_limits={"codex-artist": 1, "claude-developer": 2},
    )
    developer = Workflow(
        IdentityAPI("claude-developer"), 6, wip_limit=3,
        wip_limits={"codex-artist": 1, "claude-developer": 2},
    )

    assert artist._effective_wip_limit() == 1
    assert developer._effective_wip_limit() == 2


def test_unknown_identity_uses_project_default():
    workflow = Workflow(
        IdentityAPI("another-agent"), 6, wip_limit=3,
        wip_limits={"codex-artist": 1},
    )

    assert workflow._effective_wip_limit() == 3


def test_config_reads_identity_limits(tmp_path):
    tmp_path.joinpath(".vikunja-mcp.toml").write_text(
        '[tracker]\nurl = "http://vikunja"\nproject_id = 6\n'
        'wip_limits = { "codex-artist" = 1, "claude-developer" = 2 }\n'
    )

    config = load_config(cwd=tmp_path, environ={"VIKUNJA_TOKEN": "secret"})

    assert config.wip_limits == {"codex-artist": 1, "claude-developer": 2}


def test_config_refuses_invalid_identity_limit(tmp_path):
    tmp_path.joinpath(".vikunja-mcp.toml").write_text(
        '[tracker]\nurl = "http://vikunja"\nproject_id = 6\n'
        'wip_limits = { "codex-artist" = 0 }\n'
    )

    try:
        load_config(cwd=tmp_path, environ={"VIKUNJA_TOKEN": "secret"})
    except ConfigError as exc:
        assert "wip_limits.codex-artist must be >= 1" in str(exc)
    else:
        raise AssertionError("invalid per-user WIP limit was accepted")
