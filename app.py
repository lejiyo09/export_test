import os
import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify

app = Flask(__name__)

DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", tempfile.gettempdir())) / "youtube_mp3"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return name[:180] or "audio"

def find_ytdlp():
    # Prefer an installed yt-dlp, then the supplied source tree.
    candidates = [
        os.environ.get("YT_DLP_BIN", ""),
        "yt-dlp",
        str(Path(__file__).parent / "yt-dlp-master" / "yt-dlp"),
    ]
    for c in candidates:
        if c and (Path(c).exists() or shutil_which(c)):
            return c
    return None

def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)

def find_ffmpeg():
    import shutil
    candidates = [
        os.environ.get("FFMPEG_BIN", ""),
        "ffmpeg",
        str(Path(__file__).parent / "ffmpeg.exe"),
    ]
    for c in candidates:
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    return None

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()

    if not re.match(r"^https?://", url):
        return jsonify(error="올바른 URL을 입력하세요."), 400

    ytdlp = find_ytdlp()
    ffmpeg = find_ffmpeg()
    if not ytdlp:
        return jsonify(error="서버에 yt-dlp가 설치되어 있지 않습니다."), 500
    if not ffmpeg:
        return jsonify(error="서버에 FFmpeg가 설치되어 있지 않습니다."), 500

    job_dir = Path(tempfile.mkdtemp(prefix="ytmp3_", dir=DOWNLOAD_DIR))
    outtmpl = str(job_dir / "%(title)s.%(ext)s")

    cmd = [
        ytdlp,
        "--no-playlist",
        "--no-warnings",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--ffmpeg-location", str(Path(ffmpeg).parent),
        "-o", outtmpl,
        url,
    ]

    # yt-dlp may use an external JS runtime for some sites.
    if os.environ.get("YTDLP_JS_RUNTIME"):
        cmd[1:1] = ["--js-runtimes", os.environ["YTDLP_JS_RUNTIME"]]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error="변환 시간이 너무 오래 걸려 중단했습니다."), 504

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "변환에 실패했습니다.").strip()
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error=err[-2500:]), 500

    files = list(job_dir.glob("*.mp3"))
    if not files:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error="MP3 파일을 찾지 못했습니다."), 500

    path = files[0]
    response = send_file(path, as_attachment=True, download_name=path.name, mimetype="audio/mpeg")

    @response.call_on_close
    def cleanup():
        shutil.rmtree(job_dir, ignore_errors=True)

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
