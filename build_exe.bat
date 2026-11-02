@echo off
setlocal
cd /d "%~dp0"

REM Genera dist\PrisDrop\PrisDrop.exe (carpeta lista para copiar a otro PC)
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --noconsole --specpath build --name PrisDrop --icon "..\PrisDrop-Logo.ico" --add-data "..\PrisDrop-Logotipo.svg;." --add-data "..\PrisDrop-Logo.svg;." --add-data "..\LICENSE;." --add-data "..\NOTICES.txt;." --add-data "..\LEGAL_DISCLAIMER.txt;." main.py
if errorlevel 1 goto :error
if not exist "dist\PrisDrop\PrisDrop.exe" goto :missing
copy /Y "LICENSE" "dist\PrisDrop\LICENSE" >nul
if errorlevel 1 goto :distribution_files_missing
copy /Y "NOTICES.txt" "dist\PrisDrop\NOTICES.txt" >nul
if errorlevel 1 goto :distribution_files_missing
copy /Y "LEGAL_DISCLAIMER.txt" "dist\PrisDrop\LEGAL_DISCLAIMER.txt" >nul
if errorlevel 1 goto :distribution_files_missing

echo.
echo Compilacion completada: "%CD%\dist\PrisDrop\PrisDrop.exe"
pause
exit /b 0

:missing
echo.
echo ERROR: PyInstaller termino sin errores, pero no se encontro dist\PrisDrop\PrisDrop.exe.
pause
exit /b 1

:distribution_files_missing
echo.
echo ERROR: No se pudieron copiar los documentos legales junto a PrisDrop.exe.
pause
exit /b 1

:error
echo.
echo ERROR: Fallo la instalacion de dependencias o la compilacion. Revisa el mensaje anterior.
pause
exit /b 1
