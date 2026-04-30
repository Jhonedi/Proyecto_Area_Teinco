# -*- coding: utf-8 -*-
"""
Módulo de Solicitudes de Repuestos
- Técnicos crean solicitudes vinculadas a vehículo y cliente
- Una solicitud contiene múltiples repuestos
- Al crearse, los ítems quedan en estado reservado
- Almacenista aprueba/rechaza y marca entrega
- Vendedores reciben notificación para facturar
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, date
from database import execute_query
from auth import (
    login_required, role_required, get_current_user,
    can_create_requests, can_approve_requests, registrar_audit_log
)
from . import solicitudes_bp
import logging

logger = logging.getLogger(__name__)


def generar_numero_solicitud():
    """Genera un número único de solicitud en formato SOL-YYYYMMDD-XXXX"""
    fecha = datetime.now().strftime('%Y%m%d')
    prefijo = current_app.config.get('PREFIJO_SOLICITUD', 'SOL')

    # Obtener el último número del día
    ultimo = execute_query("""
        SELECT numero_solicitud FROM solicitudes_repuestos
        WHERE numero_solicitud LIKE %s
        ORDER BY id DESC LIMIT 1
    """, (f'{prefijo}-{fecha}-%',), fetch_one=True)

    if ultimo:
        try:
            ultimo_num = int(ultimo['numero_solicitud'].split('-')[-1])
            nuevo_num = ultimo_num + 1
        except:
            nuevo_num = 1
    else:
        nuevo_num = 1

    return f"{prefijo}-{fecha}-{nuevo_num:04d}"


# ==================== RUTAS DE SOLICITUDES ====================

@solicitudes_bp.route('/')
@login_required
def lista_solicitudes():
    """Lista de solicitudes de repuestos"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    estado = request.args.get('estado', '')
    search = request.args.get('search', '')

    per_page = current_app.config['ITEMS_PER_PAGE']
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    # Filtrar por rol - técnicos solo ven sus solicitudes
    if user['rol_nombre'] == 'TECNICO':
        where_clauses.append("s.tecnico_id = %s")
        params.append(user['id'])

    if estado:
        where_clauses.append("s.estado = %s")
        params.append(estado)

    if search:
        where_clauses.append("""
            (s.numero_solicitud LIKE %s OR c.nombre_completo LIKE %s OR v.placa LIKE %s)
        """)
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Total de registros
    total = execute_query(f"""
        SELECT COUNT(*) as count
        FROM solicitudes_repuestos s
        JOIN clientes c ON s.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON s.vehiculo_id = v.placa
        WHERE {where_sql}
    """, tuple(params), fetch_one=True)['count']

    # Obtener solicitudes con orden alfanumérico
    params.extend([per_page, offset])
    solicitudes = execute_query(f"""
        SELECT s.*,
               u.nombre_completo as tecnico_nombre,
               c.nombre_completo as cliente_nombre,
               c.numero_documento as cliente_documento,
               v.placa,
               (SELECT COUNT(*) FROM items_solicitud WHERE solicitud_id = s.id) as total_items,
               (SELECT SUM(cantidad_solicitada * precio_unitario) FROM items_solicitud WHERE solicitud_id = s.id) as valor_total
        FROM solicitudes_repuestos s
        JOIN usuarios u ON s.tecnico_id = u.numero_documento
        JOIN clientes c ON s.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON s.vehiculo_id = v.placa
        WHERE {where_sql}
        ORDER BY s.numero_solicitud DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    estados = ['PENDIENTE', 'APROBADA', 'RECHAZADA', 'ENTREGADA', 'FACTURADA', 'DEVOLUCION_PARCIAL', 'ANULADA']

    return render_template('solicitudes/lista.html',
                         solicitudes=solicitudes,
                         page=page,
                         total_pages=total_pages,
                         estado=estado,
                         search=search,
                         estados=estados)


@solicitudes_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def nueva_solicitud():
    """Crear nueva solicitud de repuestos"""
    user = get_current_user()

    # Solo técnicos, almacenistas, admin y superusuario pueden crear
    if not can_create_requests():
        flash('No tiene permisos para crear solicitudes', 'danger')
        return redirect(url_for('solicitudes.lista_solicitudes'))

    if request.method == 'POST':
        try:
            cliente_id = request.form['cliente_id']      # numero_documento del cliente
            vehiculo_id = request.form['vehiculo_id']    # placa del vehículo
            observaciones = request.form.get('observaciones', '')
            fecha_requerida = request.form.get('fecha_requerida') or None

            # Obtener items del formulario
            repuesto_ids = request.form.getlist('repuesto_id[]')  # codigos de repuesto
            cantidades = request.form.getlist('cantidad[]')

            if not repuesto_ids or not any(repuesto_ids):
                flash('Debe agregar al menos un repuesto a la solicitud', 'warning')
                return redirect(url_for('solicitudes.nueva_solicitud'))

            # Generar número de solicitud
            numero_solicitud = generar_numero_solicitud()

            # Crear la solicitud
            solicitud_id = execute_query("""
                INSERT INTO solicitudes_repuestos
                (numero_solicitud, tecnico_id, cliente_id, vehiculo_id, observaciones, fecha_requerida)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                numero_solicitud, user['id'], cliente_id, vehiculo_id,
                observaciones, fecha_requerida
            ), commit=True)

            # Agregar items y reservar stock
            for i, repuesto_id in enumerate(repuesto_ids):
                if not repuesto_id:
                    continue

                cantidad = int(cantidades[i])

                # Obtener precio actual del repuesto (por codigo)
                repuesto = execute_query(
                    "SELECT precio_venta, cantidad_actual, cantidad_reservada FROM repuestos WHERE codigo = %s",
                    (repuesto_id,), fetch_one=True
                )

                # Verificar disponibilidad
                stock_disponible = repuesto['cantidad_actual'] - repuesto['cantidad_reservada']
                if cantidad > stock_disponible:
                    flash(f'Stock insuficiente para uno de los repuestos. Disponible: {stock_disponible}', 'warning')
                    # Rollback de la solicitud
                    execute_query("DELETE FROM solicitudes_repuestos WHERE id = %s", (solicitud_id,), commit=True)
                    return redirect(url_for('solicitudes.nueva_solicitud'))

                # Insertar item en estado RESERVADO
                execute_query("""
                    INSERT INTO items_solicitud
                    (solicitud_id, repuesto_id, cantidad_solicitada, precio_unitario, estado)
                    VALUES (%s, %s, %s, %s, 'RESERVADO')
                """, (solicitud_id, repuesto_id, cantidad, repuesto['precio_venta']), commit=True)

                # Reservar stock (incrementar cantidad_reservada)
                execute_query("""
                    UPDATE repuestos
                    SET cantidad_reservada = cantidad_reservada + %s,
                        updated_by = %s
                    WHERE codigo = %s
                """, (cantidad, user['id'], repuesto_id), commit=True)

            # Registrar en audit log
            registrar_audit_log(
                usuario_id=user['id'],
                tabla='solicitudes_repuestos',
                registro_id=str(solicitud_id),
                accion='CREAR',
                tipo_cambio='SOLICITUD',
                datos_nuevos={
                    'numero_solicitud': numero_solicitud,
                    'cliente_id': cliente_id,
                    'vehiculo_id': vehiculo_id,
                    'total_items': len([r for r in repuesto_ids if r])
                }
            )

            # Crear alerta para almacenistas
            crear_alerta_solicitud_pendiente(solicitud_id, numero_solicitud)

            flash(f'Solicitud {numero_solicitud} creada exitosamente', 'success')
            return redirect(url_for('solicitudes.ver_solicitud', id=solicitud_id))

        except Exception as e:
            logger.error(f"Error creando solicitud: {e}")
            flash('Error al crear la solicitud', 'danger')

    # Obtener datos para el formulario
    # clientes: numero_documento como id para el form
    clientes = execute_query(
        "SELECT numero_documento as id, numero_documento, nombre_completo FROM clientes WHERE activo = TRUE ORDER BY nombre_completo ASC",
        fetch_all=True
    )

    # Obtener repuestos con stock disponible (ordenados por codigo)
    repuestos = execute_query("""
        SELECT r.codigo as id, r.codigo, r.nombre, r.precio_venta,
               r.cantidad_actual, r.cantidad_reservada,
               (r.cantidad_actual - r.cantidad_reservada) as disponible,
               c.nombre as categoria,
               r.categoria_id
        FROM repuestos r
        LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
        WHERE r.activo = TRUE AND (r.cantidad_actual - r.cantidad_reservada) > 0
        ORDER BY r.codigo ASC
    """, fetch_all=True)

    # Obtener categorías para filtro
    categorias = execute_query(
        "SELECT * FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre",
        fetch_all=True
    )

    return render_template('solicitudes/form.html',
                         solicitud=None,
                         clientes=clientes,
                         repuestos=repuestos,
                         categorias=categorias)


@solicitudes_bp.route('/<int:id>')
@login_required
def ver_solicitud(id):
    """Ver detalle de una solicitud"""
    user = get_current_user()

    solicitud = execute_query("""
        SELECT s.*,
               ut.nombre_completo as tecnico_nombre,
               ua.nombre_completo as aprobado_por_nombre,
               ue.nombre_completo as entregado_por_nombre,
               uf.nombre_completo as facturado_por_nombre,
               c.nombre_completo as cliente_nombre,
               c.numero_documento as cliente_documento,
               c.telefono as cliente_telefono,
               v.placa, v.color, v.anio,
               mv.nombre as modelo_nombre,
               ma.nombre as marca_nombre,
               s.fecha_facturacion
        FROM solicitudes_repuestos s
        JOIN usuarios ut ON s.tecnico_id = ut.numero_documento
        LEFT JOIN usuarios ua ON s.aprobado_por = ua.numero_documento
        LEFT JOIN usuarios ue ON s.entregado_por = ue.numero_documento
        LEFT JOIN usuarios uf ON s.facturado_por = uf.numero_documento
        JOIN clientes c ON s.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON s.vehiculo_id = v.placa
        JOIN modelos_vehiculos mv ON v.modelo_vehiculo_id = mv.id
        JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
        WHERE s.id = %s
    """, (id,), fetch_one=True)

    if not solicitud:
        flash('Solicitud no encontrada', 'danger')
        return redirect(url_for('solicitudes.lista_solicitudes'))

    # Verificar permisos - técnicos solo ven sus solicitudes
    if user['rol_nombre'] == 'TECNICO' and solicitud['tecnico_id'] != user['id']:
        flash('No tiene permisos para ver esta solicitud', 'danger')
        return redirect(url_for('solicitudes.lista_solicitudes'))

    # Obtener items de la solicitud
    items = execute_query("""
        SELECT i.*,
               r.codigo as repuesto_codigo,
               r.nombre as repuesto_nombre,
               r.cantidad_actual as stock_actual,
               r.cantidad_reservada as stock_reservado,
               c.nombre as categoria
        FROM items_solicitud i
        JOIN repuestos r ON i.repuesto_id = r.codigo
        LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
        WHERE i.solicitud_id = %s
        ORDER BY r.codigo ASC
    """, (id,), fetch_all=True)

    return render_template('solicitudes/ver.html',
                         solicitud=solicitud,
                         items=items,
                         can_approve=can_approve_requests(),
                         can_deliver=can_approve_requests())


@solicitudes_bp.route('/<int:id>/aprobar', methods=['POST'])
@login_required
def aprobar_solicitud(id):
    """Aprobar solicitud (almacenista)"""
    user = get_current_user()

    if not can_approve_requests():
        flash('No tiene permisos para aprobar solicitudes', 'danger')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    solicitud = execute_query(
        "SELECT * FROM solicitudes_repuestos WHERE id = %s",
        (id,), fetch_one=True
    )

    if not solicitud:
        flash('Solicitud no encontrada', 'danger')
        return redirect(url_for('solicitudes.lista_solicitudes'))

    if solicitud['estado'] != 'PENDIENTE':
        flash('Solo se pueden aprobar solicitudes pendientes', 'warning')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    try:
        # Obtener cantidades aprobadas del formulario
        items = execute_query(
            "SELECT id, repuesto_id, cantidad_solicitada FROM items_solicitud WHERE solicitud_id = %s",
            (id,), fetch_all=True
        )

        for item in items:
            cantidad_aprobada = request.form.get(f'cantidad_aprobada_{item["id"]}', type=int)
            if cantidad_aprobada is None:
                cantidad_aprobada = item['cantidad_solicitada']

            # Actualizar item
            execute_query("""
                UPDATE items_solicitud
                SET cantidad_aprobada = %s, estado = 'APROBADO'
                WHERE id = %s
            """, (cantidad_aprobada, item['id']), commit=True)

            # Ajustar reserva si se aprobó menos cantidad
            diferencia = item['cantidad_solicitada'] - cantidad_aprobada
            if diferencia > 0:
                execute_query("""
                    UPDATE repuestos
                    SET cantidad_reservada = cantidad_reservada - %s
                    WHERE codigo = %s
                """, (diferencia, item['repuesto_id']), commit=True)

        # Actualizar estado de solicitud
        execute_query("""
            UPDATE solicitudes_repuestos
            SET estado = 'APROBADA', aprobado_por = %s, fecha_aprobacion = NOW()
            WHERE id = %s
        """, (user['id'], id), commit=True)

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='solicitudes_repuestos',
            registro_id=str(id),
            accion='APROBAR',
            tipo_cambio='SOLICITUD',
            datos_anteriores={'estado': 'PENDIENTE'},
            datos_nuevos={'estado': 'APROBADA', 'aprobado_por': user['id']}
        )

        flash('Solicitud aprobada exitosamente', 'success')

    except Exception as e:
        logger.error(f"Error aprobando solicitud: {e}")
        flash('Error al aprobar la solicitud', 'danger')

    return redirect(url_for('solicitudes.ver_solicitud', id=id))


@solicitudes_bp.route('/<int:id>/rechazar', methods=['POST'])
@login_required
def rechazar_solicitud(id):
    """Rechazar solicitud (almacenista)"""
    user = get_current_user()

    if not can_approve_requests():
        flash('No tiene permisos para rechazar solicitudes', 'danger')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    solicitud = execute_query(
        "SELECT * FROM solicitudes_repuestos WHERE id = %s",
        (id,), fetch_one=True
    )

    if not solicitud or solicitud['estado'] != 'PENDIENTE':
        flash('Solo se pueden rechazar solicitudes pendientes', 'warning')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    try:
        motivo = request.form.get('motivo_rechazo', '')

        # Liberar reservas de stock
        items = execute_query(
            "SELECT repuesto_id, cantidad_solicitada FROM items_solicitud WHERE solicitud_id = %s",
            (id,), fetch_all=True
        )

        for item in items:
            execute_query("""
                UPDATE repuestos
                SET cantidad_reservada = cantidad_reservada - %s
                WHERE codigo = %s
            """, (item['cantidad_solicitada'], item['repuesto_id']), commit=True)

            execute_query(
                "UPDATE items_solicitud SET estado = 'RECHAZADO' WHERE solicitud_id = %s",
                (id,), commit=True
            )

        # Actualizar estado de solicitud
        execute_query("""
            UPDATE solicitudes_repuestos
            SET estado = 'RECHAZADA', aprobado_por = %s, fecha_aprobacion = NOW(),
                observaciones = CONCAT(IFNULL(observaciones, ''), '\nMotivo rechazo: ', %s)
            WHERE id = %s
        """, (user['id'], motivo, id), commit=True)

        registrar_audit_log(
            usuario_id=user['id'],
            tabla='solicitudes_repuestos',
            registro_id=str(id),
            accion='RECHAZAR',
            tipo_cambio='SOLICITUD',
            datos_nuevos={'estado': 'RECHAZADA', 'motivo': motivo}
        )

        flash('Solicitud rechazada', 'info')

    except Exception as e:
        logger.error(f"Error rechazando solicitud: {e}")
        flash('Error al rechazar la solicitud', 'danger')

    return redirect(url_for('solicitudes.ver_solicitud', id=id))


@solicitudes_bp.route('/<int:id>/entregar', methods=['POST'])
@login_required
def marcar_entrega(id):
    """Marcar solicitud como entregada (almacenista)"""
    user = get_current_user()

    if not can_approve_requests():
        flash('No tiene permisos para marcar entregas', 'danger')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    solicitud = execute_query(
        "SELECT * FROM solicitudes_repuestos WHERE id = %s",
        (id,), fetch_one=True
    )

    if not solicitud or solicitud['estado'] != 'APROBADA':
        flash('Solo se pueden marcar como entregadas las solicitudes aprobadas', 'warning')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    try:
        # Actualizar items como entregados
        items = execute_query(
            "SELECT id, cantidad_aprobada FROM items_solicitud WHERE solicitud_id = %s AND estado = 'APROBADO'",
            (id,), fetch_all=True
        )

        for item in items:
            cantidad_entregada = request.form.get(f'cantidad_entregada_{item["id"]}', type=int)
            if cantidad_entregada is None:
                cantidad_entregada = item['cantidad_aprobada']

            execute_query("""
                UPDATE items_solicitud
                SET cantidad_entregada = %s, estado = 'ENTREGADO'
                WHERE id = %s
            """, (cantidad_entregada, item['id']), commit=True)

        # Actualizar estado de solicitud
        execute_query("""
            UPDATE solicitudes_repuestos
            SET estado = 'ENTREGADA', entregado_por = %s, fecha_entrega = NOW()
            WHERE id = %s
        """, (user['id'], id), commit=True)

        # Crear notificación para vendedores
        notificar_vendedores_facturacion(id, solicitud['numero_solicitud'])

        registrar_audit_log(
            usuario_id=user['id'],
            tabla='solicitudes_repuestos',
            registro_id=str(id),
            accion='ACTUALIZAR',
            tipo_cambio='SOLICITUD',
            datos_nuevos={'estado': 'ENTREGADA', 'entregado_por': user['id']}
        )

        flash('Solicitud marcada como entregada. Vendedores notificados para facturación.', 'success')

    except Exception as e:
        logger.error(f"Error marcando entrega: {e}")
        flash('Error al marcar la entrega', 'danger')

    return redirect(url_for('solicitudes.ver_solicitud', id=id))


@solicitudes_bp.route('/<int:id>/devolver', methods=['POST'])
@login_required
def registrar_devolucion(id):
    """Registrar devolución de items antes de facturar"""
    user = get_current_user()

    solicitud = execute_query(
        "SELECT * FROM solicitudes_repuestos WHERE id = %s",
        (id,), fetch_one=True
    )

    if not solicitud or solicitud['estado'] not in ['APROBADA', 'ENTREGADA']:
        flash('Solo se pueden hacer devoluciones de solicitudes aprobadas o entregadas', 'warning')
        return redirect(url_for('solicitudes.ver_solicitud', id=id))

    try:
        item_id = request.form['item_id']
        cantidad_devuelta = int(request.form['cantidad_devuelta'])

        item = execute_query(
            "SELECT * FROM items_solicitud WHERE id = %s AND solicitud_id = %s",
            (item_id, id), fetch_one=True
        )

        if not item:
            flash('Item no encontrado', 'danger')
            return redirect(url_for('solicitudes.ver_solicitud', id=id))

        cantidad_maxima = item['cantidad_entregada'] or item['cantidad_aprobada']
        if cantidad_devuelta > cantidad_maxima - item['cantidad_devuelta']:
            flash('Cantidad a devolver mayor a la disponible', 'warning')
            return redirect(url_for('solicitudes.ver_solicitud', id=id))

        # Actualizar item
        nueva_cantidad_devuelta = item['cantidad_devuelta'] + cantidad_devuelta
        execute_query("""
            UPDATE items_solicitud
            SET cantidad_devuelta = %s,
                estado = CASE WHEN %s >= cantidad_entregada THEN 'DEVUELTO' ELSE estado END
            WHERE id = %s
        """, (nueva_cantidad_devuelta, nueva_cantidad_devuelta, item_id), commit=True)

        # Liberar reserva de stock
        execute_query("""
            UPDATE repuestos
            SET cantidad_reservada = cantidad_reservada - %s
            WHERE codigo = %s
        """, (cantidad_devuelta, item['repuesto_id']), commit=True)

        # Verificar si hay devolución parcial
        items_pendientes = execute_query("""
            SELECT COUNT(*) as count FROM items_solicitud
            WHERE solicitud_id = %s AND estado NOT IN ('DEVUELTO', 'RECHAZADO')
        """, (id,), fetch_one=True)['count']

        if items_pendientes == 0:
            execute_query(
                "UPDATE solicitudes_repuestos SET estado = 'ANULADA' WHERE id = %s",
                (id,), commit=True
            )
        else:
            execute_query(
                "UPDATE solicitudes_repuestos SET estado = 'DEVOLUCION_PARCIAL' WHERE id = %s",
                (id,), commit=True
            )

        # Registrar movimiento de entrada por devolución
        execute_query("""
            INSERT INTO movimientos_inventario
            (repuesto_id, tipo_movimiento_id, cantidad, usuario_id, solicitud_id, estado, observaciones)
            VALUES (%s, (SELECT id FROM tipos_movimiento WHERE nombre = 'Devolución Técnico'),
                    %s, %s, %s, 'CONFIRMADO', 'Devolución antes de facturar')
        """, (item['repuesto_id'], cantidad_devuelta, user['id'], id), commit=True)

        registrar_audit_log(
            usuario_id=user['id'],
            tabla='items_solicitud',
            registro_id=str(item_id),
            accion='ACTUALIZAR',
            tipo_cambio='SOLICITUD',
            datos_nuevos={'cantidad_devuelta': nueva_cantidad_devuelta}
        )

        flash('Devolución registrada y reserva liberada', 'success')

    except Exception as e:
        logger.error(f"Error registrando devolución: {e}")
        flash('Error al registrar la devolución', 'danger')

    return redirect(url_for('solicitudes.ver_solicitud', id=id))


# ==================== FUNCIONES AUXILIARES ====================

def crear_alerta_solicitud_pendiente(solicitud_id, numero_solicitud):
    """Crea alerta para almacenistas sobre nueva solicitud pendiente"""
    try:
        # Crear alerta
        alerta_id = execute_query("""
            INSERT INTO alertas_inventario
            (tipo_alerta, nivel_prioridad, mensaje, datos_adicionales)
            VALUES ('SOLICITUD_PENDIENTE', 'ALTA', %s, %s)
        """, (
            f'Nueva solicitud de repuestos {numero_solicitud} pendiente de aprobación',
            f'{{"solicitud_id": {solicitud_id}, "numero_solicitud": "{numero_solicitud}"}}'
        ), commit=True)

        # Notificar a almacenistas y administradores
        usuarios = execute_query("""
            SELECT u.numero_documento as id FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE r.nombre IN ('SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA') AND u.activo = TRUE
        """, fetch_all=True)

        for usuario in usuarios:
            execute_query("""
                INSERT INTO notificaciones_usuarios (usuario_id, alerta_id)
                VALUES (%s, %s)
            """, (usuario['id'], alerta_id), commit=True)

    except Exception as e:
        logger.error(f"Error creando alerta de solicitud: {e}")


def notificar_vendedores_facturacion(solicitud_id, numero_solicitud):
    """Notifica a vendedores que hay una solicitud lista para facturar"""
    try:
        # Crear alerta
        alerta_id = execute_query("""
            INSERT INTO alertas_inventario
            (tipo_alerta, nivel_prioridad, mensaje, datos_adicionales)
            VALUES ('FACTURA_PENDIENTE', 'MEDIA', %s, %s)
        """, (
            f'Solicitud {numero_solicitud} entregada - pendiente de facturación',
            f'{{"solicitud_id": {solicitud_id}, "numero_solicitud": "{numero_solicitud}"}}'
        ), commit=True)

        # Notificar a vendedores
        usuarios = execute_query("""
            SELECT u.numero_documento as id FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE r.nombre IN ('SUPER_USUARIO', 'ADMINISTRADOR', 'VENDEDOR') AND u.activo = TRUE
        """, fetch_all=True)

        for usuario in usuarios:
            execute_query("""
                INSERT INTO notificaciones_usuarios (usuario_id, alerta_id)
                VALUES (%s, %s)
            """, (usuario['id'], alerta_id), commit=True)

    except Exception as e:
        logger.error(f"Error notificando vendedores: {e}")


# ==================== API ENDPOINTS ====================

@solicitudes_bp.route('/api/vehiculos-cliente/<string:cliente_id>')
@login_required
def api_vehiculos_cliente(cliente_id):
    """Obtener vehículos de un cliente (cliente_id = numero_documento)"""
    vehiculos = execute_query("""
        SELECT vc.placa as id, vc.placa, vc.color, vc.anio,
               mv.nombre as modelo, ma.nombre as marca
        FROM vehiculos_clientes vc
        JOIN modelos_vehiculos mv ON vc.modelo_vehiculo_id = mv.id
        JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
        WHERE vc.cliente_id = %s AND vc.activo = TRUE
        ORDER BY vc.placa
    """, (cliente_id,), fetch_all=True)

    return jsonify([dict(v) for v in vehiculos])


@solicitudes_bp.route('/api/repuestos-categoria/<int:categoria_id>')
@login_required
def api_repuestos_categoria(categoria_id):
    """Obtener repuestos por categoría con disponibilidad"""
    repuestos = execute_query("""
        SELECT r.codigo as id, r.codigo, r.nombre, r.precio_venta,
               r.cantidad_actual, r.cantidad_reservada,
               (r.cantidad_actual - r.cantidad_reservada) as disponible
        FROM repuestos r
        WHERE r.categoria_id = %s AND r.activo = TRUE
        AND (r.cantidad_actual - r.cantidad_reservada) > 0
        ORDER BY r.codigo ASC
    """, (categoria_id,), fetch_all=True)

    return jsonify([dict(r) for r in repuestos])


@solicitudes_bp.route('/api/buscar-repuestos')
@login_required
def api_buscar_repuestos():
    """Buscar repuestos para autocompletado"""
    query = request.args.get('q', '')
    categoria_id = request.args.get('categoria_id', type=int)

    params = []
    where_clauses = ["r.activo = TRUE", "(r.cantidad_actual - r.cantidad_reservada) > 0"]

    if query:
        where_clauses.append("(r.codigo LIKE %s OR r.nombre LIKE %s)")
        search_param = f"%{query}%"
        params.extend([search_param, search_param])

    if categoria_id:
        where_clauses.append("r.categoria_id = %s")
        params.append(categoria_id)

    where_sql = " AND ".join(where_clauses)

    repuestos = execute_query(f"""
        SELECT r.codigo as id, r.codigo, r.nombre, r.precio_venta,
               r.cantidad_actual, r.cantidad_reservada,
               (r.cantidad_actual - r.cantidad_reservada) as disponible,
               c.nombre as categoria
        FROM repuestos r
        LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
        WHERE {where_sql}
        ORDER BY r.codigo ASC
        LIMIT 20
    """, tuple(params), fetch_all=True)

    return jsonify([dict(r) for r in repuestos])
