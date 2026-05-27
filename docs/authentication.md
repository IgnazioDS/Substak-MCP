# Authentication Guide for Substack MCP Plus

This guide explains how to set up authentication for Substack MCP Plus. The
recommended setup uses a real browser login so Substack can show CAPTCHA,
password, magic-link, or email-verification steps normally.

## 🚀 Quick Setup (Recommended)

The easiest way to set up authentication is using our interactive setup wizard:

```bash
substack-mcp-plus-setup
```

This wizard will:
1. ✅ Ask how you want to sign in (magic link or password)
2. ✅ Request your Substack email
3. ✅ If using password, ask for your password
4. ✅ Open a browser window for secure login
5. ✅ Handle CAPTCHA challenges if they appear
6. ✅ Store the authenticated browser session cookies
7. ✅ Test the connection automatically
8. ✅ Configure everything for you

**That's it!** No manual token extraction, no dealing with browser developer tools, no passwords in MCP client config.

For local development from the repository, use:

```bash
./venv/bin/python setup_auth.py
```

### Authentication Methods

#### 🔗 Magic Link (Email Code)
- Substack sends a 6-digit code to your email
- Enter the code in the browser when prompted
- No password needed - more secure!
- If Substack sends a sign-in link instead, paste it into the same setup browser

#### 🔑 Password Authentication  
- Traditional email + password login
- Substack may still require CAPTCHA or email verification
- If an email link opens in your normal browser, copy it back into the setup browser

## 🔐 How It Works

Our authentication system uses a three-tier approach for maximum reliability:

1. **Secure Browser Session Storage** (Primary)
   - Session cookies are encrypted and stored at `~/.substack-mcp-plus/auth.json`
   - The auth file is owner-readable only (`600`)
   - The auth directory is owner-only (`700`)
   - Automatically used when available
   - Checked for expiration and refreshed as needed

2. **Environment Variables** (Fallback)
   - Supports traditional environment variable configuration
   - Useful for CI/CD environments where browser setup is not possible

3. **Automatic Fallback** (Seamless)
   - If stored browser session fails, tries environment variables
   - Provides clear guidance if re-authentication is needed

## 📝 Configuration

After running `substack-mcp-plus-setup`, you only need to provide the publication URL in your Claude Desktop config:

```json
{
  "mcpServers": {
    "substack-mcp-plus": {
      "command": "substack-mcp-plus",
      "env": {
        "SUBSTACK_PUBLICATION_URL": "https://yourpublication.substack.com"
      }
    }
  }
}
```

**No passwords or tokens in the config!** Authentication is handled automatically.

## 🔄 Session Management

### Automatic Features
- **Secure Storage**: Browser session cookies are encrypted in `~/.substack-mcp-plus/auth.json`
- **Expiration Tracking**: Monitors session age and prompts for refresh
- **Cache Management**: Reuses authenticated sessions for performance
- **Clear Error Messages**: Helpful guidance when authentication fails

### Manual Session Refresh
If needed, simply run the setup wizard again:
```bash
substack-mcp-plus-setup
```

It will detect existing authentication and ask if you want to replace it.

## 🛠 Alternative Setup Methods

### Method 1: Environment Variables

If you prefer traditional environment variables (e.g., for CI/CD):

Create a `.env` file:
```env
SUBSTACK_EMAIL=your-email@example.com
SUBSTACK_PASSWORD=your-password
SUBSTACK_PUBLICATION_URL=https://yourpublication.substack.com
```

Or set them in your shell:
```bash
export SUBSTACK_EMAIL="YOUR_EMAIL@example.com"
export SUBSTACK_PASSWORD="YOUR_PASSWORD"
export SUBSTACK_PUBLICATION_URL="https://YOUR_PUBLICATION.substack.com"
```

### Method 2: Session Token (Advanced)

If you already have a session token:

```env
SUBSTACK_SESSION_TOKEN=YOUR_SUBSTACK_SESSION_TOKEN
SUBSTACK_PUBLICATION_URL=https://YOUR_PUBLICATION.substack.com
```

## 🚨 Troubleshooting

### "No authentication found" Error
**Solution**: Run `substack-mcp-plus-setup`

### CAPTCHA Issues
The setup wizard handles CAPTCHA automatically. If you still have issues:
1. Clear your browser cookies for substack.com
2. Try using magic link authentication instead of password
3. Log in manually once in your browser
4. Wait 5 minutes
5. Run `substack-mcp-plus-setup` again

### Email Link Opened in Another Browser
**Solution**: Copy the email link and paste it into the browser window opened by
`substack-mcp-plus-setup`. The setup must see the final signed-in browser state
before it can store the session.

### Session Expired
**Solution**: Run `substack-mcp-plus-setup` to refresh

### "Authentication failed" Error
1. Verify your email is correct
2. If using password auth, verify your password is correct
3. Try using magic link authentication instead
4. Check that your publication URL includes `https://`
5. Ensure you have access to the publication

## 🔒 Security Best Practices

1. **Never commit credentials** to version control
2. **Use the setup wizard** for the most secure configuration
3. **Session cookies are encrypted** in `~/.substack-mcp-plus/auth.json`
4. **Enable 2FA** on your Substack account
5. **Rotate passwords** periodically

## 📚 Advanced Topics

### How Sessions Are Stored

Sessions are stored using:
- **Encrypted local file**: `~/.substack-mcp-plus/auth.json`
- **Encryption**: Additional layer using Fernet symmetric encryption
- **Permissions**: auth file `600`, config directory `700`
- **Metadata**: Expiration tracking and email association

### Authentication Priority

The system tries authentication in this order:
1. Stored browser session cookies (from setup wizard)
2. Environment session token
3. Email/password from environment
4. Clear error with setup instructions

### Token Expiration

- Tokens are set to expire after 30 days
- System checks for expiration before each use
- Automatic refresh reminders at 7 days before expiry
- Future updates will support automatic refresh

## 🎯 Summary

For 99% of users, just run:
```bash
substack-mcp-plus-setup
```

Follow the prompts, and you're done! The system handles everything else automatically.
