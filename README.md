# Substack MCP

An MCP server for Substack that lets AI clients work with your publication and research public Substack content.

It supports:
- authenticated account tools for drafts, publishing, scheduling, previews, sections, and post analytics
- limited documented integration tools for RSS feeds, embeds, and profile lookup
- public research tools for finding, analyzing, and studying Substack posts and publications
- content strategy tools for ideas, hooks, repurposing, gap analysis, and series planning

The account side is the primary supported surface. Research and strategy tools are intentionally heuristic and public-web-limited.

This project is unofficial and is not affiliated with Substack Inc.

## What You Can Do

With your own Substack account:
- create formatted drafts
- update drafts
- publish immediately
- schedule future posts
- list drafts, published posts, and scheduled posts
- preview drafts
- upload images
- inspect sections
- read post content
- get post analytics

With public Substack content:
- fetch a publication's RSS feed
- inspect the limited documented Substack integration options for a publication, post, or note
- look up public Substack profiles by LinkedIn handle through Substack's narrow help-documented Developer API
- research a topic across Substack
- analyze a public post URL
- analyze a publication URL
- create a study plan around a topic
- heuristically summarize coding lessons from public posts

For strategy:
- analyze your own posts
- generate post ideas
- repurpose posts into other formats
- run content gap analysis
- improve titles and hooks
- plan a series

## Requirements

- `Node.js >= 16`
- `Python >= 3.10`
- a Substack publication URL such as `https://yourpublication.substack.com`

## Install

Install globally with npm:

```bash
npm install -g github:IgnazioDS/Substak-MCP
```

This installs two commands:

```bash
substack-mcp-plus
substack-mcp-plus-setup
```

### Migrating From the Old Package

If you previously installed another package variant, remove it before
installing from this repository:

```bash
npm uninstall -g substack-mcp-plus
npm install -g github:IgnazioDS/Substak-MCP
substack-mcp-plus-setup
```

After reinstalling, fully restart your MCP client so it reloads the command.

## First-Time Setup

Run the setup wizard:

```bash
substack-mcp-plus-setup
```

The setup flow will:
- open a browser
- let you sign in to Substack
- handle CAPTCHA/manual login flow
- store an encrypted browser session locally for later use

The local auth file lives at `~/.substack-mcp-plus/auth.json`. The setup stores
the browser session cookie jar after login, not your Substack password.

If Substack sends an email sign-in link, open or paste that link in the same
browser window opened by `substack-mcp-plus-setup`. That same-browser step is
what lets the setup capture the final authenticated session.

If your client later says authentication failed, run the setup again.

## MCP Client Config

Use this server in any MCP client that supports a stdio server definition.

Server block:

```json
{
  "mcpServers": {
    "substack-mcp-plus": {
      "command": "substack-mcp-plus",
      "env": {
        "SUBSTACK_PUBLICATION_URL": "https://YOUR_PUBLICATION.substack.com",
        "SUBSTACK_DEVELOPER_API_TOKEN": "optional-developer-api-token"
      }
    }
  }
}
```

If your GUI client does not inherit your shell `PATH`, use an absolute path instead:

```bash
which substack-mcp-plus
```

Then replace `"substack-mcp-plus"` with the full path to the binary.

### Client Notes

- Claude Desktop
  Config file locations:
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`
  - Linux: `~/.config/Claude/claude_desktop_config.json`
- Claude Code
  Add the same `mcpServers.substack-mcp-plus` block to `~/.claude.json`.
- Codex
  Add this to `~/.codex/config.toml`:

  ```toml
  [mcp_servers.substack-mcp-plus]
  command = "substack-mcp-plus"

  [mcp_servers.substack-mcp-plus.env]
  SUBSTACK_PUBLICATION_URL = "https://YOUR_PUBLICATION.substack.com"
  SUBSTACK_DEVELOPER_API_TOKEN = "optional-developer-api-token"
  ```
- Cursor
  Add the same server block anywhere Cursor expects MCP server JSON.
- Antigravity
  Add the same server block anywhere Antigravity expects MCP server JSON.
- Windsurf
  Add the same server block anywhere Windsurf expects MCP server JSON.
- Generic MCP client
  Use the same stdio definition if the client supports `command` + `env`.

After updating the config, fully restart the client.

## Tool List

### Publishing and Account Tools

- `create_formatted_post`
- `update_post`
- `publish_post`
- `schedule_post`
- `list_drafts`
- `list_published`
- `list_scheduled_posts`
- `get_post_content`
- `get_post_analytics`
- `duplicate_post`
- `preview_draft`
- `upload_image`
- `delete_draft`
- `get_sections`
- `get_subscriber_count`

### Developer and Public Research Tools

- `get_publication_rss_feed`
- `get_substack_integration_options`
- `search_substack_profiles_by_linkedin`
- `research_substack`
- `research_substack_post`
- `research_substack_publication`
- `study_topic_on_substack`
- `extract_coding_lessons`

### Strategy Tools

- `analyze_my_posts`
- `generate_post_ideas`
- `repurpose_post`
- `content_gap_analysis`
- `title_and_hook_optimizer`
- `series_planner`

## Example Prompts

### Account Workflows

- `List my latest drafts`
- `Show me my scheduled posts`
- `Get the content of draft 123456`
- `Create a draft titled "Why SwiftUI image caching matters" with markdown content`
- `Schedule draft 123456 for 2026-03-12T09:00:00Z`
- `Show analytics for published post 123456`

### Research Workflows

- `Fetch the RSS feed for https://example.substack.com`
- `What documented integration options does https://example.substack.com support?`
- `Search Substack profiles for LinkedIn handle johndoe`
- `Research Substack for swiftui image caching`
- `Research this Substack post: https://www.oneusefulthing.org/p/change-blindness`
- `Research this publication: https://oneusefulthing.substack.com`
- `Study SwiftUI performance on Substack`
- `Extract coding lessons from https://example.substack.com/p/some-post`

### Strategy Workflows

- `Analyze my posts`
- `Generate post ideas for indie iOS app marketing`
- `Repurpose my latest draft into a Twitter thread`
- `Improve the title and hook for post 123456`
- `Plan a 5-part series on Swift concurrency`

## Notes About Confirmation

High-risk write actions are protected by a server-side confirmation token flow, not just description text.

- First call: request a preview without `confirm_*`.
- Server response: preview text plus `confirmation_token`.
- Second call: resend the same arguments with `confirm_*=true` and `confirmation_token=<token>`.

Protected tools:

- `create_formatted_post`
- `update_post`
- `publish_post`
- `schedule_post`
- `duplicate_post`
- `delete_draft`

## Known Limitations

These are the current honest limits, not marketing wallpaper:

- `schedule_post` is implemented through a reverse-engineered private endpoint and should be treated as best-effort until it has been smoke-tested against your publication.
- `get_subscriber_count` may return an unavailable state if Substack does not expose a reliable count through publication metadata, page markup, or section data.
- `preview_draft` may return an author-only `/publish/post/...` URL when Substack does not expose a shareable preview token.
- `upload_image` accepts local paths and direct image URLs, but rejects unsupported image content and files larger than 25 MB.
- Public research works best on focused queries such as `swiftui image caching` or `ios concurrency` rather than very broad topics.
- Broad-topic discovery can still have lower recall than niche queries.
- `study_topic_on_substack` and `extract_coding_lessons(query=...)` depend on the quality of the underlying discovery results.
- `extract_coding_lessons` is heuristic summarization, not a structured extractor.
- Public research tools only work on public pages that are reachable and parseable, identify themselves with a project User-Agent, and honor `robots.txt`.
- `search_substack_profiles_by_linkedin` may require prior Developer API approval and a token. If anonymous requests fail, set `SUBSTACK_DEVELOPER_API_TOKEN` or pass `developer_api_token` directly to the tool.
- Substack does not appear to offer a broad public developer portal. The repo only treats RSS plus a narrow Help Center documented profile-lookup endpoint as semi-official surfaces; most account tools still depend on internal or reverse-engineered behavior.

For a real-account release audit, use the live smoke guidance in [docs/LIVE_SMOKE_TEST.md](docs/LIVE_SMOKE_TEST.md).

## Troubleshooting

### Command not found

Your client may not inherit your shell `PATH`.

Find the installed binary:

```bash
which substack-mcp-plus
```

Then use the absolute path in the client config.

### Authentication failed

Run setup again:

```bash
substack-mcp-plus-setup
```

If Substack sent a sign-in email, paste the email link into the same setup
browser window before closing it.

### MCP shows connected but tools do not appear

This is usually a client session cache issue.

Do this:
- fully quit the MCP client
- reopen it
- start a fresh session

### Research results are weak or empty

Try a narrower query.

Better:
- `swiftui image loading`
- `swiftui asyncimage`
- `ios monetization`

Usually weaker:
- `AI for work`
- `coding`
- `productivity`

### GUI client still cannot launch the server

Use an absolute command path instead of `substack-mcp-plus`.

## Development

Install editable Python dependencies in the project venv:

```bash
./venv/bin/python -m pip install -e '.[dev]'
```

Run tests:

```bash
./venv/bin/python -m pytest -q
```

Run the server directly:

```bash
node src/index.js
```

## Security

- Do not commit tokens, passwords, or private keys.
- Prefer interactive setup over hardcoded credentials.
- Stored browser session data is encrypted under `~/.substack-mcp-plus/`.
- Use obvious placeholders in configs and examples.
- Re-run authentication if a stored Substack session expires.

See [SECURITY.md](SECURITY.md) for project security notes.

## License

[MIT](LICENSE)
