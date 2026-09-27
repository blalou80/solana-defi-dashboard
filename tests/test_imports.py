"""Import smoke test.

Every application module must import cleanly. This guards against the
Phase-0 failure class where ~half the services layer referenced modules
that did not exist (or were shadowed by same-named files) and nothing
caught it because no test ever imported them.
"""

import importlib
import os
import pkgutil
import warnings

import pytest

import src

# Executable scripts with __main__ guards and hyphenated names; not importable.
EXCLUDE_PREFIXES = ("src.xyops.scripts",)

_BASE = os.path.dirname(os.path.abspath(src.__file__))

# Directories without __init__.py that walk_packages cannot descend into.
_NAMESPACE_DIRS = [
    ("dashboard/components", "src.dashboard.components."),
    ("dashboard/pages", "src.dashboard.pages."),
]


def _all_module_names():
    names = set()
    for m in pkgutil.walk_packages(
        src.__path__, "src.", onerror=lambda e: None
    ):
        if not m.name.startswith(EXCLUDE_PREFIXES):
            names.add(m.name)
    for rel, prefix in _NAMESPACE_DIRS:
        path = os.path.join(_BASE, rel)
        if os.path.isdir(path):
            for m in pkgutil.iter_modules([path]):
                names.add(prefix + m.name)
    return sorted(names)


MODULES = _all_module_names()


def test_module_discovery_is_not_empty():
    """If discovery silently breaks, the suite must not pass vacuously."""
    assert len(MODULES) >= 30, f"only discovered {len(MODULES)} modules: {MODULES}"
    # sanity: the modules that were broken in the 2026-09 audit must be present
    for must in (
        "src.services.dex_api_client",
        "src.services.solana_rpc_client",
        "src.services.cl_position_service",
        "src.utils.error_handling",
        "src.models.cl_position",
    ):
        assert must in MODULES, f"{must} missing from discovery"


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    with warnings.catch_warnings():
        # streamlit emits ScriptRunContext warnings when imported "bare";
        # they are noise here, not failures.
        warnings.simplefilter("ignore")
        importlib.import_module(module_name)
