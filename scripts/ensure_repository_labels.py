#!/usr/bin/env python3
"""Create the repository labels required by the intake Issue Form."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REQUIRED_LABELS: dict[str, dict[str, str]] = {
    "study-request": {
        "color": "1D76DB",
        "description": "Submissão do formulário de criação da trilha",
    },
    "intake:imported": {
        "color": "0E8A16",
        "description": "Intake já importado para a configuração da trilha",
    },
    "diagnostic:in-progress": {
        "color": "FBCA04",
        "description": "Sessão de diagnóstico aberta, aguardando resposta do aluno",
    },
    "diagnostic:answer": {
        "color": "1D76DB",
        "description": "Submissão do formulário de resposta ao diagnóstico",
    },
    "diagnostic:answer-imported": {
        "color": "0E8A16",
        "description": "Resposta de diagnóstico já importada para a sessão",
    },
}


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


RequestJson = Callable[[str, str, dict[str, Any] | None], Any]


def github_request_factory(token: str, api_url: str = "https://api.github.com") -> RequestJson:
    def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            api_url.rstrip("/") + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "open-study-path-label-provisioner",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ApiError(error.code, details or error.reason) from error

    return request_json


def ensure_repository_labels(repository: str, request_json: RequestJson) -> dict[str, list[str]]:
    if not REPOSITORY.fullmatch(repository):
        raise ValueError(f"invalid repository identifier: {repository}")

    existing: list[str] = []
    created: list[str] = []
    base = f"/repos/{repository}"

    for name, definition in REQUIRED_LABELS.items():
        try:
            request_json("GET", f"{base}/labels/{quote(name, safe='')}", None)
            existing.append(name)
        except ApiError as error:
            if error.status != 404:
                raise
            request_json("POST", f"{base}/labels", {"name": name, **definition})
            created.append(name)

    return {"existing": existing, "created": created}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("GITHUB_TOKEN is required to provision repository labels")

    result = ensure_repository_labels(
        args.repository,
        github_request_factory(args.token, args.api_url),
    )
    print(
        "Intake labels ready. "
        f"Created: {', '.join(result['created']) or 'none'}; "
        f"existing: {', '.join(result['existing']) or 'none'}."
    )


if __name__ == "__main__":
    try:
        main()
    except (ApiError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
