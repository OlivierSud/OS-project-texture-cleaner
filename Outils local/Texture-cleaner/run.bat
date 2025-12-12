@echo off
echo ========================================
echo 2D Texture Listing - Lancement
echo ========================================
echo.

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé
    echo Veuillez installer Python depuis https://www.python.org/
    pause
    exit /b 1
)

echo Vérification des dépendances...
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo Installation des dépendances nécessaires...
    python -m pip install -r requirements.txt
)

echo.
echo Lancement de l'application...
python app.py

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application a rencontré une erreur
    pause
)
