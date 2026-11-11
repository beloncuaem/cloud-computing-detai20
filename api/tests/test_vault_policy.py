"""Lock the workload and operator policies without a running Vault."""
from scripts.setup_vault import (
    APP_POLICY,
    APP_SECRET_ID_NUM_USES,
    APP_SECRET_ID_TTL,
    OPERATOR_POLICY_HCL,
)


def test_workload_secret_id_is_single_use_and_short_lived() -> None:
    assert APP_SECRET_ID_TTL == "10m"
    assert APP_SECRET_ID_NUM_USES == 1


def test_workload_policy_can_use_keys_but_cannot_administer_them() -> None:
    assert "datakey/plaintext/" in APP_POLICY
    assert "/decrypt/" in APP_POLICY
    assert "/rewrap/" in APP_POLICY
    assert "/creds/" in APP_POLICY
    assert "/keys/" not in APP_POLICY
    assert "/rotate" not in APP_POLICY
    assert "/export/" not in APP_POLICY
    assert "/config" not in APP_POLICY


def test_operator_policy_owns_key_lifecycle() -> None:
    assert "/rotate" in OPERATOR_POLICY_HCL
    assert "/config" in OPERATOR_POLICY_HCL
    assert "/rewrap/" in OPERATOR_POLICY_HCL
    assert "secret-id" in OPERATOR_POLICY_HCL
    assert "datakey/plaintext/" not in OPERATOR_POLICY_HCL
    assert "/decrypt/" not in OPERATOR_POLICY_HCL
