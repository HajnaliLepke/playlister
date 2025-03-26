import os
import subprocess
import uuid
import shutil
from typing import Dict
from threading import Lock

from fastapi import FastAPI
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import BackgroundTasks

from utils import sanitize_filename, empty_folder

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DOWNLOAD_DIR = "playlists"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

progress_data: Dict[str, Dict] = {}
progress_lock = Lock()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/download", response_class=HTMLResponse)
async def download_playlist(request: Request, playlist_url: str = Form(...), background_tasks: BackgroundTasks = None):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_download, playlist_url, task_id)

    return templates.TemplateResponse("progress.html", {
        "request": request,
        "task_id": task_id
    })


@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    with progress_lock:
        data = progress_data.get(task_id, {})
    return data


def run_download(playlist_url: str, task_id: str):
    try:
        # Step 1: Get playlist metadata using yt-dlp with --flat-playlist and -J
        metadata_cmd = [
            "yt-dlp",
            "-J",  # Dump JSON
            "--flat-playlist",
            playlist_url
        ]
        result = subprocess.run(metadata_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception("Failed to get playlist info:\n" +
                            result.stderr.strip())

        import json
        playlist_info = json.loads(result.stdout)
        total = len(playlist_info["entries"])
        raw_title = playlist_info.get("title", "unnamed_playlist")
        playlist_title = sanitize_filename(raw_title)
        folder_name = os.path.join(DOWNLOAD_DIR, playlist_title)
        os.makedirs(folder_name, exist_ok=True)
        empty_folder(folder_name=folder_name)

        # Init progress
        with progress_lock:
            progress_data[task_id] = {
                "total": total, "downloaded": 0, "done": False}

        # Download each video individually so we can track progress
        for index, entry in enumerate(playlist_info["entries"], start=1):
            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            subprocess.run([
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "-o", f"{folder_name}/%(title)s.%(ext)s",
                video_url
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            with progress_lock:
                progress_data[task_id]["downloaded"] = index

        with progress_lock:
            progress_data[task_id]["done"] = True
            shutil.make_archive(
                f"{DOWNLOAD_DIR}/{playlist_title}", "zip", folder_name)

    except Exception as e:
        with progress_lock:
            progress_data[task_id] = {"error": str(e), "done": True}

        # # Step 2: Download the playlist into that folder
        # download_cmd = [
        #     "yt-dlp",
        #     # If you want then index of the number
        #     # "-o", f"{folder_name}/%(playlist_index)s - %(title)s.%(ext)s",

        #     "-o", f"{folder_name}/%(title)s.%(ext)s",
        #     # "-f", "bestvideo+bestaudio/best",
        #     "--yes-playlist",
        #     "--extract-audio",
        #     "--audio-format", "mp3",
        #     playlist_url
        # ]
