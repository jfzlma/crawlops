"""Run real Scrapy against deterministic files when Scrapy is installed."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    importlib.util.find_spec("scrapy") is None and not os.environ.get("CRAWLOPS_SCRAPY_PYTHON"),
    reason="Install dev extras or set CRAWLOPS_SCRAPY_PYTHON for real Scrapy integration",
)
@pytest.mark.parametrize("prefix", ["first", "second"])
def test_real_scrapy_runner(prefix):
    root = Path(__file__).resolve().parents[1]
    runner = root / "apps/api/crawlops/runner.py"
    spec = {"spider": "catalog", "arguments": {"prefix": prefix}, "settings": {}, "timeout": 30}
    result = subprocess.run(
        [os.environ.get("CRAWLOPS_SCRAPY_PYTHON", sys.executable), "-u", "-c", runner.read_text()],
        cwd=root / "examples/simple-spider",
        env={**os.environ, "CRAWLOPS_SPEC": json.dumps(spec)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    metrics = [
        json.loads(line.split("__CRAWLOPS_STATS__", 1)[1])
        for line in result.stdout.splitlines()
        if line.startswith("__CRAWLOPS_STATS__")
    ]
    assert metrics[-1]["item_scraped_count"] == 3
    assert metrics[-1]["finish_reason"] == "finished"
    assert metrics[-1].get("log_count/ERROR", 0) == 0
