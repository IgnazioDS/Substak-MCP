<p align="center">
  <a href="https://github.com/IgnazioDS/Substak-MCP/stargazers"><img src="https://img.shields.io/github/stars/IgnazioDS/Substak-MCP?style=for-the-badge&logo=github&color=ffb400" alt="GitHub stars"></a>
  <a href="https://github.com/IgnazioDS/Substak-MCP/network/members"><img src="https://img.shields.io/github/forks/IgnazioDS/Substak-MCP?style=for-the-badge&logo=github" alt="GitHub forks"></a>
  <a href="https://github.com/IgnazioDS/Substak-MCP/blob/main/LICENSE"><img src="https://img.shields.io/github/license/IgnazioDS/Substak-MCP?style=for-the-badge&color=blue" alt="MIT License"></a>
  <a href="https://github.com/sponsors/IgnazioDS"><img src="https://img.shields.io/badge/Sponsor-%E2%9D%A4-ff69b4?style=for-the-badge&logo=githubsponsors" alt="Sponsor"></a>
</p>

<p align="center">
  <b>Substack MCP server for AI clients</b> &mdash; draft, publish, schedule, analyze, and research Substack publications from clients that support stdio MCP servers, including <b>Claude</b>, <b>Cursor</b>, <b>Codex</b>, <b>Windsurf</b>, and other compatible MCP hosts.
</p>

<p align="center">
  <a href="#install">Install</a> &nbsp;•&nbsp;
  <a href="#first-time-setup">Setup</a> &nbsp;•&nbsp;
  <a href="#mcp-client-config">Clients</a> &nbsp;•&nbsp;
  <a href="#tool-list">Tools</a> &nbsp;•&nbsp;
  <a href="#sponsor-this-project">❤ Sponsor</a>
</p>

---

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
substack-mcp
substack-mcp-setup
```

Naming note:
- the repository is `IgnazioDS/Substak-MCP`
- the current npm package is `@ignaziods/substack-mcp`
- the installed commands are `substack-mcp` and `substack-mcp-setup`
- the default MCP server key in examples is `substack-mcp`

### Migrating From the Old Package

If you previously installed the older plus-era package, remove it before
installing from this repository:

```bash
npm uninstall -g @ignaziods/substack-mcp-plus
npm install -g github:IgnazioDS/Substak-MCP
substack-mcp-setup
```

After reinstalling, fully restart your MCP client so it reloads the command.

## First-Time Setup

Run the setup wizard:

```bash
substack-mcp-setup
```

The setup flow will:
- open a browser
- let you sign in to Substack
- handle CAPTCHA/manual login flow
- store an encrypted browser session locally for later use

The local auth file lives at `~/.substack-mcp/auth.json`. The setup stores
the browser session cookie jar after login, not your Substack password.
If you already have auth stored under `~/.substack-mcp-plus/`, the runtime
reuses that legacy directory until you migrate it.

If Substack sends an email sign-in link, open or paste that link in the same
browser window opened by `substack-mcp-setup`. That same-browser step is
what lets the setup capture the final authenticated session.

If your client later says authentication failed, run the setup again.

## MCP Client Config

Use this server in any MCP client that supports a stdio server definition.

Server block:

```json
{
  "mcpServers": {
    "substack-mcp": {
      "command": "substack-mcp",
      "env": {
        "SUBSTACK_PUBLICATION_URL": "https://YOUR_PUBLICATION.substack.com",
        "SUBSTACK_DEVELOPER_API_TOKEN": "optional-developer-api-token"
      }
    }
  }
}
```

`SUBSTACK_DEVELOPER_API_TOKEN` is only needed for the limited Developer API
profile-lookup surface. Most account tools and public research flows do not
require it.

If your GUI client does not inherit your shell `PATH`, use an absolute path instead:

```bash
which substack-mcp
```

Then replace `"substack-mcp"` with the full path to the binary.

### Client Notes

- Claude Desktop
  Config file locations:
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`
  - Linux: `~/.config/Claude/claude_desktop_config.json`
- Claude Code
  Add the same `mcpServers.substack-mcp` block to `~/.claude.json`.
- Codex
  Add this to `~/.codex/config.toml`:

  ```toml
  [mcp_servers.substack-mcp]
  command = "substack-mcp"

  [mcp_servers.substack-mcp.env]
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

The server currently registers 29 tools.

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
which substack-mcp
```

Then use the absolute path in the client config.

### Authentication failed

Run setup again:

```bash
substack-mcp-setup
```

If Substack sent a sign-in email, paste the email link into the same setup
browser window before closing it.

### Magic-link email never arrives

Substack's anti-bot layer sometimes silently drops the magic-link email when
it is requested from the automated setup browser — no error is shown and the
wizard waits forever. The fallback is manual session-cookie auth, which the
server already supports through the `SUBSTACK_SESSION_TOKEN` environment
variable:

1. In your normal browser, already signed in to Substack, open
   `https://substack.com`.
2. Open DevTools → Application tab (Chrome) or Storage (Firefox/Safari) →
   Cookies → `https://substack.com`.
3. Copy the value of the `substack.sid` cookie. Either the decoded `s:...`
   form or the URL-encoded `s%3A...` form works — the token is passed
   directly as the cookie value.
4. Set it as `SUBSTACK_SESSION_TOKEN` in your MCP client config alongside
   `SUBSTACK_PUBLICATION_URL`. For Claude Code:

   ```bash
   claude mcp add substack --scope user \
     --env SUBSTACK_PUBLICATION_URL=https://YOUR_PUBLICATION.substack.com \
     --env SUBSTACK_SESSION_TOKEN=PASTED_COOKIE_VALUE \
     -- substack-mcp
   ```

   For Claude Desktop and other clients, add both variables to the server's
   `env` block instead.

This cookie is password-equivalent — treat it like a secret. To revoke it,
sign out of all sessions in your Substack account settings, then capture a
fresh cookie.

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

Use an absolute command path instead of `substack-mcp`.

## Development

For local development, activate the project virtual environment first:

```bash
source venv/bin/activate
python3 -m pip install -e '.[dev]'
```

Run tests:

```bash
python3 -m pytest -q
```

Run the Python server directly:

```bash
python3 -m src.server
```

Run the npm wrapper entrypoint used by the installed CLI:

```bash
node src/index.js
```

If you are developing from the repository and the auth setup cannot launch
Chromium, install the Playwright browser once:

```bash
python3 -m playwright install chromium
```

## Security

- Do not commit tokens, passwords, or private keys.
- Prefer interactive setup over hardcoded credentials.
- Stored browser session data is encrypted under `~/.substack-mcp/`.
- Use obvious placeholders in configs and examples.
- Re-run authentication if a stored Substack session expires.

See [SECURITY.md](SECURITY.md) for project security notes.

## Consider Sponsor This Project

`Substak-MCP` is built and maintained in the open by [@IgnazioDS](https://github.com/IgnazioDS). If your team relies on it, or you'd like to support continued development of new tools, integrations, and improvements, please consider sponsoring:

- ❤️ **GitHub Sponsors:** https://github.com/sponsors/IgnazioDS

Sponsorships fund ongoing maintenance, new features (more MCP clients, deeper Substack analytics, smarter research tools), bug fixes, and community support. Even a small monthly tier makes a real difference.

### Other Ways To Help

- ⭐ Star this repository so other Substack writers and AI builders can find it.
- 🐦 Share it with creators using Claude, Cursor, Codex, Windsurf, or any MCP client.
- 🐛 [Open an issue](https://github.com/IgnazioDS/Substak-MCP/issues) for bugs or feature requests.
- 🔀 Submit a pull request — contributions are very welcome.

---

## License

[MIT](LICENSE)
