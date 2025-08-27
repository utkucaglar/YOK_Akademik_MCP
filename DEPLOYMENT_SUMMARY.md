# YÖK Akademik MCP Server - Deployment Özeti

## Projenin Mevcut Durumu

Bu proje, YÖK Akademik platformundan akademisyen bilgilerini çeken ve real-time olarak kullanıcıya sunan bir MCP (Model Context Protocol) server'ıdır.

### Ana Özellikler

**1. Real-Time Streaming Scraping**
- Kullanıcı bir akademisyen adı girdiğinde, server arka planda YÖK Akademik'te arama yapar
- Bulunan sonuçlar anlık olarak Server-Sent Events (SSE) ile kullanıcıya akışla gönderilir
- Scraping tamamlandığında tüm profil listesi sunulur

**2. İşbirlikçi Araştırması**
- Bulunan profiller arasından seçilen birinin işbirlikçileri taranır
- Bu işlem de real-time streaming ile sonuçları gösterir
- Binlerce işbirlikçi verisi anlık olarak aktarılır

**3. Session Yönetimi**
- Her arama için benzersiz session ID'si oluşturulur
- Veriler `public/collaborator-sessions/` altında JSON formatında saklanır
- Her session bağımsız çalışır, veriler karışmaz

### Tool Sistemi

**search_profile**: Akademisyen adıyla arama başlatır (streaming)
**get_profile**: Session'daki tüm profil verilerini JSON olarak döndürür
**get_collaborators**: Seçilen profil için işbirlikçi araması başlatır (streaming)

### Teknik Altyapı

**MCP 2025-03-26 Protokolü**: En yeni MCP standardı ile uyumlu
**Streamable HTTP Transport**: Real-time veri akışı için optimize edilmiş
**CORS Desteği**: Web uygulamalarından erişim için gerekli güvenlik ayarları
**Chrome Headless**: Selenium ile otomatik tarayıcı kontrolü
**asyncio**: Python'da asenkron programlama ile yüksek performans

### Smithery Deploy Hazırlığı

**Dockerfile**: Production ortamı için Chrome ve gerekli bağımlılıkları içeren container
**smithery.yaml**: Smithery platformu için detaylı konfigürasyon
**Health Checks**: `/ready` endpoint'i ile server durumu kontrolü
**Environment Variables**: Production/development ortam ayarları
**Resource Limits**: 2GB RAM, 1 CPU core, 10GB storage limitleri

### Kullanım Senaryosu

1. Kullanıcı "ahmet yılmaz" adını arar
2. Server YÖK Akademik'te gerçek zamanlı arama yapar
3. Bulunan 24 profil streaming ile kullanıcıya gönderilir
4. Kullanıcı 1. profili seçer
5. Server o profilin işbirlikçilerini taramaya başlar
6. 150+ işbirlikçi verisi anlık olarak akışla gelir
7. Tüm veriler JSON formatında saklanır

### Güvenlik ve Performans

**Rate Limiting**: Dakikada 60 istek limiti
**Concurrent Sessions**: Maksimum 10 eşzamanlı kullanıcı
**Auto-scaling**: Yük artışında 1-3 instance arası otomatik ölçeklendirme
**Session Isolation**: Her kullanıcının verisi ayrı klasörlerde güvenli şekilde saklanır

Proje şu anda Smithery platformuna deploy edilmeye hazır durumda. Real-time streaming, güvenlik ayarları ve performans optimizasyonları tamamlanmıştır.
