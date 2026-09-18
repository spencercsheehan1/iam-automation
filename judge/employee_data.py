"""Employee / organizational data access.

This stands in for an authoritative HR system (e.g. Workday). For the MVP
it reads synthetic data from a local CSV. The lookup function returns
``None`` when a user cannot be found so callers can distinguish "employee
unknown" (an ERROR condition per the PRD) from any legitimate FAIL.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EMPLOYEES_PATH = Path(__file__).parent / "data" / "employees.csv"


@dataclass(frozen=True)
class Employee:
    employee_id: str
    name: str
    email: str
    department: str
    employment_status: str
    snowflake_username: str


class EmployeeDataError(Exception):
    """Raised when the employee data source itself cannot be read."""


def load_employees(path: Path = DEFAULT_EMPLOYEES_PATH) -> list[Employee]:
    """Load all employees.

    Raises EmployeeDataError if the source file is missing or malformed —
    this must surface as ERROR upstream, never be treated as an empty
    (and therefore silently-passing) dataset.
    """
    if not path.exists():
        raise EmployeeDataError(f"Employee data source not found: {path}")

    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {
                "employee_id",
                "name",
                "email",
                "department",
                "employment_status",
                "snowflake_username",
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise EmployeeDataError(f"Employee data source missing columns: {sorted(missing)}")

            return [
                Employee(
                    employee_id=row["employee_id"].strip(),
                    name=row["name"].strip(),
                    email=row["email"].strip(),
                    department=row["department"].strip(),
                    employment_status=row["employment_status"].strip(),
                    snowflake_username=row["snowflake_username"].strip(),
                )
                for row in reader
            ]
    except EmployeeDataError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any parse failure as ERROR upstream
        raise EmployeeDataError(f"Failed to read employee data source: {exc}") from exc


def get_employee_by_snowflake_username(
    snowflake_username: str, path: Path = DEFAULT_EMPLOYEES_PATH
) -> Employee | None:
    """Look up a single employee by their Snowflake username (case-insensitive).

    This is the identifier `snowflake_client.get_role_assignments()` returns
    (Snowflake's `grantee_name`), so it's what `evaluator.evaluate_all()`
    uses to join role assignments back to employee attributes.
    """
    target = snowflake_username.strip().lower()
    for emp in load_employees(path):
        if emp.snowflake_username.lower() == target:
            return emp
    return None


def get_employee(email: str, path: Path = DEFAULT_EMPLOYEES_PATH) -> Employee | None:
    """Look up a single employee by email. Returns None if not found."""
    target = email.strip().lower()
    for emp in load_employees(path):
        if emp.email.lower() == target:
            return emp
    return None
