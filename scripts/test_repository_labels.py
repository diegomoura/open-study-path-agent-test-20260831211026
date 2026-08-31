#!/usr/bin/env python3
"""Regression tests for intake-label provisioning and setup fallback behavior."""

from __future__ import annotations

from pathlib import Path

from ensure_repository_labels import ApiError, REQUIRED_LABELS, ensure_repository_labels

ROOT = Path(__file__).resolve().parents[1]


class FakeApi:
    def __init__(self, existing: set[str] | None = None, fail_status: int | None = None):
        self.existing = set(existing or set())
        self.fail_status = fail_status
        self.created: list[str] = []

    def __call__(self, method: str, path: str, payload: dict | None):
        if self.fail_status:
            raise ApiError(self.fail_status, "forced failure")
        if method == "GET":
            name = path.rsplit("/", 1)[-1].replace("%3A", ":")
            if name not in self.existing:
                raise ApiError(404, "missing")
            return {"name": name}
        if method == "POST":
            assert payload is not None
            name = payload["name"]
            self.existing.add(name)
            self.created.append(name)
            return payload
        raise AssertionError(f"unexpected method: {method}")


def assert_setup_contract() -> None:
    contract = (ROOT / "instructions/02-setup-execution.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ensure-repository-labels.yml").read_text(encoding="utf-8")

    required_contract_terms = [
        "never ask the learner to run that workflow manually",
        "is not, by itself, a setup blocker",
        "sufficient for `intake_entrypoint_ready` during setup",
        "The merge push provisions labels automatically",
        "Label existence remains a strict gate at intake candidate discovery and import",
        "Do not transfer the repair to the learner",
    ]
    for term in required_contract_terms:
        if term not in contract:
            raise SystemExit(f"setup contract lost automatic label-provisioning rule: {term}")

    for term in [
        "on:\n  push:",
        "issues: write",
        "Ensure intake labels",
        "scripts/ensure_repository_labels.py",
        "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)",
    ]:
        if term not in workflow:
            raise SystemExit(f"automatic provisioning workflow is incomplete: {term}")


def main() -> None:
    fake = FakeApi()
    result = ensure_repository_labels("example/study", fake)
    if set(result["created"]) != set(REQUIRED_LABELS) or set(fake.created) != set(REQUIRED_LABELS):
        raise SystemExit(f"missing labels were not created: {result}")

    fake = FakeApi({"study-request"})
    result = ensure_repository_labels("example/study", fake)
    expected_created = [name for name in REQUIRED_LABELS if name != "study-request"]
    if result != {"existing": ["study-request"], "created": expected_created}:
        raise SystemExit(f"existing labels were not reused: {result}")

    fake = FakeApi(set(REQUIRED_LABELS))
    result = ensure_repository_labels("example/study", fake)
    if result["created"]:
        raise SystemExit("idempotent provisioning created duplicate labels")

    try:
        ensure_repository_labels("invalid", FakeApi())
    except ValueError:
        pass
    else:
        raise SystemExit("invalid repository identifier was accepted")

    try:
        ensure_repository_labels("example/study", FakeApi(fail_status=403))
    except ApiError as error:
        if error.status != 403:
            raise
    else:
        raise SystemExit("non-404 API failure was swallowed")

    assert_setup_contract()
    print("Repository label provisioning regressions passed.")


if __name__ == "__main__":
    main()
