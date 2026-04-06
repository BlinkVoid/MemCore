import asyncio
import unittest
from unittest.mock import patch

from src.memcore.utils.llm import LLMInterface


class _FakeProcess:
    def __init__(self, stdout: bytes = b'{"ok": true}', stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        pass

    async def wait(self):
        return None


class KimiCliTestCase(unittest.TestCase):
    def test_kimi_cli_completion_uses_bounded_noninteractive_flags(self):
        captured = {}

        async def fake_create_subprocess_exec(*cmd, **kwargs):
            captured["cmd"] = list(cmd)
            captured["kwargs"] = kwargs
            return _FakeProcess()

        llm = LLMInterface.__new__(LLMInterface)
        llm._cli_tool = "kimi"
        llm.catalogue = {"fast": "cli/kimi", "strong": "cli/kimi"}
        llm.provider = "cli"
        llm._local_embedder = None

        async def run():
            with patch("src.memcore.utils.llm.shutil.which", return_value="/usr/bin/kimi"):
                with patch("src.memcore.utils.llm.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
                    result = await llm._cli_completion(
                        "cli/kimi",
                        [{"role": "user", "content": "Return JSON only."}],
                        tier="strong",
                        response_format={"type": "json_object"},
                    )
            self.assertEqual(result, '{"ok": true}')

        asyncio.run(run())

        cmd = captured["cmd"]
        self.assertEqual(cmd[:2], ["kimi", "--print"])
        self.assertIn("--final-message-only", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("text", cmd)
        self.assertIn("--max-steps-per-turn", cmd)
        self.assertEqual(cmd[cmd.index("--max-steps-per-turn") + 1], "1")
        self.assertIn("--max-ralph-iterations", cmd)
        self.assertEqual(cmd[cmd.index("--max-ralph-iterations") + 1], "0")


if __name__ == "__main__":
    unittest.main()
