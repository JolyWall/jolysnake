@echo off
REM Пересборка статики и публикация на GitHub Pages.
REM Запускать из корня проекта, когда хочешь обновить игру на сайте.

setlocal
set PYTHONUTF8=1
set HERE=%~dp0

echo === [1/5] Сборка статики через pygbag ===
"%HERE%.venv\Scripts\python.exe" -m pygbag --build --disable-sound-format-error "%HERE%"
if errorlevel 1 goto :err

echo === [2/5] Копирование build\web в docs ===
if exist "%HERE%docs" rmdir /S /Q "%HERE%docs"
xcopy /E /I /Y "%HERE%build\web" "%HERE%docs" > nul
if errorlevel 1 goto :err

echo === [3/5] Патч index.html: отключаем браузерный скролл на тач ===
powershell -NoProfile -Command ^
  "$p='%HERE%docs\index.html';" ^
  "$c=Get-Content $p -Raw -Encoding UTF8;" ^
  "$css='    <style>html,body{margin:0;padding:0;overflow:hidden;overscroll-behavior:none;touch-action:none;height:100%%;width:100%%;-webkit-user-select:none;user-select:none}canvas{touch-action:none !important}</style>'+[char]10+'</head>';" ^
  "$js='<script>document.addEventListener(''touchmove'',function(e){e.preventDefault()},{passive:false});document.addEventListener(''gesturestart'',function(e){e.preventDefault()},{passive:false});document.addEventListener(''dblclick'',function(e){e.preventDefault()},{passive:false});</script>'+[char]10+'</body>';" ^
  "if ($c -notmatch 'touch-action: none') { $c = $c -replace '</head>', $css };" ^
  "if ($c -notmatch 'touchmove.*preventDefault') { $c = $c -replace '</body>', $js };" ^
  "[System.IO.File]::WriteAllText($p,$c,[System.Text.UTF8Encoding]::new($false))"
if errorlevel 1 goto :err

echo === [4/5] Коммит ===
git add docs main.py game.py render.py config.py effects.py assets pygbag.ini
git commit -m "Update web build"

echo === [5/5] Push ===
git push

echo.
echo Готово. Игра на https://jolywall.github.io/jolysnake/
goto :eof

:err
echo Ошибка. Деплой прерван.
exit /b 1
