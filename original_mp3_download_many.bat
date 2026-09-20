@echo off
:loop
cls
echo.
echo ==========================================
echo       유튜브 MP3 추출 프로그램 (yt-dlp)
echo ==========================================
echo.

set /p url="다운로드할 유튜브 URL을 입력하세요: "

echo.
echo [추출 시작...] 잠시만 기다려주세요.
yt-dlp.exe -x --audio-format mp3 -o "%%(title)s.%%(ext)s" %url%

echo.
echo [완료!] 파일이 저장되었습니다.
echo.
pause
goto loop
