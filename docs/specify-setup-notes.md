# Specify CLI Setup Notes

## Project Context
- Repository root: `AUTOSR-SDSE`
- Python toolchain managed with `uv`; project environment located in `sdse-uv/` alongside `pyproject.toml`
- Specify CLI installed following `docs/spec-kit-guide.md`

## Initialization Guidance
- Create a new project directory from the parent folder: `specify init <PROJECT_NAME>`
- Reuse the current directory without creating a subfolder: `specify init --here`
- Avoid naming conflicts: `<PROJECT_NAME>` must be different from an existing folder unless `--here` is used

## Using the `sdse-uv` Environment
- From inside `sdse-uv/`, run project commands with `uv`, e.g. `uv run python -c "import sys; print(sys.executable)"`
- From other directories (such as the repo root), target the project explicitly: `uv run --project sdse-uv <command>`
- The same pattern works for Specify CLI: `uv run --project sdse-uv specify <subcommand>`

## Issues Encountered
- `codex` warns that custom prompts do not support arguments; additional project instructions must be placed directly in `.codex/prompts/` files
- `specify init` exited with `Codex CLI is required for Codex projects` because Codex CLI was not installed
- Running `uv run ...` failed with `error: path segment contains separator ':'` because the repository lived under `Survey for survey:review with LLMs`
- Creating a symlink with `ln -s` did not help; `uv` resolves the canonical path and still sees the colon
- After renaming the directory tree, existing virtual environment scripts still pointed to the old path, leading to `No such file or directory` errors when running `specify`

## Resolution
- When using Codex custom prompts, embed extra instructions inside `.codex/prompts/<prompt>.md` files because argument placeholders are not yet supported
- Install Codex CLI so the agent check passes: `brew install codex` (or `npm install -g @openai/codex`)
- Launch `codex` once and sign in with your ChatGPT Plus/Team/Enterprise account (or supply an OpenAI API key) so the CLI can authenticate
- Move/rename the repository so that no directory in the path contains `:` (current path: `/Users/xjp/Desktop/Survey-with-LLMs/Survey-for-survey-review-with-LLMs/AUTOSR-SDSE`)
- Recreate the virtual environment so its scripts reference the new location: `rm -rf sdse-uv/.venv && (cd sdse-uv && uv sync)`
- After relocating and recreating the environment, `uv run` commands succeed and pick up the `sdse-uv` environment automatically

## Handy Commands
- Verify the interpreter in use: `uv run --project sdse-uv python -c "import sys; print(sys.executable)"`
- Run Specify inside the project environment: `uv run --project sdse-uv specify <command>`
