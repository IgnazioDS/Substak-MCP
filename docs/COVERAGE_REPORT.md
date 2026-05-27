# Test Coverage Report

Last Updated: May 27, 2026

## Overall Coverage: 72%

The repository is now above the short-term 70% threshold. Coverage is still uneven: core handlers are in much better shape, while `src/server.py` remains the biggest gap.

## Current Snapshot

### Strong Coverage
| Module | Coverage |
|--------|----------|
| `src/converters/block_builder.py` | 100% |
| `src/converters/markdown_converter.py` | 95% |
| `src/handlers/auth_handler.py` | 91% |
| `src/handlers/research_handler.py` | 91% |
| `src/handlers/strategy_handler.py` | 87% |

### Moderate Coverage
| Module | Coverage |
|--------|----------|
| `src/converters/html_converter.py` | 88% |
| `src/simple_auth_manager.py` | 84% |
| `src/handlers/image_handler.py` | 77% |
| `src/handlers/post_handler.py` | 77% |
| `src/utils/api_wrapper.py` | 69% |

### Low Coverage
| Module | Coverage |
|--------|----------|
| `src/server.py` | 23% |

## What changed

- tool wrapper coverage is no longer at 0%
- `auth_handler`, `research_handler`, and strategy flows have strong branch coverage
- `post_handler` improved substantially through scheduling, preview, analytics, and content-extraction tests
- `mypy src` now checks the whole tree instead of relying on stale excludes

## Remaining priorities

1. Raise `src/server.py` coverage. It is operationally important and still lightly exercised.
2. Push `src/utils/api_wrapper.py` above 80% because it is the failure boundary for private Substack endpoints.
3. Continue increasing `src/handlers/post_handler.py` where live account behavior is safety-sensitive.
4. Keep a clear distinction between local green tests and credentialed live smoke verification.

## Important context

- Default local runs skip `requires_auth` tests when Substack credentials are absent.
- Live write-account smoke tests are opt-in through `SUBSTACK_MCP_ENABLE_WRITE_TESTS=true`.
- A green local suite does not by itself prove release-readiness for private Substack endpoints.

## Commands

```bash
python3 -m pytest -q
python3 -m pytest --cov=src --cov-report=term -q
mypy src
python3 -m pytest tests/integration/test_live_account_surface.py -m requires_auth -q
python3 -m pytest tests/integration/test_live_account_surface.py -m requires_auth_write -q
```
