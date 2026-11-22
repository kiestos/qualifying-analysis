"""Dependency direction between modules (design rule, not a spec requirement).

models.py depends on nothing in the package; the rules depend on models, never on the
loader; only the CLI wires loading, rules and output together.
"""

import ast

import pytest

from conftest import ROOT

SRC = ROOT / "src" / "qualifying"


def package_imports(module: str) -> set[str]:
    """Names of qualifying modules imported by ``module`` (relative or absolute)."""
    tree = ast.parse((SRC / f"{module}.py").read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1 and node.module:
                found.add(node.module.split(".")[0])
            elif node.level == 0 and node.module and node.module.startswith("qualifying."):
                found.add(node.module.split(".")[1])
    return found


def test_models_depend_on_nothing_in_the_package():
    assert package_imports("models") == set()


@pytest.mark.parametrize("module", ["laps", "classification", "insights", "format"])
def test_rules_do_not_depend_on_the_loader_or_cli(module):
    assert package_imports(module).isdisjoint({"load", "cli"})


def test_loader_depends_only_on_models():
    assert package_imports("load") == {"models"}
