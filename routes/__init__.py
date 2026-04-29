# Módulos de rutas para el Sistema de Inventario de Taller Automotriz
# Cada módulo contiene las rutas relacionadas con una funcionalidad específica

from flask import Blueprint

# Blueprints para cada módulo
solicitudes_bp = Blueprint('solicitudes', __name__, url_prefix='/solicitudes')
facturacion_bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')
alertas_bp = Blueprint('alertas', __name__, url_prefix='/alertas')
reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')
categorias_bp = Blueprint('categorias', __name__, url_prefix='/categorias')
mensajes_bp = Blueprint('mensajes', __name__, url_prefix='/mensajes')
audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

def register_blueprints(app):
    """Registra todos los blueprints en la aplicación"""
    from . import solicitudes
    from . import facturacion
    from . import alertas
    from . import reportes
    from . import categorias
    from . import mensajes
    from . import audit
    
    app.register_blueprint(solicitudes_bp)
    app.register_blueprint(facturacion_bp)
    app.register_blueprint(alertas_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(categorias_bp)
    app.register_blueprint(mensajes_bp)
    app.register_blueprint(audit_bp)
