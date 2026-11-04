"""Guard: every place that pins a dev tool agrees with ``pyproject.toml``.

Dependabot's pip ecosystem bumps the pins in ``pyproject.toml`` but never the
hook ``rev:`` in ``.pre-commit-config.yaml``. A ruff bump therefore leaves the
hook on the old version, and nothing in CI can see it: the lint job installs
ruff from ``pyproject.toml``, so it keeps passing while pre-commit formats with
a different ruff than CI checks with. PR #57 aligned the two sites by hand, the
0.17.2 -> 0.17.3 bump in #58 undid it a few days later, and #59 aligned them
again. This test turns that drift into a failing ``test`` job, so the next bump
cannot land while the sites disagree.

To fix a failure: on the same branch as the bump, set the hook ``rev:`` named
in the message to the version ``pyproject.toml`` pins. For ruff, first compare
``ruff check --statistics`` and ``ruff format --check`` output between the two
versions — a changed default rule set is a code change, not a version string.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]

# Each dev tool whose version also appears outside pyproject.toml, and the
# pre-commit hook repository that ships it.
HOOK_REPOS = {
    "ruff": "https://github.com/astral-sh/ruff-pre-commit",
    "mypy": "https://github.com/pre-commit/mirrors-mypy",
}

Sites = list[tuple[str, SpecifierSet]]


def _version(text: str) -> Version | None:
    """Parse a version, tolerating the ``v`` prefix pre-commit revs carry."""
    try:
        return Version(text.removeprefix("v"))
    except InvalidVersion:
        return None


def _hook_revs(precommit_text: str) -> dict[str, str]:
    """Map each ``- repo:`` URL in a pre-commit config to its ``rev:``."""
    revs: dict[str, str] = {}
    repo: str | None = None
    for line in precommit_text.splitlines():
        repo_match = re.match(r"\s*-\s*repo:\s*(\S+)", line)
        if repo_match:
            repo = repo_match.group(1)
            continue
        rev_match = re.match(r"\s*rev:\s*['\"]?([^'\"\s#]+)", line)
        if rev_match and repo is not None:
            revs[repo] = rev_match.group(1)
    return revs


def _tool_specs(pyproject: dict) -> tuple[dict[str, Sites], list[str]]:
    """Map each requirement name to the (location, specifier) pairs pinning it.

    Reads every dependency group rather than a hand-listed few, so a new extra
    that installs a pinned tool is covered without touching this test.
    """
    project = pyproject.get("project", {})
    groups: list[tuple[str, object]] = [
        ("project.dependencies", project.get("dependencies", []))
    ]
    for extra, requirements in project.get("optional-dependencies", {}).items():
        groups.append((f"project.optional-dependencies.{extra}", requirements))

    specs: dict[str, Sites] = {}
    problems: list[str] = []
    for where, requirements in groups:
        if not isinstance(requirements, list):
            problems.append(f"pyproject.toml: {where} is not a list")
            continue
        for raw in requirements:
            try:
                requirement = Requirement(str(raw))
            except InvalidRequirement:
                problems.append(f"pyproject.toml: {where} has unparseable {raw!r}")
                continue
            name = canonicalize_name(requirement.name)
            specs.setdefault(name, []).append((where, requirement.specifier))
    return specs, problems


def _exact_pin(specifier: SpecifierSet) -> str | None:
    """Return the version an ``==1.2.3`` specifier pins, else None."""
    clauses = list(specifier)
    if len(clauses) == 1 and clauses[0].operator == "==":
        version = clauses[0].version
        if not version.endswith(".*"):
            return version
    return None


def _conflict(found: str, pin: str | None, sites: Sites) -> str | None:
    """Say why the version ``found`` elsewhere disagrees with pyproject.toml."""
    version = _version(found)
    if version is None:
        return f"which is not a version, so it cannot be compared with {pin or sites}"
    if pin is not None:
        return None if version == Version(pin) else f"pyproject.toml pins {pin}"
    unmet = [f"{where} requires {spec}" for where, spec in sites if version not in spec]
    return "; ".join(unmet) or None


def pin_problems(root: Path) -> list[str]:
    """Return one message per pin site that disagrees with pyproject.toml."""
    specs, problems = _tool_specs(tomllib.loads((root / "pyproject.toml").read_text()))
    revs = _hook_revs((root / ".pre-commit-config.yaml").read_text())
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        problems.append(".github/workflows: no workflow files to scan")

    for tool, hook_repo in HOOK_REPOS.items():
        sites = specs.get(tool, [])
        if not sites:
            problems.append(
                f"pyproject.toml: no {tool} requirement in any dependency group"
            )
            continue

        pinned = {where: pin for where, spec in sites if (pin := _exact_pin(spec))}
        if len(set(pinned.values())) > 1:
            disagreeing = ", ".join(
                f"{where} pins {pin}" for where, pin in sorted(pinned.items())
            )
            problems.append(
                f"pyproject.toml: {tool} is pinned to more than one version — "
                f"{disagreeing}"
            )
            continue
        pin = next(iter(pinned.values()), None)

        rev = revs.get(hook_repo)
        if rev is None:
            problems.append(
                f".pre-commit-config.yaml: no {hook_repo} hook, so nothing keeps "
                f"pre-commit's {tool} in step with pyproject.toml"
            )
        elif reason := _conflict(rev, pin, sites):
            remedy = f"; set rev: v{pin}" if pin else ""
            problems.append(
                f".pre-commit-config.yaml: {hook_repo} rev is {rev}, {reason}{remedy}"
            )

        for workflow in workflows:
            lines = workflow.read_text().splitlines()
            for number, line in enumerate(lines, start=1):
                pattern = rf"\b{re.escape(tool)}==([0-9][^\s\"';,)\]]*)"
                for found in re.findall(pattern, line):
                    if reason := _conflict(found, pin, sites):
                        problems.append(
                            f".github/workflows/{workflow.name}:{number}: "
                            f"{tool}=={found}, {reason}"
                        )
    return problems


def _write_repo(
    root: Path,
    *,
    ruff_rev: str = "v0.17.3",
    dev_ruff: str = "0.17.3",
    all_ruff: str = "0.17.3",
    mypy_rev: str = "v1.20.2",
    mypy_spec: str = ">=1.20.0",
    workflow_line: str = "run: ruff check src/ tests/",
) -> Path:
    """Write a minimal repo whose pins agree unless an argument says otherwise."""
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "drop2md"\n'
        'dependencies = ["typer>=0.12.0"]\n'
        "[project.optional-dependencies]\n"
        f'dev = ["ruff=={dev_ruff}", "mypy{mypy_spec}"]\n'
        f'all = ["ruff=={all_ruff}", "mypy{mypy_spec}"]\n'
    )
    hooks = (
        f"  - repo: {HOOK_REPOS['ruff']}\n"
        f"    rev: {ruff_rev}\n"
        "    hooks:\n"
        "      - id: ruff-check\n"
    )
    if mypy_rev:
        hooks += f"  - repo: {HOOK_REPOS['mypy']}\n    rev: {mypy_rev}\n"
    (root / ".pre-commit-config.yaml").write_text(f"repos:\n{hooks}")
    (root / ".github" / "workflows" / "ci.yml").write_text(
        f"jobs:\n  test:\n    steps:\n      - {workflow_line}\n"
    )
    return root


def test_repository_pin_sites_agree():
    """The real repo: the guard this test exists for."""
    assert pin_problems(REPO_ROOT) == []


def test_guard_reads_the_repository_pin_sites():
    """An empty problem list must mean "agreed", never "found nothing to read".

    Without this, moving a pin or renaming a config file turns the test above
    into a vacuous pass — the same blind spot that let the drift through.
    """
    specs, problems = _tool_specs(
        tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    )
    assert problems == []
    revs = _hook_revs((REPO_ROOT / ".pre-commit-config.yaml").read_text())

    for tool, hook_repo in HOOK_REPOS.items():
        assert specs.get(tool), f"no {tool} requirement in pyproject.toml"
        assert hook_repo in revs, f"no {hook_repo} hook in .pre-commit-config.yaml"

    ruff_pins = {_exact_pin(spec) for _, spec in specs["ruff"]}
    assert ruff_pins == {revs[HOOK_REPOS["ruff"]].removeprefix("v")}
    assert sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml"))


def test_aligned_repo_has_no_problems(tmp_path):
    assert pin_problems(_write_repo(tmp_path)) == []


def test_detects_stale_hook_rev(tmp_path):
    """The #58 regression: pyproject moved to 0.17.3, the hook stayed behind."""
    problems = pin_problems(_write_repo(tmp_path, ruff_rev="v0.17.2"))

    assert problems == [
        f".pre-commit-config.yaml: {HOOK_REPOS['ruff']} rev is v0.17.2, "
        "pyproject.toml pins 0.17.3; set rev: v0.17.3"
    ]


def test_detects_extras_that_disagree(tmp_path):
    """A bump that moves [dev] but not [all] — both pin ruff exactly."""
    problems = pin_problems(_write_repo(tmp_path, all_ruff="0.17.2"))

    assert problems == [
        "pyproject.toml: ruff is pinned to more than one version — "
        "project.optional-dependencies.all pins 0.17.2, "
        "project.optional-dependencies.dev pins 0.17.3"
    ]


def test_detects_missing_hook(tmp_path):
    problems = pin_problems(_write_repo(tmp_path, mypy_rev=""))

    assert problems == [
        f".pre-commit-config.yaml: no {HOOK_REPOS['mypy']} hook, so nothing keeps "
        "pre-commit's mypy in step with pyproject.toml"
    ]


def test_detects_hook_below_a_declared_floor(tmp_path):
    """mypy is a range, not a pin: the hook rev has to satisfy it."""
    problems = pin_problems(_write_repo(tmp_path, mypy_spec=">=1.21.0"))

    assert problems == [
        f".pre-commit-config.yaml: {HOOK_REPOS['mypy']} rev is v1.20.2, "
        "project.optional-dependencies.dev requires >=1.21.0; "
        "project.optional-dependencies.all requires >=1.21.0"
    ]


def test_detects_a_workflow_pin(tmp_path):
    root = _write_repo(tmp_path, workflow_line="run: pip install ruff==0.16.9 build")

    assert pin_problems(root) == [
        ".github/workflows/ci.yml:4: ruff==0.16.9, pyproject.toml pins 0.17.3"
    ]


def test_detects_an_unparseable_hook_rev(tmp_path):
    problems = pin_problems(_write_repo(tmp_path, ruff_rev="main"))

    assert len(problems) == 1
    assert problems[0].startswith(
        f".pre-commit-config.yaml: {HOOK_REPOS['ruff']} rev is main, "
    )
    assert "not a version" in problems[0]
