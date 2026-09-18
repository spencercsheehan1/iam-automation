"""Snowflake role-assignment retrieval.

Two modes, selected by the JUDGE_MODE env var:

  sample (default) — read data/snowflake_roles_sample.csv. Used until a
      real Snowflake trial account exists; keeps the app fully
      self-contained with zero external setup.

  live — query a real Snowflake account for current grants of
      PROD_ANALYTICS_ROLE using `snowflake-connector-python`. Requires
      SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
      SNOWFLAKE_WAREHOUSE, and (optionally) SNOWFLAKE_ROLE env vars.

In both modes, any failure to retrieve role-assignment data raises
SnowflakeQueryError — callers must surface this as ERROR, never as FAIL
or as an empty (silently-passing) result set.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SAMPLE_PATH = Path(__file__).parent / "data" / "snowflake_roles_sample.csv"


@dataclass(frozen=True)
class RoleAssignment:
    user: str
    assigned_role: str


class SnowflakeQueryError(Exception):
    """Raised when role-assignment data cannot be retrieved, for any reason."""


def get_role_assignments(role: str, mode: str | None = None) -> list[RoleAssignment]:
    """Return current assignments of `role`, in the configured mode.

    mode defaults to the JUDGE_MODE env var, falling back to "sample".
    """
    mode = (mode or os.environ.get("JUDGE_MODE", "sample")).strip().lower()

    if mode == "sample":
        return _get_role_assignments_sample(role)
    if mode == "live":
        return _get_role_assignments_live(role)

    raise SnowflakeQueryError(f"Unknown JUDGE_MODE: {mode!r} (expected 'sample' or 'live')")


def _get_role_assignments_sample(role: str, path: Path = DEFAULT_SAMPLE_PATH) -> list[RoleAssignment]:
    if not path.exists():
        raise SnowflakeQueryError(f"Sample role-assignment source not found: {path}")

    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"user", "assigned_role"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise SnowflakeQueryError(f"Sample role source missing columns: {sorted(missing)}")

            return [
                RoleAssignment(user=row["user"].strip(), assigned_role=row["assigned_role"].strip())
                for row in reader
                if row["assigned_role"].strip() == role
            ]
    except SnowflakeQueryError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parse failure is a retrieval ERROR
        raise SnowflakeQueryError(f"Failed to read sample role source: {exc}") from exc


def _load_private_key_der(path: str) -> bytes:
    """Load a PKCS8 PEM private key and return it as DER bytes, as required
    by snowflake.connector.connect(private_key=...).
    """
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    with open(path, "rb") as f:
        pem_data = f.read()

    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    private_key = serialization.load_pem_private_key(
        pem_data,
        password=passphrase.encode() if passphrase else None,
        backend=default_backend(),
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _get_role_assignments_live(role: str) -> list[RoleAssignment]:
    """Query a real Snowflake account for current grants of `role`.

    Requires SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_WAREHOUSE, and
    either:
      - SNOWFLAKE_PRIVATE_KEY_PATH (key-pair auth, preferred for service
        accounts — bypasses password/MFA policy entirely), or
      - SNOWFLAKE_PASSWORD (password auth; blocked if the account enforces
        MFA on password logins).
    SNOWFLAKE_ROLE is optional in both cases.
    """
    try:
        import snowflake.connector  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SnowflakeQueryError(
            "snowflake-connector-python is not installed. "
            "Run `pip install snowflake-connector-python` to use JUDGE_MODE=live."
        ) from exc

    required_env = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE"]
    missing_env = [name for name in required_env if not os.environ.get(name)]
    if missing_env:
        raise SnowflakeQueryError(f"Missing required env vars for live Snowflake mode: {missing_env}")

    private_key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    password = os.environ.get("SNOWFLAKE_PASSWORD")
    if not private_key_path and not password:
        raise SnowflakeQueryError(
            "Missing credentials for live Snowflake mode: set either "
            "SNOWFLAKE_PRIVATE_KEY_PATH (key-pair auth, preferred) or "
            "SNOWFLAKE_PASSWORD."
        )

    connect_kwargs: dict = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    if private_key_path:
        try:
            connect_kwargs["private_key"] = _load_private_key_der(private_key_path)
        except Exception as exc:  # noqa: BLE001
            raise SnowflakeQueryError(f"Failed to load private key from {private_key_path}: {exc}") from exc
    else:
        connect_kwargs["password"] = password

    conn = None
    try:
        conn = snowflake.connector.connect(**connect_kwargs)
        cur = conn.cursor()
        # SHOW GRANTS OF ROLE returns one row per principal the role is
        # granted to, including grantee_name (the user) for USER grants.
        cur.execute(f"SHOW GRANTS OF ROLE {role}")
        rows = cur.fetchall()
        columns = [desc[0].lower() for desc in cur.description]

        assignments: list[RoleAssignment] = []
        for row in rows:
            record = dict(zip(columns, row))
            if record.get("granted_to", "").upper() == "USER":
                assignments.append(RoleAssignment(user=record["grantee_name"], assigned_role=role))
        return assignments
    except SnowflakeQueryError:
        raise
    except Exception as exc:  # noqa: BLE001 - any connector/query failure is a retrieval ERROR
        raise SnowflakeQueryError(f"Live Snowflake query failed: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()
