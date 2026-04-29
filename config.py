import os
from datetime import timedelta

class Config:
    """Configuración base de la aplicación"""

    # Configuración de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-super-segura-cambiar-en-produccion'

    # Configuración de base de datos MySQL
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'taller_inventario'
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3307)
    MYSQL_CHARSET = 'utf8mb4'

    # Configuración de sesión
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_INACTIVITY_TIMEOUT = 30  # Minutos de inactividad

    # Configuración de aplicación
    DEBUG = os.environ.get('FLASK_DEBUG') == '1'
    TESTING = False

    # Configuración de paginación
    ITEMS_PER_PAGE = 20

    # Configuración de alertas de inventario
    STOCK_BAJO_THRESHOLD = 0.3
    STOCK_CRITICO_THRESHOLD = 0

    # Configuración de impuestos (IVA en Colombia)
    IVA_PERCENTAGE = 19.0

    # Prefijos para numeración
    PREFIJO_SOLICITUD = 'SOL'
    PREFIJO_FACTURA = 'FAC'

    # Configuración de uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True

class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
