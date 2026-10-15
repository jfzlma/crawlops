from types import SimpleNamespace

import pytest
from crawlops.state import transition


def test_success_requires_running():
    job = SimpleNamespace(status="QUEUED")
    with pytest.raises(ValueError):
        transition(job, "SUCCEEDED")
    transition(job, "DISPATCHING")
    transition(job, "STARTING")
    transition(job, "RUNNING")
    transition(job, "SUCCEEDED")
    with pytest.raises(ValueError):
        transition(job, "RUNNING")
