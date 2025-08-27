## 🎓 YÖK Akademik Asistanı (MCP Protocol Server)

Modern bir MCP (Model Context Protocol) sunucusu ile YÖK Akademik platformundan profilleri ve işbirlikçileri toplayan, gerçek zamanlı SSE (Server‑Sent Events) akışı veren, dosya tabanlı oturum yönetimi ve otomasyon içeren bir scraping ve orkestrasyon sistemi.

> **🚀 Smithery Deployment Ready** - Bu proje Smithery platformunda deploy edilmeye hazır haldedir. Detaylı deployment rehberi için [DEPLOYMENT.md](DEPLOYMENT.md) dosyasına bakınız.

### Ana Özellikler
- **MCP JSON‑RPC 2.0 sunucusu**: `aiohttp` tabanlı `/mcp` endpoint’i
- **Gerçek zamanlı akış**: `/mcp/stream` ile SSE; polling yok
- **Oturum izolasyonu**: Her çalışma için benzersiz `session_id`
- **Dosya tabanlı durum**: `public/collaborator-sessions/<session_id>/...`
- **Otomasyon**: `scrape_main_profile.py` ve `scrape_collaborators.py` alt süreçler olarak çalışır
- **Dosya izleme**: `watchdog` ile JSON dosyaları değiştikçe SSE yayını
- **Windows uyumlu**: ChromeDriver otomatik kurulum; PowerShell ile kolay kullanım


## Mimari Genel Bakış

```
İstemci (MCP Inspector veya HTTP client)
    │
    ├─ POST /mcp (JSON‑RPC): initialize, tools/list, tools/call
    │       │
    │       └─ Adapter → Orchestrator → (subprocess) scraping tools
    │                                      ├─ scrape_main_profile.py → main_profile.json + main_done.txt
    │                                      └─ scrape_collaborators.py → collaborators.json + collaborators_done.txt
    │
    └─ GET /mcp/stream?session_id=... (SSE): gerçek zamanlı event akışı
```

### Bileşenler
- `mcp_server_protocol.py`: HTTP katmanı ve MCP JSON‑RPC endpoint’leri; SSE endpoint’i
- `mcp_adapter.py`: MCP tool tanımları ve orkestratör ile köprü
- `src/core/mcp_orchestrator.py`: oturum yönetimi, dosya izleme, subprocess yönetimi, SSE yayıncısı
- `src/tools/scrape_main_profile.py`: YÖK arama sonuçlarından profil listesi toplar (Selenium)
- `src/tools/scrape_collaborators.py`: seçilen profilin işbirlikçilerini toplar (Selenium)
- `config/config.py`: yollar, zaman aşımları, SSE ayarları ve sabitler


## Kurulum

### Gereksinimler
- Python 3.10+
- Google Chrome (veya Chromium)
- Sistem genelinde internet erişimi

### Bağımlılıklar

```bash
pip install -r requirements.txt
```

`webdriver-manager` ChromeDriver’ı otomatik indirir. İlk çalıştırmada indirme yapabilir.

### Dizin Yapısı (özet)

```
public/
  collaborator-sessions/
    session_YYYYMMDD_HHMMSS_xxxxxxxx/
      main_profile.json
      main_done.txt
      collaborators.json
      collaborators_done.txt
config/config.py
src/core/mcp_orchestrator.py
src/tools/scrape_main_profile.py
src/tools/scrape_collaborators.py
mcp_server_protocol.py
mcp_adapter.py
```


## Çalıştırma

### Sunucuyu Başlatma

```powershell
python .\mcp_server_protocol.py
```

- MCP endpoint: `http://localhost:5000/mcp`
- SSE endpoint: `http://localhost:5000/mcp/stream`
- Health: `http://localhost:5000/health`

### Test Scripti

```powershell
python .\test_mcp_protocol.py
```

Script sırasıyla: health → initialize → tools/list → search_profile → get_session_status → (gerekirse) get_profile → (gerekirse) get_collaborators çalıştırır. Ayrıca dosya güncellemelerini izleyen bir thread ile ilerlemeyi gösterir.

### Terminal Kullanımı ve Girdi Formatı

- İsim: serbest metin
- Email (opsiyonel): email hızlı eşleşme modu (aşağıya bakın)
- Alan: `fields.json` içinden tek seçim (ID girilir). Boş geçilebilir.
- Uzmanlık(lar): seçilen alanın altındaki uzmanlıklar için çoklu seçim.
  - Çoklu giriş örnekleri: "1,5,12" veya "1 5 12"
  - Tümü için: `all` veya `*`

Not: Test scripti ID → ad eşlemeyi otomatik yapar ve tool’a `field` ile `specialties` değerlerini isim olarak iletir.


## HTTP API ve MCP İşlemleri

### 1) JSON‑RPC: POST /mcp

- `initialize` → sunucu bilgi ve capability’leri döner; yanıt başlığında `mcp-session-id` bulunur
- `tools/list` → mevcut tool’lar ve şemaları
- `tools/call` → bir tool’u çağırır

Örnek initialize:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "clientInfo": {"name": "MyClient", "version": "1.0.0"}
  }
}
```

Yanıt başlığında: `mcp-session-id: <uuid>`

### 2) SSE: GET /mcp/stream

Gerçek zamanlı event akışı sağlar.

- Bağlantı: `GET /mcp/stream?session_id=<yok_session_id>` veya header’da `mcp-session-id`
- İçerik: `text/event-stream`, kalp atışı: `: ping` her ~15 saniyede

Örnek bağlanma (PowerShell curl):

```powershell
curl -N http://localhost:5000/mcp/stream?session_id=SESSION_ID
```

Örnek event (satır içi):

```json
{"session_id":"...","event":"progress_update","data":{"profiles_found": 12, "total_profiles": 12, "status": "ongoing", "searched_name": "NURETTİN", "timestamp":"..."}}
```

Ek olaylar:
- `search_timeout_warning`: Email modunda 45 sn içinde eşleşme bulunamazsa uyarı
- `profile_url_missing`: Minimal JSON’da URL yoksa otomatik işbirlikçi başlatılamadığında uyarı


## Tool’lar (Adapter)

Sunucu `tools/list` ile aşağıdaki tool’ları bildirir:

- `search_profile`
  - Amaç: Ana profil aramasını başlatır; dosya izleme + SSE akışı aktive olur
  - Girdi: `{ "name": string, "email"?: string, "field"?: string, "specialties"?: string[] }`
    - `email` verilirse: hızlı email eşleşme modu aktive olur (yalnız email kontrol edilir)
    - `field` tek seçimdir; `specialties` birden çok isim içerebilir veya `"all"`
  - Çıktı: `{ session_id, status: "started", message, timestamp }`

- `get_session_status`
  - Amaç: Oturum durumunu ve dosyaların varlığını özetler
  - Girdi: `{ "session_id": string }`
  - Çıktı: `{ session_id, state, created_at, profiles_found, collaborators_found, files: { ... } }`

- `get_profile`
  - Amaç: Birden fazla profil bulunursa seçim yapar ve işbirlikçi taramayı başlatır
  - Girdi: `{ "session_id": string, "profile_id": number }`
  - Çıktı: `{ session_id, profile_id, profile_name, status: "started", ... }`

- `get_collaborators`
  - Amaç: Seçili profil için işbirlikçi taramayı manuel başlatır (tek profilse otomatik başlar)
  - Girdi: `{ "session_id": string }`
  - Çıktı: `{ session_id, status: "started", message, ... }`


## Akış ve Durum Yönetimi

### Süreç Durumları
- initializing → scraping_main → analyzing → awaiting_selection → scraping_collabs → completed (veya failed)

### Dosya İzlencesi
- `main_profile.json` değişince: `progress_update` SSE eventi (total_profiles, status, searched_name bilgileri ile)
- `main_done.txt` oluşunca: tek profil ise otomatik `scrape_collaborators` başlar
- `collaborators.json` değişince: artan sayıda `collaborator_found` eventi
- `collaborators_done.txt` oluşunca: `process_complete` eventi ve süreç kapanışı

### SSE Event Tipleri (örnekler)
- `session_started`, `log_message`, `progress_update`, `unique_profile_found`, `multiple_profiles_found`, `no_results`, `email_match_found`, `auto_collaborator_start`, `collaborator_found`, `no_collaborators_found`, `collaborators_completed`, `process_complete`, `search_timeout_warning`, `profile_url_missing`, `error`

### Arama Modları

- İsim + Email (opsiyonel hızlı mod):
  - Yalnızca email eşleşmesi kontrol edilir (isim eşleşmesi gerekmez)
  - Eşleşme bulunduğunda: `main_profile.json` minimal yazılır (yalnızca isim + email), `main_done.txt = completed`
  - Eşleşme bulunduysa işbirlikçi taraması otomatik başlar (profil URL’i elde edilmişse)
  - 45 sn içinde eşleşme yoksa: `search_timeout_warning` SSE olayı gönderilir, `main_profile.json` boş liste ile yazılır, `main_done.txt = timeout`

- İsim + Alan/Uzmanlık filtresi:
  - `field` (green_label) isimle eşleşmeli (büyük-küçük harf duyarsız)
  - `speciality` (blue_label) verilen listede olmalı; `all/*` verilirse uzmanlık filtresi uygulanmaz
  - Yalnız eşleşen profiller `main_profile.json` içine eklenir

Örnek `main_profile.json` (email hızlı mod):

```json
{
  "session_id": "session_20250101_123000_abcd1234",
  "total_profiles": 1,
  "status": "completed",
  "searched_name": "Ada Lovelace",
  "profiles": [
    { "id": 1, "name": "Ada Lovelace", "email": "ada@uni.edu" }
  ]
}
```

Örnek `main_profile.json` (alan/uzmanlık filtresi):

```json
{
  "session_id": "session_20250101_123000_abcd1234",
  "total_profiles": 1,
  "status": "completed",
  "searched_name": "Grace Hopper",
  "profiles": [
    {
      "id": 7,
      "name": "Grace Hopper",
      "title": "Prof.",
      "profile_url": "https://...",
      "photo_url": "https://...",
      "info": "...",
      "education": "...",
      "field": "Bilgisayar Bilimleri",
      "speciality": "Yapay Zeka",
      "keywords": "...",
      "email": "..."
    }
  ]
}
```


## Konfigürasyon

`config/config.py` ana ayarlar:

- Yollar: `PROJECT_ROOT`, `SESSIONS_DIR`, `FIELDS_FILE`
- Zaman aşımı ve seçenekler: `TIMEOUTS`, `WEBDRIVER_OPTIONS`
- SSE: `SSE_CONFIG` (`text/event-stream`, `no-cache`, `keep-alive`)
- Sabitler: `SSE_EVENTS`, `ERROR_MESSAGES`, `SUCCESS_MESSAGES`, `CSS_SELECTORS`


## Geliştirme ve Test

1) Sunucuyu başlatın:

```powershell
python .\mcp_server_protocol.py
```

2) Ayrı bir terminalde testleri çalıştırın:

```powershell
python .\test_mcp_protocol.py
```

Test, kullanıcıdan isim girdisi ister ve sonuçları gerçek zamanlı gösterir. İsterseniz MCP Inspector ile de deneyebilirsiniz.


## Sorun Giderme

- Chrome/Driver Hatası: Chrome’un kurulu olduğundan emin olun; ilk çalıştırmada `webdriver-manager` driver indirir
- Erişim Problemleri: `public/collaborator-sessions` dizininde yazma izni
- `fields.json` eksik: `public/fields.json` mevcut olmalı (scriptler uyarı basar)
- SSE Akışı Yok: `/mcp/stream` için doğru `session_id` kullanın; firewall/proxy engellerini kontrol edin
- Windows Konsol Penceresi: Araçlar arka planda başlatılır; gerekiyorsa antivirüs/SmartScreen izinleri


## Güvenlik ve Etik Notlar

Bu proje eğitim/araştırma amaçlıdır. Hedef sitelerin kullanım şartlarına uyun, orantılı istek hızları kullanın ve kişisel verilerin işlenmesinde geçerli mevzuata uyun.


## Lisans

Bu depodaki kod, aksi belirtilmedikçe telif sahibine aittir. Yeniden kullanım koşullarını projenin sahipleriyle netleştirin.


