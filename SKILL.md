---
name: sub2api-imagegen
description: Generate or edit raster images only after detecting that the active Codex provider is a third-party gateway with an OpenAI-compatible image API, such as sub2api_local. Do not use with the built-in openai provider, OpenAI or ChatGPT endpoints, or an unknown provider. Missing image_gen alone is not a trigger.
---

# Sub2API Image Generation

## Trigger gate

Use this skill only when both conditions hold: the user requests raster image generation or editing, and the active provider is confirmed to be a third-party gateway. Provider setup, a missing `image_gen` tool, or the existence of an unused custom provider does not meet these conditions.

Before generating, run the helper's `--check` preflight. It reports `applicable: true` only for the selected custom provider with a third-party URL and usable credentials. If it reports `applicable: false`, return to the normal imagegen workflow without calling the third-party API. With the built-in `openai` provider or an OpenAI/ChatGPT endpoint, this skill must not execute an image request, even when explicitly mentioned. If the active turn uses a CLI or profile override, resolve that effective provider first; do not assume an unused definition or the base configuration describes the current session. If the effective provider is unknown, do not use this skill.

Once this gate passes, an ordinary image request is sufficient to use the configured third-party API. Do not ask the user to switch to an official API key or reconfirm the same API workflow merely because `image_gen` is absent.

This skill does not register or restore Codex's built-in `image_gen.imagegen` tool. Describe successful work as generation through Sub2API, and never report that the built-in tool was enabled.

## Run

The helper reads `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`) and resolves the selected custom provider's `base_url` and credentials. It supports command-backed auth, `env_key`, and `experimental_bearer_token`, and delegates image operations to the installed system imagegen script without modifying it. Credentials stay in the child process environment; do not print them, paste them into commands, or copy them into this skill.

Resolve this skill's absolute path from its installed location. Prefer the installed `.venv/bin/python`, which already has the image dependencies:

```bash
<skill-dir>/.venv/bin/python <skill-dir>/scripts/image_gen.py --check
```

Generate:

```bash
<skill-dir>/.venv/bin/python <skill-dir>/scripts/image_gen.py generate \
  --prompt "A chilled Hong Kong salted lemon soda, Japanese product photography, Japanese headline: 香港式 塩レモンソーダ" \
  --model gpt-image-2 --size 1024x1024 --quality medium \
  --out output/imagegen/salted-lemon-soda.png
```

Edit:

```bash
<skill-dir>/.venv/bin/python <skill-dir>/scripts/image_gen.py edit \
  --image input.png --prompt "Replace the background with a pale blue studio backdrop; preserve the product and label" \
  --model gpt-image-2 --out output/imagegen/product-edit.png
```

For an installation without `.venv`, use Python 3.11 or later with `openai`, `pillow`, and `socksio`, or run `uv run --no-project --with openai --with pillow --with socksio --python 3.13 python <skill-dir>/scripts/image_gen.py ...`. `socksio` supports environments with a SOCKS proxy configured, including when the gateway itself uses a proxy bypass. Use `--dry-run` to inspect the request without generating an image. The default model is `gpt-image-2`; follow an explicitly requested model when the provider supports it. Generation and editing use `/images/generations` and `/images/edits` under the configured base URL.

## Finish and failures

- Preserve the user's subject, brand, requested language, composition, and destination. For edits, state which parts must remain unchanged in the prompt.
- Save project assets inside the project, normally under `output/imagegen/`. Use a new filename for revisions; do not overwrite an existing image unless requested.
- Inspect the actual saved image with `view_image`, check its actual format, and show or link the result. Match its extension to the returned format.
- A missing key or provider is a configuration error, not permission to switch to OpenAI directly. A missing built-in tool is not an API failure.
- On a group-permission error, report which provider failed and that the Sub2API group needs image generation enabled. Do not change group permissions as part of ordinary image requests.
- On an upstream error, retain the error and stop; do not repeatedly retry a possibly completed paid generation or silently switch providers.
