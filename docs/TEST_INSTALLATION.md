# Test Installation Instructions

## Method 1: Global Install from Tarball (Recommended)

```bash
# 1. First uninstall any existing version
npm uninstall -g @ignaziods/substack-mcp

# 2. Build and install from the tarball
TARBALL="$(npm pack)"
npm install -g "./$TARBALL"

# 3. Verify installation
which substack-mcp
# Should show: /opt/homebrew/bin/substack-mcp

# 4. Test the command works
substack-mcp-setup --help
```

## Method 2: Test in Isolated Directory

```bash
# 1. Create a test directory
mkdir -p ~/test-substack-mcp
cd ~/test-substack-mcp

# 2. Install the package locally
TARBALL="$(ls ../myApps/substack-mcp/*.tgz | tail -n 1)"
npm install "$TARBALL"

# 3. Run from node_modules
./node_modules/.bin/substack-mcp

# 4. Or configure Claude Desktop to use this path:
# "command": "/Users/Matt/test-substack-mcp/node_modules/.bin/substack-mcp"
```

## Method 3: Direct Test Without NPM

```bash
# From the project directory, you can test directly:
cd /Users/Matt/myApps/substack-mcp

# Run the server directly
node src/index.js

# Or with Python directly
source venv/bin/activate
python -m src.server
```

## After Testing

To revert to the published version:
```bash
# Uninstall test version
npm uninstall -g @ignaziods/substack-mcp

# Install from the GitHub repository
npm install -g github:IgnazioDS/Substak-MCP
```

## Notes

- The tarball includes all necessary files including the virtual environment
- The postinstall script will run automatically during installation
- Make sure to restart Claude Desktop after changing the installation
