# -*- coding: utf-8 -*-
"""
Modulo de Mensajes Internos
- Sistema de mensajeria interna entre usuarios del sistema
- Bandeja de entrada y enviados con paginacion
- Vinculacion opcional a alertas, solicitudes y facturas
- API para conteo de mensajes no leidos (badge en navbar)
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime
from database import execute_query
from auth import (
    login_required, get_current_user
)
from . import mensajes_bp
import logging

logger = logging.getLogger(__name__)


# ==================== RUTAS DE MENSAJES ====================

@mensajes_bp.route('/')
@login_required
def bandeja_entrada():
    """Bandeja de entrada - mensajes recibidos por el usuario actual"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)

    per_page = current_app.config['ITEMS_PER_PAGE']
    offset = (page - 1) * per_page

    # Total de mensajes recibidos
    total = execute_query(
        "SELECT COUNT(*) as count FROM mensajes_internos WHERE destinatario_id = %s",
        (user['id'],), fetch_one=True
    )['count']

    # Obtener mensajes con datos del remitente
    mensajes = execute_query("""
        SELECT m.*,
               u_rem.nombre_completo as remitente_nombre,
               u_rem.username as remitente_username
        FROM mensajes_internos m
        JOIN usuarios u_rem ON m.remitente_id = u_rem.numero_documento
        WHERE m.destinatario_id = %s
        ORDER BY m.created_at DESC
        LIMIT %s OFFSET %s
    """, (user['id'], per_page, offset), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    return render_template('mensajes/bandeja_entrada.html',
                         mensajes=mensajes,
                         page=page,
                         total_pages=total_pages)


@mensajes_bp.route('/enviados')
@login_required
def mensajes_enviados():
    """Lista de mensajes enviados por el usuario actual"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)

    per_page = current_app.config['ITEMS_PER_PAGE']
    offset = (page - 1) * per_page

    # Total de mensajes enviados
    total = execute_query(
        "SELECT COUNT(*) as count FROM mensajes_internos WHERE remitente_id = %s",
        (user['id'],), fetch_one=True
    )['count']

    # Obtener mensajes con datos del destinatario
    mensajes = execute_query("""
        SELECT m.*,
               u_dest.nombre_completo as destinatario_nombre,
               u_dest.username as destinatario_username
        FROM mensajes_internos m
        JOIN usuarios u_dest ON m.destinatario_id = u_dest.numero_documento
        WHERE m.remitente_id = %s
        ORDER BY m.created_at DESC
        LIMIT %s OFFSET %s
    """, (user['id'], per_page, offset), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    return render_template('mensajes/enviados.html',
                         mensajes=mensajes,
                         page=page,
                         total_pages=total_pages)


@mensajes_bp.route('/nuevo')
@login_required
def nuevo():
    """Formulario para componer un nuevo mensaje"""
    user = get_current_user()

    # Obtener todos los usuarios activos como posibles destinatarios (excepto el actual)
    usuarios = execute_query("""
        SELECT u.numero_documento as id, u.nombre_completo, u.username, r.nombre as rol_nombre
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.activo = TRUE AND u.numero_documento != %s
        ORDER BY u.nombre_completo ASC
    """, (user['id'],), fetch_all=True)

    # Obtener alertas activas para vincular (opcional)
    alertas = execute_query("""
        SELECT id, tipo_alerta, mensaje
        FROM alertas_inventario
        WHERE estado IN ('NUEVA', 'EN_PROCESO')
        ORDER BY created_at DESC
        LIMIT 50
    """, fetch_all=True)

    # Obtener solicitudes recientes para vincular (opcional)
    solicitudes = execute_query("""
        SELECT id, numero_solicitud, estado
        FROM solicitudes_repuestos
        WHERE estado NOT IN ('ANULADA')
        ORDER BY created_at DESC
        LIMIT 50
    """, fetch_all=True)

    # Obtener facturas recientes para vincular (opcional)
    facturas = execute_query("""
        SELECT id, numero_factura, estado
        FROM facturas
        ORDER BY created_at DESC
        LIMIT 50
    """, fetch_all=True) or []

    # Pre-rellenar destinatario si viene por parametro
    destinatario_id = request.args.get('destinatario_id')
    alerta_id = request.args.get('alerta_id', type=int)
    solicitud_id = request.args.get('solicitud_id', type=int)
    factura_id = request.args.get('factura_id', type=int)

    return render_template('mensajes/form.html',
                         usuarios=usuarios,
                         alertas=alertas,
                         solicitudes=solicitudes,
                         facturas=facturas,
                         destinatario_id=destinatario_id,
                         alerta_id=alerta_id,
                         solicitud_id=solicitud_id,
                         factura_id=factura_id)


@mensajes_bp.route('/enviar', methods=['POST'])
@login_required
def enviar():
    """Enviar un nuevo mensaje interno"""
    user = get_current_user()

    try:
        destinatario_id = request.form.get('destinatario_id', '').strip() or None
        asunto = request.form.get('asunto', '').strip()
        mensaje = request.form.get('mensaje', '').strip()
        alerta_id = request.form.get('alerta_id', type=int) or None
        solicitud_id = request.form.get('solicitud_id', type=int) or None
        factura_id = request.form.get('factura_id', type=int) or None

        # Validaciones
        if not destinatario_id:
            flash('Debe seleccionar un destinatario', 'warning')
            return redirect(url_for('mensajes.nuevo'))

        if not asunto:
            flash('El asunto es obligatorio', 'warning')
            return redirect(url_for('mensajes.nuevo'))

        if not mensaje:
            flash('El mensaje no puede estar vacio', 'warning')
            return redirect(url_for('mensajes.nuevo'))

        # Verificar que el destinatario existe y esta activo
        destinatario = execute_query(
            "SELECT numero_documento as id, nombre_completo FROM usuarios WHERE numero_documento = %s AND activo = TRUE",
            (destinatario_id,), fetch_one=True
        )

        if not destinatario:
            flash('Destinatario no encontrado o inactivo', 'danger')
            return redirect(url_for('mensajes.nuevo'))

        # No permitir enviarse mensajes a si mismo
        if destinatario_id == user['id']:
            flash('No puede enviarse mensajes a si mismo', 'warning')
            return redirect(url_for('mensajes.nuevo'))

        execute_query("""
            INSERT INTO mensajes_internos
            (remitente_id, destinatario_id, asunto, mensaje, alerta_id, solicitud_id, factura_id, leido)
            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
        """, (
            user['id'], destinatario_id, asunto, mensaje,
            alerta_id, solicitud_id, factura_id
        ), commit=True)

        flash(f'Mensaje enviado exitosamente a {destinatario["nombre_completo"]}', 'success')
        return redirect(url_for('mensajes.bandeja_entrada'))

    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        flash('Error al enviar el mensaje', 'danger')
        return redirect(url_for('mensajes.nuevo'))


@mensajes_bp.route('/<int:id>')
@login_required
def ver_mensaje(id):
    """Ver detalle de un mensaje y marcarlo como leido si es el destinatario"""
    user = get_current_user()

    mensaje = execute_query("""
        SELECT m.*,
               u_rem.nombre_completo as remitente_nombre,
               u_rem.username as remitente_username,
               u_dest.nombre_completo as destinatario_nombre,
               u_dest.username as destinatario_username
        FROM mensajes_internos m
        JOIN usuarios u_rem ON m.remitente_id = u_rem.numero_documento
        JOIN usuarios u_dest ON m.destinatario_id = u_dest.numero_documento
        WHERE m.id = %s
    """, (id,), fetch_one=True)

    if not mensaje:
        flash('Mensaje no encontrado', 'danger')
        return redirect(url_for('mensajes.bandeja_entrada'))

    # Verificar que el usuario es remitente o destinatario
    if mensaje['remitente_id'] != user['id'] and mensaje['destinatario_id'] != user['id']:
        flash('No tiene permisos para ver este mensaje', 'danger')
        return redirect(url_for('mensajes.bandeja_entrada'))

    # Marcar como leido si es el destinatario y no esta leido
    if mensaje['destinatario_id'] == user['id'] and not mensaje['leido']:
        try:
            execute_query("""
                UPDATE mensajes_internos
                SET leido = TRUE, leido_at = NOW()
                WHERE id = %s
            """, (id,), commit=True)
        except Exception as e:
            logger.error(f"Error marcando mensaje como leido: {e}")

    # Obtener datos vinculados si existen
    alerta = None
    solicitud = None
    factura = None

    if mensaje['alerta_id']:
        alerta = execute_query(
            "SELECT id, tipo_alerta, mensaje as alerta_mensaje, nivel_prioridad, estado FROM alertas_inventario WHERE id = %s",
            (mensaje['alerta_id'],), fetch_one=True
        )

    if mensaje['solicitud_id']:
        solicitud = execute_query(
            "SELECT id, numero_solicitud, estado FROM solicitudes_repuestos WHERE id = %s",
            (mensaje['solicitud_id'],), fetch_one=True
        )

    if mensaje['factura_id']:
        factura = execute_query(
            "SELECT id, numero_factura, estado FROM facturas WHERE id = %s",
            (mensaje['factura_id'],), fetch_one=True
        )

    return render_template('mensajes/ver.html',
                         mensaje=mensaje,
                         alerta=alerta,
                         solicitud=solicitud,
                         factura=factura)


# ==================== API ENDPOINTS ====================

@mensajes_bp.route('/api/no-leidos')
@login_required
def api_no_leidos():
    """Retorna el conteo de mensajes no leidos para el badge del navbar"""
    user = get_current_user()

    resultado = execute_query(
        "SELECT COUNT(*) as count FROM mensajes_internos WHERE destinatario_id = %s AND leido = FALSE",
        (user['id'],), fetch_one=True
    )

    return jsonify({
        'no_leidos': resultado['count']
    })
