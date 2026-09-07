"""Static AST and regex linter enforcing zero silent fallbacks and loud failure rules."""

import ast
from pathlib import Path
import re
import pytest

CORE_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_SRC = CORE_ROOT.parent / "apps" / "desktop" / "src"


def find_python_files(root: Path) -> list[Path]:
    """Find all production Python files excluding venvs and caches."""
    py_files: list[Path] = []
    for p in root.rglob("*.py"):
        rel = str(p.relative_to(root))
        if ".venv" in rel or "__pycache__" in rel or "egg-info" in rel:
            continue
        py_files.append(p)
    return py_files


def find_typescript_files(root: Path) -> list[Path]:
    """Find all TypeScript and TSX files in desktop frontend."""
    if not root.exists():
        return []
    ts_files: list[Path] = []
    for p in root.rglob("*"):
        if p.suffix in (".ts", ".tsx") and "node_modules" not in str(p):
            ts_files.append(p)
    return ts_files


def test_no_bare_except_in_core_python():
    """Rule 8: Bare 'except:' clauses are strictly forbidden."""
    violations: list[str] = []
    for py_file in find_python_files(CORE_ROOT):
        # Allow test files to use pytest constructs if needed
        if "tests" in py_file.parts:
            continue

        source = py_file.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    violations.append(f"{py_file.name}:{node.lineno} -> Bare except: detected")

    assert not violations, f"Bare except clauses forbidden:\n" + "\n".join(violations)


def test_no_swallowed_exceptions_without_logging_or_handling():
    """Rule 8: 'except Exception: pass' or empty error suppression is forbidden in core."""
    violations: list[str] = []
    for py_file in find_python_files(CORE_ROOT):
        if "tests" in py_file.parts:
            continue

        source = py_file.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if body is solely 'pass'
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    # Check if line has an explicit documented justification
                    lines = source.splitlines()
                    handler_line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    if "# allowed-silent" not in handler_line:
                        violations.append(
                            f"{py_file.name}:{node.lineno} -> Swallowed exception with bare 'pass': {handler_line.strip()}"
                        )

    assert not violations, f"Silent exception swallowing forbidden:\n" + "\n".join(violations)


def test_no_empty_catch_blocks_in_typescript():
    """Rule 8: Empty 'catch {}' blocks are forbidden in desktop frontend."""
    violations: list[str] = []
    empty_catch_regex = re.compile(r"catch\s*(\([^\)]*\))?\s*\{\s*\}")

    for ts_file in find_typescript_files(DESKTOP_SRC):
        content = ts_file.read_text(encoding="utf-8", errors="replace")
        for match in empty_catch_regex.finditer(content):
            # Calculate line number
            line_num = content[: match.start()].count("\n") + 1
            violations.append(f"{ts_file.name}:{line_num} -> Empty catch block: '{match.group(0)}'")

    assert not violations, f"Empty catch blocks forbidden in UI:\n" + "\n".join(violations)


def test_model_registry_no_silent_fallback_substitution():
    """Rule 8: Model registry must fail loudly when requested role is not configured."""
    from models.registry import ModelRegistry, NoModelForRoleError

    registry = ModelRegistry()
    with pytest.raises(NoModelForRoleError):
        # Resolving a non-existent role must raise an error, not substitute another model
        registry.resolve("non_existent_fake_role_999")


def test_no_hardcoded_model_tags_in_production_source():
    """Rule 3: Model tags appear strictly in models.yaml, never in production code."""
    import yaml

    models_yaml_path = CORE_ROOT.parent / "models.yaml"
    assert models_yaml_path.exists(), "models.yaml not found"

    with open(models_yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Collect all configured model tags
    model_tags: set[str] = set()
    for role_models in config.get("roles", {}).values():
        if isinstance(role_models, list):
            model_tags.update(role_models)
        elif isinstance(role_models, str):
            model_tags.add(role_models)

    for tag in config.get("overrides", {}).keys():
        model_tags.add(tag)

    for tag in config.get("priors", {}).keys():
        model_tags.add(tag)

    assert len(model_tags) > 0, "No model tags found in models.yaml"

    violations: list[str] = []
    # Check Python production files (exclude tests, synthetic fixtures)
    for py_file in find_python_files(CORE_ROOT):
        if "tests" in py_file.parts or "fixtures" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8", errors="replace")
        for tag in model_tags:
            # Check for exact quoted tag (e.g. "bge-m3:latest", 'gpt-oss:20b')
            base_tag = tag.split(":")[0]
            if f'"{tag}"' in content or f"'{tag}'" in content or f'"{base_tag}"' in content or f"'{base_tag}'" in content:
                # Allowed only if in registry defaults or comments
                lines = content.splitlines()
                for idx, line in enumerate(lines):
                    if (f'"{tag}"' in line or f"'{tag}'" in line or f'"{base_tag}"' in line or f"'{base_tag}'" in line) and not line.strip().startswith("#"):
                        # If in registry fallback or comment, skip
                        if "models/registry.py" in str(py_file).replace("\\", "/") and "DEFAULT_" in line:
                            continue
                        violations.append(f"{py_file.name}:{idx+1} -> Hardcoded model tag '{tag}' in code: {line.strip()}")

    assert not violations, f"Hardcoded model tags forbidden in production code (Rule 3):\n" + "\n".join(violations)
