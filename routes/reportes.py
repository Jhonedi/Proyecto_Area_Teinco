# -*- coding: utf-8 -*-
"""
Módulo de Reportes Periódicos
- Generación de reportes por tipo y rango de fechas
- Tipos: INVENTARIO, VENTAS, MOVIMIENTOS, ALERTAS, USUARIOS, GENERAL
- Almacenamiento permanente de reportes generados
- Solo accesible por ADMIN, SUPER_USUARIO y ALMACENISTA/VENDEDOR (lectura)
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, date, timedelta
from decimal import Decimal
from database import execute_query
from auth import (
    login_required, role_required, get_current_user,
    can_view_reports, registrar_audit_log
)
from . import reportes_bp
import json
import logging

logger = logging.getLogger(__name__)


# ==================== RUTAS DE REPORTES ====================

@reportes_bp.route('/')
@login_required
def lista_reportes():
    """Lista de reportes generados con paginación"""
    if not can_view_reports():
        flash('No tiene permisos para acceder a reportes', 'danger')
        return redirect(url_for('dashboard'))

    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    tipo = request.args.get('tipo', '')

    per_page = current_app.config['ITEMS_PER_PAGE']
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    if tipo:
        where_clauses.append("r.tipo_reporte = %s")
        params.append(tipo)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    total = execute_query(f"""
        SELECT COUNT(*) as count FROM reportes_generados r WHERE {where_sql}
    """, tuple(params), fetch_one=True)['count']

    params.extend([per_page, offset])
    reportes = execute_query(f"""
        SELECT r.*,
               r.nombre as titulo,
               r.periodo_inicio as fecha_inicio,
               r.periodo_fin as fecha_fin,
               r.datos as datos_json,
               u.nombre_completo as generado_por_nombre
        FROM reportes_generados r
        JOIN usuarios u ON r.generado_por = u.numero_documento
        WHERE {where_sql}
        ORDER BY r.created_at DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    tipos_reporte = ['INVENTARIO', 'VENTAS', 'MOVIMIENTOS', 'ALERTAS', 'USUARIOS', 'GENERAL']

    return render_template('reportes/lista.html',
                         reportes=reportes,
                         page=page,
                         total_pages=total_pages,
                         tipo=tipo,
                         tipos_reporte=tipos_reporte)


@reportes_bp.route('/generar')
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def form_generar():
    """Formulario para generar un nuevo reporte"""
    tipos_reporte = ['INVENTARIO', 'VENTAS', 'MOVIMIENTOS', 'ALERTAS', 'USUARIOS', 'GENERAL']

    # Fechas por defecto: último mes
    fecha_hasta = date.today()
    fecha_desde = fecha_hasta - timedelta(days=30)

    return render_template('reportes/generar.html',
                         tipos_reporte=tipos_reporte,
                         fecha_desde=fecha_desde.strftime('%Y-%m-%d'),
                         fecha_hasta=fecha_hasta.strftime('%Y-%m-%d'))


@reportes_bp.route('/generar', methods=['POST'])
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def generar_reporte():
    """Generar un nuevo reporte"""
    user = get_current_user()

    try:
        tipo_reporte = request.form.get('tipo_reporte', 'GENERAL')
        fecha_desde = request.form.get('fecha_desde', '')
        fecha_hasta = request.form.get('fecha_hasta', '')
        titulo = request.form.get('titulo', '').strip()

        if not fecha_desde or not fecha_hasta:
            flash('Debe seleccionar un rango de fechas', 'warning')
            return redirect(url_for('reportes.form_generar'))

        if not titulo:
            titulo = f"Reporte {tipo_reporte} - {fecha_desde} a {fecha_hasta}"

        # Generar datos del reporte según tipo
        datos = _generar_datos_reporte(tipo_reporte, fecha_desde, fecha_hasta)

        # Guardar reporte (columnas reales de reportes_generados)
        reporte_id = execute_query("""
            INSERT INTO reportes_generados
            (tipo_reporte, nombre, periodo_inicio, periodo_fin, datos, generado_por)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            tipo_reporte, titulo, fecha_desde, fecha_hasta,
            json.dumps(datos, default=str), user['id']
        ), commit=True)

        registrar_audit_log(
            usuario_id=user['id'],
            tabla='reportes_generados',
            registro_id=reporte_id,
            accion='CREAR',
            tipo_cambio='OTRO',
            datos_nuevos={
                'tipo_reporte': tipo_reporte,
                'titulo': titulo,
                'fecha_inicio': fecha_desde,
                'fecha_fin': fecha_hasta
            }
        )

        flash(f'Reporte "{titulo}" generado exitosamente', 'success')
        return redirect(url_for('reportes.ver_reporte', id=reporte_id))

    except Exception as e:
        logger.error(f"Error generando reporte: {e}")
        flash('Error al generar el reporte', 'danger')
        return redirect(url_for('reportes.form_generar'))


@reportes_bp.route('/<int:id>')
@login_required
def ver_reporte(id):
    """Ver detalle de un reporte generado"""
    if not can_view_reports():
        flash('No tiene permisos para ver reportes', 'danger')
        return redirect(url_for('dashboard'))

    reporte = execute_query("""
        SELECT r.*,
               r.nombre as titulo,
               r.periodo_inicio as fecha_inicio,
               r.periodo_fin as fecha_fin,
               r.datos as datos_json,
               u.nombre_completo as generado_por_nombre
        FROM reportes_generados r
        JOIN usuarios u ON r.generado_por = u.numero_documento
        WHERE r.id = %s
    """, (id,), fetch_one=True)

    if not reporte:
        flash('Reporte no encontrado', 'danger')
        return redirect(url_for('reportes.lista_reportes'))

    # Parsear datos JSON
    datos = {}
    try:
        if reporte['datos_json']:
            if isinstance(reporte['datos_json'], str):
                datos = json.loads(reporte['datos_json'])
            else:
                datos = reporte['datos_json']
    except (json.JSONDecodeError, TypeError):
        datos = {}

    return render_template('reportes/ver.html',
                         reporte=reporte,
                         datos=datos)


# ==================== FUNCIONES DE GENERACIÓN ====================

def _generar_datos_reporte(tipo, fecha_desde, fecha_hasta):
    """Genera datos de reporte según el tipo"""
    datos = {
        'tipo': tipo,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'generado_en': datetime.now().isoformat()
    }

    if tipo == 'INVENTARIO':
        datos.update(_reporte_inventario(fecha_desde, fecha_hasta))
    elif tipo == 'VENTAS':
        datos.update(_reporte_ventas(fecha_desde, fecha_hasta))
    elif tipo == 'MOVIMIENTOS':
        datos.update(_reporte_movimientos(fecha_desde, fecha_hasta))
    elif tipo == 'ALERTAS':
        datos.update(_reporte_alertas(fecha_desde, fecha_hasta))
    elif tipo == 'USUARIOS':
        datos.update(_reporte_usuarios(fecha_desde, fecha_hasta))
    elif tipo == 'GENERAL':
        datos.update(_reporte_inventario(fecha_desde, fecha_hasta))
        datos.update(_reporte_ventas(fecha_desde, fecha_hasta))
        datos.update(_reporte_movimientos(fecha_desde, fecha_hasta))
        datos.update(_reporte_alertas(fecha_desde, fecha_hasta))

    return datos


def _reporte_inventario(fecha_desde, fecha_hasta):
    """Datos de inventario"""
    resumen = execute_query("""
        SELECT
            COUNT(*) as total_repuestos,
            SUM(cantidad_actual) as total_unidades,
            SUM(cantidad_actual * precio_venta) as valor_total,
            SUM(CASE WHEN cantidad_actual = 0 THEN 1 ELSE 0 END) as agotados,
            SUM(CASE WHEN cantidad_actual > 0 AND cantidad_actual <= cantidad_minima THEN 1 ELSE 0 END) as stock_bajo
        FROM repuestos
        WHERE activo = TRUE
    """, fetch_one=True)

    por_categoria = execute_query("""
        SELECT c.nombre as categoria,
               COUNT(r.codigo) as total,
               SUM(r.cantidad_actual) as unidades,
               SUM(r.cantidad_actual * r.precio_venta) as valor
        FROM repuestos r
        LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
        WHERE r.activo = TRUE
        GROUP BY c.id, c.nombre
        ORDER BY valor DESC
    """, fetch_all=True)

    return {
        'inventario_resumen': dict(resumen) if resumen else {},
        'inventario_por_categoria': [dict(c) for c in por_categoria] if por_categoria else []
    }


def _reporte_ventas(fecha_desde, fecha_hasta):
    """Datos de ventas/facturación"""
    resumen = execute_query("""
        SELECT
            COUNT(*) as total_facturas,
            SUM(CASE WHEN estado = 'PAGADA' THEN 1 ELSE 0 END) as pagadas,
            SUM(CASE WHEN estado IN ('PENDIENTE', 'EN_ESPERA') THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN estado = 'ANULADA' THEN 1 ELSE 0 END) as anuladas,
            IFNULL(SUM(CASE WHEN estado = 'PAGADA' THEN total ELSE 0 END), 0) as total_facturado,
            IFNULL(SUM(CASE WHEN estado IN ('PENDIENTE', 'EN_ESPERA') THEN total ELSE 0 END), 0) as total_pendiente
        FROM facturas
        WHERE DATE(created_at) BETWEEN %s AND %s
    """, (fecha_desde, fecha_hasta), fetch_one=True)

    por_vendedor = execute_query("""
        SELECT u.nombre_completo as vendedor,
               COUNT(f.id) as total_facturas,
               IFNULL(SUM(CASE WHEN f.estado = 'PAGADA' THEN f.total ELSE 0 END), 0) as total_vendido
        FROM facturas f
        JOIN usuarios u ON f.vendedor_id = u.numero_documento
        WHERE DATE(f.created_at) BETWEEN %s AND %s
        GROUP BY u.numero_documento, u.nombre_completo
        ORDER BY total_vendido DESC
    """, (fecha_desde, fecha_hasta), fetch_all=True)

    return {
        'ventas_resumen': dict(resumen) if resumen else {},
        'ventas_por_vendedor': [dict(v) for v in por_vendedor] if por_vendedor else []
    }


def _reporte_movimientos(fecha_desde, fecha_hasta):
    """Datos de movimientos de inventario"""
    resumen = execute_query("""
        SELECT
            COUNT(*) as total_movimientos,
            SUM(CASE WHEN tm.tipo = 'ENTRADA' THEN 1 ELSE 0 END) as entradas,
            SUM(CASE WHEN tm.tipo = 'SALIDA' THEN 1 ELSE 0 END) as salidas,
            SUM(CASE WHEN tm.tipo = 'ENTRADA' THEN mi.cantidad ELSE 0 END) as unidades_entrada,
            SUM(CASE WHEN tm.tipo = 'SALIDA' THEN mi.cantidad ELSE 0 END) as unidades_salida
        FROM movimientos_inventario mi
        JOIN tipos_movimiento tm ON mi.tipo_movimiento_id = tm.id
        WHERE DATE(mi.created_at) BETWEEN %s AND %s
    """, (fecha_desde, fecha_hasta), fetch_one=True)

    por_tipo = execute_query("""
        SELECT tm.nombre as tipo_movimiento,
               tm.tipo,
               COUNT(*) as total,
               SUM(mi.cantidad) as unidades
        FROM movimientos_inventario mi
        JOIN tipos_movimiento tm ON mi.tipo_movimiento_id = tm.id
        WHERE DATE(mi.created_at) BETWEEN %s AND %s
        GROUP BY tm.id, tm.nombre, tm.tipo
        ORDER BY total DESC
    """, (fecha_desde, fecha_hasta), fetch_all=True)

    return {
        'movimientos_resumen': dict(resumen) if resumen else {},
        'movimientos_por_tipo': [dict(t) for t in por_tipo] if por_tipo else []
    }


def _reporte_alertas(fecha_desde, fecha_hasta):
    """Datos de alertas"""
    resumen = execute_query("""
        SELECT
            COUNT(*) as total_alertas,
            SUM(CASE WHEN estado = 'NUEVA' THEN 1 ELSE 0 END) as nuevas,
            SUM(CASE WHEN estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as en_proceso,
            SUM(CASE WHEN estado = 'RESUELTA' THEN 1 ELSE 0 END) as resueltas,
            SUM(CASE WHEN estado = 'ARCHIVADA' THEN 1 ELSE 0 END) as archivadas
        FROM alertas_inventario
        WHERE DATE(created_at) BETWEEN %s AND %s
    """, (fecha_desde, fecha_hasta), fetch_one=True)

    por_tipo = execute_query("""
        SELECT tipo_alerta,
               COUNT(*) as total
        FROM alertas_inventario
        WHERE DATE(created_at) BETWEEN %s AND %s
        GROUP BY tipo_alerta
        ORDER BY total DESC
    """, (fecha_desde, fecha_hasta), fetch_all=True)

    return {
        'alertas_resumen': dict(resumen) if resumen else {},
        'alertas_por_tipo': [dict(a) for a in por_tipo] if por_tipo else []
    }


def _reporte_usuarios(fecha_desde, fecha_hasta):
    """Datos de actividad de usuarios"""
    actividad = execute_query("""
        SELECT u.nombre_completo as usuario,
               r.nombre as rol,
               COUNT(a.id) as total_acciones,
               SUM(CASE WHEN a.accion = 'LOGIN' THEN 1 ELSE 0 END) as logins,
               MAX(a.created_at) as ultima_actividad
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        LEFT JOIN audit_log a ON u.numero_documento = a.usuario_id
            AND DATE(a.created_at) BETWEEN %s AND %s
        WHERE u.activo = TRUE
        GROUP BY u.numero_documento, u.nombre_completo, r.nombre
        ORDER BY total_acciones DESC
    """, (fecha_desde, fecha_hasta), fetch_all=True)

    return {
        'usuarios_actividad': [dict(u) for u in actividad] if actividad else []
    }
