# sub2api-imagegen

让 Codex 通过当前选中的第三方 OpenAI 兼容网关生成、编辑图片，默认模型为 `gpt-image-2`。

只有用户要求生成或编辑位图，且当前会话确认使用第三方 provider 时才执行。内置 `openai` provider、OpenAI/ChatGPT 官方端点、未知 provider 均跳过。仅仅缺少内置 `image_gen` 工具不会触发本技能。

## 直接交给 Agent 安装

将下面这段话连同仓库链接发给其他 Agent：

```text
请安装 https://github.com/iceseaboy/sub2api-imagegen 。
先阅读仓库 README.md 和 SKILL.md。技能位于仓库根目录；使用 skill-installer 时指定 --path . --name sub2api-imagegen。
安装到当前环境可发现的用户技能目录，已有同名目录时先核对并保留备份。
按 README 创建 Python 虚拟环境、安装 requirements.txt，并检查系统 imagegen CLI；只有缺失时才从 vendor/imagegen/ 补齐，不覆盖已有系统脚本。
保留第三方 provider 检测、鉴权和官方端点跳过规则，不修改我当前的 provider、登录或密钥配置。
运行原有测试，核对 SHA256SUMS；安装阶段不发送真实图片 API 请求。报告安装位置、依赖状态和测试结果。
```

这是采用 `SKILL.md` 结构的技能，可由支持该结构的 Agent 读取；运行脚本仍读取 Codex 的配置文件。其他 Agent 使用时也需要有效的这份配置，不能自行套用其他产品的登录信息。

## 安装

### 使用内置 skill-installer

先确认 Python 为 3.11 或更新版本。安装器位于本机技能目录时：

```bash
SKILL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
python3 "$SKILL_CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo iceseaboy/sub2api-imagegen \
  --path . \
  --name sub2api-imagegen
```

`--name` 必须保留，因为技能位于仓库根目录。安装器发现目标已存在时会退出，不会覆盖。

### 使用 Git

```bash
SKILL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_DIR="$SKILL_CODEX_HOME/skills/sub2api-imagegen"
mkdir -p "$SKILL_CODEX_HOME/skills"
git clone https://github.com/iceseaboy/sub2api-imagegen.git "$SKILL_DIR"
```

确认当前 Codex 会扫描该目录；使用 `~/.agents/skills/` 的环境可把技能安装到该目录，或将现有技能目录链接过去，避免重复安装同名技能。自定义安装位置时，将下文的 `SKILL_DIR` 改成实际路径。

## 安装运行依赖

要求 Python 3.11+，推荐 Python 3.13。仓库只发布源码，不携带 `.venv`、配置或凭据。

```bash
SKILL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_DIR="$SKILL_CODEX_HOME/skills/sub2api-imagegen"
uv venv --python 3.13 "$SKILL_DIR/.venv"
uv pip install --python "$SKILL_DIR/.venv/bin/python" -r "$SKILL_DIR/requirements.txt"
```

没有 `uv` 时，可用 Python 3.11+ 的 `python3 -m venv` 创建同一路径的环境，再用该环境的 `python -m pip install -r requirements.txt` 安装依赖。`socksio` 用于兼容设置了 SOCKS 代理的环境。

### 补齐缺失的系统 imagegen CLI

原版 wrapper 调用以下文件：

```text
${CODEX_HOME:-~/.codex}/skills/.system/imagegen/scripts/image_gen.py
```

如果该脚本已存在，直接使用现有版本。以下命令仅在缺失时从仓库附带的原始快照补齐脚本及许可，不覆盖现有系统脚本，也不修改 provider 配置：

```bash
"$SKILL_DIR/.venv/bin/python" - "$SKILL_DIR" <<'PY'
import os
from pathlib import Path
import sys

skill_dir = Path(sys.argv[1])
codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
system_dir = codex_home / "skills/.system/imagegen"
cli = system_dir / "scripts/image_gen.py"
if cli.exists():
    print(f"Preserved existing system CLI: {cli}")
else:
    cli.parent.mkdir(parents=True, exist_ok=True)
    with cli.open("xb") as target:
        target.write((skill_dir / "vendor/imagegen/image_gen.py").read_bytes())
    license_path = system_dir / "LICENSE.txt"
    if not license_path.exists():
        with license_path.open("xb") as target:
            target.write((skill_dir / "vendor/imagegen/LICENSE.txt").read_bytes())
    print(f"Installed missing system CLI: {cli}")
PY
```

快照及 Apache 许可见 [`vendor/imagegen/`](vendor/imagegen/)。如果已有系统脚本的版本不同，保留它并报告差异；运行行为也可能随系统 CLI 版本变化。本仓库的三个原版运行文件及快照哈希记录在 `SHA256SUMS`。

## 配置要求

脚本读取 `$CODEX_HOME/config.toml`，默认是 `~/.codex/config.toml`。使用本机已有的第三方 provider 配置，支持以下鉴权来源，按顺序选择：

1. `model_providers.<provider>.auth` 命令返回的 token。
2. `env_key` 指向的环境变量。
3. `experimental_bearer_token`。

配置了前面的来源但未取得有效 token 时，不回退到后面的来源或其他官方密钥。凭据只注入图片 CLI 子进程环境，不写入技能文件。

本脚本只读取配置顶层的 `model_provider`，不自动合并 profile 或命令行覆盖。使用前必须由 Agent 确认当前会话的有效 provider；无法确认时不要生成。基础配置的 `--check` 结果不能代替会话覆盖检查。

网关还需支持 Images API，并为所用账号或分组启用图片功能。安装成功本身不证明网关权限或上游图片服务可用。

## 验证与使用

运行原有测试及哈希检查，这些操作不发送图片请求：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/test_image_gen.py" -v
```

在仓库或技能根目录执行 `shasum -a 256 -c SHA256SUMS`；Linux 环境也可以使用 `sha256sum -c SHA256SUMS`。

预检会读取本机配置，并在配置使用命令鉴权时执行该凭据命令；不会请求图片 API：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/image_gen.py" --check
```

只有 `applicable: true` 且会话 provider 核对通过后，才可以生成。安装验证可使用下面的 `--dry-run` 查看请求参数；它仍需有效的 provider 配置与凭据，但不请求图片 API：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/image_gen.py" generate \
  --prompt "A chilled Hong Kong salted lemon soda on a pale blue studio background" \
  --model gpt-image-2 --size 1024x1024 --quality medium \
  --out output/imagegen/salted-lemon-soda.png \
  --dry-run
```

用户要求实际生成时，移除 `--dry-run`。编辑示例：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/image_gen.py" edit \
  --image input.png \
  --prompt "Replace the background with pale blue; preserve the product and label" \
  --model gpt-image-2 --out output/imagegen/product-edit.png
```

真实请求地址由配置的 `base_url` 加上 `/images/generations` 或 `/images/edits` 组成；通常网关的 `base_url` 已含 `/v1`。系统 CLI 的 dry-run 文案固定展示 `/v1/images/...`，不代表它会覆盖网关地址。

结果保存在当前项目中；Agent 应查看实际图片、核对格式并展示结果。出现上游错误时保留错误并停止，不另行切换 provider 或手动重复提交。系统 CLI 和 SDK 自带的内部重试沿用其原有实现。

技能自动发现规则以本机版本为准；安装后可在新一轮对话使用 `$sub2api-imagegen`，如未显示再重启会话。[官方技能说明](https://learn.chatgpt.com/docs/build-skills)

本技能通过第三方 Images API 工作，不会注册或恢复内置 `image_gen.imagegen` 工具。

## 许可

本仓库原有 [MIT 许可](LICENSE)适用于技能自身代码与文档。`vendor/imagegen/` 中的第三方 CLI 快照沿用其 [Apache 2.0 许可](vendor/imagegen/LICENSE.txt)，来源说明见 [NOTICE.md](vendor/imagegen/NOTICE.md)。
