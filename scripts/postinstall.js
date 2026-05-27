#!/usr/bin/env node

import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { existsSync, mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

function runCommand(command, args, options = {}) {
  return execFileSync(command, args, {
    encoding: 'utf8',
    ...options,
  });
}

function getPythonVersion(cmd) {
  return runCommand(cmd, ['--version'], { stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

function supportsVirtualEnv(cmd) {
  const probeRoot = mkdtempSync(join(tmpdir(), 'substack-mcp-plus-venv-probe-'));
  const probeVenv = join(probeRoot, 'venv');

  try {
    runCommand(cmd, ['-m', 'venv', probeVenv], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return true;
  } catch (error) {
    const output = [error.stdout, error.stderr]
      .filter(Boolean)
      .join('\n')
      .trim();

    console.log(`⚠️  Skipping ${cmd}: unable to create a virtual environment`);
    if (output) {
      const firstLine = output.split('\n')[0];
      console.log(`   ${firstLine}`);
    }
    return false;
  } finally {
    rmSync(probeRoot, { recursive: true, force: true });
  }
}

// Function to find the best Python executable
export function findPython() {
  const candidates = [
    'python3.12',
    'python3.11', 
    'python3.10',
    'python3',
    'python'
  ];
  
  for (const cmd of candidates) {
    try {
      const version = getPythonVersion(cmd);
      const match = version.match(/Python (\d+)\.(\d+)/);
      
      if (match) {
        const major = parseInt(match[1]);
        const minor = parseInt(match[2]);
        
        // MCP requires Python 3.10+
        if (major === 3 && minor >= 10) {
          console.log(`🔎 Found Python candidate: ${cmd} (${version})`);
          if (supportsVirtualEnv(cmd)) {
            console.log(`✅ Using Python: ${cmd} (${version})`);
            return cmd;
          }
        }
      }
    } catch (e) {
      continue;
    }
  }
  
  console.log('❌ Error: Could not find Python 3.10 or higher');
  console.log('📋 This MCP server requires Python 3.10+');
  console.log('🔧 Please install Python 3.10+ and try again:');
  console.log('   - macOS: brew install python@3.12');
  console.log('   - Windows: Download from python.org');
  console.log('   - Ubuntu: sudo apt install python3.12');
  process.exit(1);
}

export function runPostInstall() {
  console.log('🔧 Setting up Substack MCP Plus...');

  try {
    const pythonCmd = findPython();
    
    // Create virtual environment
    const venvPath = join(projectRoot, 'venv');
    if (!existsSync(venvPath)) {
      console.log('🏗️  Creating Python virtual environment...');
      runCommand(pythonCmd, ['-m', 'venv', 'venv'], { cwd: projectRoot, stdio: 'inherit' });
    }
    
    // Install Python dependencies
    console.log('📦 Installing Python dependencies...');
    const pipCmd = process.platform === 'win32' 
      ? join(projectRoot, 'venv', 'Scripts', 'pip')
      : join(projectRoot, 'venv', 'bin', 'pip');
      
    runCommand(pipCmd, ['install', '-e', '.'], { cwd: projectRoot, stdio: 'inherit' });
    
    console.log('✅ Setup complete!');
    console.log('');
    console.log('🎯 Next steps:');
    console.log('   1. Run: python setup_auth.py');
    console.log('   2. Add to Claude Desktop config:');
    console.log('      {');
    console.log('        "mcpServers": {');
    console.log('          "substack-mcp-plus": {');
    console.log('            "command": "substack-mcp-plus"');
    console.log('          }');
    console.log('        }');
    console.log('      }');
    
  } catch (error) {
    console.error('❌ Setup failed:', error.message);
    console.log('');
    console.log('💡 Manual setup:');
    console.log('   1. Ensure Python 3.10+ is installed');
    console.log('   2. Run: python -m venv venv');
    console.log('   3. Activate: source venv/bin/activate (or venv\\Scripts\\activate on Windows)');
    console.log('   4. Install: pip install -e .');
    process.exit(1);
  }
}

if (process.argv[1] === __filename) {
  runPostInstall();
}
