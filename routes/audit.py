# -*- coding: utf-8 -*-
"""
Modulo de Auditoria (Audit Log)
- Visualizacion del registro de auditoria del sistema
- Filtros por tipo de cambio, accion, usuario y rango de fechas
- Detalle con comparacion lado a lado de datos anteriores/nuevos
- Historial de acciones por usuario especifico
- Solo accesible por ADMIN y SUPER_USUARIO
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime
from database import execute_query
from auth import (
    login_required, role_required, get_current_user
)
from . import audit_bp
import json
import logging

logger = logging.getLogger(__name__)


# ==================== RUTAS DE AUDITORIA ====================

@audit_bp.route('/')
@login_required
@role_required('ADMINISTRADOR')
def lista_audit():
    """Lista paginada y filtrable del audit log"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)

    # Filtros
    tipo_cambio = request.args.get('tipo_cambio', '')
    accion = request.args.get('accion', '')
    usuario_id = request.args.get('usuario_id', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    search = request.args.get('search', '')

    per_page = 50
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    if tipo_cambio:
        where_clauses.append("a.tipo_cambio = %s")
        params.append(tipo_cambio)

    if accion:
        where_clauses.append("a.accion = %s")
        params.append(accion)

    if usuario_id:
        where_clauses.append("a.usuario_id = %s")
        params.append(usuario_id)

    if fecha_desde:
        where_clauses.append("DATE(a.created_at) >= %s")
        params.append(fecha_desde)

    if fecha_hasta:
        where_clauses.append("DATE(a.created_at) <= %s")
        params.append(fecha_hasta)

    if search:
        where_clauses.append("""
            (a.tabla_afectada LIKE %s OR u.nombre_completo LIKE %s OR u.username LIKE %s)
        """)
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Total de registros
    total = execute_query(f"""
        SELECT COUNT(*) as count
        FROM audit_log a
        JOIN usuarios u ON a.usuario_id = u.numero_documento
        WHERE {where_sql}
    """, tuple(params), fetch_one=True)['count']

    # Obtener registros de auditoria
    params.extend([per_page, offset])
    registros = execute_query(f"""
        SELECT a.id, a.usuario_id, a.tabla_afectada, a.registro_id,
               a.accion, a.tipo_cambio, a.ip_address, a.created_at,
               u.nombre_completo as usuario_nombre,
               u.username as usuario_username
        FROM audit_log a
        JOIN usuarios u ON a.usuario_id = u.numero_documento
        WHERE {where_sql}
        ORDER BY a.created_at DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    # Obtener listas para los filtros
    tipos_cambio = [
        'INVENTARIO', 'USUARIO', 'CLIENTE', 'VEHICULO', 'FACTURA',
        'SOLICITUD', 'ALERTA', 'CONFIGURACION', 'SESION', 'OTRO'
    ]

    acciones = [
        'CREAR', 'ACTUALIZAR', 'ELIMINAR', 'APROBAR', 'RECHAZAR',
        'FACTURAR', 'ANULAR', 'AJUSTE', 'LOGIN', 'LOGOUT'
    ]

    # Obtener usuarios para filtro
    usuarios = execute_query(
        "SELECT DISTINCT u.numero_documento as id, u.nombre_completo FROM usuarios u "
        "JOIN audit_log a ON u.numero_documento = a.usuario_id ORDER BY u.nombre_completo",
        fetch_all=True
    )

    return render_template('audit/lista.html',
                         registros=registros,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         tipo_cambio=tipo_cambio,
                         accion=accion,
                         usuario_id=usuario_id,
                         fecha_desde=fecha_desde,
                         fecha_hasta=fecha_hasta,
                         search=search,
                         tipos_cambio=tipos_cambio,
                         acciones=acciones,
                         usuarios=usuarios)


@audit_bp.route('/<int:id>')
@login_required
@role_required('ADMINISTRADOR')
def detalle_audit(id):
    """Detalle de un registro de auditoria con comparacion de datos"""
    registro = execute_query("""
        SELECT a.*,
               u.nombre_completo as usuario_nombre,
               u.username as usuario_username,
               u.email as usuario_email
        FROM audit_log a
        JOIN usuarios u ON a.usuario_id = u.numero_documento
        WHERE a.id = %s
    """, (id,), fetch_one=True)

    if not registro:
        flash('Registro de auditoria no encontrado', 'danger')
        return redirect(url_for('audit.lista_audit'))

    # Parsear datos JSON para mostrar comparacion lado a lado
    datos_anteriores = None
    datos_nuevos = None
    campos_modificados = None

    try:
        if registro['datos_anteriores']:
            if isinstance(registro['datos_anteriores'], str):
                datos_anteriores = json.loads(registro['datos_anteriores'])
            else:
                datos_anteriores = registro['datos_anteriores']
    except (json.JSONDecodeError, TypeError):
        datos_anteriores = {'raw': str(registro['datos_anteriores'])}

    try:
        if registro['datos_nuevos']:
            if isinstance(registro['datos_nuevos'], str):
                datos_nuevos = json.loads(registro['datos_nuevos'])
            else:
                datos_nuevos = registro['datos_nuevos']
    except (json.JSONDecodeError, TypeError):
        datos_nuevos = {'raw': str(registro['datos_nuevos'])}

    try:
        if registro['campos_modificados']:
            if isinstance(registro['campos_modificados'], str):
                campos_modificados = json.loads(registro['campos_modificados'])
            else:
                campos_modificados = registro['campos_modificados']
    except (json.JSONDecodeError, TypeError):
        campos_modificados = None

    # Si hay datos anteriores y nuevos, generar comparacion de todos los campos
    comparacion = []
    if datos_anteriores and datos_nuevos:
        todos_campos = set(list(datos_anteriores.keys()) + list(datos_nuevos.keys()))
        for campo in sorted(todos_campos):
            valor_anterior = datos_anteriores.get(campo, '---')
            valor_nuevo = datos_nuevos.get(campo, '---')
            modificado = str(valor_anterior) != str(valor_nuevo)
            comparacion.append({
                'campo': campo,
                'anterior': valor_anterior,
                'nuevo': valor_nuevo,
                'modificado': modificado
            })
    elif datos_nuevos:
        for campo, valor in sorted(datos_nuevos.items()):
            comparacion.append({
                'campo': campo,
                'anterior': '---',
                'nuevo': valor,
                'modificado': True
            })
    elif datos_anteriores:
        for campo, valor in sorted(datos_anteriores.items()):
            comparacion.append({
                'campo': campo,
                'anterior': valor,
                'nuevo': '---',
                'modificado': True
            })

    return render_template('audit/detalle.html',
                         registro=registro,
                         datos_anteriores=datos_anteriores,
                         datos_nuevos=datos_nuevos,
                         campos_modificados=campos_modificados,
                         comparacion=comparacion)


@audit_bp.route('/usuario/<string:usuario_id>')
@login_required
@role_required('ADMINISTRADOR')
def acciones_usuario(usuario_id):
    """Historial de acciones realizadas por un usuario especifico"""
    page = request.args.get('page', 1, type=int)

    # Obtener datos del usuario consultado
    usuario = execute_query(
        "SELECT numero_documento as id, nombre_completo, username, email FROM usuarios WHERE numero_documento = %s",
        (usuario_id,), fetch_one=True
    )

    if not usuario:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('audit.lista_audit'))

    per_page = 50
    offset = (page - 1) * per_page

    # Total de acciones del usuario
    total = execute_query(
        "SELECT COUNT(*) as count FROM audit_log WHERE usuario_id = %s",
        (usuario_id,), fetch_one=True
    )['count']

    # Obtener registros
    registros = execute_query("""
        SELECT a.id, a.tabla_afectada, a.registro_id,
               a.accion, a.tipo_cambio, a.ip_address, a.created_at
        FROM audit_log a
        WHERE a.usuario_id = %s
        ORDER BY a.created_at DESC
        LIMIT %s OFFSET %s
    """, (usuario_id, per_page, offset), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    # Resumen de actividad del usuario
    resumen = execute_query("""
        SELECT accion, COUNT(*) as total
        FROM audit_log
        WHERE usuario_id = %s
        GROUP BY accion
        ORDER BY total DESC
    """, (usuario_id,), fetch_all=True)

    # Ultima actividad
    ultima_actividad = execute_query("""
        SELECT created_at
        FROM audit_log
        WHERE usuario_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (usuario_id,), fetch_one=True)

    # Total de logins
    total_logins = execute_query(
        "SELECT COUNT(*) as count FROM audit_log WHERE usuario_id = %s AND accion = 'LOGIN'",
        (usuario_id,), fetch_one=True
    )['count']

    return render_template('audit/usuario.html',
                         usuario=usuario,
                         registros=registros,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         resumen=resumen,
                         ultima_actividad=ultima_actividad,
                         total_logins=total_logins)
