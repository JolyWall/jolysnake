@echo off
REM Rebuild static bundle and publish to GitHub Pages.
REM Run from project root.

setlocal
chcp 65001 > nul
set PYTHONUTF8=1
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

echo === [1/5] Building static bundle via pygbag ===
"%HERE%\.venv\Scripts\python.exe" -m pygbag --build --disable-sound-format-error "%HERE%"
if errorlevel 1 goto :err

echo === [2/5] Copying build\web to docs ===
if exist "%HERE%\docs" rmdir /S /Q "%HERE%\docs"
xcopy /E /I /Y "%HERE%\build\web" "%HERE%\docs" > nul
if errorlevel 1 goto :err

echo === [3/5] Patching index.html (mobile fixes) ===
"%HERE%\.venv\Scripts\python.exe" "%HERE%\patch_html.py" "%HERE%\docs\index.html"
if errorlevel 1 goto :err

echo === [4/5] Commit ===
git add docs main.py game.py render.py config.py effects.py assets pygbag.ini patch_html.py
git commit -m "Update web build"

echo === [5/5] Push ===
git push

echo.
echo Done. Game at https://jolywall.github.io/jolysnake/
goto :eof

:err
echo Build failed.
exit /b 1
