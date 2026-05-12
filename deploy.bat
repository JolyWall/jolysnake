@echo off
REM Rebuild static bundle and publish to GitHub Pages.
REM Run from project root.

setlocal enabledelayedexpansion
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

echo === [3/5] Patching index.html (touch scroll, canvas size) ===
powershell -NoProfile -Command ^
  "$p='%HERE%\docs\index.html';" ^
  "$c=Get-Content $p -Raw -Encoding UTF8;" ^
  "$css='    <style>html,body{margin:0;padding:0;overflow:hidden;overscroll-behavior:none;touch-action:none;height:100%%;width:100%%;-webkit-user-select:none;user-select:none}canvas{touch-action:none !important}canvas.emscripten{position:fixed !important;top:50%% !important;left:50%% !important;transform:translate(-50%%,-50%%) !important;width:min(100vw,calc(100vh * 672 / 728)) !important;height:min(100vh,calc(100vw * 728 / 672)) !important;z-index:5 !important}</style>'+[char]10+'</head>';" ^
  "$js='<script>document.addEventListener(''touchmove'',function(e){e.preventDefault()},{passive:false});document.addEventListener(''gesturestart'',function(e){e.preventDefault()},{passive:false});document.addEventListener(''dblclick'',function(e){e.preventDefault()},{passive:false});</script>'+[char]10+'</body>';" ^
  "if ($c -notmatch 'touch-action: none') { $c = $c -replace '</head>', $css };" ^
  "if ($c -notmatch 'touchmove.*preventDefault') { $c = $c -replace '</body>', $js };" ^
  "[System.IO.File]::WriteAllText($p,$c,[System.Text.UTF8Encoding]::new($false))"
if errorlevel 1 goto :err

echo === [4/5] Commit ===
git add docs main.py game.py render.py config.py effects.py assets pygbag.ini
git commit -m "Update web build"

echo === [5/5] Push ===
git push

echo.
echo Done. Game at https://jolywall.github.io/jolysnake/
goto :eof

:err
echo Build failed.
exit /b 1
