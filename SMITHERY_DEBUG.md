# 🐛 Smithery Connection Debugging

## 🔍 Current Issue
- ✅ Deployment succeeded
- ❌ Scan failed: "couldn't connect to your server"
- ❌ "Unexpected internal error or timeout"

## 🛠️ Applied Fixes

### 1. Health Check Improvements
- **New endpoint**: `/ready` - Simple text response "OK"
- **Root endpoint**: `/` - Also returns "OK" 
- **Robust health**: `/health` - Full JSON with error handling

### 2. Timeout Optimizations
```yaml
# Smithery config
health:
  path: "/ready"
  timeout: 15  # Increased from 10

probes:
  readiness:
    initial_delay: 10  # Reduced from 30
    timeout: 5
```

### 3. Startup Command
```yaml
start_command: "python -u mcp_server_streaming_real.py"
# -u flag: unbuffered output for better logging
```

### 4. Server Timeouts Reduced
```python
web.run_app(
    app,
    shutdown_timeout=30,  # Reduced from 60
    keepalive_timeout=15, # Reduced from 30
    client_timeout=30     # Reduced from 60
)
```

## 🧪 Test Endpoints

After deployment, test these URLs:

```bash
# Basic ready check
curl https://your-deployment-url/

# Health check  
curl https://your-deployment-url/ready

# Full health info
curl https://your-deployment-url/health

# MCP initialize test
curl -X POST https://your-deployment-url/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}'
```

## 📊 Expected Responses

### `/ready` or `/`
```
OK
```

### `/health`
```json
{
  "status": "ok",
  "service": "YOK Academic MCP Real Scraping Server",
  "version": "3.0.0",
  "environment": "production"
}
```

### `/mcp` (initialize)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": {
      "name": "YOK Academic MCP Real Scraping Server",
      "version": "3.0.0"
    }
  }
}
```

## 🔧 Troubleshooting Steps

### If Still Failing:

1. **Check Smithery Logs**
   - Look for container startup errors
   - Check for port binding issues
   - Verify environment variables

2. **Test Local Docker Build**
   ```bash
   docker build -t test-yok-mcp .
   docker run -p 5000:5000 test-yok-mcp
   curl http://localhost:5000/ready
   ```

3. **Verify Chrome Installation**
   ```bash
   docker run --rm test-yok-mcp chromium --version
   docker run --rm test-yok-mcp chromedriver --version
   ```

4. **Check Resource Limits**
   - Increase memory if needed: `memory: "4Gi"`
   - Check CPU usage
   - Monitor startup time

### Common Issues:

- **Port 5000 conflicts**: Change to different port
- **Memory issues**: Chrome needs sufficient RAM
- **Startup timeout**: Server takes too long to initialize
- **Missing dependencies**: Chromium installation failed

## 🚀 Next Deployment

After these fixes:

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "Fix Smithery connection timeout issues"
   git push
   ```

2. **Redeploy in Smithery**
   - New health checks will be faster
   - Server startup should be more reliable
   - Connection scanning should work

3. **Test immediately after deployment**:
   ```bash
   curl https://your-new-deployment-url/ready
   ```

## 📋 Checklist

- [x] Simple `/ready` endpoint added
- [x] Health check timeout increased
- [x] Startup delays reduced  
- [x] Server timeouts optimized
- [x] Error handling improved
- [x] Chrome path validation added
- [x] Unbuffered Python output
- [x] Robust error logging

---

**🎯 These changes should resolve the connection timeout issues!**
