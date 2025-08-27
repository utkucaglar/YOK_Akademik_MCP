#!/usr/bin/env python3
"""
YÖK Akademik Profil Scraping Tool
YÖK Akademik platformundan akademisyen profillerini çeker
"""

import os
import sys
import json
import time
import uuid
import argparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def save_base64_image(data_url: str, filename: str):
    """Base64 encoded image'i dosyaya kaydet"""
    try:
        import base64
        if data_url.startswith('data:image'):
            header, data = data_url.split(',', 1)
            image_data = base64.b64decode(data)
            with open(filename, 'wb') as f:
                f.write(image_data)
            return True
    except Exception as e:
        print(f"[ERROR] Image kaydedilemedi: {e}")
    return False

def sanitize_filename(name: str) -> str:
    """Dosya adı için güvenli karakterler"""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()

def parse_labels_and_keywords(line):
    """Label ve keyword'leri parse et"""
    parts = line.split(';')
    labels = []
    keywords = []
    
    for part in parts:
        part = part.strip()
        if part.startswith('Anahtar Kelime:'):
            keyword_part = part.replace('Anahtar Kelime:', '').strip()
            if keyword_part:
                keywords.extend([k.strip() for k in keyword_part.split(',')])
        else:
            if part and not part.startswith('Anahtar Kelime:'):
                labels.append(part)
    
    return labels, keywords

def extract_author_id_from_url(url):
    """Profile URL'den authorId parametresini çıkar"""
    try:
        if 'authorId=' in url:
            author_id_part = url.split('authorId=')[1]
            # Eğer authorId'den sonra başka parametre varsa & ile kes
            if '&' in author_id_part:
                author_id = author_id_part.split('&')[0]
            else:
                author_id = author_id_part
            return author_id
        return None
    except Exception:
        return None

# Argparse ekle
parser = argparse.ArgumentParser()
parser.add_argument('name', help='Aranacak isim')
parser.add_argument('session_id', nargs='?', help='Session ID (opsiyonel - otomatik oluşturulur)')
args = parser.parse_args()

print(f"[DEBUG] scrape_main_profile.py started with arguments: {args}", flush=True)
print(f"[DEBUG] Current working directory: {os.getcwd()}", flush=True)
print(f"[DEBUG] Script location: {os.path.abspath(__file__)}", flush=True)

target_name = args.name

# Otomatik session ID oluştur
if args.session_id:
    session_id = args.session_id
else:
    # Timestamp + UUID ile benzersiz session ID oluştur
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    session_id = f"session_{timestamp}_{unique_id}"
    print(f"[INFO] Otomatik session ID oluşturuldu: {session_id}", flush=True)

# --- YENİ KLASÖR YAPISI ---
# Absolute path kullan
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..", "..")
SESSION_DIR = os.path.join(project_root, "public", "collaborator-sessions", session_id)

# Session klasörünü oluştur
print(f"[DEBUG] Session klasörü oluşturuluyor: {SESSION_DIR}", flush=True)
os.makedirs(SESSION_DIR, exist_ok=True)
print(f"[INFO] Session klasörü oluşturuldu: {SESSION_DIR}", flush=True)

BASE = "https://akademik.yok.gov.tr/"
DEFAULT_PHOTO_URL = "/default_photo.jpg"

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-extensions")
options.add_argument("--disable-plugins")
options.add_argument("--disable-images")
options.add_argument("user-agent=Mozilla/5.0")
prefs = {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
    "profile.managed_default_content_settings.fonts": 2,
}
options.add_experimental_option("prefs", prefs)

# Set Chrome binary path from environment or auto-detect
chrome_bin = os.getenv("CHROME_BIN")

# Windows için Chrome binary otomatik tespiti
if not chrome_bin:
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv("USERNAME", "")),
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            chrome_bin = path
            print(f"[DEBUG] Chrome binary found at: {chrome_bin}", flush=True)
            break
    
    if not chrome_bin:
        print("[WARNING] Chrome binary not found, using webdriver-manager default", flush=True)

if chrome_bin and os.path.exists(chrome_bin):
    options.binary_location = chrome_bin
    print(f"[DEBUG] Using Chrome binary: {chrome_bin}", flush=True)
else:
    print("[DEBUG] Using webdriver-manager auto-detected Chrome", flush=True)

print("[DEBUG] WebDriver başlatılıyor...", flush=True)
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
driver.set_window_size(1920, 1080)

try:
    print("[DEBUG] Akademik Arama sayfası açılıyor...", flush=True)
    driver.get(BASE + "AkademikArama/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "aramaTerim"))
    )
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Tümünü Kabul Et')]"))
        )
        btn.click()
        print("[DEBUG] Çerez onaylandı.", flush=True)
    except Exception as e:
        print(f"[DEBUG] Çerez butonu bulunamadı: {e}", flush=True)
    try:
        # Normal arama yap
        kutu = driver.find_element(By.ID, "aramaTerim")
        kutu.send_keys(target_name)
        driver.find_element(By.ID, "searchButton").click()
        
        print(f"[DEBUG] '{target_name}' için normal arama yapıldı.", flush=True)
    except Exception as e:
        print(f"[ERROR] Arama kutusu veya butonu bulunamadı: {e}", flush=True)
        driver.quit()
        sys.exit(1)
    try:
        # Her durumda Akademisyenler sekmesine geç
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Akademisyenler"))
        ).click()
        print("[DEBUG] 'Akademisyenler' sekmesine geçildi.", flush=True)
    except Exception as e:
        print(f"[ERROR] 'Akademisyenler' sekmesi bulunamadı: {e}", flush=True)
        driver.quit()
        sys.exit(1)
    # Tüm profil satırlarını çek (tüm sayfalarda, tekrarları önle)
    profiles = []
    profile_urls = set()
    page_num = 1

    while True:
        print(f"[INFO] {page_num}. sayfa yükleniyor...", flush=True)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr[id^='authorInfo_']"))
            )
        except Exception as e:
            print(f"[ERROR] Profil satırları yüklenemedi: {e}", flush=True)
            break
        profile_rows = driver.find_elements(By.CSS_SELECTOR, "tr[id^='authorInfo_']")
        print(f"[INFO] {page_num}. sayfada {len(profile_rows)} profil bulundu.", flush=True)
        if len(profile_rows) == 0:
            print("[INFO] Profil bulunamadı, döngü bitiyor.", flush=True)
            break
        for row in profile_rows:
            try:
                info_td = row.find_element(By.XPATH, "./td[h6]")
                # Sadece green_label ve blue_label'ı hızlıca çek
                all_links = info_td.find_elements(By.CSS_SELECTOR, 'a.anahtarKelime')
                green_label = all_links[0].text.strip() if len(all_links) > 0 else ''
                blue_label = all_links[1].text.strip() if len(all_links) > 1 else ''
                
                # Eşleşiyorsa, detayları scrape et
                link = row.find_element(By.CSS_SELECTOR, "a")
                link_text = link.text.strip()
                url = link.get_attribute("href")
                if url in profile_urls:
                    print(f"[SKIP] Profil zaten eklenmiş: {url}", flush=True)
                    continue
                info = info_td.text.strip() if info_td else ""
                img = row.find_element(By.CSS_SELECTOR, "img")
                img_src = img.get_attribute("src") if img else None
                if not img_src:
                    img_src = DEFAULT_PHOTO_URL
                info_lines = info.splitlines()
                if len(info_lines) > 1:
                    title = info_lines[0].strip()
                    name = info_lines[1].strip()
                else:
                    title = link_text
                    name = link_text
                header = info_lines[2].strip() if len(info_lines) > 2 else ''
                label_text = f"{green_label}   {blue_label}"
                keywords_text = info_td.text.replace(label_text, '').strip()
                keywords_text = keywords_text.lstrip(';:,. \u000b\n\t')
                lines = [l.strip() for l in keywords_text.split('\n') if l.strip()]
                if lines:
                    keywords_line = lines[-1]
                    if header.strip() == keywords_line or header.strip() in keywords_line:
                        keywords_str = ""
                    else:
                        keywords = [k.strip() for k in keywords_line.split(';') if k.strip()]
                        keywords_str = " ; ".join(keywords) if keywords else ""
                else:
                    keywords_str = ""
                email = ''
                try:
                    email_link = row.find_element(By.CSS_SELECTOR, "a[href^='mailto']")
                    email = email_link.text.strip().replace('[at]', '@')
                except Exception:
                    email = ''
                
                # Normal mod: tüm profilleri detaylı biriktir - YENİ YAPI
                # URL'den authorId'yi çıkar
                author_id = extract_author_id_from_url(url)
                
                profiles.append({
                    "author_id": author_id,
                    "name": name,
                    "title": title,
                    "profile_url": url,
                    "photo_url": img_src,
                    "info": info,
                    "education": header,
                    "field": green_label,
                    "speciality": blue_label,
                    "keywords": keywords_str,
                    "email": email
                })
                profile_urls.add(url)
                print(f"[ADD] Profil eklendi: {name} - {url}", flush=True)
                
                # 100 kişi limitini kontrol et
                if len(profiles) >= 100:
                    print(f"[LIMIT] 100 kişi limitine ulaşıldı. Toplam: {len(profiles)} profil", flush=True)
                    break
            except Exception as e:
                print(f"[ERROR] Profil satırı işlenemedi: {e}", flush=True)
        
        print(f"[INFO] Şu ana kadar {len(profiles)} profil toplandı.", flush=True)
        
        # 100 kişi limitine ulaşıldıysa ana döngüden çık
        if len(profiles) >= 100:
            print(f"[LIMIT] 100 kişi limitine ulaşıldı. Scraping tamamlandı.", flush=True)
            break
        
        # Sayfa sonunda incremental JSON yaz - YENİ YAPI
        try:
            result_data = {
                "session_id": session_id,
                "total_profiles": len(profiles),
                "status": "ongoing",
                "searched_name": target_name,
                "profiles": profiles
            }
            with open(os.path.join(SESSION_DIR, "main_profile.json"), "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] main_profile.json dosyası güncellendi ({len(profiles)} profil).", flush=True)
        except Exception as e:
            print(f"[ERROR] main_profile.json yazılamadı: {e}", flush=True)
        
        # Pagination: aktif sayfa <li> elementinden sonra gelen <a>'ya tıkla
        try:
            pagination = driver.find_element(By.CSS_SELECTOR, "ul.pagination")
            active_li = pagination.find_element(By.CSS_SELECTOR, "li.active")
            all_lis = pagination.find_elements(By.TAG_NAME, "li")
            active_index = all_lis.index(active_li)
            if active_index == len(all_lis) - 1:
                print("[INFO] Son sayfaya gelindi, döngü bitiyor.", flush=True)
                break
            next_li = all_lis[active_index + 1]
            next_a = next_li.find_element(By.TAG_NAME, "a")
            print(f"[INFO] {page_num+1}. sayfaya geçiliyor...", flush=True)
            next_a.click()
            page_num += 1
            WebDriverWait(driver, 10).until(EC.staleness_of(profile_rows[0]))
        except Exception as e:
            print(f"[INFO] Sonraki sayfa bulunamadı veya tıklanamadı: {e}", flush=True)
            break
    print(f"[INFO] Toplam {len(profiles)} profil toplandı (maksimum 100). JSON'a yazılıyor...", flush=True)
    
    # Final result_data - YENİ YAPI
    result_data = {
        "session_id": session_id,
        "total_profiles": len(profiles),
        "status": "completed",
        "searched_name": target_name,
        "profiles": profiles
    }
    
    # main_profile.json dosyasını yaz
    main_profile_path = os.path.join(SESSION_DIR, "main_profile.json")
    print(f"[DEBUG] main_profile.json yazılıyor: {main_profile_path}", flush=True)
    with open(main_profile_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    print("[INFO] main_profile.json dosyası yazıldı.", flush=True)
    
    # Scraping tamamlandı sinyali (main_done.txt)
    if profiles:
        done_path = os.path.join(SESSION_DIR, "main_done.txt")
        print(f"[DEBUG] main_done.txt oluşturuluyor: {done_path}", flush=True)
        with open(done_path, "w") as f:
            f.write("done")
            f.flush()
            os.fsync(f.fileno())
        print("[INFO] main_done.txt dosyası oluşturuldu.", flush=True)
        if hasattr(os, "sync"):
            os.sync()

finally:
    driver.quit()
    print("[DEBUG] WebDriver kapatıldı.", flush=True)
