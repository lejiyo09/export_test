# 크롬북용 YouTube → MP3 웹 변환기

크롬북에서 Windows `.bat` 파일을 실행하지 않고 브라우저로 사용하는 구조입니다.

## 구조
ChromeOS 브라우저 → Flask 서버 → yt-dlp + FFmpeg → MP3 다운로드

## Codespaces에서 실행
```bash
pip install -r requirements.txt
sudo apt-get update && sudo apt-get install -y ffmpeg nodejs
export YTDLP_JS_RUNTIME=node
python app.py
```

Codespaces에서는 포트 8080을 Public으로 열어 브라우저에서 접속하세요.

## Render 배포
이 프로젝트를 GitHub 저장소에 올린 뒤 Render에서 Docker Web Service로 배포할 수 있습니다.
Dockerfile이 FFmpeg와 Node.js를 설치합니다.

주의: YouTube 등 서비스의 약관 및 저작권을 준수하고, 다운로드 권한이 있는 콘텐츠에만 사용하세요.
