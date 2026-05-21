from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _repo_root_cwd() -> None:
    os.chdir(_REPO_ROOT)
