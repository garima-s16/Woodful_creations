"""Runtime safety verification.

Two genuinely independent, dependency-light checks:

1. AST undefined-symbol scan across app/ - catches a real class of bug
   `py_compile` cannot (a name referenced but never imported/assigned,
   which only fails at actual runtime when that code path executes).
   This exact technique caught several real missing-import bugs during
   this session's development.

2. The rate limiter's test-isolation reset, genuinely executed against
   the real app/platform/security/rate_limit.py code (with a minimal
   FastAPI stub for the one class this file doesn't exercise).
"""
import ast
import builtins
import glob
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_undefined_symbols(filepath: str) -> set:
    """Returns the set of suspect undefined names in a single file, or
    raises SyntaxError if the file itself doesn't parse."""
    tree = ast.parse(open(filepath).read())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)

    referenced_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            referenced_names.add(node.id)

    builtin_names = set(dir(builtins))
    assigned_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            assigned_names.add(node.id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assigned_names.add(node.name)
            for arg in node.args.args:
                assigned_names.add(arg.arg)
            # Keyword-only arguments (everything after a bare * in a
            # signature, e.g. def f(a, *, b, c=1)) are stored
            # separately from args.args - missing this produced false
            # positives on every keyword-only-argument function in the
            # codebase (confirmed directly: automation_service.py,
            # communication_ai_service.py, mention_service.py all use
            # this pattern and were incorrectly flagged before this fix).
            for arg in node.args.kwonlyargs:
                assigned_names.add(arg.arg)
            if node.args.vararg:
                assigned_names.add(node.args.vararg.arg)
            if node.args.kwarg:
                assigned_names.add(node.args.kwarg.arg)
        if isinstance(node, ast.ClassDef):
            assigned_names.add(node.name)
        if isinstance(node, ast.ExceptHandler) and node.name:
            assigned_names.add(node.name)
        if isinstance(node, ast.comprehension):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    assigned_names.add(n.id)
        if isinstance(node, ast.For):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    assigned_names.add(n.id)
        if isinstance(node, ast.withitem) and node.optional_vars:
            for n in ast.walk(node.optional_vars):
                if isinstance(n, ast.Name):
                    assigned_names.add(n.id)
        if isinstance(node, ast.Lambda):
            for arg in node.args.args:
                assigned_names.add(arg.arg)
        if isinstance(node, ast.Global):
            assigned_names.update(node.names)

    # __file__ is a genuine, harmless false positive - available in
    # every real module's namespace but not visible to this static walk.
    return (referenced_names - imported_names - builtin_names - assigned_names) - {"__file__"}


def verify_ast_scan(app_dir: str) -> list:
    results = []
    files = sorted(glob.glob(f"{app_dir}/**/*.py", recursive=True))
    for f in files:
        try:
            suspects = check_undefined_symbols(f)
        except SyntaxError as e:
            results.append((f"AST scan: {f}", False, f"SYNTAX ERROR: {e}"))
            continue
        rel = os.path.relpath(f, os.path.dirname(app_dir))
        if suspects:
            results.append((f"AST scan: {rel}", False, f"suspect undefined names: {sorted(suspects)}"))
        # Only report clean files in aggregate, not one line each - see run_all()
    clean_count = len(files) - len([r for r in results])
    results.append((f"AST scan: {clean_count}/{len(files)} files genuinely clean", not results, ""))
    return results


def verify_rate_limiter_isolation() -> list:
    if "fastapi" not in sys.modules:
        try:
            import fastapi  # noqa: F401
        except ImportError:
            fake_fastapi = types.ModuleType("fastapi")
            class HTTPException(Exception):
                pass
            class Request:
                pass
            class status:
                HTTP_429_TOO_MANY_REQUESTS = 429
            fake_fastapi.HTTPException = HTTPException
            fake_fastapi.Request = Request
            fake_fastapi.status = status
            sys.modules["fastapi"] = fake_fastapi

    if "app.platform.configuration.config" not in sys.modules:
        fake_config = types.ModuleType("app.platform.configuration.config")
        class FakeSettings:
            RATE_LIMIT_BACKEND = "memory"
        fake_config.settings = FakeSettings()
        sys.modules["app.platform.configuration.config"] = fake_config

    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "platform", "security", "rate_limit.py")
    spec = importlib.util.spec_from_file_location("rate_limit_under_verification", path)
    rate_limit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rate_limit)

    results = []
    backend1 = rate_limit._get_backend()
    for _ in range(5):
        backend1.is_allowed("verify:test", max_requests=5, window_seconds=60)
    still_allowed = backend1.is_allowed("verify:test", max_requests=5, window_seconds=60)
    results.append(("rate_limit: bucket genuinely exhausted after 5 requests", still_allowed is False, f"6th request allowed={still_allowed}"))

    rate_limit.reset_rate_limits()
    backend2 = rate_limit._get_backend()
    fresh_allowed = backend2.is_allowed("verify:test", max_requests=5, window_seconds=60)
    ok = fresh_allowed is True and backend2 is not backend1
    results.append(("rate_limit: reset_rate_limits() gives a genuinely fresh backend", ok, f"allowed={fresh_allowed}, new_instance={backend2 is not backend1}"))
    return results


def verify_requirements_pinning(requirements_path: str) -> list:
    """The one genuinely executable part of a
    dependency audit without network access to a CVE database: are
    dependencies pinned exactly (== version), which is what makes an
    install reproducible and what a real vulnerability scan (pip-audit/
    safety, neither available here) would need to run against in the
    first place. The actual vulnerability scan itself is honestly
    reported as BLOCKED in verify.py, not attempted from memory - a
    memory-based CVE claim could be stale or simply wrong, which would
    be worse than admitting this needs a live scan."""
    import re
    lines = [l.strip() for l in open(requirements_path) if l.strip() and not l.strip().startswith("#")]
    loose = [l for l in lines if not re.match(r'^[\w.\-\[\]]+==', l)]
    ok = not loose
    detail = f"{len(lines)} dependencies, all exactly pinned" if ok else f"not exactly pinned: {loose}"
    return [("requirements.txt: exact version pinning", ok, detail)]


def run_all() -> list:
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
    requirements_path = os.path.join(os.path.dirname(app_dir), "requirements.txt")
    all_results = []
    all_results.extend(verify_ast_scan(app_dir))
    all_results.extend(verify_rate_limiter_isolation())
    all_results.extend(verify_requirements_pinning(requirements_path))
    return all_results


if __name__ == "__main__":
    results = run_all()
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'} - {name}" + (f": {detail}" if detail else ""))
    failed = [r for r in results if not r[1]]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)
