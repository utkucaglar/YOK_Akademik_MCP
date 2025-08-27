# 🚀 YÖK Akademik MCP Server - Smithery Deployment Guide

Bu rehber, YÖK Akademik MCP Server'ın Smithery platformunda nasıl deploy edileceğini açıklamaktadır.

## 🎯 Deployment Özeti

Bu MCP server şu özellikleri sağlar:
- **Real-time Streaming**: SSE (Server-Sent Events) ile gerçek zamanlı veri akışı
- **YÖK Akademik Scraping**: Gerçek YÖK Akademik platformundan veri çekme
- **MCP Protocol**: JSON-RPC 2.0 ile MCP 2024-11-05 protokol desteği
- **Production Ready**: CORS, logging, monitoring, error handling

## 📋 Deployment Gereksinimleri

### Sistem Gereksinimleri
- **Python**: 3.10+
- **Memory**: 2GB RAM (minimum)
- **CPU**: 1 vCPU (minimum)
- **Storage**: 10GB disk
- **Browser**: Google Chrome (headless mode)

### Bağımlılıklar
- aiohttp (web server)
- selenium (web scraping)
- webdriver-manager (ChromeDriver yönetimi)
- python-dotenv (environment variables)
- aiohttp-cors (CORS desteği)

## 🔧 Smithery Konfigürasyonu

### 1. smithery.yml
```yaml
name: yok-akademik-mcp
description: "YÖK Akademik Asistanı - MCP Server with Real-time Streaming"
version: "3.0.0"

deployment:
  type: mcp-server
  protocol: http
  streaming: true
  
runtime:
  python: "3.10"
  port: 5000

start_command: "python mcp_server_streaming_real.py"
```

### 2. Environment Variables
```bash
# Server Configuration
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=5000
NODE_ENV=production

# Browser Configuration  
HEADLESS_MODE=true
CHROME_BIN=/usr/bin/google-chrome
CHROME_DRIVER_PATH=/usr/local/bin/chromedriver

# Performance
MAX_CONCURRENT_SESSIONS=10
SSE_HEARTBEAT_INTERVAL=15
```

## 🐳 Docker Deployment

### Dockerfile Önemli Noktalar
```dockerfile
# Chrome ve ChromeDriver kurulumu
RUN apt-get update && apt-get install -y google-chrome-stable
RUN wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/..."

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:5000/health
```

## 🌐 API Endpoints

### MCP Protocol Endpoints
- `POST /mcp` - Ana MCP JSON-RPC endpoint
- `GET /mcp` - MCP status
- `OPTIONS /mcp` - CORS preflight

### Monitoring Endpoints  
- `GET /health` - Sağlık durumu
- `GET /metrics` - Server metrikleri

### Example Health Response
```json
{
  "status": "ok",
  "service": "YOK Academic MCP Real Scraping Server",
  "version": "3.0.0",
  "protocol": "MCP 2024-11-05",
  "environment": "production",
  "active_sessions": 2,
  "active_streams": 1
}
```

## 🔄 Streaming Architecture

### Server-Sent Events (SSE)
```
Client Request → MCP Tool Call → Background Scraping Process
     ↓              ↓                      ↓
   JSON-RPC    Streaming Response     Real-time Events
     ↓              ↓                      ↓
  Tool Result ← SSE Data Stream ← File System Watching
```

### Event Types
- `search_started` - Arama başladı
- `progress_update` - İlerleme güncellesi
- `profiles_update` - Yeni profiller bulundu
- `collaborators_update` - Yeni işbirlikçiler bulundu
- `search_completed` - Arama tamamlandı

## 📊 Performance & Scaling

### Resource Limits
```yaml
resources:
  memory: "2Gi"
  cpu: "1000m"
  storage: "10Gi"

scaling:
  min_instances: 1
  max_instances: 3
  target_cpu: 70%
```

### Session Management
- **Max Concurrent Sessions**: 10 (configurable)
- **Session Timeout**: 24 hours
- **Cleanup Interval**: 1 hour
- **File-based State**: Persistent across restarts

## 🔒 Security Features

### CORS Configuration
```python
CORS_ENABLED=true
CORS_ORIGINS=*  # Production'da specific domains kullanın
```

### Rate Limiting
```yaml
rate_limiting:
  enabled: true
  requests_per_minute: 60
  burst: 10
```

### Headless Browser Security
```bash
CHROME_NO_SANDBOX=true
CHROME_DISABLE_DEV_SHM=true
CHROME_DISABLE_GPU=true
```

## 📈 Monitoring & Logging

### Structured Logging
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO", 
  "module": "mcp_server",
  "message": "Session started: session_20240115_103000_abc123"
}
```

### Metrics Collection
- Active sessions count
- SSE connections count
- Scraping success/failure rates
- Response times

### Health Checks
- **Readiness**: Server can accept requests
- **Liveness**: Server is responsive
- **Dependency**: Chrome browser availability

## 🚀 Deployment Steps

### 1. Repository Hazırlama
```bash
# Dosyaları kontrol edin
ls -la
# smithery.yml ✓
# Dockerfile ✓  
# requirements.txt ✓
# config.env ✓
# mcp_server_streaming_real.py ✓
```

### 2. Smithery Deploy
```bash
# Smithery CLI ile deploy
smithery deploy yok-akademik-mcp

# Veya web interface üzerinden
# 1. Repository URL'i verin
# 2. smithery.yml otomatik algılanır
# 3. Deploy butonuna tıklayın
```

### 3. Deployment Doğrulama
```bash
# Health check
curl https://your-deployment-url/health

# MCP protocol test
curl -X POST https://your-deployment-url/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}'
```

## 🧪 Test Scenarios

### 1. Basic MCP Test
```python
# Initialize session
POST /mcp
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "clientInfo": {"name": "TestClient", "version": "1.0.0"}
  }
}
```

### 2. Profile Search Test
```python
# Search academic profiles
POST /mcp
{
  "jsonrpc": "2.0", 
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "search_profile",
    "arguments": {"name": "Ahmet Yılmaz"}
  }
}
```

### 3. Streaming Test
```bash
# Monitor real-time events
curl -N -H "Accept: text/event-stream" \
  "https://your-deployment-url/mcp/stream?session_id=SESSION_ID"
```

## 🔧 Troubleshooting

### Common Issues

#### Chrome/ChromeDriver Problems
```bash
# Check Chrome installation
google-chrome --version

# Check ChromeDriver
chromedriver --version

# Fix permissions
chmod +x /usr/local/bin/chromedriver
```

#### Memory Issues
```yaml
# Increase memory limit
resources:
  memory: "4Gi"  # 2Gi → 4Gi

# Enable swap if needed
environment:
  CHROME_DISABLE_DEV_SHM: "true"
```

#### Network/CORS Issues
```bash
# Check CORS headers
curl -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS https://your-deployment-url/mcp

# Should return CORS headers
```

### Debug Logs
```bash
# Enable debug logging
LOG_LEVEL=DEBUG

# Check logs
tail -f logs/mcp_server.log
```

## 📋 Deployment Checklist

- [ ] `smithery.yml` configured
- [ ] `Dockerfile` optimized
- [ ] `requirements.txt` updated
- [ ] Environment variables set
- [ ] CORS properly configured
- [ ] Health checks working
- [ ] Resource limits appropriate
- [ ] Security headers set
- [ ] Logging configured
- [ ] Monitoring enabled

## 🎯 Production Recommendations

### Security
- Use specific CORS origins (not `*`)
- Enable rate limiting
- Use HTTPS only
- Regular security updates

### Performance  
- Monitor memory usage
- Set appropriate timeouts
- Use connection pooling
- Enable compression

### Reliability
- Health check intervals
- Graceful shutdowns
- Error recovery
- Data persistence

## 📞 Support

Deployment sorunları için:
1. Health endpoint kontrol edin
2. Logs'ları inceleyin
3. Resource kullanımını izleyin
4. CORS ayarlarını doğrulayın

---

**🎓 YÖK Akademik MCP Server v3.0.0**  
*Production-ready deployment for Smithery platform*
