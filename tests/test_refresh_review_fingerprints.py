import hashlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import unittest

import yaml

SCRIPT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "refresh_review_fingerprints.py"
).read_text(encoding="utf-8")


class RefreshReviewFingerprintsTest(unittest.TestCase):
    def prepare(self, root: Path) -> Path:
        (root / "scripts").mkdir()
        (root / "state" / "reviews").mkdir(parents=True)
        script = root / "scripts" / "refresh_review_fingerprints.py"
        script.write_text(SCRIPT_SOURCE, encoding="utf-8")
        return script

    def review(
        self,
        root: Path,
        name: str,
        reviewed_at,
        artifacts: list[dict],
    ) -> Path:
        path = root / "state" / "reviews" / name
        path.write_text(
            yaml.safe_dump(
                {
                    "status": "approved",
                    "reviewed_at": reviewed_at,
                    "artifacts": artifacts,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return path

    def run_script(self, root: Path, script: Path, write: bool = False):
        command = [sys.executable, str(script)]
        if write:
            command.append("--write")
        return subprocess.run(
            command, cwd=root, text=True, capture_output=True
        )

    def test_historical_review_remains_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.prepare(root)
            artifact = root / "state" / "integrations.json"
            artifact.write_text('{"status":"current"}', encoding="utf-8")
            old = self.review(
                root,
                "setup.yml",
                "2026-08-01T10:00:00Z",
                [
                    {
                        "path": "state/integrations.json",
                        "change": "current",
                        "sha256": "0" * 64,
                    }
                ],
            )
            current_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.review(
                root,
                "publication.yml",
                "2026-08-03T10:00:00Z",
                [
                    {
                        "path": "state/integrations.json",
                        "change": "current",
                        "sha256": current_hash,
                    }
                ],
            )
            result = self.run_script(root, script)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                "0" * 64,
                yaml.safe_load(old.read_text(encoding="utf-8"))["artifacts"][0][
                    "sha256"
                ],
            )

    def test_write_refreshes_only_latest_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.prepare(root)
            (root / "study").mkdir()
            artifact = root / "study" / "a.md"
            artifact.write_text("current", encoding="utf-8")
            old = self.review(
                root,
                "old.yml",
                "2026-08-01T10:00:00Z",
                [
                    {
                        "path": "study/a.md",
                        "change": "current",
                        "sha256": "0" * 64,
                    }
                ],
            )
            latest = self.review(
                root,
                "latest.yml",
                "2026-08-03T10:00:00Z",
                [
                    {
                        "path": "study/a.md",
                        "change": "current",
                        "sha256": "1" * 64,
                    }
                ],
            )
            result = self.run_script(root, script, write=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                "0" * 64,
                yaml.safe_load(old.read_text(encoding="utf-8"))["artifacts"][0][
                    "sha256"
                ],
            )
            self.assertEqual(
                hashlib.sha256(b"current").hexdigest(),
                yaml.safe_load(latest.read_text(encoding="utf-8"))["artifacts"][0][
                    "sha256"
                ],
            )

    def test_equal_review_times_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.prepare(root)
            (root / "study").mkdir()
            (root / "study" / "a.md").write_text("A", encoding="utf-8")
            for name, fingerprint in (
                ("one.yml", "0" * 64),
                ("two.yml", "1" * 64),
            ):
                self.review(
                    root,
                    name,
                    "2026-08-03T10:00:00Z",
                    [
                        {
                            "path": "study/a.md",
                            "change": "current",
                            "sha256": fingerprint,
                        }
                    ],
                )
            result = self.run_script(root, script)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("ambiguous current review owner", result.stderr)

    def test_yaml_extension_and_timestamp_object_are_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self.prepare(root)
            (root / "study").mkdir()
            artifact = root / "study" / "a.md"
            artifact.write_text("A", encoding="utf-8")
            current_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.review(
                root,
                "publication.yaml",
                datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc),
                [
                    {
                        "path": "study/a.md",
                        "change": "current",
                        "sha256": current_hash,
                    }
                ],
            )
            result = self.run_script(root, script)
            self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
