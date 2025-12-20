import os, uuid, shutil, zipfile, subprocess, requests, sys
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()

# CORS для работы с расширением
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = "workdir"
os.makedirs(BASE, exist_ok=True)

class Item(BaseModel):
    url: str
    date: int

class Dump(BaseModel):
    voices: List[Item]
    videos: List[Item]

def find_ffmpeg():
    """Ищет ffmpeg в разных локациях"""
    # 1. Проверяем в PATH
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    
    # 2. Проверяем рядом с Python (для Electron)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Возможные пути для упакованного приложения
    possible_paths = [
        os.path.join(base_path, "ffmpeg", "ffmpeg.exe"),
        os.path.join(base_path, "..", "ffmpeg", "ffmpeg.exe"),
        os.path.join(os.path.dirname(sys.executable), "..", "ffmpeg", "ffmpeg.exe"),
        os.path.join(os.path.dirname(sys.executable), "..", "..", "ffmpeg", "ffmpeg.exe"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

# Находим ffmpeg при старте
FFMPEG_PATH = find_ffmpeg()
if not FFMPEG_PATH:
    print("WARNING: ffmpeg not found! Voice messages will not be converted.")

def download(url, path):
    """Скачивает файл с повторными попытками"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to download {url}: {e}")
                return False
            continue
    return False

def convert_audio(input_path, output_path):
    """Конвертирует OGG в MP3 с помощью ffmpeg"""
    if not FFMPEG_PATH:
        return False
    
    try:
        cmd = [FFMPEG_PATH, "-y", "-i", input_path, "-acodec", "libmp3lame", "-ab", "128k", output_path]
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"Conversion error: {e}")
        return False

@app.get("/health")
def health_check():
    """Проверка работоспособности сервера"""
    return {
        "status": "ok",
        "ffmpeg": FFMPEG_PATH is not None,
        "ffmpeg_path": FFMPEG_PATH
    }

@app.post("/dump")
def dump(data: Dump):
    if not data.voices and not data.videos:
        raise HTTPException(status_code=400, detail="No media files provided")
    
    job = str(uuid.uuid4())
    root = os.path.join(BASE, job)
    vdir = os.path.join(root, "voices")
    mdir = os.path.join(root, "videos")
    
    try:
        os.makedirs(vdir, exist_ok=True)
        os.makedirs(mdir, exist_ok=True)

        # Обработка голосовых
        for i, v in enumerate(data.voices):
            ogg = os.path.join(vdir, f"{v.date}_{i}.ogg")
            mp3 = ogg.replace(".ogg", ".mp3")
            
            if not download(v.url, ogg):
                print(f"Skipping voice {i} - download failed")
                continue
            
            # Пытаемся конвертировать, если не получилось - оставляем OGG
            if FFMPEG_PATH:
                if convert_audio(ogg, mp3):
                    os.remove(ogg)
                else:
                    print(f"Keeping OGG format for voice {i}")
            else:
                print(f"Keeping OGG format (ffmpeg not found)")

        # Обработка видео
        for i, v in enumerate(data.videos):
            mp4 = os.path.join(mdir, f"{v.date}_{i}.mp4")
            if not download(v.url, mp4):
                print(f"Skipping video {i} - download failed")
                continue

        # Создаем ZIP
        zip_path = os.path.join(BASE, f"{job}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root_dir, _, files in os.walk(root):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    arcname = os.path.relpath(full_path, root)
                    z.write(full_path, arcname)

        # Удаляем временные файлы
        shutil.rmtree(root)
        
        return FileResponse(
            zip_path, 
            filename=f"vk_media_dump_{job[:8]}.zip",
            media_type="application/zip"
        )
    
    except Exception as e:
        # Очищаем в случае ошибки
        if os.path.exists(root):
            shutil.rmtree(root)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print(f"FFmpeg path: {FFMPEG_PATH}")
    uvicorn.run(app, host="127.0.0.1", port=8765)
