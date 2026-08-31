import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pedagogical_content_hash.py"
SPEC = importlib.util.spec_from_file_location("pedagogical_content_hash", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PedagogicalContentHashTests(unittest.TestCase):
    def test_practice_link_changes_do_not_change_digest(self):
        first = """# Aula\n\nConteúdo aprovado.\n\n<!-- open-study-path:practice-links:start -->\n- [Quizlet A](https://example.com/a)\n<!-- open-study-path:practice-links:end -->\n"""
        second = """# Aula\n\nConteúdo aprovado.\n\n<!-- open-study-path:practice-links:start -->\n- [Quizlet B](https://example.com/b)\n<!-- open-study-path:practice-links:end -->\n"""
        self.assertEqual(module.pedagogical_sha256(first), module.pedagogical_sha256(second))

    def test_pedagogical_change_changes_digest(self):
        first = "# Aula\n\nExplicação original.\n"
        second = "# Aula\n\nExplicação corrigida.\n"
        self.assertNotEqual(module.pedagogical_sha256(first), module.pedagogical_sha256(second))

    def test_duplicate_managed_block_is_rejected(self):
        text = """# Aula
<!-- open-study-path:practice-links:start -->
a
<!-- open-study-path:practice-links:end -->
<!-- open-study-path:practice-links:start -->
b
<!-- open-study-path:practice-links:end -->
"""
        with self.assertRaises(ValueError):
            module.strip_operational_blocks(text)


if __name__ == "__main__":
    unittest.main()
