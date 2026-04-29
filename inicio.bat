@echo off
echo ========================================
echo Sistema de Inventario - Taller Automotriz
echo ========================================
echo.

REM Verificar si existe el entorno virtual
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
    echo.
)

echo Activando entorno virtual...
call venv\Scripts\activate.bat
echo.

echo Instalando/Actualizando dependencias...
pip install -r requirements.txt
echo.

echo Iniciando aplicación Flask...
echo La aplicación estará disponible en: http://localhost:5000
echo.
echo Credenciales por defecto:
echo Usuario: admin
echo Contraseña: admin123
echo.
echo Presione Ctrl+C para detener el servidor
echo.

python app.py

pause
