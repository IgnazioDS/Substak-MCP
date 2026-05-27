#!/usr/bin/env node

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Function to find the best Python executable
function findPython() {
  const projectRoot = join(__dirname, '..');
  const venvPython = process.platform === 'win32' 
    ? join(projectRoot, 'venv', 'Scripts', 'python.exe')
    : join(projectRoot, 'venv', 'bin', 'python');
  
  // First try the virtual environment if it exists
  const candidates = [
    venvPython,
    'python3.12',
    'python3.11', 
    'python3.10',
    'python3',
    'python'
  ];
  
  for (const cmd of candidates) {
    try {
      // Check if command exists and get version
      const version = execSync(`${cmd} --version 2>&1`, { encoding: 'utf8' }).trim();
      const match = version.match(/Python (\d+)\.(\d+)/);
      
      if (match) {
        const major = parseInt(match[1]);
        const minor = parseInt(match[2]);
        
        // MCP requires Python 3.10+
        if (major === 3 && minor >= 10) {
          console.error(`Using Python: ${cmd} (${version})`);
          return cmd;
        }
      }
    } catch (e) {
      // Command not found, continue to next candidate
      continue;
    }
  }
  
  // Fallback: try to give helpful error
  console.error('❌ Error: Could not find Python 3.10 or higher');
  console.error('📋 This MCP server requires Python 3.10+');
  console.error('🔧 Please install Python 3.10+ and ensure it\'s in your PATH');
  console.error('💡 Common solutions:');
  console.error('   - macOS: brew install python@3.12');
  console.error('   - Windows: Download from python.org');
  console.error('   - Ubuntu: sudo apt install python3.12');
  process.exit(1);
}

// Get the best Python executable
const pythonCmd = findPython();

// Spawn the Python MCP server with explicit stdio pipes so this wrapper can
// transparently bridge the transport instead of relying on inherited streams.
const pythonProcess = spawn(pythonCmd, ['-m', 'src.server'], {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: { ...process.env },
  cwd: join(__dirname, '..')
});

process.stdin.on('data', (chunk) => {
  pythonProcess.stdin.write(chunk);
});

process.stdin.on('end', () => {
  pythonProcess.stdin.end();
});

pythonProcess.stdout.on('data', (chunk) => {
  process.stdout.write(chunk);
});

pythonProcess.stderr.on('data', (chunk) => {
  process.stderr.write(chunk);
});

process.stdin.resume();

// Handle process termination
process.on('SIGINT', () => {
  pythonProcess.kill('SIGINT');
  process.exit(0);
});

process.on('SIGTERM', () => {
  pythonProcess.kill('SIGTERM');
  process.exit(0);
});

pythonProcess.on('error', (err) => {
  console.error('Failed to start Python server:', err);
  process.exit(1);
});

pythonProcess.on('exit', (code, signal) => {
  if (code !== 0 && code !== null) {
    console.error('\n❌ Python server exited with an error');
    console.error('💡 Common solutions:');
    console.error('   1. Install dependencies: pip install -e .');
    console.error('   2. Run setup: substack-mcp-plus-setup');
    console.error('   3. Check your Python environment has required packages');
  }
  process.exit(code || 0);
});
