# Contributing to RTLAMR Meter Reader

Thanks for your interest in contributing! This document covers the process for filing issues, submitting changes, and getting them reviewed.

## Getting Started

1. **Clone the repo** and set up your RTL-SDR dongle following the [SKILL.md](SKILL.md) guide
2. **Test the setup** with `--dry-run` before making changes
3. **Run `bash -n scripts/*.sh`** and **`python3 -m py_compile scripts/*.py`** to verify script syntax

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Include:
- Your OS, SDR dongle model, and rtlamr version
- Steps to reproduce
- Full error output (journalctl logs, rtlamr output)
- Whether the issue is reproducible

## Suggesting Features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml). Frame the request around the **problem** you're solving, not just your proposed solution.

## Pull Request Process

1. **File an issue first** — discuss the approach before implementing significant changes
2. **Branch from `master`** — use a descriptive branch name (`fix/description` or `feat/description`)
3. **One PR per logical change** — don't mix bug fixes with features
4. **Include tests** for new code where practical
5. **Update docs** — if you change behavior, update README.md and/or SKILL.md
6. **Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md)** — fill it out completely

### Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description

Longer explanation if needed.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`, `perf`

All commits must include a DCO sign-off:

```bash
git commit -s -m "fix: correct meter ID filter in bridge script"
```

The `-s` flag adds `Signed-off-by: Your Name <email>` certifying you have the right to contribute the code under the project's MIT license.

## Code Style

- Shell scripts: `bash -n` to verify syntax
- Python: Follow PEP 8. Run `python3 -m py_compile` to verify syntax
- Markdown: Keep lines under 100 characters where practical

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
