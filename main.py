import os
import subprocess
import uuid
import shutil
import json
import logging
from datetime import datetime
import time
from typing import Dict
from threading import Lock

from fastapi import FastAPI
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import BackgroundTasks
from fastapi.responses import FileResponse

from utils import sanitize_filename, empty_folder, check_or_create_folder


def setup_logger(timestamp: str, file='playlist_log.log') -> logging.Logger:
    log_file = file.replace(".", f"_{timestamp}.")
    # Ellenőrizzük, hogy létezik-e a logs mappa
    log_dir = 'logs'
    check_or_create_folder(folder_name=log_dir)

    log_path = os.path.join(log_dir, log_file)

    # Logger konfigurálása
    logger = logging.getLogger('playlister')
    logger.setLevel(logging.INFO)

    # Fájl handler hozzáadása
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Konzol handler hozzáadása
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Handlerek hozzáadása a loggerhez
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Timestamp generálása a fájlnévhez (yyyyMMddhhmm formátumban)
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
start_time = time.time()

# Logger létrehozása
logger = setup_logger(timestamp=timestamp)

logger.info(f"App setup indítása, kezdés: {timestamp}")

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DOWNLOAD_DIR = "playlists"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

progress_data: Dict[str, Dict] = {}
progress_lock = Lock()

app_setup_end_time = time.time()
app_setup_elapsed_time = app_setup_end_time - start_time
logger.info(
    f"App setup kész, időtartam: {app_setup_elapsed_time:.2f} másodperc")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/download", response_class=HTMLResponse)
async def download_playlist(request: Request, playlist_url: str = Form(...), background_tasks: BackgroundTasks = None):
    task_id = str(uuid.uuid4())
    playlist_info = get_playlist_metadata(playlist_url)
    playlist_title = sanitize_filename(
        logger, playlist_info.get("title", "unnamed_playlist"))

    background_tasks.add_task(
        run_download, logger, playlist_url, task_id, playlist_info)

    return templates.TemplateResponse("progress.html", {
        "request": request,
        "task_id": task_id,
        "download_zip_file": f"{playlist_title}.zip"
    })


@app.get("/progress/{task_id}")
async def get_progress(task_id: str, download_zip_file: str | None = None):
    with progress_lock:
        data = progress_data.get(task_id, {})
    return data


@app.get("/download-zip/{file_path}")
async def download_zip(file_path: str):
    # , filename='downloaded_file.zip')
    file_path_extended = f"{DOWNLOAD_DIR}/{file_path}"
    return FileResponse(file_path_extended, media_type='application/zip', filename=file_path)


def run_download(logger: logging.Logger, playlist_url: str, task_id: str, playlist_info):
    try:
        main_start_time = time.time()
        total = len(playlist_info["entries"])
        raw_title = playlist_info.get("title", "unnamed_playlist")
        playlist_title = sanitize_filename(logger, raw_title)
        logger.info(
            f"Downloading playlist: {playlist_title} started with {total} videos")
        folder_name = os.path.join(DOWNLOAD_DIR, playlist_title)
        os.makedirs(folder_name, exist_ok=True)
        empty_folder(logger, folder_name=folder_name)

        # Init progress
        with progress_lock:
            progress_data[task_id] = {
                "total": total, "downloaded": 0, "done": False}

        # Download each video individually so we can track progress
        for index, entry in enumerate(playlist_info["entries"], start=1):
            start_time = time.time()
            logger.info(
                f"{total}/{index}: Downloading video {playlist_title}/{entry['title']} -- ({entry['id']})")
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
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(
                f"{total}/{index}: Downloaded video {playlist_title}/{entry['title']} -- ({entry['id']}), időtartam: {elapsed_time:.2f} másodperc")

        with progress_lock:
            progress_data[task_id]["done"] = True
            zip_start_time = time.time()
            logger.info(f"Zipping {DOWNLOAD_DIR}/{playlist_title}")
            shutil.make_archive(
                f"{DOWNLOAD_DIR}/{playlist_title}", "zip", folder_name)
            zip_end_time = time.time()
            zip_elapsed_time = zip_end_time - zip_start_time
            logger.info(
                f"Zipping {DOWNLOAD_DIR}/{playlist_title} done, időtartam: {zip_elapsed_time:.2f} másodperc")

            main_end_time = time.time()
            elapsed_time = main_end_time - main_start_time
            logger.info(
                f"Downloading playlist: {playlist_title} finished, időtartam: {elapsed_time:.2f} másodperc")

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


def get_playlist_metadata(playlist_url: str):
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

        playlist_info = json.loads(result.stdout)
    except Exception as e:
        print(e)
    return playlist_info
