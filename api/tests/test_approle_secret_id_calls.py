"""Guard the AppRole SecretID call sites against unsupported hvac keywords.

`secret_id_ttl` and `secret_id_num_uses` are role-level properties in Vault's
AppRole API: they belong on create_or_update_approle(), not on the
secret-id issuance endpoint. Passing them to generate_secret_id() raises
TypeError at runtime and aborts vault-init, so the whole stack fails to start.
This test reproduces that failure without a running Vault.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from hvac.api.auth_methods import AppRole

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _secret_id_call_sites() -> list[tuple[Path, int, list[str]]]:
    sites: list[tuple[Path, int, list[str]]] = []
    for source_file in sorted(SCRIPTS_DIR.glob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "generate_secret_id":
                keywords = [kw.arg for kw in node.keywords if kw.arg is not None]
                sites.append((source_file, node.lineno, keywords))
    return sites


def test_there_are_secret_id_call_sites_to_check() -> None:
    # An empty scan would make the guard below vacuously pass.
    assert _secret_id_call_sites(), "no generate_secret_id call sites found under api/scripts"


def test_generate_secret_id_keywords_are_supported_by_hvac() -> None:
    accepted = set(inspect.signature(AppRole.generate_secret_id).parameters)
    accepted.discard("self")
    offenders: list[str] = []
    for source_file, lineno, keywords in _secret_id_call_sites():
        unsupported = sorted(set(keywords) - accepted)
        if unsupported:
            offenders.append(
                f"{source_file.name}:{lineno} passes unsupported keyword(s) {unsupported}"
            )
    assert not offenders, (
        "generate_secret_id() only accepts "
        f"{sorted(accepted)}; set secret_id_ttl/secret_id_num_uses on the role instead.\n"
        + "\n".join(offenders)
    )


def test_role_config_still_owns_the_secret_id_lifecycle() -> None:
    # Removing the bad keywords must not silently drop the D-02 requirement.
    accepted = set(inspect.signature(AppRole.create_or_update_approle).parameters)
    assert {"secret_id_ttl", "secret_id_num_uses"} <= accepted
    source = (SCRIPTS_DIR / "setup_vault.py").read_text(encoding="utf-8")
    assert "secret_id_ttl=APP_SECRET_ID_TTL" in source
    assert "secret_id_num_uses=APP_SECRET_ID_NUM_USES" in source