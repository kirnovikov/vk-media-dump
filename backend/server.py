import os, uuid, shutil, zipfile, subprocess, requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        for c in r.iter_content(8192):
            f.write(c)

@app.post("/dump")
def dump(data: Dump):
    job = str(uuid.uuid4())
    root = os.path.join(BASE, job)
    vdir = os.path.join(root, "voices")
    mdir = os.path.join(root, "videos")
    os.makedirs(vdir)
    os.makedirs(mdir)

    for i, v in enumerate(data.voices):
        ogg = f"{vdir}/{v.date}_{i}.ogg"
        mp3 = ogg.replace(".ogg", ".mp3")
        download(v.url, ogg)
        subprocess.run(["ffmpeg", "-y", "-i", ogg, mp3], check=True)
        os.remove(ogg)

    for i, v in enumerate(data.videos):
        download(v.url, f"{mdir}/{v.date}_{i}.mp4")

    zip_path = f"{BASE}/{job}.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        for r, _, f in os.walk(root):
            for file in f:
                full = os.path.join(r, file)
                z.write(full, os.path.relpath(full, root))

    shutil.rmtree(root)
    return FileResponse(zip_path, filename="vk_media_dump.zip")
