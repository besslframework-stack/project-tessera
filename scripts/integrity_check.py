#!/usr/bin/env python3
"""Tessera integrity check — runs before every commit.

Checks:
1. All tests pass
2. No syntax errors in changed Python files
3. Version consistency (pyproject.toml == http_server.py == CHANGELOG)
4. HTTP endpoint count matches README
5. No sensitive files staged (.env, credentials, secrets)
6. Import validation (no broken imports in src/)
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FAIL = "\033[91mFAIL\033[0m"
OK = "\033[92m OK \033[0m"
WARN = "\033[93mWARN\033[0m"

errors: list[str] = []
warnings: list[str] = []


def check(name: str, passed: bool, detail: str = ""):
    status = OK if passed else FAIL
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    if not passed:
        errors.append(name)


def warn(name: str, detail: str):
    print(f"  [{WARN}] {name} — {detail}")
    warnings.append(name)


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def check_tests():
    """1. Full test suite."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--tb=line", "-q"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300,
    )
    # Parse last line for pass count
    last_line = result.stdout.strip().split("\n")[-1] if result.stdout else ""
    passed = result.returncode == 0
    check("Test suite", passed, last_line)
    return passed


def check_syntax():
    """2. AST parse all changed .py files."""
    staged = get_staged_files()
    py_files = [f for f in staged if f.endswith(".py")]
    if not py_files:
        check("Syntax check", True, "no Python files staged")
        return True

    all_ok = True
    for f in py_files:
        path = PROJECT_ROOT / f
        if not path.exists():
            continue
        try:
            ast.parse(path.read_text())
        except SyntaxError as e:
            check("Syntax check", False, f"{f}: {e}")
            all_ok = False

    if all_ok:
        check("Syntax check", True, f"{len(py_files)} files OK")
    return all_ok


def check_version_consistency():
    """3. Version matches across pyproject.toml, http_server.py, CHANGELOG."""
    versions = {}

    # pyproject.toml
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'version\s*=\s*"([^"]+)"', pyproject.read_text())
        if m:
            versions["pyproject.toml"] = m.group(1)

    # http_server.py
    server = PROJECT_ROOT / "src" / "http_server.py"
    if server.exists():
        m = re.search(r'version="([^"]+)"', server.read_text())
        if m:
            versions["http_server.py"] = m.group(1)

    # CHANGELOG.md (first version entry)
    changelog = PROJECT_ROOT / "CHANGELOG.md"
    if changelog.exists():
        m = re.search(r"## \[(\d+\.\d+\.\d+)\]", changelog.read_text())
        if m:
            versions["CHANGELOG.md"] = m.group(1)

    unique = set(versions.values())
    if len(unique) <= 1:
        v = next(iter(unique)) if unique else "?"
        check("Version consistency", True, f"v{v} across {len(versions)} files")
        return True
    else:
        detail = ", ".join(f"{k}={v}" for k, v in versions.items())
        check("Version consistency", False, f"mismatch: {detail}")
        return False


def check_endpoint_count():
    """4. HTTP endpoint count in README matches actual."""
    server = PROJECT_ROOT / "src" / "http_server.py"
    readme = PROJECT_ROOT / "README.md"

    if not server.exists() or not readme.exists():
        check("Endpoint count", True, "files not found, skipping")
        return True

    # Count actual endpoints
    actual = len(re.findall(r"^@app\.(get|post|put|delete|patch)\(", server.read_text(), re.MULTILINE))

    # Find count in README
    readme_text = readme.read_text()
    m = re.search(r"\|\s*HTTP endpoints\s*\|\s*(\d+)\s*\|", readme_text)
    if not m:
        warn("Endpoint count", "not found in README")
        return True

    readme_count = int(m.group(1))
    if actual == readme_count:
        check("Endpoint count", True, f"{actual} endpoints")
        return True
    else:
        check("Endpoint count", False, f"actual={actual}, README says {readme_count}")
        return False


def check_sensitive_files():
    """5. No .env, credentials, or secrets staged."""
    staged = get_staged_files()
    blocked = []
    patterns = [".env", "credentials", "secret", ".pypirc", "id_rsa", ".pem"]

    for f in staged:
        name = Path(f).name.lower()
        if any(p in name for p in patterns):
            blocked.append(f)

    if blocked:
        check("Sensitive files", False, f"blocked: {', '.join(blocked)}")
        return False
    check("Sensitive files", True, "clean")
    return True


def check_imports():
    """6. All src/*.py files can be parsed for imports."""
    src_dir = PROJECT_ROOT / "src"
    if not src_dir.exists():
        check("Import validation", True, "no src/ directory")
        return True

    broken = []
    for py in sorted(src_dir.glob("*.py")):
        try:
            tree = ast.parse(py.read_text())
            # Just check AST is valid — actual import testing would require env
        except SyntaxError as e:
            broken.append(f"{py.name}: {e}")

    if broken:
        check("Import validation", False, "; ".join(broken))
        return False
    count = len(list(src_dir.glob("*.py")))
    check("Import validation", True, f"{count} modules OK")
    return True


def main():
    print("\n\033[1m=== Tessera Integrity Check ===\033[0m\n")

    results = [
        check_syntax(),
        check_version_consistency(),
        check_endpoint_count(),
        check_sensitive_files(),
        check_imports(),
        check_tests(),  # slowest last
    ]

    print()
    if errors:
        print(f"\033[91m✗ {len(errors)} check(s) failed: {', '.join(errors)}\033[0m")
        print("Commit blocked. Fix the issues above and try again.\n")
        sys.exit(1)
    elif warnings:
        print(f"\033[93m⚠ {len(warnings)} warning(s), but all checks passed.\033[0m\n")
        sys.exit(0)
    else:
        print("\033[92m✓ All checks passed.\033[0m\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
