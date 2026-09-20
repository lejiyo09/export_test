import os
import re
import subprocess
import shutil
import tempfile
import base64
from pathlib import Path
import urllib.request
import urllib.error
from flask import Flask, render_template, request, send_file, jsonify

app = Flask(__name__)

DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", tempfile.gettempdir())) / "youtube_mp3"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return name[:180] or "audio"

def prepare_cookies():
    raw = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if not raw:
        return None, None
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise RuntimeError("YOUTUBE_COOKIES_B64가 올바른 Base64가 아닙니다.") from e
    fd, name = tempfile.mkstemp(prefix="ytcookies_", suffix=".txt")
    os.close(fd)
    cookie_file = Path(name)
    cookie_file.write_bytes(data)
    return str(cookie_file), cookie_file

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

@app.post("/api/search")
def search():
    data = request.get_json(silent=True) or request.form
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify(error="검색어를 입력하세요."), 400
    if len(query) > 120:
        return jsonify(error="검색어가 너무 깁니다."), 400

    ytdlp = find_ytdlp()
    if not ytdlp:
        return jsonify(error="서버에 yt-dlp가 설치되어 있지 않습니다."), 500

    cookie_path, cookie_file = prepare_cookies()
    cmd = [ytdlp, "--flat-playlist", "--dump-single-json", "--no-warnings", "--skip-download", "ytsearch10:" + query]
    if cookie_path:
        cmd[1:1] = ["--cookies", cookie_path]
    if os.environ.get("YTDLP_JS_RUNTIME"):
        cmd[1:1] = ["--js-runtimes", os.environ["YTDLP_JS_RUNTIME"]]
    if os.environ.get("BGUTIL_BASE_URL"):
        cmd[1:1] = ["--extractor-args", f"youtubepot-bgutilhttp:base_url={os.environ['BGUTIL_BASE_URL']}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return jsonify(error="검색 시간이 너무 오래 걸렸습니다."), 504
    finally:
        if cookie_file:
            cookie_file.unlink(missing_ok=True)

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "검색에 실패했습니다.").strip()
        return jsonify(error=err[-2500:]), 500
    try:
        import json
        data = json.loads(result.stdout)
    except Exception:
        return jsonify(error="검색 결과를 읽지 못했습니다."), 500

    items = []
    for e in data.get("entries", []):
        if not e or not e.get("id"):
            continue
        video_id = e["id"]
        items.append({
            "id": video_id,
            "title": e.get("title") or "제목 없음",
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": e.get("duration"),
            "thumbnail": e.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return jsonify(results=items)

@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()

    if not re.match(r"^https?://", url):
        return jsonify(error="올바른 URL을 입력하세요."), 400

    # Primary extractor: self-hosted Cobalt API.
    cobalt_url = os.environ.get("COBALT_URL", "").strip().rstrip("/")
    if cobalt_url:
        try:
            payload = json.dumps({
                "url": url,
                "downloadMode": "audio",
                "audioFormat": "mp3",
                "audioBitrate": "192",
                "filenameStyle": "classic",
                "youtubeBetterAudio": True,
                "localProcessing": "disabled"
            }).encode("utf-8")

            cobalt_req = urllib.request.Request(
                cobalt_url + "/",
                data=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(cobalt_req, timeout=60) as resp:
                info = json.loads(resp.read().decode("utf-8"))

            status = info.get("status")
            if status in ("tunnel", "redirect") and info.get("url"):
                filename = safe_filename(info.get("filename") or "audio.mp3")
                if not filename.lower().endswith(".mp3"):
                    filename += ".mp3"

                fd, name = tempfile.mkstemp(prefix="cobalt_", suffix=".mp3")
                os.close(fd)
                tmp = Path(name)

                try:
                    with urllib.request.urlopen(info["url"], timeout=600) as media:
                        with tmp.open("wb") as f:
                            shutil.copyfileobj(media, f)

                    response = send_file(
                        tmp,
                        as_attachment=True,
                        download_name=filename,
                        mimetype="audio/mpeg",
                    )

                    @response.call_on_close
                    def cleanup_cobalt():
                        tmp.unlink(missing_ok=True)

                    return response
                except Exception:
                    tmp.unlink(missing_ok=True)
                    raise

            if status == "error":
                err = info.get("error") or {}
                if isinstance(err, dict):
                    code = err.get("code") or "unknown"
                else:
                    code = str(err)
                return jsonify(error=f"Cobalt 추출 실패: {code}"), 502

        except urllib.error.HTTPError as e:
            # Continue to the yt-dlp fallback for transient/internal Cobalt errors.
            if e.code >= 500:
                pass
        except Exception:
            # Continue to the yt-dlp fallback.
            pass

    # Secondary extractor: yt-dlp.
    ytdlp = find_ytdlp()
    ffmpeg = find_ffmpeg()
    if not ytdlp:
        return jsonify(error="서버에 yt-dlp가 설치되어 있지 않습니다."), 500
    if not ffmpeg:
        return jsonify(error="서버에 FFmpeg가 설치되어 있지 않습니다."), 500

    job_dir = Path(tempfile.mkdtemp(prefix="ytmp3_", dir=DOWNLOAD_DIR))
    outtmpl = str(job_dir / "%(title)s.%(ext)s")
    cookie_path, cookie_file = prepare_cookies()

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

    if cookie_path:
        cmd[1:1] = ["--cookies", cookie_path]
    if os.environ.get("YTDLP_JS_RUNTIME"):
        cmd[1:1] = ["--js-runtimes", os.environ["YTDLP_JS_RUNTIME"]]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        if cookie_file:
            cookie_file.unlink(missing_ok=True)
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error="변환 시간이 너무 오래 걸려 중단했습니다."), 504

    if result.returncode != 0:
        if cookie_file:
            cookie_file.unlink(missing_ok=True)
        err = (result.stderr or result.stdout or "변환에 실패했습니다.").strip()
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error=err[-2500:]), 500

    files = list(job_dir.glob("*.mp3"))
    if not files:
        if cookie_file:
            cookie_file.unlink(missing_ok=True)
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error="MP3 파일을 찾지 못했습니다."), 500

    path = files[0]
    response = send_file(
        path,
        as_attachment=True,
        download_name=path.name,
        mimetype="audio/mpeg",
    )

    @response.call_on_close
    def cleanup():
        if cookie_file:
            cookie_file.unlink(missing_ok=True)
        shutil.rmtree(job_dir, ignore_errors=True)

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
