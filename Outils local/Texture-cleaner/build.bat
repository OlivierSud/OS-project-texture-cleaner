@echo off
cd /d "%~dp0"
echo ========================================
echo 2D Texture Listing - Build Script
echo ========================================
echo.

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé ou n'est pas dans le PATH
    echo Veuillez installer Python depuis https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Installation des dépendances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo [ERREUR] Échec de l'installation des dépendances
    pause
    exit /b 1
)

echo.
echo [2/4] Nettoyage des anciens builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

echo.
echo [3/4] Compilation de l'exécutable...
python -m PyInstaller --name="Project-texture-cleaner" ^
    --onefile ^
    --windowed ^
    --icon=icone_final.ico ^
    --add-data="icone_final.ico;." ^
    --add-data="README.md;." ^
    app.py

if errorlevel 1 (
    echo [ERREUR] Échec de la compilation
    pause
    exit /b 1
)

echo.
echo [4/4] Nettoyage...
rmdir /s /q "build"
del /q "*.spec"

echo.
echo ========================================
echo ✅ BUILD TERMINÉ AVEC SUCCÈS !
echo ========================================
echo.
echo L'exécutable se trouve dans le dossier "dist"
echo Fichier: dist\Project-texture-cleaner.exe
echo.
echo Vous pouvez maintenant:
echo 1. Tester l'application: dist\Project-texture-cleaner.exe
echo 2. Déplacer l'exécutable où vous voulez
echo.
pause
