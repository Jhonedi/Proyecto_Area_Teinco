from functools import wraps
from flask import session, redirect, url_for, flash, request
import bcrypt
import json
from database import execute_query

def hash_password(password):
    """Genera un hash de la contraseña"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Verifica si una contraseña coincide con el hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def login_user(username, password):
    """Autentica un usuario"""
    query = """
        SELECT u.numero_documento, u.username, u.nombre_completo, u.email, u.password_hash,
               u.activo, u.es_protegido, r.id as rol_id, r.nombre as rol_nombre
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.username = %s AND u.activo = TRUE
    """

    user = execute_query(query, (username,), fetch_one=True)

    if user and check_password(password, user['password_hash']):
        session['user_id'] = user['numero_documento']
        session['username'] = user['username']
        session['nombre_completo'] = user['nombre_completo']
        session['rol_id'] = user['rol_id']
        session['rol_nombre'] = user['rol_nombre']
        session['es_protegido'] = user['es_protegido']
        # No usar session.permanent para que expire al cerrar navegador

        # Registrar última actividad
        from datetime import datetime
        session['last_activity'] = datetime.now().isoformat()

        # Actualizar última actividad en BD
        try:
            execute_query(
                "UPDATE usuarios SET ultima_actividad = NOW() WHERE numero_documento = %s",
                (user['numero_documento'],), commit=True
            )
        except:
            pass

        # Registrar login en audit log
        try:
            registrar_audit_log(
                usuario_id=user['numero_documento'],
                tabla='usuarios',
                registro_id=user['numero_documento'],
                accion='LOGIN',
                tipo_cambio='SESION',
                datos_nuevos={'username': user['username']}
            )
        except:
            pass

        return {
            'id': user['numero_documento'],
            'username': user['username'],
            'nombre_completo': user['nombre_completo'],
            'email': user['email'],
            'rol_id': user['rol_id'],
            'rol_nombre': user['rol_nombre'],
            'es_protegido': user['es_protegido']
        }

    return None

def logout_user():
    """Cierra la sesión del usuario"""
    user = get_current_user()
    if user:
        try:
            registrar_audit_log(
                usuario_id=user['id'],
                tabla='usuarios',
                registro_id=user['id'],  # user['id'] ya es numero_documento
                accion='LOGOUT',
                tipo_cambio='SESION',
                datos_nuevos={'username': user['username']}
            )
        except:
            pass
    session.clear()

def get_current_user():
    """Obtiene el usuario actual de la sesión"""
    if 'user_id' in session:
        return {
            'id': session['user_id'],
            'username': session['username'],
            'nombre_completo': session['nombre_completo'],
            'rol_id': session['rol_id'],
            'rol_nombre': session['rol_nombre'],
            'es_protegido': session.get('es_protegido', False)
        }
    return None

def is_authenticated():
    """Verifica si hay un usuario autenticado"""
    return 'user_id' in session

# Decoradores para proteger rutas

def login_required(f):
    """Decorador que requiere autenticación para acceder a una ruta"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash('Debe iniciar sesión para acceder a esta página', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Decorador que requiere uno de los roles especificados.
    SUPER_USUARIO siempre tiene acceso."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_authenticated():
                flash('Debe iniciar sesión para acceder a esta página', 'warning')
                return redirect(url_for('login', next=request.url))

            user = get_current_user()
            if user['rol_nombre'] == 'SUPER_USUARIO':
                return f(*args, **kwargs)
            if user['rol_nombre'] not in allowed_roles:
                flash('No tiene permisos para acceder a esta página', 'danger')
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Funciones de verificación de permisos

def can_view_inventory():
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR', 'TECNICO']

def can_edit_inventory():
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA']

def can_create_sales():
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR']

def can_confirm_sales():
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'VENDEDOR']

def can_manage_users():
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR']

def can_view_reports():
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR']

def can_create_requests():
    """Verifica si el usuario puede crear solicitudes de repuestos"""
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA', 'TECNICO']

def can_approve_requests():
    """Verifica si el usuario puede aprobar solicitudes"""
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA']

def can_resolve_alerts():
    """Verifica si el usuario puede resolver alertas"""
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR']

def can_approve_adjustments():
    """Verifica si el usuario puede aprobar ajustes de inventario"""
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] in ['SUPER_USUARIO', 'ADMINISTRADOR']

def is_super_user():
    """Verifica si el usuario es Super Usuario"""
    user = get_current_user()
    if not user:
        return False
    return user['rol_nombre'] == 'SUPER_USUARIO'

def get_permissions():
    """Obtiene los permisos del usuario actual"""
    return {
        'can_view_inventory': can_view_inventory(),
        'can_edit_inventory': can_edit_inventory(),
        'can_create_sales': can_create_sales(),
        'can_confirm_sales': can_confirm_sales(),
        'can_manage_users': can_manage_users(),
        'can_view_reports': can_view_reports(),
        'can_create_requests': can_create_requests(),
        'can_approve_requests': can_approve_requests(),
        'can_resolve_alerts': can_resolve_alerts(),
        'can_approve_adjustments': can_approve_adjustments(),
        'is_super_user': is_super_user()
    }

def registrar_audit_log(usuario_id, tabla, registro_id, accion, tipo_cambio,
                        datos_anteriores=None, datos_nuevos=None, campos_modificados=None):
    """Registra una entrada en el audit log"""
    try:
        from flask import request as flask_request
        ip = flask_request.remote_addr if flask_request else None
        ua = str(flask_request.user_agent) if flask_request else None
    except:
        ip = None
        ua = None

    try:
        execute_query("""
            INSERT INTO audit_log
            (usuario_id, tabla_afectada, registro_id, accion, tipo_cambio,
             datos_anteriores, datos_nuevos, campos_modificados, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            usuario_id, tabla, registro_id, accion, tipo_cambio,
            json.dumps(datos_anteriores, default=str) if datos_anteriores else None,
            json.dumps(datos_nuevos, default=str) if datos_nuevos else None,
            json.dumps(campos_modificados, default=str) if campos_modificados else None,
            ip, ua
        ), commit=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error registrando audit log: {e}")
