# Contributing to AWS Integration

Thank you for your interest in contributing to AWS Integration! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Style](#code-style)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create a branch** for your changes
4. **Make your changes** with tests
5. **Submit a pull request**

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- MariaDB 10.6+
- Redis 6+
- A working [Frappe Bench](https://frappeframework.com/docs/user/en/installation) setup

### Setting Up the Development Environment

```bash
# Clone your fork into the bench apps directory
cd $BENCH_PATH
bench get-app https://github.com/<your-username>/aws_integration.git --branch main

# Install the app on your development site
bench --site <your-site> install-app aws_integration

# Run migrations
bench --site <your-site> migrate

# Build frontend assets
bench build --app aws_integration

# Install pre-commit hooks
cd apps/aws_integration
pip install pre-commit
pre-commit install
```

### Running the Development Server

```bash
bench start
```

### Running Tests

```bash
# Run all tests for the app
bench --site <your-site> run-tests --app aws_integration

# Run tests for a specific DocType
bench --site <your-site> run-tests --doctype "AWS Settings"

# Run a specific test file
bench --site <your-site> run-tests --module aws_integration.aws_integration.doctype.aws_settings.test_aws_settings
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feat/s3-multipart-upload` — New features
- `fix/presigned-url-expiry` — Bug fixes
- `docs/setup-guide` — Documentation
- `refactor/client-error-handling` — Code refactoring

### What to Work On

- Check the [open issues](https://github.com/UnityAppSuite/aws_integration/issues) for things to work on
- Issues labeled `good first issue` are great starting points
- If you want to work on something not listed, open an issue first to discuss

### Tips

- Keep changes focused — one feature or fix per PR
- Write tests for new functionality
- Update documentation if you change behavior
- Test with both public and private files when modifying S3 logic
- Test with `delete_local_after_upload` both enabled and disabled

## Code Style

This project uses automated formatting and linting via [pre-commit](https://pre-commit.com/). The hooks run automatically on every commit.

### Python

- **Formatter**: [Ruff](https://docs.astral.sh/ruff/) (format)
- **Linter**: [Ruff](https://docs.astral.sh/ruff/) (lint)
- **Line length**: 110 characters
- **Target**: Python 3.10+
- **Style**: Tabs for indentation (Frappe convention)

### JavaScript

- **Formatter**: [Prettier](https://prettier.io/)
- **Linter**: [ESLint](https://eslint.org/)
- **Style**: Tabs for indentation (Frappe convention)

### General Guidelines

- Follow existing patterns in the codebase
- Use `frappe.db.set_value()` with `update_modified=False` for internal state updates
- Use `frappe.log_error()` for error logging, not `print()`
- Use parameterized queries — never use f-strings in SQL
- Use `frappe.cache.set_value()` / `get_value()` for Redis — not raw Redis methods
- Always commit before deleting local files (crash safety pattern)
- Use row-level locks (`SELECT ... FOR UPDATE`) when updating shared File records

### Running Linters Manually

```bash
cd apps/aws_integration

# Run all pre-commit hooks
pre-commit run --all-files

# Run only ruff
ruff check .
ruff format .

# Run only eslint
npx eslint aws_integration/public/js/
```

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `chore` | Build process, dependencies, or tooling |

### Examples

```
feat: add multipart upload for files larger than 5 MB
fix: prevent double URL-encoding in S3 attachment links
docs: add architecture diagram to README
refactor: extract S3 key generation into dedicated method
```

## Pull Request Process

### Before Submitting

1. **Rebase** your branch on the latest `main`
2. **Run linters**: `pre-commit run --all-files`
3. **Run tests**: `bench --site <site> run-tests --app aws_integration`
4. **Test manually** in a browser — verify the feature works end-to-end
5. **Update documentation** if you changed behavior

### PR Guidelines

- Fill out the PR template completely
- Link related issues using `Fixes #123` or `Closes #123`
- Keep the diff small and focused — large PRs are hard to review
- Add screenshots for UI changes
- Respond to review feedback promptly

### Review Process

1. A maintainer will review your PR
2. They may request changes — this is normal and expected
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release

## Reporting Issues

### Bug Reports

When reporting a bug, include:

- **Frappe version** and **Python version**
- **Steps to reproduce** the issue
- **Expected behavior** vs. **actual behavior**
- **Error logs** (from browser console or `bench --site <site> console`)
- **Screenshots** if applicable

### Feature Requests

When requesting a feature:

- Describe the **problem** you're trying to solve
- Explain your **proposed solution**
- Consider if there are **alternative approaches**
- Note if you're willing to **implement it yourself**

---

Thank you for contributing!
