#!/usr/bin/env python3
"""Run the installed imagegen CLI using the selected custom provider's credentials."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit


class ProviderNotApplicable(ValueError):
    pass


def provider_environment(config, environ):
    provider_id = config.get("model_provider", "openai")
    if provider_id == "openai":
        raise ProviderNotApplicable("The built-in OpenAI provider is selected; use the normal imagegen workflow.")
    provider = config.get("model_providers", {}).get(provider_id)
    if not provider:
        raise ValueError("Select a configured third-party provider in config.toml first.")
    base_url = provider.get("base_url", "").rstrip("/")
    url = urlsplit(base_url)
    if url.scheme not in ("http", "https") or not url.hostname:
        raise ValueError("The selected provider needs an explicit HTTP(S) base_url.")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("Keep credentials and query parameters out of the provider base_url.")
    host = url.hostname.lower().rstrip(".")
    if any(host == domain or host.endswith("." + domain) for domain in ("openai.com", "chatgpt.com")):
        raise ProviderNotApplicable("An OpenAI/ChatGPT endpoint is selected; use the normal imagegen workflow.")

    if provider.get("auth"):
        auth = provider["auth"]
        try:
            result = subprocess.run(
                [auth["command"], *auth.get("args", [])],
                capture_output=True,
                text=True,
                check=True,
                cwd=auth.get("cwd"),
                env=environ,
                timeout=auth.get("timeout_ms", 5000) / 1000,
            )
        except (subprocess.SubprocessError, OSError):
            raise ValueError("The provider's credential command failed; no key was printed.") from None
        token = result.stdout.strip()
        source = "provider.auth"
    elif provider.get("env_key"):
        source = provider["env_key"]
        token = environ.get(source, "").strip()
    else:
        source = "provider.experimental_bearer_token"
        token = provider.get("experimental_bearer_token", "").strip()
    if not token or "\n" in token or "\r" in token:
        raise ValueError(f"No valid bearer token from {source}; the official API key is not used as a fallback.")

    child_env = dict(environ)
    child_env["OPENAI_API_KEY"] = token
    child_env["OPENAI_BASE_URL"] = base_url
    if url.hostname in ("localhost", "127.0.0.1", "::1"):
        for name in ("NO_PROXY", "no_proxy"):
            existing = child_env.get(name, "")
            child_env[name] = ",".join(filter(None, [existing, "localhost,127.0.0.1,::1"]))
    return child_env, {"applicable": True, "provider": provider_id, "base_url": base_url, "credential_source": source}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    try:
        config = tomllib.loads((codex_home / "config.toml").read_text())
        child_env, details = provider_environment(config, os.environ)
        cli = codex_home / "skills/.system/imagegen/scripts/image_gen.py"
        if not cli.is_file():
            raise ValueError("The system imagegen CLI is missing; restore the installed imagegen skill.")
        if args == ["--check"]:
            print(json.dumps(details, ensure_ascii=False, indent=2))
            return 0
        return subprocess.run([sys.executable, str(cli), *args], env=child_env).returncode
    except ProviderNotApplicable as error:
        if args == ["--check"]:
            print(json.dumps({"applicable": False, "provider": config.get("model_provider", "openai"), "reason": str(error)}, indent=2))
            return 0
        print(f"sub2api-imagegen: skipped: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"sub2api-imagegen: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
