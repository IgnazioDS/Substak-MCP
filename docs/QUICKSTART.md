# Substack MCP Plus - Quick Start Guide

This is the fastest setup path I recommend for Substack MCP Plus.

## 🚀 Quick Setup

```bash
# Install globally from the GitHub repository
npm install -g github:IgnazioDS/Substak-MCP

# Run the authentication setup wizard  
substack-mcp-plus-setup
```

The setup wizard handles the heavy lifting:
- ✅ Choice of magic link or password authentication
- ✅ Browser-based login
- ✅ CAPTCHA handling
- ✅ Encrypted local browser session storage
- ✅ Automatic configuration

If Substack sends an email sign-in link, open or paste that link in the same
browser window opened by `substack-mcp-plus-setup`. The setup captures the final
browser cookies after that window reaches a signed-in Substack page.

## 🔄 Existing Users

If you installed another package variant, reinstall from this repository and rerun setup:

```bash
npm uninstall -g substack-mcp-plus
npm install -g github:IgnazioDS/Substak-MCP
substack-mcp-plus-setup
```

Then fully restart your MCP client.

## 🔧 Claude Desktop Config

After running setup, add this minimal config to Claude Desktop:

```json
{
  "mcpServers": {
    "substack-mcp-plus": {
      "command": "substack-mcp-plus",
      "env": {
        "SUBSTACK_PUBLICATION_URL": "https://YOUR-PUBLICATION.substack.com"
      }
    }
  }
}
```

**Important**: Replace `YOUR-PUBLICATION` with your actual Substack subdomain (e.g., if your Substack is at `https://johndoe.substack.com`, use `johndoe`).

If you already have other MCP servers configured, add this alongside them:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"]
    },
    "substack-mcp-plus": {
      "command": "substack-mcp-plus",
      "env": {
        "SUBSTACK_PUBLICATION_URL": "https://YOUR-PUBLICATION.substack.com"
      }
    }
  }
}
```

**No passwords or tokens needed!** Authentication is handled automatically.

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

## 🧪 Test Your Setup

In Claude Desktop, try these commands:

```
# List your drafts
Show me my draft posts

# Create a simple post
Create a draft titled "Hello World" with content "This is my first post!"

# Create a formatted post
Create a draft with title "Formatted Post" and content:
# Main Header
This has **bold** and *italic* text.
- Bullet point 1
- Bullet point 2

> A blockquote for emphasis

# Upload an image
Upload image from https://picsum.photos/800/400 optimized for web
```

## 📊 Available Tools

1. **create_formatted_post** - Create posts with rich formatting
2. **update_post** - Update existing drafts
3. **publish_post** - Publish or schedule posts
4. **list_drafts** - List your draft posts
5. **upload_image** - Upload images to Substack CDN

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "No authentication found" | Run `substack-mcp-plus-setup` |
| CAPTCHA appears | Solve it in the browser window |
| Email link opens elsewhere | Copy the link and paste it into the setup browser |
| Session expired | Run `substack-mcp-plus-setup` again |
| Import errors | Reinstall with `npm install -g github:IgnazioDS/Substak-MCP` |

## 🎯 Pro Tips

1. **Markdown Support**: Full CommonMark + tables, code blocks, etc.
2. **Paywall Marker**: Use `<!-- PAYWALL -->` in your content
3. **Batch Operations**: Ask Claude to create multiple posts at once
4. **Image Optimization**: Use the upload_image tool for best performance

## 🔑 Alternative Setup (Advanced)

If you prefer manual setup or need CI/CD configuration:

### Environment Variables
```bash
export SUBSTACK_EMAIL="YOUR_EMAIL@example.com"
export SUBSTACK_PASSWORD="YOUR_PASSWORD"
export SUBSTACK_PUBLICATION_URL="https://YOUR_PUBLICATION.substack.com"
```

### Session Token (If you have one)
```bash
export SUBSTACK_SESSION_TOKEN="YOUR_SUBSTACK_SESSION_TOKEN"
export SUBSTACK_PUBLICATION_URL="https://YOUR_PUBLICATION.substack.com"
```

## 📚 More Resources

- [Full Documentation](docs/)
- [Authentication Guide](docs/authentication.md)
- [Formatting Examples](docs/formatting.md)
- [Testing Guide](docs/testing_guide.md)

---

**Need help?** I kept the setup flow opinionated on purpose. In most cases, rerunning `substack-mcp-plus-setup` is the right fix.
