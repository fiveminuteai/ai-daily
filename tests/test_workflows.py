"""Every workflow file is valid YAML with jobs (11 Nov 2026: a one-line `run:` with ': ' in it broke deploy.yml
before it was pushed; GitHub would only have said so by not running it)."""
from pathlib import Path

import pytest
import yaml

FILES = sorted(Path(".github/workflows").glob("*.yml"))


@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_workflow_parses_and_has_jobs(path):
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(d, dict) and d.get("jobs"), path.name
    for name, job in d["jobs"].items():
        assert job.get("steps") or job.get("uses"), f"{path.name}: job {name} has no steps"


def test_there_are_workflows():
    assert len(FILES) >= 8
