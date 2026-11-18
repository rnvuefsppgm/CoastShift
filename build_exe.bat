@echo off
REM Compila o CoastShift em um executável único para Windows 10/11 (64 bits).
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean CoastShift.spec
echo Executavel em dist\CoastShift.exe
