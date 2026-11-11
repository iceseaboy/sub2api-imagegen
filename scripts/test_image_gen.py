import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("sub2api_image_gen", Path(__file__).with_name("image_gen.py"))
image_gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image_gen)


class ProviderRoutingTests(unittest.TestCase):
    def config(self, **auth):
        return {"model_provider": "relay", "model_providers": {"relay": {
            "base_url": "http://127.0.0.1:8080/v1", **auth,
        }}}

    def test_gateway_credentials_replace_inherited_official_credentials(self):
        env, details = image_gen.provider_environment(
            self.config(env_key="RELAY_KEY"),
            {"RELAY_KEY": "relay-secret", "OPENAI_API_KEY": "official-secret", "OPENAI_BASE_URL": "https://api.openai.com/v1"},
        )
        self.assertEqual(env["OPENAI_API_KEY"], "relay-secret")
        self.assertEqual(env["OPENAI_BASE_URL"], "http://127.0.0.1:8080/v1")
        self.assertTrue(details["applicable"])
        self.assertIn("127.0.0.1", env["NO_PROXY"])
        self.assertNotIn("secret", str(details))

    def test_missing_gateway_key_does_not_fall_back_to_official_key(self):
        with self.assertRaisesRegex(ValueError, "No valid bearer token"):
            image_gen.provider_environment(self.config(env_key="RELAY_KEY"), {"OPENAI_API_KEY": "official-secret"})

    def test_command_credentials_are_captured_without_exposing_the_key(self):
        auth = {"command": "/bin/cat", "args": ["/private/key"], "timeout_ms": 2000}
        with patch.object(image_gen.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "relay-secret\n")) as run:
            env, details = image_gen.provider_environment(self.config(auth=auth), {})
        self.assertEqual(env["OPENAI_API_KEY"], "relay-secret")
        self.assertEqual(run.call_args.args[0], ["/bin/cat", "/private/key"])
        self.assertEqual(run.call_args.kwargs["timeout"], 2)
        self.assertNotIn("relay-secret", str(details))

    def test_explicit_bearer_token_is_supported(self):
        env, _ = image_gen.provider_environment(self.config(experimental_bearer_token="relay-secret"), {})
        self.assertEqual(env["OPENAI_API_KEY"], "relay-secret")

    def test_official_destination_is_rejected(self):
        config = self.config(env_key="RELAY_KEY")
        config["model_providers"]["relay"]["base_url"] = "https://api.openai.com/v1"
        with self.assertRaises(image_gen.ProviderNotApplicable):
            image_gen.provider_environment(config, {"RELAY_KEY": "relay-secret"})

    def test_official_subdomains_are_rejected_before_credential_lookup(self):
        for host in ["us.api.openai.com", "gov.chatgpt.com", "chatgpt.com."]:
            with self.subTest(host=host):
                config = self.config(auth={"command": "/should/not/run"})
                config["model_providers"]["relay"]["base_url"] = "https://" + host + "/v1"
                with patch.object(image_gen.subprocess, "run") as run:
                    with self.assertRaises(image_gen.ProviderNotApplicable):
                        image_gen.provider_environment(config, {})
                    run.assert_not_called()

    def test_openai_does_not_use_an_unused_custom_provider(self):
        config = self.config(auth={"command": "/should/not/run"})
        config["model_provider"] = "openai"
        with patch.object(image_gen.subprocess, "run") as run:
            with self.assertRaises(image_gen.ProviderNotApplicable):
                image_gen.provider_environment(config, {})
            run.assert_not_called()

    def test_default_provider_is_openai(self):
        with self.assertRaises(image_gen.ProviderNotApplicable):
            image_gen.provider_environment({}, {})

    def test_official_mode_preflight_and_generation_never_spawn_a_child(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "config.toml").write_text('model_provider = "openai"\n')
            with patch.dict(image_gen.os.environ, {"CODEX_HOME": directory}), patch.object(image_gen.subprocess, "run") as run:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(image_gen.main(["--check"]), 0)
                self.assertFalse(json.loads(output.getvalue())["applicable"])
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(image_gen.main(["generate", "--prompt", "test"]), 2)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
