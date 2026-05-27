# Live Smoke Testing

This document describes the live-account checks used for release-readiness audits.

## Why this exists

Most of the repository test suite is safe to run without touching a real Substack account. That is good for local development, but it means account-bound behavior still needs an explicit live smoke pass before calling a release ready.

## Prerequisites

Set one of these auth flows:

```bash
export SUBSTACK_PUBLICATION_URL="https://yourpublication.substack.com"
export SUBSTACK_SESSION_TOKEN="..."
```

or:

```bash
export SUBSTACK_PUBLICATION_URL="https://yourpublication.substack.com"
export SUBSTACK_EMAIL="you@example.com"
export SUBSTACK_PASSWORD="..."
```

## Read-only smoke suite

This suite authenticates and exercises safe account reads only:

```bash
python3 -m pytest tests/integration/test_live_account_surface.py -m requires_auth -q
```

It covers:
- authentication
- `list_drafts`
- `list_published`
- `get_sections`
- `get_subscriber_count`

## Opt-in write smoke suite

Write tests are intentionally disabled unless you opt in.

```bash
export SUBSTACK_MCP_ENABLE_WRITE_TESTS=true
python3 -m pytest tests/integration/test_live_account_surface.py -m requires_auth_write -q
```

The write smoke creates a disposable draft, verifies preview generation, reads it back, and deletes it in cleanup.

## Release recommendation

Before shipping changes that affect account tools, run:

```bash
python3 -m pytest -q
python3 -m pytest tests/integration/test_live_account_surface.py -m requires_auth -q
python3 -m pytest tests/integration/test_live_account_surface.py -m requires_auth_write -q
python3 -m pytest --cov=src --cov-report=term -q
mypy src
```

If live credentials are unavailable, the repository can still be locally healthy, but the authenticated surface should not be described as fully release-verified.
