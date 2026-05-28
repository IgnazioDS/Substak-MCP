# Deep Audit of `substack-mcp`

Date: 2026-05-27  
Branch: `audit/complete-mcp`  
Scope: Phase 1 read-only audit of the current `/Users/ignaziodesantis/Substak-MCP` worktree

## Audit Baseline

- Git state: unborn branch / no local commits yet; repository contents are present but uncommitted.
- Python environment state: `venv/` is absent.
- Test probe:
  - `source venv/bin/activate && python3 -m pytest -q` failed because `venv/bin/activate` does not exist.
  - `python3 -m pytest -q` failed with `No module named pytest`.
- Consequence: this audit is based on source inspection plus existing test files, not a successful local test run.

## `src/` File Map

### Python entrypoints and package files

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/__init__.py` | package marker only | nothing |
| `src/server.py` | `SubstackMCPServer.run()`, `main()` | MCP SDK, `AuthHandler`, `PostHandler`, `ImageHandler`, `ResearchHandler`, `StrategyHandler`, direct `client.get_draft/delete_draft/get_sections` in some branches |
| `src/server_mcp.py` | legacy `SubstackMCPServer.run()`, `main()` | older MCP server path; eagerly authenticates, uses `AuthHandler`, `PostHandler`, `ImageHandler` |

### Auth

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/handlers/auth_handler.py` | `AuthHandler.authenticate()`, `get_headers()`, `clear_cache()` | `SimpleAuthManager`, `substack.Api`, `APIWrapper`, temp cookie-file creation |
| `src/simple_auth_manager.py` | `SimpleAuthManager.store_token()`, `store_session_cookies()`, `get_token()`, `get_session_cookies()`, `clear_token()`, `get_metadata()`, `needs_refresh()` | local encrypted file storage via `cryptography.fernet` |
| `src/auth_manager.py` | `AuthManager.store_token()`, `get_token()`, `clear_token()`, `get_metadata()`, `needs_refresh()`, `list_stored_publications()` | dead/unused keyring-backed auth path using `keyring` and `cryptography.fernet` |

### Post and image handlers

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/handlers/post_handler.py` | `create_draft()`, `update_draft()`, `publish_draft()`, `schedule_draft()`, `list_scheduled_posts()`, `list_drafts()`, `list_published()`, `get_post_analytics()`, `get_post()`, `get_post_content()`, `duplicate_post()`, `get_sections()`, `get_subscriber_count()`, `preview_draft()` | `MarkdownConverter`, `HTMLConverter`, `BlockBuilder`, `substack.post.Post`, `APIWrapper`/client methods such as `get_draft`, `get_drafts`, `post_draft`, `put_draft`, `publish_draft`, `schedule_draft`, `get_post_management`, `get_sections`, `get_publication_subscriber_stats`, `prepublish_draft` |
| `src/handlers/image_handler.py` | `upload_image()`, `get_optimized_url()`, `batch_upload()` | `client.get_image()`, local filesystem, `aiohttp` for URL download helper code |

### Research and strategy

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/handlers/research_handler.py` | `sanitize_text_for_topics()`, `extract_meaningful_tokens()`, `ResearchHandler.research_substack()`, `inspect_url()` | public web via `aiohttp.ClientSession.get()`, `BeautifulSoup`, heuristic parsing |
| `src/handlers/strategy_handler.py` | `analyze_post_collection()`, `research_post_url()`, `research_publication_url()`, `generate_post_ideas()`, `repurpose_post()`, `content_gap_analysis()`, `optimize_title_and_hook()`, `series_plan()`, `study_topic_on_substack()`, `extract_coding_lessons()` | `ResearchHandler.inspect_url()` and in-memory heuristics only |
| `src/handlers/__init__.py` | package marker only | nothing |

### API wrapper

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/utils/api_wrapper.py` | `SubstackAPIError`, `APIWrapper.get_user_id()`, `get_draft()`, `get_drafts()`, `get_post_management()`, `post_draft()`, `put_draft()`, `publish_draft()`, `schedule_draft()`, `unschedule_draft()`, `delete_draft()`, `prepublish_draft()`, `get_sections()`, `get_publication_subscriber_count()`, `get_publication_subscriber_stats()`, `get_image()` | python-substack methods plus raw `client._session.get/post/delete` calls to private/HTML endpoints |
| `src/utils/__init__.py` | package marker only | nothing |

### Converters

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/converters/block_builder.py` | `BlockBuilder.paragraph()`, `header()`, `unordered_list()`, `ordered_list()`, `code_block()`, `blockquote()`, `image()`, `link()`, `horizontal_rule()`, `paywall()`, `text()` | pure block construction |
| `src/converters/markdown_converter.py` | `MarkdownConverter.convert()` | `BlockBuilder`; regex-based markdown parsing |
| `src/converters/html_converter.py` | `HTMLConverter.convert()` | `BeautifulSoup`, `BlockBuilder` |
| `src/converters/__init__.py` | package marker only | nothing |

### Tool modules

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/tools/create_formatted_post.py` | `CreateFormattedPostTool.execute()` | `server.post_handler.create_draft()` |
| `src/tools/update_post.py` | `UpdatePostTool.execute()` | `server.post_handler.update_draft()` |
| `src/tools/publish_post.py` | `PublishPostTool.execute()` | `server.post_handler.publish_draft()` |
| `src/tools/list_drafts.py` | `ListDraftsTool.execute()` | `server.post_handler.list_drafts()` |
| `src/tools/upload_image_tool.py` | `UploadImageTool.execute()` | `ImageHandler.upload_image()`, `ImageHandler.get_optimized_url()` |
| `src/tools/debug_post_structure.py` | `debug_post_structure()` | direct `post_handler.client.get_draft()` |
| `src/tools/__init__.py` | package marker only | nothing |

### Node wrapper files

| File | Public surface | What it calls into |
| --- | --- | --- |
| `src/index.js` | CLI binary entrypoint | selects a Python executable, spawns `python -m src.server`, bridges stdio |
| `src/setup.js` | setup CLI entrypoint | spawns `setup_auth.py` via `venv/bin/python` only |

## Substack Call Inventory

### A. Official-ish `python-substack` method calls

| Local call site | Wrapper/client method | Exposed by tools |
| --- | --- | --- |
| `APIWrapper.get_user_id()` | `client.get_user_id()` | indirectly `create_formatted_post`, `update_post`, `duplicate_post` |
| `APIWrapper.get_draft()` | `client.get_draft(post_id)` | `update_post`, `schedule_post`, `delete_draft`, `get_post_content`, `duplicate_post`, `preview_draft`, `repurpose_post`, `title_and_hook_optimizer`, plus account-post collection helpers |
| `APIWrapper.get_drafts()` | `client.get_drafts(limit=...)` | `list_drafts`, fallback path of `list_scheduled_posts`, fallback path of `list_published`, strategy tools that read drafts |
| `APIWrapper.post_draft()` | `client.post_draft(draft_data)` | `create_formatted_post`, `duplicate_post` |
| `APIWrapper.put_draft()` | `client.put_draft(post_id, **kwargs)` | `update_post` |
| `APIWrapper.publish_draft()` | `client.publish_draft(post_id)` | `publish_post` |
| `APIWrapper.delete_draft()` | `client.delete_draft(post_id)` | wrapper exists, but `src/server.py` actually bypasses it and calls `client.delete_draft(post_id)` directly in `delete_draft` |
| `APIWrapper.prepublish_draft()` | `client.prepublish_draft(post_id)` | `preview_draft` |
| `APIWrapper.get_sections()` | `client.get_sections()` | `get_sections`, fallback path of `get_subscriber_count` |
| `APIWrapper.get_publication_subscriber_count()` / `get_publication_subscriber_stats()` | `client.get_publication_subscriber_count()` | `get_subscriber_count` |
| `APIWrapper.get_image()` / `ImageHandler.upload_image()` | `client.get_image(source)` | `upload_image` |

### B. Raw `client._session.{get,post,delete}` calls to private or undocumented endpoints

| Local method | HTTP | URL template | Params / payload shape | Observed response shape in code/tests | Exposed by tools |
| --- | --- | --- | --- | --- | --- |
| `APIWrapper.get_post_management()` | `GET` | `{publication_url}/api/v1/post_management/{view}` | query params: `offset`, `limit`, optional `order_by`, `order_direction`, `query` | dict with `posts: []`, `total`; used as management feed | `list_scheduled_posts`, `list_published`, `get_post_analytics`, `analyze_my_posts`, `generate_post_ideas`, `content_gap_analysis` via published-post collection |
| `APIWrapper.schedule_draft()` | `POST` | `{publication_url}/drafts/{post_id}/scheduled_release` | JSON body: `trigger_at`, `post_audience`, `email_audience` | either empty-body 200 handled as synthetic `postSchedules`, or JSON body | `schedule_post` |
| `APIWrapper.unschedule_draft()` | `DELETE` | `{publication_url}/drafts/{post_id}/scheduled_release` | none | JSON list or dict normalized to list | not exposed by any tool |
| `APIWrapper._get_subscriber_count_from_publication_page()` | `GET` | `{publication_url}` | none | HTML page parsed for subscriber counts | `get_subscriber_count` fallback |

## MCP Tool Dependency Graph

`src/server.py` currently declares 26 tools in `handle_list_tools()`. `handle_call_tool()` has 26 public branches plus one extra dead `debug_post_structure` branch.

| MCP tool | Server handler path | Handler/helper method(s) | Wrapper method(s) | Underlying Substack/web call |
| --- | --- | --- | --- | --- |
| `create_formatted_post` | `handle_call_tool -> create_formatted_post` | `PostHandler.create_draft()` | `APIWrapper.get_user_id()`, `APIWrapper.post_draft()` | `client.get_user_id()`, `client.post_draft()` |
| `update_post` | `handle_call_tool -> update_post` | `PostHandler.update_draft()` | `APIWrapper.get_draft()`, `APIWrapper.get_user_id()`, `APIWrapper.put_draft()` | `client.get_draft()`, `client.get_user_id()`, `client.put_draft()` |
| `publish_post` | `handle_call_tool -> publish_post` | `PostHandler.publish_draft()` | `APIWrapper.publish_draft()` | `client.publish_draft()` |
| `schedule_post` | `handle_call_tool -> schedule_post` | `PostHandler.schedule_draft()` | `APIWrapper.get_draft()`, `APIWrapper.schedule_draft()` | `client.get_draft()`, raw `POST {publication_url}/drafts/{post_id}/scheduled_release` |
| `list_drafts` | `handle_call_tool -> list_drafts` | `PostHandler.list_drafts()` | `APIWrapper.get_drafts()` | `client.get_drafts(limit=...)` |
| `list_scheduled_posts` | `handle_call_tool -> list_scheduled_posts` | `PostHandler.list_scheduled_posts()` | `APIWrapper.get_post_management()` or `APIWrapper.get_drafts()` fallback | raw `GET {publication_url}/api/v1/post_management/scheduled` or `client.get_drafts()` |
| `upload_image` | `handle_call_tool -> upload_image` | `ImageHandler.upload_image()` | `APIWrapper.get_image()` if client is wrapped; otherwise direct client | `client.get_image(path_or_url)` |
| `delete_draft` | `handle_call_tool -> delete_draft` | inline server logic only | none in current path | direct `client.get_draft()`, direct `client.delete_draft()` |
| `list_published` | `handle_call_tool -> list_published` | `PostHandler.list_published()` | `APIWrapper.get_post_management()` or `APIWrapper.get_drafts()` fallback | raw `GET {publication_url}/api/v1/post_management/published` or `client.get_drafts()` filter |
| `get_post_analytics` | `handle_call_tool -> get_post_analytics` | `PostHandler.get_post_analytics()` | `APIWrapper.get_post_management()` | raw `GET {publication_url}/api/v1/post_management/published` |
| `get_post_content` | `handle_call_tool -> get_post_content` | `PostHandler.get_post_content()` | `APIWrapper.get_draft()` | `client.get_draft(post_id)` |
| `duplicate_post` | `handle_call_tool -> duplicate_post` | `PostHandler.duplicate_post()` | `APIWrapper.get_draft()`, `APIWrapper.get_user_id()`, `APIWrapper.post_draft()` | `client.get_draft()`, `client.get_user_id()`, `client.post_draft()` |
| `get_sections` | `handle_call_tool -> get_sections` | `PostHandler.get_sections()` | `APIWrapper.get_sections()` | `client.get_sections()` |
| `get_subscriber_count` | `handle_call_tool -> get_subscriber_count` | `PostHandler.get_subscriber_count()` | `APIWrapper.get_publication_subscriber_stats()` | `client.get_publication_subscriber_count()`, fallback `GET {publication_url}`, fallback `client.get_sections()` |
| `preview_draft` | `handle_call_tool -> preview_draft` | `PostHandler.preview_draft()` | `APIWrapper.get_draft()`, `APIWrapper.prepublish_draft()` | `client.get_draft()`, `client.prepublish_draft()` |
| `research_substack` | `handle_call_tool -> research_substack` | `ResearchHandler.research_substack()` | n/a | public web `GET` to Substack search, DuckDuckGo HTML, Bing HTML, then public page fetches |
| `analyze_my_posts` | `handle_call_tool -> analyze_my_posts` | `collect_account_posts()`, `PostHandler.list_published()/list_drafts()/get_post_content()`, `StrategyHandler.analyze_post_collection()` | `APIWrapper.get_post_management()` / `APIWrapper.get_drafts()` / `APIWrapper.get_draft()` | raw post-management feed or `client.get_drafts()` and `client.get_draft()` |
| `research_substack_post` | `handle_call_tool -> research_substack_post` | `StrategyHandler.research_post_url()` -> `ResearchHandler.inspect_url()` | n/a | public page fetch only |
| `research_substack_publication` | `handle_call_tool -> research_substack_publication` | `StrategyHandler.research_publication_url()` -> `ResearchHandler.inspect_url()` | n/a | public page fetch only |
| `generate_post_ideas` | `handle_call_tool -> generate_post_ideas` | optional `collect_account_posts()`, `StrategyHandler.analyze_post_collection()`, `ResearchHandler.research_substack()`, `StrategyHandler.generate_post_ideas()` | optional `APIWrapper.get_post_management()` / `get_drafts()` / `get_draft()` | account feed lookups plus public search/page fetches |
| `repurpose_post` | `handle_call_tool -> repurpose_post` | optional `PostHandler.get_post_content()`, `StrategyHandler.repurpose_post()` | optional `APIWrapper.get_draft()` | `client.get_draft()` when `post_id` is supplied |
| `content_gap_analysis` | `handle_call_tool -> content_gap_analysis` | `collect_account_posts()`, `StrategyHandler.analyze_post_collection()`, `ResearchHandler.research_substack()`, `StrategyHandler.content_gap_analysis()` | `APIWrapper.get_post_management()` / `get_drafts()` / `get_draft()` | account feed lookups plus public search/page fetches |
| `title_and_hook_optimizer` | `handle_call_tool -> title_and_hook_optimizer` | optional `PostHandler.get_post_content()`, `StrategyHandler.optimize_title_and_hook()` | optional `APIWrapper.get_draft()` | `client.get_draft()` when `post_id` is supplied |
| `series_planner` | `handle_call_tool -> series_planner` | `StrategyHandler.series_plan()` | n/a | no Substack call |
| `study_topic_on_substack` | `handle_call_tool -> study_topic_on_substack` | `ResearchHandler.research_substack()`, `StrategyHandler.study_topic_on_substack()` | n/a | public web fetches only |
| `extract_coding_lessons` | `handle_call_tool -> extract_coding_lessons` | optional `StrategyHandler.research_post_url()` or `ResearchHandler.research_substack()`, then `StrategyHandler.extract_coding_lessons()` | n/a | public page fetches only |

## Confirmed Bug List

Severity scale:

- `P0`: blocking / data-loss / trust boundary bug
- `P1`: correctness / contract drift / likely runtime bug
- `P2`: polish / stale docs / dead code / maintainability

### Seeded issues from the prompt

| Severity | Issue | Evidence |
| --- | --- | --- |
| `P1` | Startup log says `Registered 23 tools`, but `handle_list_tools()` declares 26 tools. | `src/server.py:69-538` declares 26 `Tool(...)` entries; `src/server.py:1650` logs `Registered 23 tools`. |
| `P1` | `server_version="1.0.3"` disagrees with package manifests at `1.0.5`. | `src/server.py:1662`; `package.json:3`; `pyproject.toml:7`. |
| `P1` | `debug_post_structure` is callable in dispatch but never declared in `list_tools()`. | Dispatch branch at `src/server.py:1406`; no matching `Tool(name="debug_post_structure")`; dead helper exists at `src/tools/debug_post_structure.py`. |
| `P0` | `_create_cookie_client()` deletes the temp cookie file in `finally` immediately after constructing the cached client, so any later lazy re-read by `python-substack` will break. | `src/handlers/auth_handler.py:224-257`, especially `os.unlink(cookies_path)` in `finally`. |
| `P1` | `APIWrapper._handle_response()` only understands string errors and dicts with singular `error`; it does not handle `errors`, `message` + failure status, or Response-like objects with `status_code >= 400`. | `src/utils/api_wrapper.py:32-81`. |
| `P2` | Prompt seed is not exactly reproducible as written: `keyring` is imported in `src/auth_manager.py`, but that module is dead in the live runtime. The real issue is stale dependency + dead auth path. | `src/auth_manager.py:10` imports `keyring`; active runtime imports `SimpleAuthManager` from `src/handlers/auth_handler.py:15,47`. |
| `P2` | `engines.python` in `package.json` is not an npm-enforced field. | `package.json:61-63`. |
| `P2` | `prepublishOnly` and `format` scripts are no-op `echo` commands. | `package.json:15` and `package.json:18`. |
| `P1` | `_normalize_future_timestamp()` rejects slightly stale but otherwise valid future-intent timestamps; zero skew tolerance. | `src/handlers/post_handler.py:363-381`. |
| `P0` | `delete_draft` is fully wired and executes on first call if `confirm_delete=true` is provided; the safeguard is description text only. | Tool schema warns at `src/server.py:221-236`, but execution path at `src/server.py:1123-1169` performs deletion immediately when boolean is true. |
| `P1` | `APIWrapper.get_post_management()` and `schedule_draft()/unschedule_draft()` hit undocumented private endpoints with no version pinning, no capability probe, and no documentation file. | `src/utils/api_wrapper.py:186-210`, `248-289`; nothing yet in `docs/REVERSE_ENGINEERED_ENDPOINTS.md`. |

### Additional issues found during audit

| Severity | Issue | Evidence |
| --- | --- | --- |
| `P1` | The current tool surface is internally inconsistent: `handle_list_tools()` has 26 names, dispatch has 26 public names + dead `debug_post_structure`, and there is no startup assertion to detect drift. | `src/server.py:69-538`, `src/server.py:604-1621`. |
| `P1` | `schedule_post` accepts arbitrary `post_audience` / `email_audience` strings; validation is missing in both server and handler. | `src/server.py:159-168`, `src/server.py:1050-1051`, `src/handlers/post_handler.py:279-300`. |
| `P1` | `list_scheduled_posts()` maps both `post_audience` and `email_audience` from the same `post.get("audience")` field when using management rows. | `src/handlers/post_handler.py:320-329`. |
| `P1` | `preview_draft` advertises shareable draft links, but fallback behavior returns author-only `/publish/post/{id}` URLs when no preview token is available. | Tool description `src/server.py:315-327`; fallback URL construction `src/handlers/post_handler.py:875-917`. |
| `P1` | `research_substack*` tools do not check `robots.txt` and do not rate-limit per host. | `src/handlers/research_handler.py:190-235` uses only raw `aiohttp.ClientSession` with a browser UA. |
| `P2` | Research tool User-Agent is a generic browser string, not a transparent project identifier. | `src/handlers/research_handler.py:172-175`. |
| `P2` | `extract_coding_lessons` is heuristic summarization, not true lesson extraction from structured coding signals. | `src/handlers/strategy_handler.py:288-302`. |
| `P2` | `src/server_mcp.py` is stale alternate entrypoint with eager auth, a 5-tool surface, and its own version drift (`1.0.0`). | `src/server_mcp.py:22-249`. |
| `P2` | `src/setup.js` hardcodes `venv/bin/python`; setup will fail when the venv is absent even if a valid global Python exists. | `src/setup.js:10-30`. |

## Tool Coverage Matrix

This matrix is conservative: “covered” means there is at least one test file that exercises the tool directly or its primary handler path. Pure string-message tests are listed, but they should not be mistaken for end-to-end tool coverage.

| Tool in `src/server.py` | Current tests touching it | Status |
| --- | --- | --- |
| `create_formatted_post` | `tests/test_confirmation_simple.py`, `tests/integration/test_post_creation_flow.py`, `tests/integration/test_claude_desktop_integration.py` | partial |
| `update_post` | `tests/test_confirmation_simple.py`, `tests/integration/test_update_posts.py`, `tests/integration/test_claude_desktop_integration.py` | partial |
| `publish_post` | `tests/test_confirmation_simple.py`, `tests/integration/test_claude_desktop_integration.py` | partial |
| `schedule_post` | `tests/test_scheduling_tools.py` | partial |
| `list_drafts` | `tests/unit/test_post_handler.py`, `tests/test_post_handler_validation.py`, `tests/integration/test_post_creation_flow.py`, `tests/integration/test_draft_deletion.py` | partial |
| `list_scheduled_posts` | `tests/test_scheduling_tools.py` | partial |
| `upload_image` | `tests/unit/test_upload_image_tool.py`, `tests/unit/test_image_handler.py`, several integration tests under `tests/integration/` | partial |
| `delete_draft` | `tests/integration/test_draft_deletion.py`, `tests/integration/test_error_handling.py`, `tests/integration/test_edge_cases.py` | partial |
| `list_published` | `tests/test_post_handler_validation.py` | partial |
| `get_post_analytics` | `tests/test_scheduling_tools.py` | partial |
| `get_post_content` | `tests/test_new_tools.py` | covered at handler level |
| `duplicate_post` | `tests/test_new_tools.py`, `tests/test_confirmation_simple.py` | covered at handler level, weak at server level |
| `get_sections` | `tests/test_new_tools.py`, `tests/test_api_wrapper_subscriber_count.py` | covered at handler/wrapper level |
| `get_subscriber_count` | `tests/test_new_tools.py`, `tests/test_api_wrapper_subscriber_count.py` | covered at handler/wrapper level |
| `preview_draft` | `tests/test_new_tools.py` | covered at handler level |
| `research_substack` | `tests/test_research_handler.py` | covered at handler level only |
| `analyze_my_posts` | none | `MISSING` |
| `research_substack_post` | no direct tool test; only underlying research/strategy helpers | `MISSING` |
| `research_substack_publication` | no direct tool test; only underlying research/strategy helpers | `MISSING` |
| `generate_post_ideas` | none | `MISSING` |
| `repurpose_post` | none | `MISSING` |
| `content_gap_analysis` | none | `MISSING` |
| `title_and_hook_optimizer` | none | `MISSING` |
| `series_planner` | none | `MISSING` |
| `study_topic_on_substack` | `tests/test_strategy_handler.py` | partial |
| `extract_coding_lessons` | none | `MISSING` |

## Definition of Done for Phase 2

### Correctness and safety

- Replace the hard-coded tool count log with a derived count.
- Add a startup invariant: `list_tools()` names must exactly match `call_tool` names.
- Unify versioning so Node package, Python package, and MCP `server_version` come from one source.
- Remove or properly gate `debug_post_structure`; no dead dispatch-only tools.
- Keep cookie tempfiles alive for the lifetime of the cached client and clean them on cache clear/process exit.
- Harden `_handle_response()` for `error`, `errors`, `message`+status, `None`, string errors, generators, and Response-like 4xx/5xx objects.
- Add skew tolerance and precise error modes to `_normalize_future_timestamp()`.
- Validate `post_audience` and `email_audience` against `everyone`, `only_paid`, `only_free`.
- Enforce two-call confirmation tokens server-side for create/update/publish/schedule/duplicate/delete.
- Make `delete_draft` impossible to execute on a first blind `confirm_delete=true` call.

### Dependency and packaging hygiene

- Remove the dead keyring dependency path from runtime and packaging, or prove it is still intentionally supported.
- Remove `engines.python` from `package.json`.
- Replace no-op `format` and `prepublishOnly` scripts with real checks.
- Pin `python-substack` to a tested range and document why the upper bound exists.

### Feature-contract cleanup

- Either implement shareable preview tokens or explicitly downgrade `preview_draft` to author-only preview behavior.
- Add explicit MIME sniffing and 25 MB rejection to `upload_image`; verify both local-path and URL flows.
- Add the fourth subscriber-count fallback source or explicitly document the three-source limit.
- Verify and fix scheduled audience field mapping against a recorded scheduled row fixture.
- Add transparent research User-Agent, robots handling, and 1 req/sec host pacing.
- Rename or relabel `extract_coding_lessons` if it remains heuristic.
- Create `docs/REVERSE_ENGINEERED_ENDPOINTS.md` and document every private endpoint actually used.

### Tests

- Add unit coverage for every `APIWrapper` method, including abnormal return shapes.
- Add unit coverage for `SimpleAuthManager` failure paths and encrypted cookie storage behavior.
- Add unit coverage for `_normalize_future_timestamp()` edge cases.
- Add unit coverage for the confirmation-token flow.
- Add a smoke test for `src.server` tool discovery vs dispatch set equality.
- Add contract tests with recorded fixtures for every `python-substack` response shape consumed by `PostHandler`.
- Fill the current tool-test gaps: `analyze_my_posts`, `research_substack_post`, `research_substack_publication`, `generate_post_ideas`, `repurpose_post`, `content_gap_analysis`, `title_and_hook_optimizer`, `series_planner`, `extract_coding_lessons`.

