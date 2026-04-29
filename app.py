from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from config import config
from database import init_db, execute_query
from auth import (
    login_user, logout_user, get_current_user, is_authenticated,
    login_required, role_required, get_permissions, hash_password,
    can_approve_adjustments, is_super_user, registrar_audit_log
)
import os
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name='default'):
    """Factory para crear la aplicación Flask"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Inicializar base de datos
    init_db(app)

    # Registrar blueprints
    from routes import register_blueprints
    register_blueprints(app)

    # Crear directorio de uploads si no existe
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)
    os.makedirs(os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'repuestos'), exist_ok=True)

    # Filtro Jinja2 para formato colombiano
    @app.template_filter('formato_cop')
    def formato_cop(value):
        """Formato colombiano: puntos para miles, coma para decimales. Ej: 54.568.950,25"""
        if value is None:
            return '0,00'
        try:
            value = float(value)
        except (ValueError, TypeError):
            return '0,00'
        negativo = value < 0
        value = abs(value)
        parte_entera = int(value)
        parte_decimal = round((value - parte_entera) * 100)
        # Formatear parte entera con puntos como separador de miles
        s = str(parte_entera)
        groups = []
        while s:
            groups.insert(0, s[-3:])
            s = s[:-3]
        formatted = '.'.join(groups)
        resultado = f"{formatted},{parte_decimal:02d}"
        if negativo:
            resultado = f"-{resultado}"
        return resultado

    @app.template_filter('formato_cop_moneda')
    def formato_cop_moneda(value):
        """Formato con signo de peso"""
        return f"$ {formato_cop(value)}"

    @app.template_filter('formato_telefono')
    def formato_telefono_filter(telefono):
        """Formato de teléfono colombiano: NNN NNN NNNN — Ej: 315 667 7889"""
        if not telefono:
            return '-'
        digits = ''.join(c for c in str(telefono) if c.isdigit())
        if len(digits) == 10:
            return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
        if len(digits) == 7:
            return f"{digits[:3]} {digits[3:]}"
        return str(telefono)

    # Context processor para variables globales en templates
    @app.context_processor
    def inject_globals():
        return {
            'current_user': get_current_user(),
            'permissions': get_permissions() if is_authenticated() else {},
            'now': datetime.now()
        }

    # ==================== CONTROL DE SESIÓN ====================

    @app.before_request
    def check_session_activity():
        """Verificar inactividad y cerrar sesión si excede el timeout"""
        # Rutas que no requieren verificación
        if request.endpoint in ('login', 'static', None):
            return

        if is_authenticated():
            last_activity = session.get('last_activity')
            timeout_minutes = app.config.get('SESSION_INACTIVITY_TIMEOUT', 30)

            if last_activity:
                try:
                    last = datetime.fromisoformat(last_activity)
                    if datetime.now() - last > timedelta(minutes=timeout_minutes):
                        logout_user()
                        flash('Sesión cerrada por inactividad', 'warning')
                        return redirect(url_for('login'))
                except (ValueError, TypeError):
                    pass

            session['last_activity'] = datetime.now().isoformat()

            # Verificar recordatorios diarios de alertas
            try:
                _verificar_recordatorios_alertas()
            except:
                pass

    def _verificar_recordatorios_alertas():
        """Resetea notificaciones leídas si la alerta sigue activa y pasó el día"""
        user = get_current_user()
        if not user:
            return
        try:
            execute_query("""
                UPDATE notificaciones_usuarios n
                JOIN alertas_inventario a ON n.alerta_id = a.id
                SET n.leida = FALSE
                WHERE n.usuario_id = %s
                AND n.leida = TRUE
                AND a.estado IN ('NUEVA', 'EN_PROCESO')
                AND (n.ultimo_recordatorio_enviado IS NULL OR n.ultimo_recordatorio_enviado < CURDATE())
            """, (user['id'],), commit=True)
            # Actualizar fecha de recordatorio
            execute_query("""
                UPDATE notificaciones_usuarios n
                JOIN alertas_inventario a ON n.alerta_id = a.id
                SET n.ultimo_recordatorio_enviado = CURDATE()
                WHERE n.usuario_id = %s
                AND a.estado IN ('NUEVA', 'EN_PROCESO')
                AND (n.ultimo_recordatorio_enviado IS NULL OR n.ultimo_recordatorio_enviado < CURDATE())
            """, (user['id'],), commit=True)
        except:
            pass

    # ==================== RUTAS DE AUTENTICACIÓN ====================

    @app.route('/')
    def index():
        if is_authenticated():
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if is_authenticated():
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            user = login_user(username, password)
            if user:
                flash(f'Bienvenido {user["nombre_completo"]}', 'success')
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('dashboard'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Sesión cerrada exitosamente', 'success')
        return redirect(url_for('login'))

    # ==================== DASHBOARD ====================

    @app.route('/dashboard')
    @login_required
    def dashboard():
        user = get_current_user()
        stats = {}

        stats['total_repuestos'] = execute_query(
            "SELECT COUNT(*) as count FROM repuestos WHERE activo = TRUE",
            fetch_one=True
        )['count']

        stats['valor_inventario'] = execute_query(
            "SELECT COALESCE(SUM(cantidad_actual * precio_venta), 0) as total FROM repuestos WHERE activo = TRUE",
            fetch_one=True
        )['total'] or 0

        stats['alertas_activas'] = execute_query(
            "SELECT COUNT(*) as count FROM alertas_inventario WHERE estado IN ('NUEVA', 'EN_PROCESO')",
            fetch_one=True
        )['count']

        stats['movimientos_hoy'] = execute_query(
            "SELECT COUNT(*) as count FROM movimientos_inventario WHERE DATE(created_at) = CURDATE()",
            fetch_one=True
        )['count']

        # Estadísticas adicionales
        try:
            stats['solicitudes_pendientes'] = execute_query(
                "SELECT COUNT(*) as count FROM solicitudes_repuestos WHERE estado = 'PENDIENTE'",
                fetch_one=True
            )['count']
        except:
            stats['solicitudes_pendientes'] = 0

        try:
            stats['facturas_pendientes'] = execute_query(
                "SELECT COUNT(*) as count FROM facturas WHERE estado IN ('EN_ESPERA', 'PENDIENTE')",
                fetch_one=True
            )['count']
        except:
            stats['facturas_pendientes'] = 0

        try:
            stats['ajustes_pendientes'] = execute_query(
                "SELECT COUNT(*) as count FROM historial_ajustes_inventario WHERE estado = 'PENDIENTE'",
                fetch_one=True
            )['count']
        except:
            stats['ajustes_pendientes'] = 0

        repuestos_bajo_stock = execute_query("""
            SELECT r.codigo, r.nombre, r.cantidad_actual, r.cantidad_minima,
                   r.cantidad_reservada, c.nombre as categoria
            FROM repuestos r
            LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
            WHERE r.activo = TRUE AND r.cantidad_actual <= r.cantidad_minima
            ORDER BY r.cantidad_actual ASC
            LIMIT 10
        """, fetch_all=True)

        ultimos_movimientos = execute_query("""
            SELECT mi.id, mi.cantidad, mi.estado, mi.created_at,
                   r.codigo as repuesto_codigo, r.nombre as repuesto_nombre,
                   tm.nombre as tipo_movimiento, tm.tipo,
                   u.nombre_completo as usuario
            FROM movimientos_inventario mi
            JOIN repuestos r ON mi.repuesto_id = r.codigo
            JOIN tipos_movimiento tm ON mi.tipo_movimiento_id = tm.id
            JOIN usuarios u ON mi.usuario_id = u.numero_documento
            ORDER BY mi.created_at DESC
            LIMIT 10
        """, fetch_all=True)

        return render_template('dashboard.html',
                             stats=stats,
                             repuestos_bajo_stock=repuestos_bajo_stock,
                             ultimos_movimientos=ultimos_movimientos)

    # ==================== GESTIÓN DE REPUESTOS ====================

    @app.route('/repuestos')
    @login_required
    def lista_repuestos():
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        categoria_id = request.args.get('categoria', type=int)

        per_page = app.config['ITEMS_PER_PAGE']
        offset = (page - 1) * per_page

        where_clauses = ["r.activo = TRUE"]
        params = []

        if search:
            where_clauses.append("(r.codigo LIKE %s OR r.nombre LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])

        if categoria_id:
            where_clauses.append("r.categoria_id = %s")
            params.append(categoria_id)

        where_sql = " AND ".join(where_clauses)

        total = execute_query(
            f"SELECT COUNT(*) as count FROM repuestos r WHERE {where_sql}",
            tuple(params), fetch_one=True
        )['count']

        params.extend([per_page, offset])
        repuestos = execute_query(f"""
            SELECT r.*, c.nombre as categoria_nombre,
                   (r.cantidad_actual - r.cantidad_reservada) as disponible
            FROM repuestos r
            LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
            WHERE {where_sql}
            ORDER BY r.codigo ASC
            LIMIT %s OFFSET %s
        """, tuple(params), fetch_all=True)

        categorias = execute_query(
            "SELECT * FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre",
            fetch_all=True
        )

        total_pages = (total + per_page - 1) // per_page

        return render_template('repuestos/lista.html',
                             repuestos=repuestos,
                             categorias=categorias,
                             page=page,
                             total_pages=total_pages,
                             search=search,
                             categoria_id=categoria_id)

    @app.route('/repuestos/nuevo', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def nuevo_repuesto():
        if request.method == 'POST':
            try:
                user = get_current_user()
                codigo = request.form['codigo']
                execute_query("""
                    INSERT INTO repuestos
                    (codigo, nombre, descripcion, descripcion_detallada, categoria_id, precio_venta,
                     cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante, observaciones, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    codigo,
                    request.form['nombre'],
                    request.form.get('descripcion', ''),
                    request.form.get('descripcion_detallada', ''),
                    request.form.get('categoria_id') or None,
                    request.form['precio_venta'],
                    request.form.get('cantidad_actual', 0),
                    request.form.get('cantidad_minima', 5),
                    request.form.get('ubicacion_fisica', ''),
                    request.form.get('marca_fabricante', ''),
                    request.form.get('observaciones', ''),
                    user['id']
                ), commit=True)

                # Manejar imágenes
                _procesar_imagenes_repuesto(codigo, user['id'])

                registrar_audit_log(
                    usuario_id=user['id'], tabla='repuestos', registro_id=codigo,
                    accion='CREAR', tipo_cambio='INVENTARIO',
                    datos_nuevos={'codigo': codigo, 'nombre': request.form['nombre']}
                )

                flash('Repuesto creado exitosamente', 'success')
                return redirect(url_for('lista_repuestos'))

            except Exception as e:
                logger.error(f"Error creando repuesto: {e}")
                flash('Error al crear el repuesto', 'danger')

        categorias = execute_query(
            "SELECT * FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre",
            fetch_all=True
        )
        return render_template('repuestos/form.html', categorias=categorias, repuesto=None)

    @app.route('/repuestos/<string:codigo>/editar', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def editar_repuesto(codigo):
        repuesto = execute_query("SELECT * FROM repuestos WHERE codigo = %s", (codigo,), fetch_one=True)

        if not repuesto:
            flash('Repuesto no encontrado', 'danger')
            return redirect(url_for('lista_repuestos'))

        if request.method == 'POST':
            try:
                user = get_current_user()
                datos_anteriores = {
                    'codigo': repuesto['codigo'], 'nombre': repuesto['nombre'],
                    'precio_venta': str(repuesto['precio_venta'])
                }

                execute_query("""
                    UPDATE repuestos
                    SET codigo = %s, nombre = %s, descripcion = %s, descripcion_detallada = %s,
                        categoria_id = %s, precio_venta = %s, cantidad_minima = %s,
                        ubicacion_fisica = %s, marca_fabricante = %s, observaciones = %s,
                        updated_by = %s
                    WHERE codigo = %s
                """, (
                    request.form['codigo'],
                    request.form['nombre'],
                    request.form.get('descripcion', ''),
                    request.form.get('descripcion_detallada', ''),
                    request.form.get('categoria_id') or None,
                    request.form['precio_venta'],
                    request.form.get('cantidad_minima', 5),
                    request.form.get('ubicacion_fisica', ''),
                    request.form.get('marca_fabricante', ''),
                    request.form.get('observaciones', ''),
                    user['id'], codigo
                ), commit=True)

                _procesar_imagenes_repuesto(codigo, user['id'])

                registrar_audit_log(
                    usuario_id=user['id'], tabla='repuestos', registro_id=codigo,
                    accion='ACTUALIZAR', tipo_cambio='INVENTARIO',
                    datos_anteriores=datos_anteriores,
                    datos_nuevos={'codigo': request.form['codigo'], 'nombre': request.form['nombre']}
                )

                flash('Repuesto actualizado exitosamente', 'success')
                return redirect(url_for('lista_repuestos'))

            except Exception as e:
                logger.error(f"Error actualizando repuesto: {e}")
                flash('Error al actualizar el repuesto', 'danger')

        categorias = execute_query(
            "SELECT * FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre",
            fetch_all=True
        )
        # Obtener imágenes existentes
        imagenes = execute_query(
            "SELECT * FROM imagenes_repuestos WHERE repuesto_id = %s ORDER BY es_principal DESC, orden",
            (codigo,), fetch_all=True
        )
        return render_template('repuestos/form.html', categorias=categorias, repuesto=repuesto, imagenes=imagenes)

    @app.route('/repuestos/<string:codigo>/eliminar', methods=['POST'])
    @role_required('ADMINISTRADOR')
    def eliminar_repuesto(codigo):
        try:
            user = get_current_user()
            execute_query("UPDATE repuestos SET activo = FALSE, updated_by = %s WHERE codigo = %s",
                         (user['id'], codigo), commit=True)
            registrar_audit_log(
                usuario_id=user['id'], tabla='repuestos', registro_id=codigo,
                accion='ELIMINAR', tipo_cambio='INVENTARIO'
            )
            flash('Repuesto eliminado exitosamente', 'success')
        except Exception as e:
            logger.error(f"Error eliminando repuesto: {e}")
            flash('Error al eliminar el repuesto', 'danger')
        return redirect(url_for('lista_repuestos'))

    @app.route('/repuestos/<string:codigo>/ajustar-cantidad', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def ajustar_cantidad_repuesto(codigo):
        repuesto = execute_query("SELECT * FROM repuestos WHERE codigo = %s", (codigo,), fetch_one=True)
        if not repuesto:
            flash('Repuesto no encontrado', 'danger')
            return redirect(url_for('lista_repuestos'))

        if request.method == 'POST':
            try:
                nueva_cantidad = int(request.form['nueva_cantidad'])
                motivo = request.form.get('motivo', '')
                user = get_current_user()

                cantidad_anterior = repuesto['cantidad_actual']
                diferencia = nueva_cantidad - cantidad_anterior

                # Si es ADMIN o SUPER_USUARIO, aprobar automáticamente
                if can_approve_adjustments():
                    estado = 'APROBADO'
                    aprobado_por = user['id']

                    execute_query("""
                        INSERT INTO historial_ajustes_inventario
                        (repuesto_id, cantidad_anterior, cantidad_nueva, diferencia, usuario_id, motivo,
                         estado, aprobado_por, fecha_aprobacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (codigo, cantidad_anterior, nueva_cantidad, diferencia, user['id'], motivo,
                          estado, aprobado_por), commit=True)

                    execute_query(
                        "UPDATE repuestos SET cantidad_actual = %s, updated_by = %s WHERE codigo = %s",
                        (nueva_cantidad, user['id'], codigo), commit=True
                    )
                    verificar_alertas(codigo)
                    flash('Cantidad ajustada exitosamente', 'success')
                else:
                    # Almacenista: crear ajuste PENDIENTE
                    ajuste_id = execute_query("""
                        INSERT INTO historial_ajustes_inventario
                        (repuesto_id, cantidad_anterior, cantidad_nueva, diferencia, usuario_id, motivo, estado)
                        VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE')
                    """, (codigo, cantidad_anterior, nueva_cantidad, diferencia, user['id'], motivo), commit=True)

                    # Crear alerta para admins
                    alerta_id = execute_query("""
                        INSERT INTO alertas_inventario
                        (tipo_alerta, nivel_prioridad, mensaje, datos_adicionales)
                        VALUES ('AJUSTE_PENDIENTE', 'ALTA', %s, %s)
                    """, (
                        f'Ajuste de inventario pendiente de aprobación para {repuesto["nombre"]}',
                        json.dumps({'ajuste_id': ajuste_id, 'repuesto_id': codigo, 'diferencia': diferencia})
                    ), commit=True)

                    # Notificar admins
                    admins = execute_query("""
                        SELECT u.numero_documento as id FROM usuarios u JOIN roles r ON u.rol_id = r.id
                        WHERE r.nombre IN ('SUPER_USUARIO', 'ADMINISTRADOR') AND u.activo = TRUE
                    """, fetch_all=True)
                    for admin in admins:
                        execute_query(
                            "INSERT IGNORE INTO notificaciones_usuarios (usuario_id, alerta_id) VALUES (%s, %s)",
                            (admin['id'], alerta_id), commit=True
                        )

                    flash('Ajuste enviado para aprobación. Un administrador debe autorizarlo.', 'info')

                registrar_audit_log(
                    usuario_id=user['id'], tabla='repuestos', registro_id=codigo,
                    accion='AJUSTE', tipo_cambio='INVENTARIO',
                    datos_anteriores={'cantidad_actual': cantidad_anterior},
                    datos_nuevos={'cantidad_nueva': nueva_cantidad, 'diferencia': diferencia}
                )

                return redirect(url_for('lista_repuestos'))

            except Exception as e:
                logger.error(f"Error ajustando cantidad: {e}")
                flash('Error al ajustar la cantidad', 'danger')

        return render_template('repuestos/ajustar_cantidad.html', repuesto=repuesto)

    # Rutas de aprobación de ajustes
    @app.route('/repuestos/ajustes-pendientes')
    @role_required('ADMINISTRADOR')
    def ajustes_pendientes():
        ajustes = execute_query("""
            SELECT h.*, r.codigo, r.nombre as repuesto_nombre, r.cantidad_actual,
                   u.nombre_completo as solicitante
            FROM historial_ajustes_inventario h
            JOIN repuestos r ON h.repuesto_id = r.codigo
            JOIN usuarios u ON h.usuario_id = u.numero_documento
            WHERE h.estado = 'PENDIENTE'
            ORDER BY h.created_at DESC
        """, fetch_all=True)
        return render_template('repuestos/ajustes_pendientes.html', ajustes=ajustes)

    @app.route('/repuestos/ajuste/<int:id>/aprobar', methods=['POST'])
    @role_required('ADMINISTRADOR')
    def aprobar_ajuste(id):
        try:
            user = get_current_user()
            ajuste = execute_query(
                "SELECT * FROM historial_ajustes_inventario WHERE id = %s AND estado = 'PENDIENTE'",
                (id,), fetch_one=True
            )
            if not ajuste:
                flash('Ajuste no encontrado o ya procesado', 'warning')
                return redirect(url_for('ajustes_pendientes'))

            execute_query("""
                UPDATE historial_ajustes_inventario
                SET estado = 'APROBADO', aprobado_por = %s, fecha_aprobacion = NOW()
                WHERE id = %s
            """, (user['id'], id), commit=True)

            execute_query(
                "UPDATE repuestos SET cantidad_actual = %s, updated_by = %s WHERE codigo = %s",
                (ajuste['cantidad_nueva'], user['id'], ajuste['repuesto_id']), commit=True
            )
            verificar_alertas(ajuste['repuesto_id'])

            registrar_audit_log(
                usuario_id=user['id'], tabla='historial_ajustes_inventario', registro_id=str(id),
                accion='APROBAR', tipo_cambio='INVENTARIO',
                datos_nuevos={'cantidad_nueva': ajuste['cantidad_nueva'], 'aprobado_por': user['id']}
            )

            flash('Ajuste aprobado y cantidad actualizada', 'success')
        except Exception as e:
            logger.error(f"Error aprobando ajuste: {e}")
            flash('Error al aprobar el ajuste', 'danger')
        return redirect(url_for('ajustes_pendientes'))

    @app.route('/repuestos/ajuste/<int:id>/rechazar', methods=['POST'])
    @role_required('ADMINISTRADOR')
    def rechazar_ajuste(id):
        try:
            user = get_current_user()
            motivo = request.form.get('motivo_rechazo', '')

            execute_query("""
                UPDATE historial_ajustes_inventario
                SET estado = 'RECHAZADO', aprobado_por = %s, fecha_aprobacion = NOW(), motivo_rechazo = %s
                WHERE id = %s AND estado = 'PENDIENTE'
            """, (user['id'], motivo, id), commit=True)

            registrar_audit_log(
                usuario_id=user['id'], tabla='historial_ajustes_inventario', registro_id=str(id),
                accion='RECHAZAR', tipo_cambio='INVENTARIO',
                datos_nuevos={'motivo_rechazo': motivo}
            )
            flash('Ajuste rechazado', 'info')
        except Exception as e:
            logger.error(f"Error rechazando ajuste: {e}")
            flash('Error al rechazar el ajuste', 'danger')
        return redirect(url_for('ajustes_pendientes'))

    # Eliminar imagen de repuesto
    @app.route('/repuestos/imagen/<int:id>/eliminar', methods=['POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def eliminar_imagen_repuesto(id):
        try:
            imagen = execute_query("SELECT * FROM imagenes_repuestos WHERE id = %s", (id,), fetch_one=True)
            if imagen:
                filepath = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'repuestos', imagen['nombre_archivo'])
                if os.path.exists(filepath):
                    os.remove(filepath)
                execute_query("DELETE FROM imagenes_repuestos WHERE id = %s", (id,), commit=True)
                flash('Imagen eliminada', 'success')
        except Exception as e:
            logger.error(f"Error eliminando imagen: {e}")
            flash('Error al eliminar la imagen', 'danger')
        return redirect(request.referrer or url_for('lista_repuestos'))

    # ==================== MOVIMIENTOS DE INVENTARIO ====================

    @app.route('/movimientos')
    @login_required
    def lista_movimientos():
        page = request.args.get('page', 1, type=int)
        tipo = request.args.get('tipo', '')
        estado = request.args.get('estado', '')

        per_page = app.config['ITEMS_PER_PAGE']
        offset = (page - 1) * per_page

        where_clauses = []
        params = []

        if tipo:
            where_clauses.append("tm.tipo = %s")
            params.append(tipo)

        if estado:
            where_clauses.append("mi.estado = %s")
            params.append(estado)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        total = execute_query(
            f"""SELECT COUNT(*) as count FROM movimientos_inventario mi
                JOIN tipos_movimiento tm ON mi.tipo_movimiento_id = tm.id
                WHERE {where_sql}""",
            tuple(params), fetch_one=True
        )['count']

        params.extend([per_page, offset])
        movimientos = execute_query(f"""
            SELECT mi.*, r.codigo as repuesto_codigo, r.nombre as repuesto_nombre,
                   tm.nombre as tipo_movimiento, tm.tipo,
                   u.nombre_completo as usuario,
                   ts.nombre_completo as tecnico_solicitante,
                   ua.nombre_completo as aprobado_por_nombre
            FROM movimientos_inventario mi
            JOIN repuestos r ON mi.repuesto_id = r.codigo
            JOIN tipos_movimiento tm ON mi.tipo_movimiento_id = tm.id
            JOIN usuarios u ON mi.usuario_id = u.numero_documento
            LEFT JOIN usuarios ts ON mi.tecnico_solicitante_id = ts.numero_documento
            LEFT JOIN usuarios ua ON mi.aprobado_por = ua.numero_documento
            WHERE {where_sql}
            ORDER BY mi.created_at DESC
            LIMIT %s OFFSET %s
        """, tuple(params), fetch_all=True)

        total_pages = (total + per_page - 1) // per_page

        return render_template('movimientos/lista.html',
                             movimientos=movimientos,
                             page=page,
                             total_pages=total_pages,
                             tipo=tipo,
                             estado=estado)

    @app.route('/movimientos/entrada', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def entrada_inventario():
        if request.method == 'POST':
            try:
                repuesto_id = request.form['repuesto_id']  # ahora es codigo
                cantidad = int(request.form['cantidad'])
                tipo_movimiento_id = request.form['tipo_movimiento_id']
                precio_unitario = float(request.form.get('precio_unitario', 0))
                user = get_current_user()

                mov_id = execute_query("""
                    INSERT INTO movimientos_inventario
                    (repuesto_id, tipo_movimiento_id, cantidad, precio_unitario,
                     usuario_id, estado, observaciones)
                    VALUES (%s, %s, %s, %s, %s, 'CONFIRMADO', %s)
                """, (
                    repuesto_id, tipo_movimiento_id, cantidad, precio_unitario,
                    user['id'], request.form.get('observaciones', '')
                ), commit=True)

                execute_query("""
                    UPDATE repuestos SET cantidad_actual = cantidad_actual + %s, updated_by = %s
                    WHERE codigo = %s
                """, (cantidad, user['id'], repuesto_id), commit=True)

                verificar_alertas(repuesto_id)

                registrar_audit_log(
                    usuario_id=user['id'], tabla='movimientos_inventario', registro_id=str(mov_id),
                    accion='CREAR', tipo_cambio='INVENTARIO',
                    datos_nuevos={'repuesto_id': repuesto_id, 'cantidad': cantidad, 'tipo': 'ENTRADA'}
                )

                flash('Entrada registrada exitosamente', 'success')
                return redirect(url_for('lista_movimientos'))

            except Exception as e:
                logger.error(f"Error en entrada de inventario: {e}")
                flash('Error al registrar la entrada', 'danger')

        categorias = execute_query(
            "SELECT * FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre",
            fetch_all=True
        )
        repuestos = execute_query(
            "SELECT codigo, codigo as id, nombre, categoria_id FROM repuestos WHERE activo = TRUE ORDER BY codigo ASC",
            fetch_all=True
        )
        tipos_movimiento = execute_query(
            "SELECT * FROM tipos_movimiento WHERE tipo = 'ENTRADA' ORDER BY nombre",
            fetch_all=True
        )
        return render_template('movimientos/entrada.html',
                             repuestos=repuestos, categorias=categorias,
                             tipos_movimiento=tipos_movimiento)

    @app.route('/movimientos/salida', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def salida_inventario():
        if request.method == 'POST':
            try:
                repuesto_id = request.form['repuesto_id']  # ahora es codigo
                cantidad = int(request.form['cantidad'])
                tipo_movimiento_id = request.form['tipo_movimiento_id']
                tecnico_solicitante_id = request.form.get('tecnico_solicitante_id') or None
                vehiculo_cliente_id = request.form.get('vehiculo_cliente_id') or None
                user = get_current_user()

                # Verificar stock disponible (actual - reservado)
                repuesto = execute_query(
                    "SELECT cantidad_actual, cantidad_reservada, nombre FROM repuestos WHERE codigo = %s",
                    (repuesto_id,), fetch_one=True
                )
                disponible = repuesto['cantidad_actual'] - repuesto['cantidad_reservada']

                if disponible < cantidad:
                    flash(f'Stock disponible insuficiente. Disponible: {disponible}', 'danger')
                    return redirect(url_for('salida_inventario'))

                # CAMBIO: No deducir de cantidad_actual, solo reservar
                mov_id = execute_query("""
                    INSERT INTO movimientos_inventario
                    (repuesto_id, tipo_movimiento_id, cantidad, usuario_id,
                     tecnico_solicitante_id, vehiculo_cliente_id, estado, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE', %s)
                """, (
                    repuesto_id, tipo_movimiento_id, cantidad, user['id'],
                    tecnico_solicitante_id, vehiculo_cliente_id,
                    request.form.get('observaciones', '')
                ), commit=True)

                # Solo reservar, no deducir
                execute_query("""
                    UPDATE repuestos
                    SET cantidad_reservada = cantidad_reservada + %s, updated_by = %s
                    WHERE codigo = %s
                """, (cantidad, user['id'], repuesto_id), commit=True)

                verificar_alertas(repuesto_id)

                registrar_audit_log(
                    usuario_id=user['id'], tabla='movimientos_inventario', registro_id=str(mov_id),
                    accion='CREAR', tipo_cambio='INVENTARIO',
                    datos_nuevos={'repuesto_id': repuesto_id, 'cantidad': cantidad, 'tipo': 'SALIDA'}
                )

                flash('Salida registrada. Stock reservado. Pendiente de facturación para descontar.', 'success')
                return redirect(url_for('lista_movimientos'))

            except Exception as e:
                logger.error(f"Error en salida de inventario: {e}")
                flash('Error al registrar la salida', 'danger')

        categorias = execute_query(
            "SELECT * FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre",
            fetch_all=True
        )
        repuestos = execute_query("""
            SELECT codigo, codigo as id, nombre, cantidad_actual, cantidad_reservada,
                   (cantidad_actual - cantidad_reservada) as disponible, categoria_id
            FROM repuestos WHERE activo = TRUE ORDER BY codigo ASC
        """, fetch_all=True)
        tipos_movimiento = execute_query(
            "SELECT * FROM tipos_movimiento WHERE tipo = 'SALIDA' ORDER BY nombre",
            fetch_all=True
        )
        tecnicos = execute_query("""
            SELECT u.numero_documento as id, u.nombre_completo FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE r.nombre = 'TECNICO' AND u.activo = TRUE
            ORDER BY u.nombre_completo
        """, fetch_all=True)
        clientes = execute_query(
            "SELECT numero_documento as id, numero_documento, nombre_completo FROM clientes WHERE activo = TRUE ORDER BY numero_documento ASC",
            fetch_all=True
        )
        return render_template('movimientos/salida.html',
                             repuestos=repuestos, categorias=categorias,
                             tipos_movimiento=tipos_movimiento,
                             tecnicos=tecnicos, clientes=clientes)

    # Transiciones de estado de movimientos
    @app.route('/movimientos/<int:id>/aprobar', methods=['POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def aprobar_movimiento(id):
        try:
            user = get_current_user()
            mov = execute_query("SELECT * FROM movimientos_inventario WHERE id = %s", (id,), fetch_one=True)
            if not mov or mov['estado'] != 'PENDIENTE':
                flash('Movimiento no encontrado o no está pendiente', 'warning')
                return redirect(url_for('lista_movimientos'))

            execute_query("""
                UPDATE movimientos_inventario
                SET estado = 'APROBADO', aprobado_por = %s, fecha_aprobacion = NOW()
                WHERE id = %s
            """, (user['id'], id), commit=True)

            registrar_audit_log(
                usuario_id=user['id'], tabla='movimientos_inventario', registro_id=str(id),
                accion='APROBAR', tipo_cambio='INVENTARIO'
            )
            flash('Movimiento aprobado', 'success')
        except Exception as e:
            logger.error(f"Error aprobando movimiento: {e}")
            flash('Error al aprobar el movimiento', 'danger')
        return redirect(url_for('lista_movimientos'))

    @app.route('/movimientos/<int:id>/rechazar', methods=['POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def rechazar_movimiento(id):
        try:
            user = get_current_user()
            mov = execute_query("SELECT * FROM movimientos_inventario WHERE id = %s", (id,), fetch_one=True)
            if not mov or mov['estado'] != 'PENDIENTE':
                flash('Movimiento no encontrado o no está pendiente', 'warning')
                return redirect(url_for('lista_movimientos'))

            motivo = request.form.get('motivo_rechazo', '')

            # Liberar reserva
            execute_query("""
                UPDATE repuestos SET cantidad_reservada = GREATEST(cantidad_reservada - %s, 0)
                WHERE codigo = %s
            """, (mov['cantidad'], mov['repuesto_id']), commit=True)

            execute_query("""
                UPDATE movimientos_inventario
                SET estado = 'RECHAZADO', aprobado_por = %s, fecha_aprobacion = NOW(), motivo_rechazo = %s
                WHERE id = %s
            """, (user['id'], motivo, id), commit=True)

            verificar_alertas(mov['repuesto_id'])

            registrar_audit_log(
                usuario_id=user['id'], tabla='movimientos_inventario', registro_id=str(id),
                accion='RECHAZAR', tipo_cambio='INVENTARIO',
                datos_nuevos={'motivo_rechazo': motivo}
            )
            flash('Movimiento rechazado y reserva liberada', 'info')
        except Exception as e:
            logger.error(f"Error rechazando movimiento: {e}")
            flash('Error al rechazar el movimiento', 'danger')
        return redirect(url_for('lista_movimientos'))

    # ==================== ALERTAS (ruta legacy redirige al blueprint) ====================

    @app.route('/alertas')
    @login_required
    def lista_alertas():
        return redirect(url_for('alertas.lista_alertas'))

    @app.route('/api/alertas/marcar-leida/<int:id>', methods=['POST'])
    @login_required
    def marcar_alerta_leida(id):
        """Marcar notificación personal como leída"""
        try:
            user = get_current_user()
            execute_query("""
                UPDATE notificaciones_usuarios
                SET leida = TRUE, leida_at = NOW()
                WHERE alerta_id = %s AND usuario_id = %s
            """, (id, user['id']), commit=True)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== GESTIÓN DE CLIENTES ====================

    @app.route('/clientes')
    @login_required
    def lista_clientes():
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')

        per_page = app.config['ITEMS_PER_PAGE']
        offset = (page - 1) * per_page

        where_clauses = ["c.activo = TRUE"]
        params = []

        if search:
            where_clauses.append("""
                (c.numero_documento LIKE %s OR c.nombre_completo LIKE %s OR
                 EXISTS (SELECT 1 FROM vehiculos_clientes vc
                         WHERE vc.cliente_id = c.numero_documento AND vc.placa LIKE %s AND vc.activo = TRUE))
            """)
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        where_sql = " AND ".join(where_clauses)

        total = execute_query(
            f"SELECT COUNT(DISTINCT c.numero_documento) as count FROM clientes c WHERE {where_sql}",
            tuple(params), fetch_one=True
        )['count']

        params.extend([per_page, offset])
        clientes = execute_query(f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM vehiculos_clientes vc
                    WHERE vc.cliente_id = c.numero_documento AND vc.activo = TRUE) as total_vehiculos,
                   (SELECT GROUP_CONCAT(vc.placa SEPARATOR ', ')
                    FROM vehiculos_clientes vc
                    WHERE vc.cliente_id = c.numero_documento AND vc.activo = TRUE
                    LIMIT 3) as placas_vehiculos
            FROM clientes c
            WHERE {where_sql}
            ORDER BY c.numero_documento ASC
            LIMIT %s OFFSET %s
        """, tuple(params), fetch_all=True)

        total_pages = (total + per_page - 1) // per_page

        return render_template('clientes/lista.html',
                             clientes=clientes, page=page,
                             total_pages=total_pages, search=search)

    @app.route('/clientes/nuevo', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR')
    def nuevo_cliente():
        if request.method == 'POST':
            try:
                user = get_current_user()
                numero_documento = request.form['numero_documento']
                execute_query("""
                    INSERT INTO clientes
                    (tipo_documento, numero_documento, nombre_completo, telefono, email, direccion, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    request.form['tipo_documento'],
                    numero_documento,
                    request.form['nombre_completo'],
                    request.form.get('telefono', ''),
                    request.form.get('email', ''),
                    request.form.get('direccion', ''),
                    user['id']
                ), commit=True)

                registrar_audit_log(
                    usuario_id=user['id'], tabla='clientes', registro_id=numero_documento,
                    accion='CREAR', tipo_cambio='CLIENTE',
                    datos_nuevos={'nombre': request.form['nombre_completo']}
                )

                flash('Cliente creado exitosamente', 'success')
                return redirect(url_for('lista_clientes'))
            except Exception as e:
                logger.error(f"Error creando cliente: {e}")
                flash('Error al crear el cliente. Verifica que el número de documento no esté duplicado.', 'danger')
        return render_template('clientes/form.html', cliente=None)

    @app.route('/clientes/<string:numero_documento>/editar', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR')
    def editar_cliente(numero_documento):
        cliente = execute_query("SELECT * FROM clientes WHERE numero_documento = %s", (numero_documento,), fetch_one=True)
        if not cliente:
            flash('Cliente no encontrado', 'danger')
            return redirect(url_for('lista_clientes'))

        if request.method == 'POST':
            try:
                user = get_current_user()
                execute_query("""
                    UPDATE clientes
                    SET tipo_documento = %s, numero_documento = %s, nombre_completo = %s,
                        telefono = %s, email = %s, direccion = %s, updated_by = %s
                    WHERE numero_documento = %s
                """, (
                    request.form['tipo_documento'],
                    request.form['numero_documento'],
                    request.form['nombre_completo'],
                    request.form.get('telefono', ''),
                    request.form.get('email', ''),
                    request.form.get('direccion', ''),
                    user['id'], numero_documento
                ), commit=True)

                registrar_audit_log(
                    usuario_id=user['id'], tabla='clientes', registro_id=numero_documento,
                    accion='ACTUALIZAR', tipo_cambio='CLIENTE',
                    datos_nuevos={'nombre': request.form['nombre_completo']}
                )
                flash('Cliente actualizado exitosamente', 'success')
                return redirect(url_for('lista_clientes'))
            except Exception as e:
                logger.error(f"Error actualizando cliente: {e}")
                flash('Error al actualizar el cliente', 'danger')
        return render_template('clientes/form.html', cliente=cliente)

    @app.route('/clientes/<string:numero_documento>/vehiculos')
    @login_required
    def vehiculos_cliente(numero_documento):
        cliente = execute_query("SELECT * FROM clientes WHERE numero_documento = %s", (numero_documento,), fetch_one=True)
        if not cliente:
            flash('Cliente no encontrado', 'danger')
            return redirect(url_for('lista_clientes'))

        vehiculos = execute_query("""
            SELECT vc.*, mv.nombre as modelo_nombre, ma.nombre as marca_nombre
            FROM vehiculos_clientes vc
            JOIN modelos_vehiculos mv ON vc.modelo_vehiculo_id = mv.id
            JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
            WHERE vc.cliente_id = %s
            ORDER BY vc.activo DESC, vc.placa ASC
        """, (numero_documento,), fetch_all=True)

        vehiculos_activos   = [v for v in vehiculos if v['activo']]
        vehiculos_inactivos = [v for v in vehiculos if not v['activo']]

        return render_template('clientes/vehiculos.html',
                               cliente=cliente,
                               vehiculos=vehiculos,
                               vehiculos_activos=vehiculos_activos,
                               vehiculos_inactivos=vehiculos_inactivos)

    # ==================== GESTIÓN DE VEHÍCULOS ====================

    @app.route('/vehiculos/nuevo/<string:cliente_id>', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR')
    def nuevo_vehiculo(cliente_id):
        cliente = execute_query("SELECT * FROM clientes WHERE numero_documento = %s", (cliente_id,), fetch_one=True)
        if not cliente:
            flash('Cliente no encontrado', 'danger')
            return redirect(url_for('lista_clientes'))

        if request.method == 'POST':
            try:
                user = get_current_user()
                placa = request.form['placa'].upper()
                execute_query("""
                    INSERT INTO vehiculos_clientes
                    (placa, cliente_id, modelo_vehiculo_id, anio, color,
                     numero_motor, numero_chasis, kilometraje_actual, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    placa,
                    cliente_id,
                    request.form['modelo_vehiculo_id'],
                    request.form.get('anio') or None,
                    request.form.get('color', ''),
                    request.form.get('numero_motor', ''),
                    request.form.get('numero_chasis', ''),
                    request.form.get('kilometraje_actual') or None,
                    request.form.get('observaciones', '')
                ), commit=True)

                registrar_audit_log(
                    usuario_id=user['id'], tabla='vehiculos_clientes', registro_id=placa,
                    accion='CREAR', tipo_cambio='VEHICULO',
                    datos_nuevos={'placa': placa, 'cliente_id': cliente_id}
                )

                flash('Vehículo registrado exitosamente', 'success')
                return redirect(url_for('vehiculos_cliente', numero_documento=cliente_id))
            except Exception as e:
                logger.error(f"Error registrando vehículo: {e}")
                flash('Error al registrar el vehículo. Verifica que la placa no esté duplicada.', 'danger')

        marcas = execute_query("SELECT * FROM marcas_vehiculos ORDER BY nombre", fetch_all=True)
        modelos = execute_query("""
            SELECT mv.*, ma.nombre as marca_nombre
            FROM modelos_vehiculos mv
            JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
            ORDER BY ma.nombre, mv.nombre
        """, fetch_all=True)
        return render_template('vehiculos/form.html', cliente=cliente, vehiculo=None, marcas=marcas, modelos=modelos)

    @app.route('/vehiculos/<string:placa>/editar', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR')
    def editar_vehiculo(placa):
        vehiculo = execute_query("""
            SELECT vc.*, mv.marca_id
            FROM vehiculos_clientes vc
            JOIN modelos_vehiculos mv ON vc.modelo_vehiculo_id = mv.id
            WHERE vc.placa = %s
        """, (placa,), fetch_one=True)
        if not vehiculo:
            flash('Vehículo no encontrado', 'danger')
            return redirect(url_for('lista_clientes'))

        cliente = execute_query("SELECT * FROM clientes WHERE numero_documento = %s", (vehiculo['cliente_id'],), fetch_one=True)

        if request.method == 'POST':
            try:
                user = get_current_user()
                nuevo_cliente_id = request.form.get('cliente_id') or vehiculo['cliente_id']
                nuevo_activo = True if request.form.get('activo') else False

                datos_ant = {
                    'cliente_id': vehiculo['cliente_id'],
                    'activo': vehiculo['activo']
                }

                execute_query("""
                    UPDATE vehiculos_clientes
                    SET placa = %s, modelo_vehiculo_id = %s, anio = %s, color = %s,
                        numero_motor = %s, numero_chasis = %s, kilometraje_actual = %s,
                        observaciones = %s, cliente_id = %s, activo = %s
                    WHERE placa = %s
                """, (
                    request.form['placa'].upper(),
                    request.form['modelo_vehiculo_id'],
                    request.form.get('anio') or None,
                    request.form.get('color', ''),
                    request.form.get('numero_motor', ''),
                    request.form.get('numero_chasis', ''),
                    request.form.get('kilometraje_actual') or None,
                    request.form.get('observaciones', ''),
                    nuevo_cliente_id,
                    nuevo_activo,
                    placa
                ), commit=True)

                registrar_audit_log(
                    usuario_id=user['id'], tabla='vehiculos_clientes', registro_id=placa,
                    accion='ACTUALIZAR', tipo_cambio='VEHICULO',
                    datos_anteriores=datos_ant,
                    datos_nuevos={
                        'placa': request.form['placa'].upper(),
                        'cliente_id': nuevo_cliente_id,
                        'activo': nuevo_activo
                    }
                )

                flash('Vehículo actualizado exitosamente', 'success')
                return redirect(url_for('vehiculos_cliente', numero_documento=nuevo_cliente_id))
            except Exception as e:
                logger.error(f"Error actualizando vehículo: {e}")
                flash('Error al actualizar el vehículo', 'danger')

        marcas = execute_query("SELECT * FROM marcas_vehiculos ORDER BY nombre", fetch_all=True)
        modelos = execute_query("""
            SELECT mv.*, ma.nombre as marca_nombre
            FROM modelos_vehiculos mv
            JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
            ORDER BY ma.nombre, mv.nombre
        """, fetch_all=True)
        clientes = execute_query(
            "SELECT numero_documento, nombre_completo, tipo_documento FROM clientes WHERE activo = TRUE ORDER BY nombre_completo ASC",
            fetch_all=True
        )
        return render_template('vehiculos/form.html',
                               cliente=cliente, vehiculo=vehiculo,
                               marcas=marcas, modelos=modelos, clientes=clientes)

    @app.route('/vehiculos/<string:placa>/toggle-estado', methods=['POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA', 'VENDEDOR')
    def toggle_estado_vehiculo(placa):
        """Activa o desactiva un vehículo manteniendo todo su historial"""
        vehiculo = execute_query(
            "SELECT * FROM vehiculos_clientes WHERE placa = %s", (placa,), fetch_one=True
        )
        if not vehiculo:
            flash('Vehículo no encontrado', 'danger')
            return redirect(url_for('lista_clientes'))

        nuevo_estado = not vehiculo['activo']
        user = get_current_user()

        execute_query(
            "UPDATE vehiculos_clientes SET activo = %s WHERE placa = %s",
            (nuevo_estado, placa), commit=True
        )

        registrar_audit_log(
            usuario_id=user['id'], tabla='vehiculos_clientes', registro_id=placa,
            accion='ACTUALIZAR', tipo_cambio='VEHICULO',
            datos_anteriores={'activo': vehiculo['activo']},
            datos_nuevos={'activo': nuevo_estado}
        )

        if nuevo_estado:
            flash(f'Vehículo {placa} activado exitosamente.', 'success')
        else:
            flash(f'Vehículo {placa} desactivado. Puede reasignarlo a otro cliente editándolo.', 'info')

        return redirect(url_for('vehiculos_cliente', numero_documento=vehiculo['cliente_id']))

    # ==================== GESTIÓN DE USUARIOS ====================

    @app.route('/usuarios')
    @role_required('ADMINISTRADOR')
    def lista_usuarios():
        usuarios = execute_query("""
            SELECT u.*, r.nombre as rol_nombre
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            ORDER BY r.id ASC, u.nombre_completo ASC
        """, fetch_all=True)
        return render_template('usuarios/lista.html', usuarios=usuarios)

    @app.route('/usuarios/nuevo', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR')
    def nuevo_usuario():
        if request.method == 'POST':
            try:
                password_hash = hash_password(request.form['password'])
                current_user_data = get_current_user()

                # Solo SUPER_USUARIO puede crear otros SUPER_USUARIO
                rol_id = int(request.form['rol_id'])
                rol = execute_query("SELECT nombre FROM roles WHERE id = %s", (rol_id,), fetch_one=True)
                if rol and rol['nombre'] == 'SUPER_USUARIO' and not is_super_user():
                    flash('Solo un Super Usuario puede crear otro Super Usuario', 'danger')
                    roles = execute_query("SELECT * FROM roles ORDER BY id ASC", fetch_all=True)
                    return render_template('usuarios/form.html', roles=roles, usuario=None)

                numero_documento = request.form['numero_documento']
                execute_query("""
                    INSERT INTO usuarios
                    (numero_documento, username, password_hash, nombre_completo, email, rol_id, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    numero_documento,
                    request.form['username'],
                    password_hash,
                    request.form['nombre_completo'],
                    request.form.get('email', ''),
                    rol_id,
                    current_user_data['id']
                ), commit=True)

                registrar_audit_log(
                    usuario_id=current_user_data['id'], tabla='usuarios', registro_id=numero_documento,
                    accion='CREAR', tipo_cambio='USUARIO',
                    datos_nuevos={'username': request.form['username'], 'nombre': request.form['nombre_completo']}
                )

                flash('Usuario creado exitosamente', 'success')
                return redirect(url_for('lista_usuarios'))
            except Exception as e:
                logger.error(f"Error creando usuario: {e}")
                flash('Error al crear el usuario', 'danger')

        roles = execute_query("SELECT * FROM roles ORDER BY id ASC", fetch_all=True)
        return render_template('usuarios/form.html', roles=roles, usuario=None)

    @app.route('/usuarios/<string:numero_documento>/editar', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR')
    def editar_usuario(numero_documento):
        usuario = execute_query(
            "SELECT u.*, r.nombre as rol_nombre FROM usuarios u JOIN roles r ON u.rol_id = r.id WHERE u.numero_documento = %s",
            (numero_documento,), fetch_one=True
        )
        if not usuario:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('lista_usuarios'))

        # Protección de super usuario
        if usuario.get('es_protegido') and not is_super_user():
            flash('Solo un Super Usuario puede modificar usuarios protegidos', 'danger')
            return redirect(url_for('lista_usuarios'))

        if request.method == 'POST':
            try:
                current_user_data = get_current_user()

                # Solo SUPER_USUARIO puede asignar rol SUPER_USUARIO
                rol_id = int(request.form['rol_id'])
                rol = execute_query("SELECT nombre FROM roles WHERE id = %s", (rol_id,), fetch_one=True)
                if rol and rol['nombre'] == 'SUPER_USUARIO' and not is_super_user():
                    flash('Solo un Super Usuario puede asignar el rol de Super Usuario', 'danger')
                    roles = execute_query("SELECT * FROM roles ORDER BY id ASC", fetch_all=True)
                    return render_template('usuarios/form.html', roles=roles, usuario=usuario)

                if request.form.get('password'):
                    password_hash = hash_password(request.form['password'])
                    execute_query("""
                        UPDATE usuarios
                        SET nombre_completo = %s, email = %s, rol_id = %s,
                            password_hash = %s, updated_by = %s
                        WHERE numero_documento = %s
                    """, (
                        request.form['nombre_completo'],
                        request.form.get('email', ''),
                        rol_id, password_hash,
                        current_user_data['id'], numero_documento
                    ), commit=True)
                else:
                    execute_query("""
                        UPDATE usuarios
                        SET nombre_completo = %s, email = %s, rol_id = %s, updated_by = %s
                        WHERE numero_documento = %s
                    """, (
                        request.form['nombre_completo'],
                        request.form.get('email', ''),
                        rol_id, current_user_data['id'], numero_documento
                    ), commit=True)

                registrar_audit_log(
                    usuario_id=current_user_data['id'], tabla='usuarios', registro_id=numero_documento,
                    accion='ACTUALIZAR', tipo_cambio='USUARIO',
                    datos_nuevos={'nombre': request.form['nombre_completo'], 'rol_id': rol_id}
                )

                flash('Usuario actualizado exitosamente', 'success')
                return redirect(url_for('lista_usuarios'))
            except Exception as e:
                logger.error(f"Error actualizando usuario: {e}")
                flash('Error al actualizar el usuario', 'danger')

        roles = execute_query("SELECT * FROM roles ORDER BY id ASC", fetch_all=True)
        return render_template('usuarios/form.html', roles=roles, usuario=usuario)

    @app.route('/usuarios/<string:numero_documento>/toggle-estado', methods=['POST'])
    @role_required('ADMINISTRADOR')
    def toggle_estado_usuario(numero_documento):
        try:
            usuario = execute_query(
                "SELECT activo, es_protegido, username FROM usuarios WHERE numero_documento = %s",
                (numero_documento,), fetch_one=True
            )
            if not usuario:
                flash('Usuario no encontrado', 'danger')
                return redirect(url_for('lista_usuarios'))

            # No permitir desactivar usuarios protegidos
            if usuario.get('es_protegido'):
                flash('No se puede desactivar un usuario protegido', 'danger')
                return redirect(url_for('lista_usuarios'))

            nuevo_estado = not usuario['activo']
            current_user_data = get_current_user()

            execute_query(
                "UPDATE usuarios SET activo = %s, updated_by = %s WHERE numero_documento = %s",
                (nuevo_estado, current_user_data['id'], numero_documento), commit=True
            )

            registrar_audit_log(
                usuario_id=current_user_data['id'], tabla='usuarios', registro_id=numero_documento,
                accion='ACTUALIZAR', tipo_cambio='USUARIO',
                datos_nuevos={'activo': nuevo_estado}
            )

            estado_texto = 'activado' if nuevo_estado else 'desactivado'
            flash(f'Usuario {estado_texto} exitosamente', 'success')
        except Exception as e:
            logger.error(f"Error cambiando estado de usuario: {e}")
            flash('Error al cambiar el estado del usuario', 'danger')
        return redirect(url_for('lista_usuarios'))

    # ==================== FUNCIONES AUXILIARES ====================

    def verificar_alertas(repuesto_codigo):
        """Verifica y crea alertas de inventario (PKs naturales: repuesto identificado por codigo)"""
        repuesto = execute_query("""
            SELECT codigo, nombre, cantidad_actual, cantidad_minima, cantidad_reservada
            FROM repuestos WHERE codigo = %s
        """, (repuesto_codigo,), fetch_one=True)

        if not repuesto:
            return

        stock_disponible = repuesto['cantidad_actual'] - repuesto.get('cantidad_reservada', 0)

        if repuesto['cantidad_actual'] > repuesto['cantidad_minima']:
            execute_query("""
                UPDATE alertas_inventario
                SET estado = 'RESUELTA', fecha_resolucion = NOW()
                WHERE repuesto_id = %s AND estado IN ('NUEVA', 'EN_PROCESO')
                AND tipo_alerta IN ('STOCK_BAJO', 'AGOTADO')
            """, (repuesto_codigo,), commit=True)
            return

        if repuesto['cantidad_actual'] == 0:
            tipo_alerta = 'AGOTADO'
            nivel = 'CRITICA'
            mensaje = f"El repuesto {repuesto['nombre']} ({repuesto['codigo']}) está AGOTADO"
        elif repuesto['cantidad_actual'] <= repuesto['cantidad_minima']:
            tipo_alerta = 'STOCK_BAJO'
            nivel = 'ALTA'
            mensaje = f"El repuesto {repuesto['nombre']} ({repuesto['codigo']}) tiene stock bajo: {repuesto['cantidad_actual']} unidades (disponible: {stock_disponible})"
        else:
            return

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

            usuarios_notificar = execute_query("""
                SELECT u.numero_documento as id FROM usuarios u
                JOIN roles r ON u.rol_id = r.id
                WHERE r.nombre IN ('SUPER_USUARIO', 'ADMINISTRADOR', 'ALMACENISTA') AND u.activo = TRUE
            """, fetch_all=True)

            for usuario in usuarios_notificar:
                execute_query("""
                    INSERT IGNORE INTO notificaciones_usuarios (usuario_id, alerta_id)
                    VALUES (%s, %s)
                """, (usuario['id'], alerta_id), commit=True)

    def _procesar_imagenes_repuesto(repuesto_codigo, user_id):
        """Procesa y guarda imágenes subidas para un repuesto"""
        if 'imagenes' not in request.files:
            return
        archivos = request.files.getlist('imagenes')
        allowed = app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
        upload_dir = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'repuestos')

        for archivo in archivos:
            if archivo and archivo.filename:
                ext = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
                if ext not in allowed:
                    continue
                filename = secure_filename(f"rep_{repuesto_codigo}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.filename}")
                filepath = os.path.join(upload_dir, filename)
                archivo.save(filepath)

                # Verificar si es la primera imagen (hacerla principal)
                count = execute_query(
                    "SELECT COUNT(*) as c FROM imagenes_repuestos WHERE repuesto_id = %s",
                    (repuesto_codigo,), fetch_one=True
                )['c']

                execute_query("""
                    INSERT INTO imagenes_repuestos (repuesto_id, nombre_archivo, ruta_archivo, es_principal, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                """, (repuesto_codigo, filename, f"uploads/repuestos/{filename}", count == 0, user_id), commit=True)

    # ==================== API ENDPOINTS ====================

    @app.route('/api/repuestos/buscar')
    @login_required
    def api_buscar_repuestos():
        query = request.args.get('q', '')
        categoria_id = request.args.get('categoria_id', type=int)

        params = []
        where_clauses = ["activo = TRUE"]

        if query:
            where_clauses.append("(codigo LIKE %s OR nombre LIKE %s)")
            params.extend([f'%{query}%', f'%{query}%'])
        if categoria_id:
            where_clauses.append("categoria_id = %s")
            params.append(categoria_id)

        where_sql = " AND ".join(where_clauses)
        repuestos = execute_query(f"""
            SELECT codigo, codigo as id, nombre, cantidad_actual, cantidad_reservada,
                   (cantidad_actual - cantidad_reservada) as disponible, precio_venta,
                   categoria_id
            FROM repuestos
            WHERE {where_sql}
            ORDER BY codigo ASC
            LIMIT 50
        """, tuple(params), fetch_all=True)

        return jsonify([dict(r) for r in repuestos])

    @app.route('/api/repuestos/por-categoria/<int:categoria_id>')
    @login_required
    def api_repuestos_por_categoria(categoria_id):
        """Obtener repuestos filtrados por categoría"""
        repuestos = execute_query("""
            SELECT codigo, codigo as id, nombre, cantidad_actual, cantidad_reservada,
                   (cantidad_actual - cantidad_reservada) as disponible, precio_venta
            FROM repuestos
            WHERE categoria_id = %s AND activo = TRUE
            ORDER BY codigo ASC
        """, (categoria_id,), fetch_all=True)
        return jsonify([dict(r) for r in repuestos])

    @app.route('/api/repuestos/<string:codigo>/detalle')
    @login_required
    def api_repuesto_detalle(codigo):
        """API para obtener detalle completo de un repuesto"""
        repuesto = execute_query("""
            SELECT r.*, c.nombre as categoria_nombre
            FROM repuestos r
            LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
            WHERE r.codigo = %s
        """, (codigo,), fetch_one=True)

        if not repuesto:
            return jsonify({'error': 'No encontrado'}), 404

        imagenes = execute_query(
            "SELECT id, nombre_archivo, ruta_archivo, es_principal FROM imagenes_repuestos WHERE repuesto_id = %s ORDER BY es_principal DESC, orden",
            (codigo,), fetch_all=True
        )

        compatibilidad = execute_query("""
            SELECT rc.*, mv.nombre as modelo, ma.nombre as marca
            FROM repuestos_compatibilidad rc
            JOIN modelos_vehiculos mv ON rc.modelo_vehiculo_id = mv.id
            JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
            WHERE rc.repuesto_id = %s
        """, (codigo,), fetch_all=True)

        equivalentes = execute_query(
            "SELECT * FROM repuestos_equivalentes WHERE repuesto_id = %s",
            (codigo,), fetch_all=True
        )

        data = dict(repuesto)
        data['precio_venta'] = str(data.get('precio_venta', 0))
        data['imagenes'] = [dict(i) for i in imagenes]
        data['compatibilidad'] = [dict(c) for c in compatibilidad]
        data['equivalentes'] = [dict(e) for e in equivalentes]
        data['disponible'] = data.get('cantidad_actual', 0) - data.get('cantidad_reservada', 0)

        return jsonify(data)

    @app.route('/api/vehiculos-cliente/<string:cliente_id>')
    @login_required
    def api_vehiculos_cliente(cliente_id):
        vehiculos = execute_query("""
            SELECT vc.placa, vc.placa as id, mv.nombre as modelo, ma.nombre as marca, vc.anio
            FROM vehiculos_clientes vc
            JOIN modelos_vehiculos mv ON vc.modelo_vehiculo_id = mv.id
            JOIN marcas_vehiculos ma ON mv.marca_id = ma.id
            WHERE vc.cliente_id = %s AND vc.activo = TRUE
            ORDER BY vc.placa ASC
        """, (cliente_id,), fetch_all=True)
        return jsonify([dict(v) for v in vehiculos])

    @app.route('/api/marcas/<int:marca_id>/modelos')
    @login_required
    def api_modelos_por_marca(marca_id):
        """Retorna los modelos de una marca específica (para select en cascada)"""
        modelos = execute_query(
            "SELECT id, nombre FROM modelos_vehiculos WHERE marca_id = %s ORDER BY nombre",
            (marca_id,), fetch_all=True
        )
        return jsonify([dict(m) for m in (modelos or [])])

    @app.route('/api/marcas/nueva', methods=['POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def api_crear_marca():
        """Crea una nueva marca de vehículo. Devuelve la marca creada o la existente."""
        nombre = (request.json or {}).get('nombre', '').strip().upper()
        if not nombre:
            return jsonify({'error': 'Nombre requerido'}), 400
        try:
            execute_query(
                "INSERT INTO marcas_vehiculos (nombre) VALUES (%s)", (nombre,), commit=True
            )
            nueva = execute_query(
                "SELECT id, nombre FROM marcas_vehiculos WHERE nombre = %s", (nombre,), fetch_one=True
            )
            return jsonify({'id': nueva['id'], 'nombre': nueva['nombre']}), 201
        except Exception as e:
            if '1062' in str(e):
                existing = execute_query(
                    "SELECT id, nombre FROM marcas_vehiculos WHERE nombre = %s", (nombre,), fetch_one=True
                )
                return jsonify({'id': existing['id'], 'nombre': existing['nombre'], 'existing': True})
            logger.error(f"Error creando marca: {e}")
            return jsonify({'error': 'Error interno al crear la marca'}), 500

    @app.route('/api/modelos/nuevo', methods=['POST'])
    @role_required('ADMINISTRADOR', 'ALMACENISTA')
    def api_crear_modelo():
        """Crea un nuevo modelo para una marca. Devuelve el modelo creado o el existente."""
        data = request.json or {}
        marca_id = data.get('marca_id')
        nombre = data.get('nombre', '').strip()
        if not marca_id or not nombre:
            return jsonify({'error': 'marca_id y nombre son requeridos'}), 400
        try:
            execute_query(
                "INSERT INTO modelos_vehiculos (marca_id, nombre) VALUES (%s, %s)",
                (marca_id, nombre), commit=True
            )
            nuevo = execute_query(
                "SELECT id, nombre, marca_id FROM modelos_vehiculos WHERE marca_id = %s AND nombre = %s",
                (marca_id, nombre), fetch_one=True
            )
            return jsonify({'id': nuevo['id'], 'nombre': nuevo['nombre'], 'marca_id': nuevo['marca_id']}), 201
        except Exception as e:
            if '1062' in str(e):
                existing = execute_query(
                    "SELECT id, nombre, marca_id FROM modelos_vehiculos WHERE marca_id = %s AND nombre = %s",
                    (marca_id, nombre), fetch_one=True
                )
                return jsonify({'id': existing['id'], 'nombre': existing['nombre'], 'existing': True})
            logger.error(f"Error creando modelo: {e}")
            return jsonify({'error': 'Error interno al crear el modelo'}), 500

    # ==================== CÓDIGOS DE DESCUENTO ====================

    @app.route('/descuentos')
    @role_required('ADMINISTRADOR', 'VENDEDOR')
    def lista_descuentos():
        """Gestión de códigos de descuento"""
        descuentos = execute_query(
            "SELECT * FROM codigos_descuento ORDER BY activo DESC, codigo ASC",
            fetch_all=True
        )
        return render_template('descuentos/lista.html', descuentos=descuentos)

    @app.route('/descuentos/nuevo', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR')
    def nuevo_descuento():
        """Crear nuevo código de descuento"""
        if request.method == 'POST':
            try:
                codigo = request.form['codigo'].strip().upper()
                descripcion = request.form['descripcion'].strip()
                tipo = request.form['tipo']
                valor = request.form['valor']
                execute_query("""
                    INSERT INTO codigos_descuento (codigo, descripcion, tipo, valor)
                    VALUES (%s, %s, %s, %s)
                """, (codigo, descripcion, tipo, valor), commit=True)
                flash(f'Código de descuento "{codigo}" creado correctamente.', 'success')
                return redirect(url_for('lista_descuentos'))
            except Exception as e:
                logger.error(f"Error creando descuento: {e}")
                flash('Error al crear el código. Verifique que el código no esté duplicado.', 'danger')
        return render_template('descuentos/form.html', descuento=None)

    @app.route('/descuentos/<string:codigo>/editar', methods=['GET', 'POST'])
    @role_required('ADMINISTRADOR')
    def editar_descuento(codigo):
        """Editar código de descuento"""
        descuento = execute_query(
            "SELECT * FROM codigos_descuento WHERE codigo = %s", (codigo,), fetch_one=True
        )
        if not descuento:
            flash('Código no encontrado', 'danger')
            return redirect(url_for('lista_descuentos'))
        if request.method == 'POST':
            try:
                descripcion = request.form['descripcion'].strip()
                tipo = request.form['tipo']
                valor = request.form['valor']
                execute_query("""
                    UPDATE codigos_descuento SET descripcion = %s, tipo = %s, valor = %s
                    WHERE codigo = %s
                """, (descripcion, tipo, valor, codigo), commit=True)
                flash('Código de descuento actualizado.', 'success')
                return redirect(url_for('lista_descuentos'))
            except Exception as e:
                logger.error(f"Error editando descuento: {e}")
                flash('Error al actualizar el código.', 'danger')
        return render_template('descuentos/form.html', descuento=descuento)

    @app.route('/descuentos/<string:codigo>/toggle', methods=['POST'])
    @role_required('ADMINISTRADOR')
    def toggle_descuento(codigo):
        """Activar o desactivar un código de descuento"""
        desc = execute_query(
            "SELECT activo FROM codigos_descuento WHERE codigo = %s", (codigo,), fetch_one=True
        )
        if desc:
            nuevo = not desc['activo']
            execute_query(
                "UPDATE codigos_descuento SET activo = %s WHERE codigo = %s",
                (nuevo, codigo), commit=True
            )
            flash(f'Código "{codigo}" {"activado" if nuevo else "desactivado"}.', 'success')
        return redirect(url_for('lista_descuentos'))

    @app.route('/api/descuentos/<string:codigo>')
    @login_required
    def api_descuento(codigo):
        """Lookup de un código de descuento para uso en formularios de factura"""
        desc = execute_query(
            "SELECT codigo, descripcion, tipo, valor FROM codigos_descuento WHERE codigo = %s AND activo = TRUE",
            (codigo.upper(),), fetch_one=True
        )
        if not desc:
            return jsonify({'error': 'Código no encontrado o inactivo'}), 404
        return jsonify({
            'codigo': desc['codigo'],
            'descripcion': desc['descripcion'],
            'tipo': desc['tipo'],
            'valor': float(desc['valor'])
        })

    @app.route('/api/notificaciones')
    @login_required
    def api_notificaciones():
        user = get_current_user()
        notificaciones = execute_query("""
            SELECT n.id, n.leida, n.created_at,
                   a.id as alerta_id, a.mensaje, a.tipo_alerta, a.nivel_prioridad, a.estado as alerta_estado
            FROM notificaciones_usuarios n
            JOIN alertas_inventario a ON n.alerta_id = a.id
            WHERE n.usuario_id = %s
            AND a.estado IN ('NUEVA', 'EN_PROCESO')
            AND (n.leida = FALSE OR
                 (n.leida = TRUE AND (n.ultimo_recordatorio_enviado IS NULL OR n.ultimo_recordatorio_enviado < CURDATE())))
            ORDER BY n.created_at DESC
            LIMIT 20
        """, (user['id'],), fetch_all=True)
        return jsonify([dict(n) for n in notificaciones])

    @app.route('/api/notificaciones/count')
    @login_required
    def api_notificaciones_count():
        """Conteo de notificaciones activas para badge"""
        user = get_current_user()
        result = execute_query("""
            SELECT COUNT(*) as count
            FROM notificaciones_usuarios n
            JOIN alertas_inventario a ON n.alerta_id = a.id
            WHERE n.usuario_id = %s
            AND a.estado IN ('NUEVA', 'EN_PROCESO')
            AND (n.leida = FALSE OR
                 (n.leida = TRUE AND (n.ultimo_recordatorio_enviado IS NULL OR n.ultimo_recordatorio_enviado < CURDATE())))
        """, (user['id'],), fetch_one=True)
        return jsonify({'count': result['count']})

    return app

if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)
