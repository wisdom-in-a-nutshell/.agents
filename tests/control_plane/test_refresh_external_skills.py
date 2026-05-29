from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, write_text


def load_refresh_module():
    path = REPO_ROOT / "scripts/refresh-external-skills.py"
    spec = importlib.util.spec_from_file_location("refresh_external_skills", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RefreshExternalSkillsTests(TempDirTestCase):
    def test_materializes_skill_md_from_source_template(self) -> None:
        refresh = load_refresh_module()
        skill_dir = self.temp_path / "skill"
        write_text(skill_dir / "SKILL.src.md", "# template\n")

        self.assertEqual(
            "SKILL.src.md->SKILL.md",
            refresh.skill_entrypoint_plan(skill_dir),
        )
        self.assertTrue(refresh.materialize_skill_entrypoint(skill_dir))
        self.assertEqual("# template\n", (skill_dir / "SKILL.md").read_text(encoding="utf-8"))

    def test_rejects_refresh_source_without_skill_entrypoint(self) -> None:
        refresh = load_refresh_module()
        skill_dir = self.temp_path / "skill"
        skill_dir.mkdir(parents=True)

        with self.assertRaisesRegex(ValueError, "missing SKILL.md"):
            refresh.skill_entrypoint_plan(Path(skill_dir))
