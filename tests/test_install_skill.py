import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallSkillTest(unittest.TestCase):
    def test_install_script_targets_workspace_skill_dir(self) -> None:
        with subprocess.Popen(["mktemp", "-d"], stdout=subprocess.PIPE, text=True) as proc:
            home_dir = Path(proc.stdout.read().strip())
        env = dict(os.environ)
        env["HOME"] = str(home_dir)
        subprocess.run(
            [str(ROOT / "scripts" / "install_skill.sh")],
            check=True,
            cwd=str(ROOT),
            env=env,
            text=True,
        )
        skill_dir = home_dir / ".openclaw" / "workspace" / "skills" / "openclaw-capture"
        self.assertTrue((skill_dir / "SKILL.md").exists())
        self.assertTrue((skill_dir / "scripts" / "dispatch_capture.py").exists())


if __name__ == "__main__":
    unittest.main()
