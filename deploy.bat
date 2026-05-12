@echo off
REM Пересборка статики и публикация на GitHub Pages.
REM Запускать из корня проекта, когда хочешь обновить игру на сайте.

setlocal
set PYTHONUTF8=1
set HERE=%~dp0

echo === [1/4] Сборка статики через pygbag ===
"%HERE%.venv\Scripts\python.exe" -m pygbag --build --disable-sound-format-error "%HERE%"
if errorlevel 1 goto :err

echo === [2/4] Копирование build\web в docs ===
if exist "%HERE%docs" rmdir /S /Q "%HERE%docs"
xcopy /E /I /Y "%HERE%build\web" "%HERE%docs" > nul
if errorlevel 1 goto :err

echo === [3/4] Коммит ===
git add docs main.py game.py render.py config.py effects.py assets pygbag.ini
git commit -m "Update web build"

echo === [4/4] Push ===
git push

echo Готово. Игра на https://jolywall.github.io/jolysnake/
goto :eof

:err
echo Ошибка. Деплой прерван.
exit /b 1
