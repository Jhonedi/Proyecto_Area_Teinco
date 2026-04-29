# -*- coding: utf-8 -*-
"""
Módulo de Alertas de Inventario (Avanzado)
- Gestión completa del ciclo de vida de alertas: NUEVA -> EN_PROCESO -> RESUELTA -> ARCHIVADA
- Notificaciones personales por usuario con estado de lectura independiente
- Recordatorios diarios automáticos para alertas no resueltas
- Historial completo de cambios de estado con timeline
- API para badge de navbar con conteo de alertas activas
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, date
from database import execute_query
from auth import (
    login_required, role_required, get_current_user,
    can_resolve_alerts, registrar_audit_log
)
from . import alertas_bp
import json
import logging

logger = logging.getLogger(__name__)


# ==================== FUNCIONES AUXILIARES ====================

def verificar_recordatorios_diarios():
    """
    Resetea el estado de lectura de notificaciones para alertas que siguen activas.
    Debe llamarse desde before_request para garantizar recordatorios diarios.

    Lógica: Si una alerta sigue en estado NUEVA o EN_PROCESO y la notificación
    del usuario fue marcada como leída pero el ultimo_recordatorio_enviado es
    anterior a hoy, se resetea leida=FALSE para que el usuario la vuelva a ver.
    """
    try:
        execute_query("""
            UPDATE notificaciones_usuarios nu
            JOIN alertas_inventario ai ON nu.alerta_id = ai.id
            SET nu.leida = FALSE,
                nu.ultimo_recordatorio_enviado = CURDATE()
            WHERE ai.estado IN ('NUEVA', 'EN_PROCESO')
              AND nu.leida = TRUE
              AND (nu.ultimo_recordatorio_enviado IS NULL
                   OR nu.ultimo_recordatorio_enviado < CURDATE())
        """, commit=True)
    except Exception as e:
        logger.error(f"Error verificando recordatorios diarios: {e}")


def registrar_historial_alerta(alerta_id, estado_anterior, estado_nuevo, accion, usuario_id, observaciones=None):
    """Registra un cambio de estado en el historial de la alerta"""
    try:
        execute_query("""
            INSERT INTO historial_alertas
            (alerta_id, estado_anterior, estado_nuevo, accion, usuario_id, observaciones)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            alerta_id, estado_anterior, estado_nuevo,
            accion, usuario_id, observaciones
        ), commit=True)
    except Exception as e:
        logger.error(f"Error registrando historial de alerta {alerta_id}: {e}")


# ==================== RUTAS DE ALERTAS ====================

@alertas_bp.route('/')
@login_required
def lista_alertas():
    """Lista de alertas con secciones activas e historial"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    estado = request.args.get('estado', '')
    tipo_alerta = request.args.get('tipo_alerta', '')
    seccion = request.args.get('seccion', 'activas')
    prioridad = request.args.get('prioridad', '')

    per_page = current_app.config['ITEMS_PER_PAGE']
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    # Determinar estados según la sección
    if seccion == 'historial':
        # Sección historial: solo RESUELTA y ARCHIVADA
        if estado and estado in ('RESUELTA', 'ARCHIVADA'):
            where_clauses.append("ai.estado = %s")
            params.append(estado)
        else:
            where_clauses.append("ai.estado IN ('RESUELTA', 'ARCHIVADA')")
    else:
        # Sección activas: solo NUEVA y EN_PROCESO
        if estado and estado in ('NUEVA', 'EN_PROCESO'):
            where_clauses.append("ai.estado = %s")
            params.append(estado)
        else:
            where_clauses.append("ai.estado IN ('NUEVA', 'EN_PROCESO')")

    # Filtro por tipo de alerta
    if tipo_alerta:
        where_clauses.append("ai.tipo_alerta = %s")
        params.append(tipo_alerta)

    # Filtro por prioridad
    if prioridad and prioridad in ('CRITICA', 'ALTA', 'MEDIA', 'BAJA'):
        where_clauses.append("ai.nivel_prioridad = %s")
        params.append(prioridad)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Total de registros para paginación
    total = execute_query(f"""
        SELECT COUNT(*) as count
        FROM alertas_inventario ai
        LEFT JOIN repuestos r ON ai.repuesto_id = r.codigo
        WHERE {where_sql}
    """, tuple(params), fetch_one=True)['count']

    # Obtener alertas con información relacionada
    # IMPORTANTE: user['id'] va primero porque nu.usuario_id = %s aparece
    # en el LEFT JOIN ANTES del WHERE {where_sql} en el SQL generado.
    params_query = [user['id']] + list(params) + [per_page, offset]
    alertas = execute_query(f"""
        SELECT ai.*,
               r.codigo as repuesto_codigo,
               r.nombre as repuesto_nombre,
               r.cantidad_actual,
               r.cantidad_minima,
               ua.nombre_completo as atendida_por_nombre,
               ur.nombre_completo as resuelta_por_nombre,
               uar.nombre_completo as archivada_por_nombre,
               nu.leida as notificacion_leida,
               nu.id as notificacion_id
        FROM alertas_inventario ai
        LEFT JOIN repuestos r ON ai.repuesto_id = r.codigo
        LEFT JOIN usuarios ua ON ai.atendida_por = ua.numero_documento
        LEFT JOIN usuarios ur ON ai.resuelta_por = ur.numero_documento
        LEFT JOIN usuarios uar ON ai.archivada_por = uar.numero_documento
        LEFT JOIN notificaciones_usuarios nu ON nu.alerta_id = ai.id AND nu.usuario_id = %s
        WHERE {where_sql}
        ORDER BY
            FIELD(ai.nivel_prioridad, 'CRITICA', 'ALTA', 'MEDIA', 'BAJA') ASC,
            ai.created_at DESC
        LIMIT %s OFFSET %s
    """, tuple(params_query), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    # Contadores para las pestañas
    count_activas = execute_query("""
        SELECT COUNT(*) as count FROM alertas_inventario
        WHERE estado IN ('NUEVA', 'EN_PROCESO')
    """, fetch_one=True)['count']

    count_historial = execute_query("""
        SELECT COUNT(*) as count FROM alertas_inventario
        WHERE estado IN ('RESUELTA', 'ARCHIVADA')
    """, fetch_one=True)['count']

    # Obtener tipos de alerta distintos para el filtro
    tipos_alerta = execute_query("""
        SELECT DISTINCT tipo_alerta FROM alertas_inventario ORDER BY tipo_alerta
    """, fetch_all=True)

    estados_activos = ['NUEVA', 'EN_PROCESO']
    estados_historial = ['RESUELTA', 'ARCHIVADA']

    return render_template('alertas/lista.html',
                         alertas=alertas,
                         page=page,
                         total_pages=total_pages,
                         estado=estado,
                         tipo_alerta=tipo_alerta,
                         prioridad=prioridad,
                         seccion=seccion,
                         count_activas=count_activas,
                         count_historial=count_historial,
                         tipos_alerta=tipos_alerta,
                         estados_activos=estados_activos,
                         estados_historial=estados_historial)


@alertas_bp.route('/<int:id>')
@login_required
def ver_alerta(id):
    """Detalle de una alerta con timeline de historial"""
    user = get_current_user()

    alerta = execute_query("""
        SELECT ai.*,
               r.codigo as repuesto_codigo,
               r.nombre as repuesto_nombre,
               r.cantidad_actual,
               r.cantidad_minima,
               r.descripcion as repuesto_descripcion,
               r.ubicacion_fisica,
               r.precio_venta,
               c.nombre as categoria_nombre,
               ua.nombre_completo as atendida_por_nombre,
               ur.nombre_completo as resuelta_por_nombre,
               uar.nombre_completo as archivada_por_nombre
        FROM alertas_inventario ai
        LEFT JOIN repuestos r ON ai.repuesto_id = r.codigo
        LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
        LEFT JOIN usuarios ua ON ai.atendida_por = ua.numero_documento
        LEFT JOIN usuarios ur ON ai.resuelta_por = ur.numero_documento
        LEFT JOIN usuarios uar ON ai.archivada_por = uar.numero_documento
        WHERE ai.id = %s
    """, (id,), fetch_one=True)

    if not alerta:
        flash('Alerta no encontrada', 'danger')
        return redirect(url_for('alertas.lista_alertas'))

    # Obtener historial (timeline) de la alerta
    historial = execute_query("""
        SELECT ha.*,
               u.nombre_completo as usuario_nombre
        FROM historial_alertas ha
        LEFT JOIN usuarios u ON ha.usuario_id = u.numero_documento
        WHERE ha.alerta_id = %s
        ORDER BY ha.created_at DESC
    """, (id,), fetch_all=True)

    # Obtener estado de notificación personal del usuario
    notificacion = execute_query("""
        SELECT * FROM notificaciones_usuarios
        WHERE alerta_id = %s AND usuario_id = %s
    """, (id, user['id']), fetch_one=True)

    # Parsear datos_adicionales si es JSON
    datos_adicionales = None
    if alerta.get('datos_adicionales'):
        try:
            if isinstance(alerta['datos_adicionales'], str):
                datos_adicionales = json.loads(alerta['datos_adicionales'])
            else:
                datos_adicionales = alerta['datos_adicionales']
        except (json.JSONDecodeError, TypeError):
            datos_adicionales = None

    return render_template('alertas/ver.html',
                         alerta=alerta,
                         historial=historial,
                         notificacion=notificacion,
                         datos_adicionales=datos_adicionales,
                         can_resolve=can_resolve_alerts())


@alertas_bp.route('/<int:id>/atender', methods=['POST'])
@login_required
def atender_alerta(id):
    """Marcar alerta como EN_PROCESO (atendida)"""
    user = get_current_user()

    if not can_resolve_alerts():
        flash('No tiene permisos para atender alertas', 'danger')
        return redirect(url_for('alertas.ver_alerta', id=id))

    alerta = execute_query(
        "SELECT * FROM alertas_inventario WHERE id = %s",
        (id,), fetch_one=True
    )

    if not alerta:
        flash('Alerta no encontrada', 'danger')
        return redirect(url_for('alertas.lista_alertas'))

    if alerta['estado'] != 'NUEVA':
        flash('Solo se pueden atender alertas en estado NUEVA', 'warning')
        return redirect(url_for('alertas.ver_alerta', id=id))

    try:
        observaciones = request.form.get('observaciones', '')

        # Actualizar estado de la alerta
        execute_query("""
            UPDATE alertas_inventario
            SET estado = 'EN_PROCESO',
                atendida_por = %s,
                fecha_atencion = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (user['id'], id), commit=True)

        # Registrar en historial de alertas
        registrar_historial_alerta(
            alerta_id=id,
            estado_anterior='NUEVA',
            estado_nuevo='EN_PROCESO',
            accion='ATENDER',
            usuario_id=user['id'],
            observaciones=observaciones
        )

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='alertas_inventario',
            registro_id=str(id),
            accion='ACTUALIZAR',
            tipo_cambio='ALERTA',
            datos_anteriores={'estado': 'NUEVA'},
            datos_nuevos={'estado': 'EN_PROCESO', 'atendida_por': user['id']}
        )

        flash('Alerta marcada como en proceso exitosamente', 'success')

    except Exception as e:
        logger.error(f"Error atendiendo alerta {id}: {e}")
        flash('Error al atender la alerta', 'danger')

    return redirect(url_for('alertas.ver_alerta', id=id))


@alertas_bp.route('/<int:id>/resolver', methods=['POST'])
@login_required
def resolver_alerta(id):
    """Marcar alerta como RESUELTA"""
    user = get_current_user()

    if not can_resolve_alerts():
        flash('No tiene permisos para resolver alertas', 'danger')
        return redirect(url_for('alertas.ver_alerta', id=id))

    alerta = execute_query(
        "SELECT * FROM alertas_inventario WHERE id = %s",
        (id,), fetch_one=True
    )

    if not alerta:
        flash('Alerta no encontrada', 'danger')
        return redirect(url_for('alertas.lista_alertas'))

    if alerta['estado'] not in ('NUEVA', 'EN_PROCESO'):
        flash('Solo se pueden resolver alertas en estado NUEVA o EN_PROCESO', 'warning')
        return redirect(url_for('alertas.ver_alerta', id=id))

    try:
        observaciones = request.form.get('observaciones', '')
        estado_anterior = alerta['estado']

        # Actualizar estado de la alerta
        execute_query("""
            UPDATE alertas_inventario
            SET estado = 'RESUELTA',
                resuelta_por = %s,
                fecha_resolucion = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (user['id'], id), commit=True)

        # Registrar en historial de alertas
        registrar_historial_alerta(
            alerta_id=id,
            estado_anterior=estado_anterior,
            estado_nuevo='RESUELTA',
            accion='RESOLVER',
            usuario_id=user['id'],
            observaciones=observaciones
        )

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='alertas_inventario',
            registro_id=str(id),
            accion='ACTUALIZAR',
            tipo_cambio='ALERTA',
            datos_anteriores={'estado': estado_anterior},
            datos_nuevos={'estado': 'RESUELTA', 'resuelta_por': user['id']}
        )

        flash('Alerta resuelta exitosamente', 'success')

    except Exception as e:
        logger.error(f"Error resolviendo alerta {id}: {e}")
        flash('Error al resolver la alerta', 'danger')

    return redirect(url_for('alertas.ver_alerta', id=id))


@alertas_bp.route('/<int:id>/archivar', methods=['POST'])
@login_required
def archivar_alerta(id):
    """Marcar alerta como ARCHIVADA"""
    user = get_current_user()

    if not can_resolve_alerts():
        flash('No tiene permisos para archivar alertas', 'danger')
        return redirect(url_for('alertas.ver_alerta', id=id))

    alerta = execute_query(
        "SELECT * FROM alertas_inventario WHERE id = %s",
        (id,), fetch_one=True
    )

    if not alerta:
        flash('Alerta no encontrada', 'danger')
        return redirect(url_for('alertas.lista_alertas'))

    if alerta['estado'] != 'RESUELTA':
        flash('Solo se pueden archivar alertas en estado RESUELTA', 'warning')
        return redirect(url_for('alertas.ver_alerta', id=id))

    try:
        observaciones = request.form.get('observaciones', '')

        # Actualizar estado de la alerta
        execute_query("""
            UPDATE alertas_inventario
            SET estado = 'ARCHIVADA',
                archivada_por = %s,
                fecha_archivado = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (user['id'], id), commit=True)

        # Registrar en historial de alertas
        registrar_historial_alerta(
            alerta_id=id,
            estado_anterior='RESUELTA',
            estado_nuevo='ARCHIVADA',
            accion='ARCHIVAR',
            usuario_id=user['id'],
            observaciones=observaciones
        )

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='alertas_inventario',
            registro_id=str(id),
            accion='ACTUALIZAR',
            tipo_cambio='ALERTA',
            datos_anteriores={'estado': 'RESUELTA'},
            datos_nuevos={'estado': 'ARCHIVADA', 'archivada_por': user['id']}
        )

        flash('Alerta archivada exitosamente', 'success')

    except Exception as e:
        logger.error(f"Error archivando alerta {id}: {e}")
        flash('Error al archivar la alerta', 'danger')

    return redirect(url_for('alertas.ver_alerta', id=id))


@alertas_bp.route('/<int:id>/marcar-leida', methods=['POST'])
@login_required
def marcar_leida(id):
    """
    Marca la notificación personal del usuario como leída.
    NO cambia el estado de la alerta, solo el estado de lectura
    del usuario actual en notificaciones_usuarios.
    """
    user = get_current_user()

    try:
        # Verificar que la alerta existe
        alerta = execute_query(
            "SELECT id FROM alertas_inventario WHERE id = %s",
            (id,), fetch_one=True
        )

        if not alerta:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Alerta no encontrada'}), 404
            flash('Alerta no encontrada', 'danger')
            return redirect(url_for('alertas.lista_alertas'))

        # Verificar si existe la notificación para este usuario
        notificacion = execute_query("""
            SELECT id FROM notificaciones_usuarios
            WHERE alerta_id = %s AND usuario_id = %s
        """, (id, user['id']), fetch_one=True)

        if notificacion:
            # Actualizar como leída
            execute_query("""
                UPDATE notificaciones_usuarios
                SET leida = TRUE,
                    leida_at = NOW()
                WHERE alerta_id = %s AND usuario_id = %s
            """, (id, user['id']), commit=True)
        else:
            # Crear la notificación como leída si no existía
            execute_query("""
                INSERT INTO notificaciones_usuarios
                (usuario_id, alerta_id, leida, leida_at)
                VALUES (%s, %s, TRUE, NOW())
            """, (user['id'], id), commit=True)

        # Responder según tipo de petición
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True})

        flash('Notificación marcada como leída', 'info')

    except Exception as e:
        logger.error(f"Error marcando notificación como leída para alerta {id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Error interno'}), 500
        flash('Error al marcar la notificación como leída', 'danger')

    return redirect(url_for('alertas.ver_alerta', id=id))


# ==================== API ENDPOINTS ====================

@alertas_bp.route('/api/count')
@login_required
def api_count_alertas():
    """
    Retorna el conteo de alertas activas para el usuario actual.

    Una alerta cuenta si:
    (a) tiene estado NUEVA o EN_PROCESO, Y
    (b) la notificación del usuario no ha sido leída O fue leída pero
        el ultimo_recordatorio_enviado es anterior a hoy (recordatorio diario).

    Usado por el badge de la navbar.
    """
    user = get_current_user()

    try:
        result = execute_query("""
            SELECT COUNT(DISTINCT ai.id) as count
            FROM alertas_inventario ai
            JOIN notificaciones_usuarios nu ON nu.alerta_id = ai.id
            WHERE ai.estado IN ('NUEVA', 'EN_PROCESO')
              AND nu.usuario_id = %s
              AND (
                  nu.leida = FALSE
                  OR (
                      nu.leida = TRUE
                      AND (nu.ultimo_recordatorio_enviado IS NULL
                           OR nu.ultimo_recordatorio_enviado < CURDATE())
                  )
              )
        """, (user['id'],), fetch_one=True)

        count = result['count'] if result else 0

        return jsonify({
            'success': True,
            'count': count
        })

    except Exception as e:
        logger.error(f"Error obteniendo conteo de alertas: {e}")
        return jsonify({
            'success': False,
            'count': 0,
            'error': 'Error al obtener el conteo de alertas'
        }), 500
