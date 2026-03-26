# Contributing to Wikifile Transfer

First off, thank you for taking the time to contribute! 🎉

Wikifile Transfer is a community-driven tool built for Wikimedia contributors worldwide. Whether you're fixing a bug, improving documentation, or proposing a new feature — every contribution matters and is deeply appreciated.

Please read this guide carefully before making your first contribution. It will help you get up and running quickly and ensure a smooth review process for everyone.

📖 **New here?** Start by reading the [README.md](README.md) to understand what the project does and how it works.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Your First Contribution](#your-first-contribution)
- [Pull Request Process](#pull-request-process)
- [Branch Naming Convention](#branch-naming-convention)
- [Commit Message Convention](#commit-message-convention)
- [Code Style & Conventions](#code-style--conventions)
- [Testing](#testing)
- [Recognition](#recognition)
- [Getting Help](#getting-help)

---

## Code of Conduct

This project follows the [Wikimedia Code of Conduct](https://www.mediawiki.org/wiki/Code_of_Conduct). By participating, you are expected to uphold this code.

In short: be respectful, be inclusive, and be constructive. Harassment or exclusionary behavior of any kind will not be tolerated.

---

## Getting Started

### 1. Fork the repository

Click the **Fork** button at the top right of the [repository page](https://github.com/indictechcom/wikifile-transfer) to create your own copy.

### 2. Clone your fork

```bash
git clone https://github.com/<your-username>/wikifile-transfer.git
cd wikifile-transfer
```

### 3. Add the upstream remote

This lets you pull in future changes from the main repo:

```bash
git remote add upstream https://github.com/indictechcom/wikifile-transfer.git
```

Verify your remotes:

```bash
git remote -v
# origin    https://github.com/<your-username>/wikifile-transfer.git (fetch)
# upstream  https://github.com/indictechcom/wikifile-transfer.git (fetch)
```

### 4. Set up the project locally

Follow the full setup guide in [README.md → Local Development](README.md#local-development). Do not skip the configuration step — the app requires a valid `config.yaml` to run.

### 5. Keep your fork up to date

Before starting any new work, always sync your fork with upstream:

```bash
git checkout master
git fetch upstream
git merge upstream/master
git push origin master
```

---

## Reporting Bugs

This project uses **two** issue trackers:

| Tracker | Use for |
|---------|---------|
| [GitHub Issues](https://github.com/indictechcom/wikifile-transfer/issues) | Code bugs, UI issues, documentation gaps |
| [Phabricator](https://phabricator.wikimedia.org/tag/indic-techcom/) | Broader tool requests, Toolforge deployment issues |

### Before reporting a bug

- Search existing [GitHub Issues](https://github.com/indictechcom/wikifile-transfer/issues) to see if it has already been reported
- Check [Phabricator](https://phabricator.wikimedia.org/tag/indic-techcom/) for known issues

### How to write a good bug report

Open a new GitHub Issue and include the following:

```
**Describe the bug**
A clear and concise description of what the bug is.

**Steps to reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Screenshots**
If applicable, add screenshots to help explain the problem.

**Environment**
- OS: [e.g. Ubuntu 22.04, Windows 11]
- Python version: [e.g. 3.11]
- Node.js version: [e.g. 18.x]
- Browser (if UI issue): [e.g. Firefox 124]

**Additional context**
Any other context about the problem (logs, error messages, etc.)
```

---

## Suggesting Features

We welcome feature suggestions! Before opening a request:

- Check if a similar idea already exists in [GitHub Issues](https://github.com/indictechcom/wikifile-transfer/issues) (look for the `enhancement` label)
- Think about whether it fits the project's core goal: transferring media files across Wikimedia projects

### Feature request template

```
**Is your feature request related to a problem?**
A clear description of what the problem is. e.g. "I find it frustrating when..."

**Describe the solution you'd like**
A clear description of the feature you want.

**Alternatives considered**
Any alternative solutions or features you've considered.

**Additional context**
Any mockups, references, or examples from other tools.
```

---

## Your First Contribution

Not sure where to start? Here are some good entry points:

- 🟢 **Documentation** — Improve the README, add inline code comments, fix typos
- 🟢 **Tests** — Add unit tests for `utils.py`, `tasks.py`, or `model.py`
- 🟡 **Bug fixes** — Pick an open issue from [GitHub Issues](https://github.com/indictechcom/wikifile-transfer/issues)
- 🟡 **UI improvements** — Frontend fixes in the `frontend/` React app

> **Tip for GSoC applicants:** Making a small, merged contribution before submitting your proposal is strongly encouraged. It shows mentors you can navigate the codebase and follow the contribution workflow.

---

## Pull Request Process

### Step 1 — Create a new branch

Never work directly on `master`. Create a feature branch from your up-to-date local master:

```bash
git checkout master
git pull upstream master
git checkout -b feat/your-feature-name
```

See [Branch Naming Convention](#branch-naming-convention) below.

### Step 2 — Make your changes

- Keep your changes focused — one PR should address one issue or feature
- Write clear, readable code with comments where necessary
- Follow the [Code Style & Conventions](#code-style--conventions) below
- Add or update tests where applicable

### Step 3 — Test your changes locally

Ensure the full app runs without errors before submitting. See [Testing](#testing) below.

### Step 4 — Commit your changes

Follow the [Commit Message Convention](#commit-message-convention) below.

```bash
git add .
git commit -m "feat: add batch upload support for multiple files"
```

### Step 5 — Push your branch

```bash
git push origin feat/your-feature-name
```

### Step 6 — Open a Pull Request

Go to your fork on GitHub and click **"Compare & pull request"**. Fill in the PR description using this template:

```
## Summary
A brief description of what this PR does.

## Related Issue
Closes #<issue-number>

## Changes Made
- List the key changes
- Keep it concise

## Screenshots (if applicable)
Add screenshots for any UI changes.

## Checklist
- [ ] I have read the CONTRIBUTING guide
- [ ] My code follows the project's code style
- [ ] I have tested my changes locally
- [ ] I have added/updated relevant tests
- [ ] I have updated documentation if needed
```

### Step 7 — Respond to review feedback

- Maintainers may request changes — please address them promptly
- Push new commits to the same branch to update the PR automatically
- Once approved, a maintainer will merge your PR

---

## Branch Naming Convention

Use a consistent prefix that describes the type of change:

| Prefix | Use for |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `test/` | Adding or updating tests |
| `refactor/` | Code refactoring (no functional change) |
| `chore/` | Build process, dependencies, tooling |

**Examples:**

```
feat/batch-upload
fix/user-agent-header
docs/contributing-guide
test/utils-unit-tests
refactor/celery-task-cleanup
```

---

## Commit Message Convention

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification. This keeps the git history readable and makes changelogs easy to generate.

### Format

```
<type>(<optional scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type | Use for |
|------|---------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `test` | Adding or updating tests |
| `refactor` | Code change that is not a fix or feature |
| `chore` | Build process, dependency updates |
| `style` | Formatting, missing semicolons (no logic change) |

### Examples

```bash
feat: add batch upload support for multiple files
fix: add missing user-agent header to MediaWiki API requests
docs: update README with troubleshooting section
test: add unit tests for utils.get_localized_wikitext
refactor: simplify Celery task error handling
chore: upgrade Flask to 2.3.x
```

> **Keep the subject line under 72 characters.** Use the body to explain *why*, not *what*.

---

## Code Style & Conventions

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes:

```python
def get_localized_wikitext(wikitext: str, lang: str) -> str:
    """
    Converts template names in wikitext to their localized equivalents.

    Args:
        wikitext: The raw wikitext string from the source page.
        lang: The target language code (e.g., 'hi', 'ta').

    Returns:
        The wikitext string with localized template names.
    """
```

- Recommended tools: `flake8` for linting, `black` for formatting

```bash
pip install flake8 black
flake8 .
black .
```

### JavaScript / React

- Follow the existing ESLint configuration in the `frontend/` directory
- Use functional components with React Hooks (no class components)
- Keep components small and single-purpose
- Use descriptive `const` names over abbreviations

### General

- Do not commit `config.yaml`, `.env`, or any file containing secrets
- Do not commit compiled files or build artifacts (`node_modules/`, `__pycache__/`, `.pyc`)
- Keep PRs small and focused — large PRs are harder to review and slower to merge

---

## Testing

Currently the project has limited test coverage — improving this is one of the goals for the project. When contributing:

### Running existing tests

```bash
# From the project root with virtualenv active
pytest
```

### Writing new tests

- Place Python tests in a `tests/` directory at the project root
- Name test files as `test_<module>.py` (e.g., `test_utils.py`)
- Use `pytest` as the testing framework
- Aim to test edge cases, not just the happy path

**Example:**

```python
# tests/test_utils.py
import pytest
from utils import get_localized_wikitext

def test_localized_wikitext_returns_string():
    result = get_localized_wikitext("{{Information}}", "hi")
    assert isinstance(result, str)

def test_localized_wikitext_empty_input():
    result = get_localized_wikitext("", "hi")
    assert result == ""
```

> PRs that include relevant tests alongside code changes are reviewed and merged faster.

---

## Recognition

All contributors are recognized via:

- The [GitHub Contributors graph](https://github.com/indictechcom/wikifile-transfer/graphs/contributors)
- Mention in release notes for significant contributions

We deeply value every contribution — from a one-line typo fix to a major feature implementation. Thank you for helping make Wikifile Transfer better for the entire Wikimedia community. 🙏

---

## Getting Help

Stuck on something? Here's where to reach out:

| Channel | Link |
|---------|------|
| GitHub Issues | [Open an issue](https://github.com/indictechcom/wikifile-transfer/issues) |
| Phabricator | [Indic TechCom tag](https://phabricator.wikimedia.org/tag/indic-techcom/) |
| Meta-Wiki Discussion | [Talk page](https://meta.wikimedia.org/wiki/Talk:Indic-TechCom/Tools/Wikifile-transfer) |
| Wikimedia IRC / Matrix | `#wikimedia-tech` on [Libera.Chat](https://libera.chat/) |

Don't hesitate to ask questions — the maintainers are friendly and happy to help new contributors get started.

---

