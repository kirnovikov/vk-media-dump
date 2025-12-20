import os, uuid, shutil, zipfile, subprocess, requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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

def download(url, path):
    """Скачивает файл с таймаутом и обработкой ошибок"""
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False

@app.post("/dump")
def dump(data: Dump):
    """Создаёт ZIP-архив с медиафайлами"""
    if not data.voices and not data.videos:
        raise HTTPException(status_code=400, detail="No media files provided")
    
    job = str(uuid.uuid4())
    root = os.path.join(BASE, job)
    vdir = os.path.join(root, "voices")
    mdir = os.path.join(root, "videos")
    
    try:
        os.makedirs(vdir, exist_ok=True)
        os.makedirs(mdir, exist_ok=True)

        # Скачиваем голосовые и конвертируем в MP3
        for i, v in enumerate(data.voices):
            ogg = f"{vdir}/{v.date}_{i}.ogg"
            mp3 = ogg.replace(".ogg", ".mp3")
            
            if download(v.url, ogg):
                try:
                    # Конвертируем OGG в MP3
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", ogg, "-q:a", "2", mp3], 
                        check=True,
                        capture_output=True,
                        timeout=60
                    )
                    os.remove(ogg)
                except subprocess.CalledProcessError as e:
                    logger.error(f"FFmpeg conversion failed: {e}")
                    # Если конвертация не удалась, оставляем OGG
                except subprocess.TimeoutExpired:
                    logger.error(f"FFmpeg timeout for {ogg}")
            else:
                logger.warning(f"Failed to download voice: {v.url}")

        # Скачиваем видео
        for i, v in enumerate(data.videos):
            output = f"{mdir}/{v.date}_{i}.mp4"
            if not download(v.url, output):
                logger.warning(f"Failed to download video: {v.url}")

        # Создаём ZIP-архив
        zip_path = f"{BASE}/{job}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for r, _, files in os.walk(root):
                for file in files:
                    full = os.path.join(r, file)
                    arcname = os.path.relpath(full, root)
                    z.write(full, arcname)

        # Удаляем временные файлы
        shutil.rmtree(root)
        
        # Возвращаем архив и удаляем его после отправки
        return FileResponse(
            zip_path, 
            filename="vk_media_dump.zip",
            background=lambda: os.remove(zip_path) if os.path.exists(zip_path) else None
        )
        
    except Exception as e:
        # Очищаем при ошибке
        if os.path.exists(root):
            shutil.rmtree(root)
        logger.error(f"Error processing dump: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    """Проверка работоспособности сервера"""
    return {"status": "ok", "ffmpeg": shutil.which("ffmpeg") is not None}
