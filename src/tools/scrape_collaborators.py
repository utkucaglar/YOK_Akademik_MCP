#!/usr/bin/env python3
"""
YÖK Akademik İşbirlikçi Scraping Tool
YÖK Akademik platformundan seçilen profilin işbirlikçilerini çeker
"""

import sys
import os
import base64
import re
import urllib.request
import json
import time
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9ĞÜŞİÖÇğüşiöç ]+', '_', name).strip().replace(" ", "_")

def extract_author_id_from_url(url: str) -> str:
    """URL'den author_id'yi çıkar"""
    if not url:
        return ""
    
    # URL'den authorId parametresini bul
    match = re.search(r'authorId=([^&]+)', url)
    if match:
        return match.group(1)
    return ""

def extract_info_from_graph_element(element) -> dict:
    """İşbirlikçi grafiğindeki elementten bilgileri çıkar"""
    info = {
        "name": "",
        "info": "",
        "photo_url": "",
        "profile_url": ""
    }
    
    try:
        # İsim bilgisini al
        text_element = element.find_element(By.CSS_SELECTOR, 'text')
        if text_element:
            info["name"] = text_element.text.strip()
    except:
        pass
    
    try:
        # Fotoğraf URL'ini al
        img_element = element.find_element(By.CSS_SELECTOR, 'image')
        if img_element:
            photo_url = img_element.get_attribute('href')
            if photo_url:
                info["photo_url"] = photo_url
            else:
                info["photo_url"] = "/default_photo.jpg"
        else:
            info["photo_url"] = "/default_photo.jpg"
    except:
        info["photo_url"] = "/default_photo.jpg"
    
    return info

# --- YÖK AKADEMİK KUTUCUK AYRIŞTIRICI (main_profile ile aynı) ---
def parse_labels_and_keywords(line):
    parts = [p.strip() for p in line.split(';')]
    left = parts[0] if parts else ''
    rest_keywords = [p.strip() for p in parts[1:] if p.strip()]
    left_parts = re.split(r'\s{2,}|\t+', left)
    green_label = left_parts[0].strip() if len(left_parts) > 0 else ''
    blue_label = left_parts[1].strip() if len(left_parts) > 1 else ''
    keywords = []
    if len(left_parts) > 2:
        keywords += [p.strip() for p in left_parts[2:] if p.strip()]
    keywords += rest_keywords
    if not keywords:
        keywords = ['-']
    return green_label, blue_label, keywords

def get_profile_url_by_id(session_id, profile_id):
    """main_profile.json'dan profile ID'ye göre URL'i al"""
    # Absolute path kullan
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(current_dir, "..", "..")
    main_profile_path = os.path.join(project_root, "public", "collaborator-sessions", session_id, "main_profile.json")
    
    try:
        with open(main_profile_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            profiles = data.get('profiles', [])
            for profile in profiles:
                if profile.get('id') == profile_id:
                    return profile.get('profile_url')
        print(f"[WARNING] Profile ID {profile_id} bulunamadı!", flush=True)
        return None
    except Exception as e:
        print(f"[ERROR] main_profile.json okunamadı: {e}", flush=True)
        print(f"[DEBUG] Denenen path: {main_profile_path}", flush=True)
        return None

# Argparse ekle
parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('session_id')
parser.add_argument('--profile-id', type=int, help='Profil ID (main_profile.json\'dan)')
parser.add_argument('--profile-url', type=str, help='Profil URL\'i (opsiyonel)')
args = parser.parse_args()

target_name = args.name
session_id = args.session_id
profile_url = args.profile_url
profile_id = args.profile_id

BASE = "https://akademik.yok.gov.tr/"
DEFAULT_PHOTO_URL = "/default_photo.jpg"

# Absolute path kullan
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..", "..")
collaborators_json_path = os.path.join(project_root, "public", "collaborator-sessions", session_id, "collaborators.json")

# Ana profil bilgilerini al (selected_profile için)
selected_profile_url = profile_url if profile_url else ""

# Collaborators veri yapısını başlat
collaborators_data = {
    "total_profiles": 0,
    "status": "scraping",
    "selected_profile": selected_profile_url,
    "collaborator_profiles": []
}

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0")
prefs = {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
    "profile.managed_default_content_settings.fonts": 2,
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
driver.set_window_size(1920, 1080)

try:
    # Profile ID ile URL'i al
    if profile_id and not profile_url:
        profile_url = get_profile_url_by_id(session_id, profile_id)
        if profile_url:
            print(f"[INFO] Profile ID {profile_id} için URL bulundu: {profile_url}", flush=True)
        else:
            print(f"[ERROR] Profile ID {profile_id} için URL bulunamadı!", flush=True)
            sys.exit(1)
    
    # Önce profil sayfasına git
    if profile_url:
        print(f"[INFO] Profil sayfasına gidiliyor: {profile_url}", flush=True)
        driver.get(profile_url)
    else:
        print(f"[INFO] Arama yapılıyor ve ilk profil seçiliyor...", flush=True)
        driver.get(BASE + "AkademikArama/")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "aramaTerim"))
        )
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Tümünü Kabul Et')]"))
            )
            btn.click()
        except:
            pass
        kutu = driver.find_element(By.ID, "aramaTerim")
        kutu.send_keys(target_name)
        driver.find_element(By.ID, "searchButton").click()
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Akademisyenler"))
        ).click()
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "tr[id^='authorInfo_'] a"))
        ).click()

    # Sonra işbirlikçiler sekmesine geç
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[@href='viewAuthorGraphs.jsp']"))
        ).click()
    except Exception as e:
        print(f"[ERROR] İşbirlikçiler sekmesine geçilemedi: {e}", flush=True)
        sys.exit(1)
    
    try:
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "svg g")) > 2
        )
    except Exception as e:
        print(f"[ERROR] İşbirlikçiler grafiği yüklenemedi: {e}", flush=True)
        sys.exit(1)
    
    # Yeni yaklaşım: Sadece mevcut sayfada bulunan bilgileri kullan
    print(f"[INFO] İşbirlikçi grafiğinden bilgiler çekiliyor...", flush=True)
    
    # SVG grafik elementlerinden işbirlikçi bilgilerini al
    script = """
const gs = document.querySelectorAll('svg g');
const results = [];
for (let i = 2; i < gs.length; i++) {
    const g = gs[i];
    const name = g.querySelector('text')?.textContent.trim() || '';
    
    // Her işbirlikçiye tıkla ve pageUrl'den profile_url'yi al
    g.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    const profileUrl = document.getElementById('pageUrl')?.href || '';
    
    // Fotoğraf URL'ini al - SVG image elementinden
    let photoUrl = '';
    const imageElement = g.querySelector('image');
    if (imageElement) {
        // Önce href attribute'unu dene
        photoUrl = imageElement.getAttribute('href') || '';
        // Eğer href yoksa xlink:href'i dene
        if (!photoUrl) {
            photoUrl = imageElement.getAttribute('xlink:href') || '';
        }
        // Eğer hala yoksa, data:image URI olabilir
        if (!photoUrl) {
            photoUrl = imageElement.getAttribute('src') || '';
        }
    }
    
    // Sol paneldeki kurum/fakülte/bölüm bilgilerini al
    let info = '';
    try {
        const detailUniv = document.getElementById('detailUniv');
        if (detailUniv) {
            info = detailUniv.textContent.trim();
        }
    } catch (e) {
        // Bilgi alınamadıysa boş bırak
    }
    
    results.push({ 
        name: name, 
        profile_url: profileUrl,
        photo_url: photoUrl,
        info: info
    });
}
return results;
"""
    isimler_ve_linkler = driver.execute_script(script)
    
    for idx, obj in enumerate(isimler_ve_linkler, start=1):
        isim = obj['name']
        profile_url = obj['profile_url']
        photo_url = obj['photo_url']
        info = obj['info']
        
        # author_id'yi profile_url'den çıkar
        author_id = extract_author_id_from_url(profile_url)
        
        # Bilgi kontrolü
        deleted = False
        
        if not profile_url:
            photo_url = DEFAULT_PHOTO_URL
            deleted = True
            info = "Profil bulunamadı"
        else:
            # Fotoğraf URL'i yoksa veya boşsa default kullan
            if not photo_url or photo_url.strip() == "":
                photo_url = DEFAULT_PHOTO_URL
            # Eğer data:image URI varsa, bunu kullan
            elif photo_url.startswith('data:image'):
                # Base64 encoded image, bunu kullan
                pass
            # Eğer relative URL varsa, base URL ile birleştir
            elif photo_url.startswith('/'):
                photo_url = BASE + photo_url.lstrip('/')
            
            # Info boşsa sadece isim kullan
            if not info:
                info = isim
        
        # Collaborator profilini ekle
        collaborator_profile = {
            "author_id": author_id,
            "name": isim,
            "info": info,
            "photo_url": photo_url,
            "profile_url": profile_url if not deleted else "",
            "status": "completed"
        }
        
        collaborators_data["collaborator_profiles"].append(collaborator_profile)
        collaborators_data["total_profiles"] = len(collaborators_data["collaborator_profiles"])
        
        # collaborators.json dosyasını yaz
        print(f"[DEBUG] collaborators.json güncelleniyor: {collaborators_json_path}", flush=True)
        with open(collaborators_json_path, "w", encoding="utf-8") as f:
            json.dump(collaborators_data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        print(f"[INFO] collaborators.json güncellendi ({collaborators_data['total_profiles']} collaborator).", flush=True)
        time.sleep(0.5)  # Progressive loading için kısa bekleme
    
    # Scraping tamamlandığında status'u güncelle
    collaborators_data["status"] = "completed"
    
    # --- DONE dosyasını sadece işbirlikçi varsa ve scraping bittiyse oluştur ---
    if collaborators_data["collaborator_profiles"]:
        # Son kez dosyayı güncelle
        with open(collaborators_json_path, "w", encoding="utf-8") as f:
            json.dump(collaborators_data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Dosya sistemini tamamen senkronize et (Linux/Unix)
        if hasattr(os, "sync"):
            os.sync()
        
        # Absolute path kullan
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(current_dir, "..", "..")
        done_path = os.path.join(project_root, "public", "collaborator-sessions", session_id, "collaborators_done.txt")
        
        with open(done_path, "w") as f:
            f.write("done")
            f.flush()
            os.fsync(f.fileno())
        print(f"[INFO] collaborators_done.txt dosyası oluşturuldu.", flush=True)
        print(f"[INFO] Toplam {collaborators_data['total_profiles']} işbirlikçi bulundu.", flush=True)
finally:
    driver.quit()
