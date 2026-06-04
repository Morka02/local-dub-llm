@echo off
setlocal enabledelayedexpansion
title Local Dub LLM v1

REM ===========================================================================
REM  dub.bat - drag a video onto this file, OR run it and paste a path.
REM
REM  The path can be:
REM    * a VIDEO FILE   -> runs the whole job, or
REM    * a CHUNK FOLDER -> resumes: keeps finished parts, dubs only the rest.
REM
REM  Live progress shows in this window. Dubbing runs fully in parallel.
REM ===========================================================================

cd /d "%~dp0"

echo.
echo  ============================================================
echo    LOCAL DUB LLM v1                       voice cloning ON
echo  ============================================================
echo.

REM If something was dragged onto the .bat, use it. Otherwise prompt.
set "INPUT=%~1"
if "%INPUT%"=="" (
    echo   Paste a VIDEO FILE path to start a new job,
    echo   OR a CHUNK FOLDER path to resume an unfinished one.
    echo.
    set /p "INPUT=  File or chunk folder: "
)

REM Strip surrounding quotes if the user pasted them
set "INPUT=!INPUT:"=!"

REM Is the input a web link (YouTube / URL) instead of a local path?
set "ISURL="
echo !INPUT!| findstr /I /B "http" >nul && set "ISURL=1"

if not defined ISURL if not exist "!INPUT!" (
    echo.
    echo   [X] Not found:
    echo       !INPUT!
    echo.
    pause
    exit /b 1
)

echo.
echo   --- Settings ------------------------------------------------
echo   (press Enter to accept the [default] shown in brackets)
echo.

set "SRC=Hindi"
set "TGT=English"
set /p "SRC=  Source language [!SRC!]: "
set /p "TGT=  Target language [!TGT!]: "

echo.
echo   Genre options:  monologue  podcast  ott_movie_sequence
echo                   advertisement  edtech  academic_lecture_formal
echo   Tip: ott_movie_sequence often preserves voice character best.
set "GENRE=monologue"
set /p "GENRE=  Genre [!GENRE!]: "

set "SPEAKERS=1"
set /p "SPEAKERS=  Number of speakers [!SPEAKERS!]: "

set "OUTDIR=%USERPROFILE%\Downloads\Dubs"
set /p "OUTDIR=  Output folder [!OUTDIR!]: "
set "OUTDIR=!OUTDIR:"=!"

echo.
echo   --- Speed ---------------------------------------------------
echo   Press ENTER for NORMAL mode.
echo   For TURBO MODE (neon, ~300 pieces, all dubbing at once),
echo   type  T  and press Enter.
set "TURBO="
set /p "SPEED=  Mode [Enter = normal / T = turbo]: "
if /I "!SPEED!"=="T" set "TURBO=1"
if /I "!SPEED!"=="TURBO" set "TURBO=1"
if "!SPEED!"=="3" set "TURBO=1"
if defined TURBO echo   ^>^>^> TURBO MODE ON ^<^<^<

echo.
echo   --- Summary -------------------------------------------------
echo     Input   : !INPUT!
echo     Dubbing : !SRC! -^> !TGT!   genre=!GENRE!   speakers=!SPEAKERS!
echo     Output  : !OUTDIR!
echo     Mode    : file = new job   /   folder = resume remaining
if defined TURBO (echo     Speed   : TURBO MODE ON) else (echo     Speed   : normal)
echo     Voice   : cloned from the original speaker
echo.
echo   Starting... long videos take a while; live progress shows below.
echo   ------------------------------------------------------------
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo   [X] python not found on PATH. Install Python 3.10/3.11 and retry.
    pause
    exit /b 1
)

if defined ISURL (
    where yt-dlp >nul 2>nul || python -m pip install -q yt-dlp
    if defined TURBO (
        python "%~dp0fetch_and_dub.py" "!INPUT!" --src "!SRC!" --target "!TGT!" --genre "!GENRE!" --speakers !SPEAKERS! --dir "!OUTDIR!" --gaming
    ) else (
        python "%~dp0fetch_and_dub.py" "!INPUT!" --src "!SRC!" --target "!TGT!" --genre "!GENRE!" --speakers !SPEAKERS! --dir "!OUTDIR!"
    )
) else if defined TURBO (
    python "%~dp0dub_video.py" "!INPUT!" --src "!SRC!" --target "!TGT!" --genre "!GENRE!" --speakers !SPEAKERS! --dir "!OUTDIR!" --gaming
) else (
    python "%~dp0dub_video.py" "!INPUT!" --src "!SRC!" --target "!TGT!" --genre "!GENRE!" --speakers !SPEAKERS! --dir "!OUTDIR!"
)
set "RC=!errorlevel!"

echo.
echo   ------------------------------------------------------------
if "!RC!"=="0" (
    echo   [OK] FINISHED. Your dubbed video is in:  !OUTDIR!
    start "" "!OUTDIR!"
) else (
    echo   [!] Something went wrong ^(exit code !RC!^). See the messages above.
    echo       Tip: run again and paste the work_*\chunks folder path to
    echo       continue - finished chunks are kept and skipped.
)
echo.
pause
endlocal
