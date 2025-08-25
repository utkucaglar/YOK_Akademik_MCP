#!/bin/bash
set -e

echo "🚀 Starting YÖK Academic MCP Server..."
echo "Environment:"
echo "  PORT: ${PORT:-8080}"
echo "  PWD: $(pwd)"
echo "  Python: $(python --version)"

echo ""
echo "🔍 Pre-startup tests:"

# Test Python imports
echo "  Testing Python imports..."
python -c "import json; import socket; import http.server; print('  ✅ All imports successful')" || {
    echo "  ❌ Import test failed"
    exit 1
}

# Test tools functionality
echo "  Testing tools functionality..."
python -c "
import sys
sys.path.append('.')
from minimal_server import execute_tool, TOOLS
result = execute_tool('search_profile', {'name': 'test'})
print(f'  ✅ Tool test result: {result.get(\"status\", \"unknown\")}')
print(f'  ✅ Available tools: {len(TOOLS)}')
" || {
    echo "  ❌ Tool test failed"
    exit 1
}

# Test WSGI functionality
echo "  Testing WSGI functionality..."
python -c "
import sys
sys.path.append('.')
from wsgi_server import application, TOOLS
print(f'  ✅ WSGI application loaded')
print(f'  ✅ WSGI tools: {len(TOOLS)}')
" || {
    echo "  ⚠️  WSGI test failed, will use minimal server"
    WSGI_FAILED=1
}

echo ""
echo "🎯 Starting server..."

if [ "$WSGI_FAILED" = "1" ]; then
    echo "Starting minimal HTTP server..."
    exec python minimal_server.py
else
    echo "Starting WSGI server..."
    exec python wsgi_server.py
fi
