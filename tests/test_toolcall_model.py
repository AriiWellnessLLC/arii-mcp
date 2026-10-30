"""Check the tool-call tests' model settings: where the key comes from, and what is sent."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from toolcalls import model

CONFIG = {"model": "gpt-5.6-luna", "endpoint": "https://gateway.example/v1/responses"}


class CredentialsTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        for path in sorted(self.folder.rglob("*"), reverse=True):
            path.rmdir() if path.is_dir() else path.unlink()
        self.folder.rmdir()

    def test_no_key_names_the_variable_and_the_file(self):
        with self.assertRaises(model.ModelError) as raised:
            model.credentials(self.folder, CONFIG, environ={})
        self.assertIn("TOOLCALL_MODEL_KEY", str(raised.exception))
        self.assertIn(".env.local", str(raised.exception))

    def test_env_file_key_and_config_endpoint(self):
        (self.folder / ".env.local").write_text("# local only\nTOOLCALL_MODEL_KEY=from-file\n")
        self.assertEqual(model.credentials(self.folder, CONFIG, environ={}), ("from-file", CONFIG["endpoint"]))

    def test_environment_wins_over_the_env_file(self):
        (self.folder / ".env.local").write_text("TOOLCALL_MODEL_KEY=from-file\nTOOLCALL_MODEL_ENDPOINT=https://file\n")
        environ = {"TOOLCALL_MODEL_KEY": "from-env", "TOOLCALL_MODEL_ENDPOINT": "https://env"}
        self.assertEqual(model.credentials(self.folder, CONFIG, environ=environ), ("from-env", "https://env"))

    def test_a_tracked_env_file_is_refused(self):
        (self.folder / ".env.local").write_text("TOOLCALL_MODEL_KEY=from-file\n")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(git + ["init", "-q"], cwd=self.folder, check=True)
        subprocess.run(git + ["add", "-f", ".env.local"], cwd=self.folder, check=True)
        with self.assertRaises(model.ModelError) as raised:
            model.credentials(self.folder, CONFIG, environ={"TOOLCALL_MODEL_KEY": "from-env"})
        self.assertIn("tracked by git", str(raised.exception))


class RequestTest(unittest.TestCase):
    def test_the_body_never_sets_temperature(self):
        body = model.Model("https://e", "k", "gpt-5.6-luna").body([{"role": "user", "content": "q"}], [])
        self.assertEqual(body, {"model": "gpt-5.6-luna", "input": [{"role": "user", "content": "q"}], "tools": []})

    def test_the_config_file_names_the_model_and_endpoint(self):
        config = model.load_config(Path(__file__).resolve().parents[1] / "toolcalls" / "config.toml")
        self.assertEqual(config["model"], "gpt-5.6-luna")
        self.assertNotIn("temperature", config)


if __name__ == "__main__":
    unittest.main()
