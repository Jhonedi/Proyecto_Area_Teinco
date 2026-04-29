# -*- coding: utf-8 -*-
"""
Módulo de Facturación
- Vendedores crean facturas desde solicitudes entregadas o directamente
- El inventario solo se deduce cuando la factura es pagada (no al entregar)
- Soporta pagos parciales y múltiples métodos de pago
- IVA 19% (impuesto colombiano)
- Anulación revierte movimientos de inventario si ya estaba pagada
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, Response
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from database import execute_query
from auth import (
    login_required, role_required, get_current_user,
    can_confirm_sales, can_create_sales, registrar_audit_log
)
from . import facturacion_bp
import logging
import json
import io

logger = logging.getLogger(__name__)

# Constante IVA Colombia
IVA_PORCENTAJE = Decimal('19.00')


def generar_numero_factura():
    """Genera un número único de factura en formato FAC-YYYYMMDD-XXXX"""
    fecha = datetime.now().strftime('%Y%m%d')
    prefijo = current_app.config.get('PREFIJO_FACTURA', 'FAC')

    # Obtener el último número del día
    ultimo = execute_query("""
        SELECT numero_factura FROM facturas
        WHERE numero_factura LIKE %s
        ORDER BY id DESC LIMIT 1
    """, (f'{prefijo}-{fecha}-%',), fetch_one=True)

    if ultimo:
        try:
            ultimo_num = int(ultimo['numero_factura'].split('-')[-1])
            nuevo_num = ultimo_num + 1
        except Exception:
            nuevo_num = 1
    else:
        nuevo_num = 1

    return f"{prefijo}-{fecha}-{nuevo_num:04d}"


# ==================== RUTAS DE FACTURACIÓN ====================

@facturacion_bp.route('/')
@login_required
@role_required('ADMINISTRADOR', 'VENDEDOR', 'ALMACENISTA')
def lista_facturas():
    """Lista de facturas con filtros y paginación"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    estado = request.args.get('estado', '')
    search = request.args.get('search', '')

    per_page = current_app.config['ITEMS_PER_PAGE']
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    # Vendedores solo ven sus propias facturas
    if user['rol_nombre'] == 'VENDEDOR':
        where_clauses.append("f.vendedor_id = %s")
        params.append(user['id'])

    if estado:
        where_clauses.append("f.estado = %s")
        params.append(estado)

    if search:
        where_clauses.append("""
            (f.numero_factura LIKE %s OR c.nombre_completo LIKE %s
             OR v.placa LIKE %s OR c.numero_documento LIKE %s)
        """)
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param, search_param])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Total de registros
    total = execute_query(f"""
        SELECT COUNT(*) as count
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON f.vehiculo_cliente_id = v.placa
        WHERE {where_sql}
    """, tuple(params), fetch_one=True)['count']

    # Obtener facturas
    params.extend([per_page, offset])
    facturas = execute_query(f"""
        SELECT f.*,
               c.nombre_completo as cliente_nombre,
               c.numero_documento as cliente_documento,
               v.placa,
               uv.nombre_completo as vendedor_nombre,
               (SELECT IFNULL(SUM(pf.monto), 0) FROM pagos_factura pf WHERE pf.factura_id = f.id) as total_pagado
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON f.vehiculo_cliente_id = v.placa
        JOIN usuarios uv ON f.vendedor_id = uv.numero_documento
        WHERE {where_sql}
        ORDER BY f.created_at DESC
        LIMIT %s OFFSET %s
    """, tuple(params), fetch_all=True)

    total_pages = (total + per_page - 1) // per_page

    estados = ['EN_ESPERA', 'PENDIENTE', 'PAGADA', 'ANULADA']

    return render_template('facturacion/lista.html',
                         facturas=facturas,
                         page=page,
                         total_pages=total_pages,
                         estado=estado,
                         search=search,
                         estados=estados)


@facturacion_bp.route('/desde-solicitud/<int:solicitud_id>')
@login_required
def crear_desde_solicitud(solicitud_id):
    """Formulario para crear factura desde una solicitud entregada"""
    user = get_current_user()

    if not can_create_sales():
        flash('No tiene permisos para crear facturas', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    # Obtener la solicitud con datos del cliente y vehículo
    solicitud = execute_query("""
        SELECT s.*,
               ut.nombre_completo as tecnico_nombre,
               c.numero_documento as cliente_id, c.nombre_completo as cliente_nombre,
               c.numero_documento as cliente_documento,
               c.telefono as cliente_telefono,
               c.email as cliente_email,
               c.direccion as cliente_direccion,
               v.placa as vehiculo_id, v.placa, v.color, v.anio,
               mv.nombre as modelo_nombre,
               ma.nombre as marca_nombre
        FROM solicitudes_repuestos s
        JOIN usuarios ut ON s.tecnico_id = ut.numero_documento
        JOIN clientes c ON s.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON s.vehiculo_id = v.placa
        JOIN modelos_vehiculos mv ON v.modelo_vehiculo_id = mv.id
        JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
        WHERE s.id = %s
    """, (solicitud_id,), fetch_one=True)

    if not solicitud:
        flash('Solicitud no encontrada', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    if solicitud['estado'] != 'ENTREGADA':
        flash('Solo se pueden facturar solicitudes en estado ENTREGADA', 'warning')
        return redirect(url_for('solicitudes.ver_solicitud', id=solicitud_id))

    # Verificar que no exista ya una factura activa para esta solicitud
    factura_existente = execute_query("""
        SELECT id, numero_factura FROM facturas
        WHERE solicitud_id = %s AND estado NOT IN ('ANULADA')
    """, (solicitud_id,), fetch_one=True)

    if factura_existente:
        flash(f'Ya existe la factura {factura_existente["numero_factura"]} para esta solicitud', 'warning')
        return redirect(url_for('facturacion.ver_factura', id=factura_existente['id']))

    # Obtener items entregados de la solicitud
    items = execute_query("""
        SELECT i.*,
               r.codigo as repuesto_codigo,
               r.nombre as repuesto_nombre,
               r.precio_venta as precio_actual,
               c.nombre as categoria
        FROM items_solicitud i
        JOIN repuestos r ON i.repuesto_id = r.codigo
        LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
        WHERE i.solicitud_id = %s AND i.estado = 'ENTREGADO'
        ORDER BY r.codigo ASC
    """, (solicitud_id,), fetch_all=True)

    if not items:
        flash('No hay ítems entregados para facturar en esta solicitud', 'warning')
        return redirect(url_for('solicitudes.ver_solicitud', id=solicitud_id))

    # Calcular totales previos
    subtotal = Decimal('0.00')
    for item in items:
        cantidad = item['cantidad_entregada'] or item['cantidad_aprobada'] or item['cantidad_solicitada']
        cantidad_devuelta = item['cantidad_devuelta'] or 0
        cantidad_facturar = cantidad - cantidad_devuelta
        precio = Decimal(str(item['precio_unitario']))
        subtotal += precio * cantidad_facturar

    iva = (subtotal * IVA_PORCENTAJE / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = subtotal + iva

    metodos_pago = ['EFECTIVO', 'TARJETA', 'TRANSFERENCIA', 'CREDITO', 'MIXTO']

    return render_template('facturacion/crear_desde_solicitud.html',
                         solicitud=solicitud,
                         items=items,
                         subtotal=subtotal,
                         iva=iva,
                         total=total,
                         iva_porcentaje=IVA_PORCENTAJE,
                         metodos_pago=metodos_pago)


@facturacion_bp.route('/crear', methods=['POST'])
@login_required
def crear_factura():
    """Crear una nueva factura"""
    user = get_current_user()

    if not can_create_sales():
        flash('No tiene permisos para crear facturas', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    try:
        cliente_id = request.form['cliente_id']
        vehiculo_cliente_id = request.form['vehiculo_cliente_id']
        solicitud_id = request.form.get('solicitud_id') or None
        metodo_pago = request.form.get('metodo_pago', 'EFECTIVO')
        observaciones = request.form.get('observaciones', '')
        descuento_global = Decimal(request.form.get('descuento_global', '0') or '0')

        # Dias de vencimiento para crédito
        dias_vencimiento = int(request.form.get('dias_vencimiento', '30') or '30')
        fecha_vencimiento = None
        if metodo_pago == 'CREDITO':
            fecha_vencimiento = (datetime.now() + timedelta(days=dias_vencimiento)).strftime('%Y-%m-%d')

        # Obtener items del formulario
        repuesto_ids = request.form.getlist('repuesto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio_unitario[]')
        descuentos_item = request.form.getlist('descuento_item[]')
        item_solicitud_ids = request.form.getlist('item_solicitud_id[]')

        if not repuesto_ids or not any(repuesto_ids):
            flash('Debe agregar al menos un ítem a la factura', 'warning')
            if solicitud_id:
                return redirect(url_for('facturacion.crear_desde_solicitud', solicitud_id=solicitud_id))
            return redirect(url_for('facturacion.lista_facturas'))

        # Si viene de solicitud, verificar estado
        if solicitud_id:
            solicitud = execute_query(
                "SELECT estado FROM solicitudes_repuestos WHERE id = %s",
                (solicitud_id,), fetch_one=True
            )
            if not solicitud or solicitud['estado'] != 'ENTREGADA':
                flash('La solicitud no está en estado válido para facturar', 'warning')
                return redirect(url_for('facturacion.lista_facturas'))

            # Verificar que no exista factura activa
            factura_existente = execute_query("""
                SELECT id FROM facturas
                WHERE solicitud_id = %s AND estado NOT IN ('ANULADA')
            """, (solicitud_id,), fetch_one=True)

            if factura_existente:
                flash('Ya existe una factura activa para esta solicitud', 'warning')
                return redirect(url_for('facturacion.ver_factura', id=factura_existente['id']))

        # Generar número de factura
        numero_factura = generar_numero_factura()

        # Calcular totales
        subtotal = Decimal('0.00')
        items_detalle = []

        for i, repuesto_id in enumerate(repuesto_ids):
            if not repuesto_id:
                continue

            cantidad = int(cantidades[i])
            precio_unitario = Decimal(precios[i])
            descuento_item = Decimal(descuentos_item[i]) if i < len(descuentos_item) and descuentos_item[i] else Decimal('0.00')
            item_solicitud_id = item_solicitud_ids[i] if i < len(item_solicitud_ids) and item_solicitud_ids[i] else None

            subtotal_item = (precio_unitario * cantidad - descuento_item).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            subtotal += subtotal_item

            items_detalle.append({
                'repuesto_id': repuesto_id,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'descuento': descuento_item,
                'subtotal': subtotal_item,
                'item_solicitud_id': item_solicitud_id
            })

        # Aplicar descuento global
        subtotal_con_descuento = subtotal - descuento_global
        if subtotal_con_descuento < 0:
            subtotal_con_descuento = Decimal('0.00')

        impuesto = (subtotal_con_descuento * IVA_PORCENTAJE / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = (subtotal_con_descuento + impuesto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Crear la factura con estado EN_ESPERA
        factura_id = execute_query("""
            INSERT INTO facturas
            (numero_factura, cliente_id, vehiculo_cliente_id, solicitud_id, vendedor_id,
             subtotal, impuesto, descuento, total, estado, metodo_pago,
             fecha_vencimiento, observaciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'EN_ESPERA', %s, %s, %s)
        """, (
            numero_factura, cliente_id, vehiculo_cliente_id, solicitud_id,
            user['id'], str(subtotal_con_descuento), str(impuesto), str(descuento_global),
            str(total), metodo_pago, fecha_vencimiento, observaciones
        ), commit=True)

        # Crear detalles de factura
        for item in items_detalle:
            execute_query("""
                INSERT INTO detalles_factura
                (factura_id, repuesto_id, item_solicitud_id, cantidad,
                 precio_unitario, descuento, subtotal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                factura_id, item['repuesto_id'], item['item_solicitud_id'],
                item['cantidad'], str(item['precio_unitario']),
                str(item['descuento']), str(item['subtotal'])
            ), commit=True)

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='facturas',
            registro_id=factura_id,
            accion='CREAR',
            tipo_cambio='FACTURA',
            datos_nuevos={
                'numero_factura': numero_factura,
                'cliente_id': cliente_id,
                'vehiculo_cliente_id': vehiculo_cliente_id,
                'solicitud_id': solicitud_id,
                'subtotal': str(subtotal_con_descuento),
                'impuesto': str(impuesto),
                'descuento': str(descuento_global),
                'total': str(total),
                'metodo_pago': metodo_pago,
                'total_items': len(items_detalle)
            }
        )

        # Crear notificación para administradores sobre nueva factura
        _crear_alerta_factura(factura_id, numero_factura, 'FACTURA_CREADA',
                              f'Nueva factura {numero_factura} creada por {user["nombre_completo"]}')

        flash(f'Factura {numero_factura} creada exitosamente en estado EN ESPERA', 'success')
        return redirect(url_for('facturacion.ver_factura', id=factura_id))

    except Exception as e:
        logger.error(f"Error creando factura: {e}")
        flash('Error al crear la factura. Verifique los datos e intente nuevamente.', 'danger')
        if request.form.get('solicitud_id'):
            return redirect(url_for('facturacion.crear_desde_solicitud',
                                    solicitud_id=request.form['solicitud_id']))
        return redirect(url_for('facturacion.lista_facturas'))


@facturacion_bp.route('/<int:id>')
@login_required
def ver_factura(id):
    """Ver detalle de una factura"""
    user = get_current_user()

    factura = execute_query("""
        SELECT f.*,
               c.nombre_completo as cliente_nombre,
               c.numero_documento as cliente_documento,
               c.tipo_documento as cliente_tipo_documento,
               c.telefono as cliente_telefono,
               c.email as cliente_email,
               c.direccion as cliente_direccion,
               v.placa, v.color, v.anio,
               mv.nombre as modelo_nombre,
               ma.nombre as marca_nombre,
               uv.nombre_completo as vendedor_nombre,
               ua.nombre_completo as anulado_por_nombre,
               s.numero_solicitud
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON f.vehiculo_cliente_id = v.placa
        JOIN modelos_vehiculos mv ON v.modelo_vehiculo_id = mv.id
        JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
        JOIN usuarios uv ON f.vendedor_id = uv.numero_documento
        LEFT JOIN usuarios ua ON f.anulado_por = ua.numero_documento
        LEFT JOIN solicitudes_repuestos s ON f.solicitud_id = s.id
        WHERE f.id = %s
    """, (id,), fetch_one=True)

    if not factura:
        flash('Factura no encontrada', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    # Verificar permisos - vendedores solo ven sus facturas
    if user['rol_nombre'] == 'VENDEDOR' and factura['vendedor_id'] != user['id']:
        flash('No tiene permisos para ver esta factura', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    # Obtener detalles (items) de la factura
    detalles = execute_query("""
        SELECT df.*,
               r.codigo as repuesto_codigo,
               r.nombre as repuesto_nombre,
               cat.nombre as categoria
        FROM detalles_factura df
        JOIN repuestos r ON df.repuesto_id = r.codigo
        LEFT JOIN categorias_repuestos cat ON r.categoria_id = cat.id
        WHERE df.factura_id = %s
        ORDER BY r.codigo ASC
    """, (id,), fetch_all=True)

    # Obtener historial de pagos
    pagos = execute_query("""
        SELECT pf.*,
               u.nombre_completo as recibido_por_nombre
        FROM pagos_factura pf
        LEFT JOIN usuarios u ON pf.recibido_por = u.numero_documento
        WHERE pf.factura_id = %s
        ORDER BY pf.created_at ASC
    """, (id,), fetch_all=True)

    # Calcular total pagado y saldo pendiente
    total_pagado = Decimal('0.00')
    for pago in pagos:
        total_pagado += Decimal(str(pago['monto']))

    saldo_pendiente = Decimal(str(factura['total'])) - total_pagado

    metodos_pago = ['EFECTIVO', 'TARJETA', 'TRANSFERENCIA', 'CREDITO', 'MIXTO']

    return render_template('facturacion/ver.html',
                         factura=factura,
                         detalles=detalles,
                         pagos=pagos,
                         total_pagado=total_pagado,
                         saldo_pendiente=saldo_pendiente,
                         metodos_pago=metodos_pago)


@facturacion_bp.route('/<int:id>/confirmar', methods=['POST'])
@login_required
def confirmar_factura(id):
    """Confirmar factura (pasar de EN_ESPERA a PENDIENTE)"""
    user = get_current_user()

    if not can_confirm_sales():
        flash('No tiene permisos para confirmar facturas', 'danger')
        return redirect(url_for('facturacion.ver_factura', id=id))

    factura = execute_query(
        "SELECT * FROM facturas WHERE id = %s",
        (id,), fetch_one=True
    )

    if not factura:
        flash('Factura no encontrada', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    if factura['estado'] != 'EN_ESPERA':
        flash('Solo se pueden confirmar facturas en estado EN ESPERA', 'warning')
        return redirect(url_for('facturacion.ver_factura', id=id))

    try:
        execute_query("""
            UPDATE facturas
            SET estado = 'PENDIENTE', updated_at = NOW()
            WHERE id = %s
        """, (id,), commit=True)

        registrar_audit_log(
            usuario_id=user['id'],
            tabla='facturas',
            registro_id=id,
            accion='ACTUALIZAR',
            tipo_cambio='FACTURA',
            datos_anteriores={'estado': 'EN_ESPERA'},
            datos_nuevos={'estado': 'PENDIENTE'}
        )

        flash(f'Factura {factura["numero_factura"]} confirmada. Ahora está PENDIENTE de pago.', 'success')

    except Exception as e:
        logger.error(f"Error confirmando factura: {e}")
        flash('Error al confirmar la factura', 'danger')

    return redirect(url_for('facturacion.ver_factura', id=id))


@facturacion_bp.route('/<int:id>/registrar-pago', methods=['POST'])
@login_required
def registrar_pago(id):
    """Registrar un pago (puede ser parcial) para una factura"""
    user = get_current_user()

    if not can_confirm_sales():
        flash('No tiene permisos para registrar pagos', 'danger')
        return redirect(url_for('facturacion.ver_factura', id=id))

    factura = execute_query(
        "SELECT * FROM facturas WHERE id = %s",
        (id,), fetch_one=True
    )

    if not factura:
        flash('Factura no encontrada', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    if factura['estado'] not in ('PENDIENTE', 'EN_ESPERA'):
        flash('Solo se pueden registrar pagos en facturas PENDIENTES o EN ESPERA', 'warning')
        return redirect(url_for('facturacion.ver_factura', id=id))

    try:
        monto = Decimal(request.form['monto'])
        metodo_pago_pago = request.form.get('metodo_pago', 'EFECTIVO')
        referencia = request.form.get('referencia', '')
        observaciones_pago = request.form.get('observaciones', '')

        if monto <= 0:
            flash('El monto del pago debe ser mayor a cero', 'warning')
            return redirect(url_for('facturacion.ver_factura', id=id))

        # Calcular total ya pagado
        pagado_result = execute_query("""
            SELECT IFNULL(SUM(monto), 0) as total_pagado
            FROM pagos_factura WHERE factura_id = %s
        """, (id,), fetch_one=True)
        total_pagado = Decimal(str(pagado_result['total_pagado']))

        total_factura = Decimal(str(factura['total']))
        saldo_pendiente = total_factura - total_pagado

        if monto > saldo_pendiente:
            flash(f'El monto del pago (${monto:,.2f}) excede el saldo pendiente (${saldo_pendiente:,.2f})', 'warning')
            return redirect(url_for('facturacion.ver_factura', id=id))

        # Registrar el pago
        pago_id = execute_query("""
            INSERT INTO pagos_factura
            (factura_id, monto, metodo_pago, referencia, observaciones, recibido_por)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            id, str(monto), metodo_pago_pago, referencia, observaciones_pago, user['id']
        ), commit=True)

        nuevo_total_pagado = total_pagado + monto

        # Si la factura estaba EN_ESPERA, pasarla a PENDIENTE automáticamente
        if factura['estado'] == 'EN_ESPERA':
            execute_query("""
                UPDATE facturas SET estado = 'PENDIENTE', updated_at = NOW()
                WHERE id = %s
            """, (id,), commit=True)

        # Si el total pagado cubre el total de la factura => PAGADA
        if nuevo_total_pagado >= total_factura:
            _procesar_factura_pagada(id, factura, user)
            flash(f'Pago registrado exitosamente. Factura {factura["numero_factura"]} PAGADA en su totalidad.', 'success')
        else:
            saldo_restante = total_factura - nuevo_total_pagado
            flash(f'Pago parcial de ${monto:,.2f} registrado. Saldo pendiente: ${saldo_restante:,.2f}', 'success')

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='pagos_factura',
            registro_id=pago_id,
            accion='CREAR',
            tipo_cambio='PAGO',
            datos_nuevos={
                'factura_id': id,
                'numero_factura': factura['numero_factura'],
                'monto': str(monto),
                'metodo_pago': metodo_pago_pago,
                'referencia': referencia,
                'total_pagado': str(nuevo_total_pagado),
                'total_factura': str(total_factura)
            }
        )

    except (ValueError, KeyError) as e:
        logger.error(f"Error en datos de pago: {e}")
        flash('Datos de pago inválidos. Verifique el monto.', 'danger')
    except Exception as e:
        logger.error(f"Error registrando pago: {e}")
        flash('Error al registrar el pago', 'danger')

    return redirect(url_for('facturacion.ver_factura', id=id))


def _procesar_factura_pagada(factura_id, factura, user):
    """
    Procesa una factura cuando queda completamente pagada:
    - Cambia estado a PAGADA
    - Deduce inventario (cantidad_actual y cantidad_reservada)
    - Crea movimientos de inventario con estado FACTURADO
    - Si viene de solicitud, actualiza solicitud e items a FACTURADO/FACTURADA
    - Verifica alertas de stock
    """
    # Actualizar estado de la factura
    execute_query("""
        UPDATE facturas SET estado = 'PAGADA', updated_at = NOW()
        WHERE id = %s
    """, (factura_id,), commit=True)

    # Obtener detalles de la factura
    detalles = execute_query("""
        SELECT df.*, r.nombre as repuesto_nombre
        FROM detalles_factura df
        JOIN repuestos r ON df.repuesto_id = r.codigo
        WHERE df.factura_id = %s
    """, (factura_id,), fetch_all=True)

    for detalle in detalles:
        # Deducir del inventario real y de la cantidad reservada
        execute_query("""
            UPDATE repuestos
            SET cantidad_actual = cantidad_actual - %s,
                cantidad_reservada = GREATEST(cantidad_reservada - %s, 0),
                updated_by = %s
            WHERE codigo = %s
        """, (
            detalle['cantidad'], detalle['cantidad'],
            user['id'], detalle['repuesto_id']
        ), commit=True)

        # Crear movimiento de inventario tipo salida por facturación
        movimiento_id = execute_query("""
            INSERT INTO movimientos_inventario
            (repuesto_id, tipo_movimiento_id, cantidad, precio_unitario,
             usuario_id, solicitud_id, estado, observaciones)
            VALUES (
                %s,
                (SELECT id FROM tipos_movimiento WHERE nombre = 'Venta' LIMIT 1),
                %s, %s, %s, %s, 'FACTURADO',
                %s
            )
        """, (
            detalle['repuesto_id'],
            detalle['cantidad'],
            str(detalle['precio_unitario']),
            user['id'],
            factura['solicitud_id'],
            f'Facturación - Factura {factura["numero_factura"]}'
        ), commit=True)

        # Vincular movimiento al detalle de factura
        if movimiento_id:
            execute_query("""
                UPDATE detalles_factura
                SET movimiento_inventario_id = %s
                WHERE id = %s
            """, (movimiento_id, detalle['id']), commit=True)

        # Verificar alertas de stock bajo
        _verificar_alertas_stock(detalle['repuesto_id'])

    # Si la factura viene de una solicitud, actualizar solicitud e items
    if factura['solicitud_id']:
        # Actualizar items de la solicitud a FACTURADO
        execute_query("""
            UPDATE items_solicitud
            SET estado = 'FACTURADO'
            WHERE solicitud_id = %s AND estado = 'ENTREGADO'
        """, (factura['solicitud_id'],), commit=True)

        # Actualizar solicitud a FACTURADA
        execute_query("""
            UPDATE solicitudes_repuestos
            SET estado = 'FACTURADA', facturado_por = %s, fecha_facturacion = NOW()
            WHERE id = %s
        """, (user['id'], factura['solicitud_id']), commit=True)

    # Registrar en audit log
    registrar_audit_log(
        usuario_id=user['id'],
        tabla='facturas',
        registro_id=factura_id,
        accion='ACTUALIZAR',
        tipo_cambio='FACTURA',
        datos_anteriores={'estado': factura['estado']},
        datos_nuevos={
            'estado': 'PAGADA',
            'numero_factura': factura['numero_factura'],
            'total': str(factura['total'])
        }
    )

    # Notificación
    _crear_alerta_factura(
        factura_id, factura['numero_factura'], 'FACTURA_PAGADA',
        f'Factura {factura["numero_factura"]} pagada completamente - Inventario actualizado'
    )


@facturacion_bp.route('/<int:id>/anular', methods=['POST'])
@login_required
@role_required('ADMINISTRADOR')
def anular_factura(id):
    """Anular una factura. Revierte movimientos de inventario si estaba PAGADA."""
    user = get_current_user()

    factura = execute_query(
        "SELECT * FROM facturas WHERE id = %s",
        (id,), fetch_one=True
    )

    if not factura:
        flash('Factura no encontrada', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    if factura['estado'] == 'ANULADA':
        flash('Esta factura ya está anulada', 'warning')
        return redirect(url_for('facturacion.ver_factura', id=id))

    motivo_anulacion = request.form.get('motivo_anulacion', '')
    if not motivo_anulacion.strip():
        flash('Debe indicar un motivo de anulación', 'warning')
        return redirect(url_for('facturacion.ver_factura', id=id))

    try:
        estado_anterior = factura['estado']

        # Si la factura estaba PAGADA, revertir inventario
        if estado_anterior == 'PAGADA':
            detalles = execute_query("""
                SELECT df.*, r.nombre as repuesto_nombre
                FROM detalles_factura df
                JOIN repuestos r ON df.repuesto_id = r.codigo
                WHERE df.factura_id = %s
            """, (id,), fetch_all=True)

            for detalle in detalles:
                # Devolver stock al inventario
                execute_query("""
                    UPDATE repuestos
                    SET cantidad_actual = cantidad_actual + %s,
                        updated_by = %s
                    WHERE codigo = %s
                """, (detalle['cantidad'], user['id'], detalle['repuesto_id']), commit=True)

                # Crear movimiento de inventario de reversa
                execute_query("""
                    INSERT INTO movimientos_inventario
                    (repuesto_id, tipo_movimiento_id, cantidad, precio_unitario,
                     usuario_id, solicitud_id, estado, observaciones)
                    VALUES (
                        %s,
                        (SELECT id FROM tipos_movimiento WHERE nombre = 'Devolución Técnico' LIMIT 1),
                        %s, %s, %s, %s, 'CONFIRMADO',
                        %s
                    )
                """, (
                    detalle['repuesto_id'],
                    detalle['cantidad'],
                    str(detalle['precio_unitario']),
                    user['id'],
                    factura['solicitud_id'],
                    f'Reversa por anulación de factura {factura["numero_factura"]}'
                ), commit=True)

                # Verificar alertas de stock
                _verificar_alertas_stock(detalle['repuesto_id'])

        # Si la factura viene de una solicitud, devolver a estado ENTREGADA
        if factura['solicitud_id']:
            solicitud = execute_query(
                "SELECT estado FROM solicitudes_repuestos WHERE id = %s",
                (factura['solicitud_id'],), fetch_one=True
            )

            if solicitud and solicitud['estado'] == 'FACTURADA':
                # Devolver items a ENTREGADO
                execute_query("""
                    UPDATE items_solicitud
                    SET estado = 'ENTREGADO'
                    WHERE solicitud_id = %s AND estado = 'FACTURADO'
                """, (factura['solicitud_id'],), commit=True)

                # Devolver solicitud a ENTREGADA
                execute_query("""
                    UPDATE solicitudes_repuestos
                    SET estado = 'ENTREGADA', facturado_por = NULL, fecha_facturacion = NULL
                    WHERE id = %s
                """, (factura['solicitud_id'],), commit=True)

                # Si estaba PAGADA, re-reservar stock para la solicitud
                if estado_anterior == 'PAGADA':
                    detalles_sol = execute_query("""
                        SELECT repuesto_id, cantidad_entregada
                        FROM items_solicitud
                        WHERE solicitud_id = %s AND estado = 'ENTREGADO'
                    """, (factura['solicitud_id'],), fetch_all=True)

                    for det_sol in detalles_sol:
                        execute_query("""
                            UPDATE repuestos
                            SET cantidad_reservada = cantidad_reservada + %s
                            WHERE codigo = %s
                        """, (det_sol['cantidad_entregada'], det_sol['repuesto_id']), commit=True)

        # Anular la factura
        execute_query("""
            UPDATE facturas
            SET estado = 'ANULADA',
                anulado_por = %s,
                fecha_anulacion = NOW(),
                motivo_anulacion = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (user['id'], motivo_anulacion, id), commit=True)

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='facturas',
            registro_id=id,
            accion='ANULAR',
            tipo_cambio='FACTURA',
            datos_anteriores={
                'estado': estado_anterior,
                'numero_factura': factura['numero_factura']
            },
            datos_nuevos={
                'estado': 'ANULADA',
                'motivo_anulacion': motivo_anulacion,
                'anulado_por': user['id'],
                'inventario_revertido': estado_anterior == 'PAGADA'
            }
        )

        # Notificación
        _crear_alerta_factura(
            id, factura['numero_factura'], 'FACTURA_ANULADA',
            f'Factura {factura["numero_factura"]} anulada por {user["nombre_completo"]}. Motivo: {motivo_anulacion}'
        )

        if estado_anterior == 'PAGADA':
            flash(f'Factura {factura["numero_factura"]} anulada. El inventario ha sido revertido.', 'success')
        else:
            flash(f'Factura {factura["numero_factura"]} anulada exitosamente.', 'success')

    except Exception as e:
        logger.error(f"Error anulando factura: {e}")
        flash('Error al anular la factura', 'danger')

    return redirect(url_for('facturacion.ver_factura', id=id))


# ==================== API ENDPOINTS ====================

@facturacion_bp.route('/api/pendientes')
@login_required
def api_facturas_pendientes():
    """API: Conteo de facturas pendientes para el dashboard"""
    user = get_current_user()

    where_extra = ""
    params = []

    # Vendedores solo ven sus facturas pendientes
    if user['rol_nombre'] == 'VENDEDOR':
        where_extra = " AND vendedor_id = %s"
        params.append(user['id'])

    result = execute_query(f"""
        SELECT
            COUNT(*) as total_pendientes,
            IFNULL(SUM(CASE WHEN estado = 'EN_ESPERA' THEN 1 ELSE 0 END), 0) as en_espera,
            IFNULL(SUM(CASE WHEN estado = 'PENDIENTE' THEN 1 ELSE 0 END), 0) as pendientes,
            IFNULL(SUM(total), 0) as valor_pendiente
        FROM facturas
        WHERE estado IN ('EN_ESPERA', 'PENDIENTE') {where_extra}
    """, tuple(params) if params else None, fetch_one=True)

    return jsonify({
        'total_pendientes': result['total_pendientes'],
        'en_espera': result['en_espera'],
        'pendientes': result['pendientes'],
        'valor_pendiente': float(result['valor_pendiente'])
    })


@facturacion_bp.route('/api/solicitudes-facturables')
@login_required
def api_solicitudes_facturables():
    """API: Solicitudes en estado ENTREGADA listas para facturar"""
    solicitudes = execute_query("""
        SELECT s.id, s.numero_solicitud, s.created_at,
               c.nombre_completo as cliente_nombre,
               v.placa,
               (SELECT SUM(i.cantidad_entregada * i.precio_unitario)
                FROM items_solicitud i
                WHERE i.solicitud_id = s.id AND i.estado = 'ENTREGADO') as valor_estimado
        FROM solicitudes_repuestos s
        JOIN clientes c ON s.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON s.vehiculo_id = v.placa
        WHERE s.estado = 'ENTREGADA'
        AND NOT EXISTS (
            SELECT 1 FROM facturas f
            WHERE f.solicitud_id = s.id AND f.estado NOT IN ('ANULADA')
        )
        ORDER BY s.created_at ASC
    """, fetch_all=True)

    return jsonify([dict(s) for s in solicitudes])


# ==================== FUNCIONES AUXILIARES ====================

def _verificar_alertas_stock(repuesto_codigo):
    """Verifica y crea alertas de stock bajo para un repuesto (identificado por codigo)"""
    try:
        repuesto = execute_query("""
            SELECT codigo, nombre, cantidad_actual, cantidad_minima
            FROM repuestos WHERE codigo = %s
        """, (repuesto_codigo,), fetch_one=True)

        if not repuesto:
            return

        # Resolver alertas si el stock está bien
        if repuesto['cantidad_actual'] > repuesto['cantidad_minima']:
            execute_query("""
                UPDATE alertas_inventario
                SET estado = 'RESUELTA', fecha_resolucion = NOW()
                WHERE repuesto_id = %s AND estado IN ('NUEVA', 'EN_PROCESO')
                AND tipo_alerta IN ('STOCK_BAJO', 'AGOTADO')
            """, (repuesto_codigo,), commit=True)
            return

        # Determinar tipo de alerta
        if repuesto['cantidad_actual'] == 0:
            tipo_alerta = 'AGOTADO'
            nivel = 'CRITICA'
            mensaje = f"AGOTADO: {repuesto['nombre']} ({repuesto['codigo']}) - Sin stock tras facturación"
        elif repuesto['cantidad_actual'] <= repuesto['cantidad_minima']:
            tipo_alerta = 'STOCK_BAJO'
            nivel = 'ALTA'
            mensaje = f"Stock bajo: {repuesto['nombre']} ({repuesto['codigo']}) - {repuesto['cantidad_actual']} unidades"
        else:
            return

        # Verificar si ya existe alerta activa del mismo tipo
        alerta_existente = execute_query("""
            SELECT id FROM alertas_inventario
            WHERE repuesto_id = %s AND estado IN ('NUEVA', 'EN_PROCESO') AND tipo_alerta = %s
        """, (repuesto_codigo, tipo_alerta), fetch_one=True)

        if not alerta_existente:
            alerta_id = execute_query("""
                INSERT INTO alertas_inventario
                (repuesto_id, tipo_alerta, nivel_prioridad, mensaje)
                VALUES (%s, %s, %s, %s)
            """, (repuesto_codigo, tipo_alerta, nivel, mensaje), commit=True)

            # Notificar a administradores y almacenistas
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
        logger.error(f"Error verificando alertas de stock: {e}")


@facturacion_bp.route('/<int:id>/pdf')
@login_required
@role_required('ADMINISTRADOR', 'VENDEDOR', 'ALMACENISTA')
def factura_pdf(id):
    """Genera y descarga el PDF de una factura"""
    factura = execute_query("""
        SELECT f.*,
               c.nombre_completo as cliente_nombre,
               c.numero_documento as cliente_documento,
               c.tipo_documento as cliente_tipo_documento,
               c.telefono as cliente_telefono,
               c.email as cliente_email,
               c.direccion as cliente_direccion,
               v.placa, v.color, v.anio,
               mv.nombre as modelo_nombre,
               ma.nombre as marca_nombre,
               uv.nombre_completo as vendedor_nombre,
               s.numero_solicitud
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.numero_documento
        JOIN vehiculos_clientes v ON f.vehiculo_cliente_id = v.placa
        JOIN modelos_vehiculos mv ON v.modelo_vehiculo_id = mv.id
        JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
        JOIN usuarios uv ON f.vendedor_id = uv.numero_documento
        LEFT JOIN solicitudes_repuestos s ON f.solicitud_id = s.id
        WHERE f.id = %s
    """, (id,), fetch_one=True)

    if not factura:
        flash('Factura no encontrada', 'danger')
        return redirect(url_for('facturacion.lista_facturas'))

    detalles = execute_query("""
        SELECT df.*,
               r.codigo as repuesto_codigo,
               r.nombre as repuesto_nombre
        FROM detalles_factura df
        JOIN repuestos r ON df.repuesto_id = r.codigo
        WHERE df.factura_id = %s
        ORDER BY r.codigo ASC
    """, (id,), fetch_all=True)

    # Cargar configuración de empresa desde BD
    # %% necesario: PyMySQL interpreta % como placeholder de formato SQL
    config_rows = execute_query("""
        SELECT clave, valor FROM configuracion_sistema
        WHERE clave LIKE 'EMPRESA_%%'
    """, fetch_all=True)
    empresa = {row['clave']: row['valor'] for row in (config_rows or [])}

    html = render_template('facturacion/pdf.html',
                           factura=factura,
                           detalles=detalles,
                           empresa=empresa,
                           now=datetime.now())

    try:
        from xhtml2pdf import pisa
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
        if pisa_status.err:
            flash('Error al generar el PDF', 'danger')
            return redirect(url_for('facturacion.ver_factura', id=id))
        pdf_buffer.seek(0)
        filename = f"Factura_{factura['numero_factura']}.pdf"
        return Response(
            pdf_buffer.read(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        flash(f'Error al generar el PDF: {e}', 'danger')
        return redirect(url_for('facturacion.ver_factura', id=id))


def _crear_alerta_factura(factura_id, numero_factura, tipo_alerta, mensaje):
    """Crea una alerta/notificación relacionada con facturación.
    tipo_alerta es ignorado en el INSERT (siempre usa 'FACTURA_PENDIENTE' que es el ENUM válido);
    el evento real se guarda en datos_adicionales.
    """
    try:
        alerta_id = execute_query("""
            INSERT INTO alertas_inventario
            (tipo_alerta, nivel_prioridad, mensaje, datos_adicionales)
            VALUES ('FACTURA_PENDIENTE', 'MEDIA', %s, %s)
        """, (
            mensaje,
            json.dumps({'factura_id': factura_id, 'numero_factura': numero_factura,
                        'evento': tipo_alerta})
        ), commit=True)

        # Notificar a administradores y vendedores
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
        logger.error(f"Error creando alerta de facturación: {e}")
