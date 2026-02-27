#!/bin/bash
set -e

# Get script directory and cd to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Install uv (if not already installed)
UV_INSTALL_DIR="$HOME/.uv"
mkdir -p "$UV_INSTALL_DIR"
command -v uv &> /dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$UV_INSTALL_DIR" sh

# Add uv to PATH (source the env file created by installer)
[ -f "$HOME/.uv/env" ] && source "$HOME/.uv/env"

# Create .venv (if it doesn't exist)
[ -d ".venv" ] || uv venv

# Install dependencies
uv sync
echo "Environment ready. Run 'source .venv/bin/activate' to activate in current shell."