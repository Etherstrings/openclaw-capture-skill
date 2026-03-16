import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "openclaw-capture" / "scripts" / "runtime"))

from openclaw_capture_skill.profiles import parse_outputs, resolve_model_profile, resolve_stt_profile


class ProfilesTest(unittest.TestCase):
    def test_resolve_stt_profile_prefers_mac_path(self) -> None:
        self.assertEqual(resolve_stt_profile("", system_name="Darwin"), "mac_local_first")

    def test_resolve_stt_profile_prefers_local_cli_on_non_mac(self) -> None:
        self.assertEqual(
            resolve_stt_profile("", system_name="Linux", local_command="python3 local_asr.py --url {url}"),
            "local_cli_then_remote",
        )

    def test_resolve_stt_profile_falls_back_to_remote(self) -> None:
        self.assertEqual(resolve_stt_profile("", system_name="Linux", local_command=""), "remote_only")

    def test_parse_outputs_dedupes_and_filters(self) -> None:
        self.assertEqual(parse_outputs("telegram,feishu,telegram,unknown"), ("telegram", "feishu"))

    def test_resolve_model_profile_defaults_to_gateway(self) -> None:
        self.assertEqual(resolve_model_profile(""), "aihubmix_gateway")
        self.assertEqual(resolve_model_profile("openai_direct"), "openai_direct")


if __name__ == "__main__":
    unittest.main()

