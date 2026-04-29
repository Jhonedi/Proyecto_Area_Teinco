# -*- coding: utf-8 -*-
"""
Modulo de Categorias de Repuestos
- CRUD completo de categorias con soft delete
- Solo ADMIN y ALMACENISTA pueden gestionar categorias
- Eliminacion solo si no hay repuestos activos asociados
- API JSON para dropdowns en formularios
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime
from database import execute_query
from auth import (
    login_required, role_required, get_current_user, registrar_audit_log
)
from . import categorias_bp
import logging

logger = logging.getLogger(__name__)


# ==================== RUTAS DE CATEGORIAS ====================

@categorias_bp.route('/')
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def lista():
    """Lista todas las categorias con conteo de repuestos en cada una"""
    user = get_current_user()

    categorias = execute_query("""
        SELECT c.*,
               u_created.nombre_completo as creado_por_nombre,
               u_updated.nombre_completo as actualizado_por_nombre,
               (SELECT COUNT(*) FROM repuestos r
                WHERE r.categoria_id = c.id AND r.activo = TRUE) as total_repuestos
        FROM categorias_repuestos c
        LEFT JOIN usuarios u_created ON c.created_by = u_created.numero_documento
        LEFT JOIN usuarios u_updated ON c.updated_by = u_updated.numero_documento
        WHERE c.activo = TRUE
        ORDER BY c.nombre ASC
    """, fetch_all=True)

    return render_template('categorias/lista.html',
                         categorias=categorias)


@categorias_bp.route('/nueva')
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def nueva():
    """Formulario para crear nueva categoria"""
    return render_template('categorias/form.html', categoria=None)


@categorias_bp.route('/crear', methods=['POST'])
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def crear():
    """Crear nueva categoria de repuestos"""
    user = get_current_user()

    try:
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()

        if not nombre:
            flash('El nombre de la categoria es obligatorio', 'warning')
            return redirect(url_for('categorias.nueva'))

        # Verificar que no exista otra categoria con el mismo nombre
        existente = execute_query(
            "SELECT id FROM categorias_repuestos WHERE nombre = %s AND activo = TRUE",
            (nombre,), fetch_one=True
        )

        if existente:
            flash('Ya existe una categoria con ese nombre', 'warning')
            return redirect(url_for('categorias.nueva'))

        categoria_id = execute_query("""
            INSERT INTO categorias_repuestos
            (nombre, descripcion, activo, created_by)
            VALUES (%s, %s, TRUE, %s)
        """, (nombre, descripcion, user['id']), commit=True)

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='categorias_repuestos',
            registro_id=str(categoria_id),
            accion='CREAR',
            tipo_cambio='INVENTARIO',
            datos_nuevos={
                'nombre': nombre,
                'descripcion': descripcion
            }
        )

        flash('Categoria creada exitosamente', 'success')
        return redirect(url_for('categorias.lista'))

    except Exception as e:
        logger.error(f"Error creando categoria: {e}")
        flash('Error al crear la categoria. Verifique que el nombre no este duplicado.', 'danger')
        return redirect(url_for('categorias.nueva'))


@categorias_bp.route('/<int:id>/editar')
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def editar(id):
    """Formulario para editar categoria existente"""
    categoria = execute_query(
        "SELECT * FROM categorias_repuestos WHERE id = %s AND activo = TRUE",
        (id,), fetch_one=True
    )

    if not categoria:
        flash('Categoria no encontrada', 'danger')
        return redirect(url_for('categorias.lista'))

    return render_template('categorias/form.html', categoria=categoria)


@categorias_bp.route('/<int:id>/actualizar', methods=['POST'])
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def actualizar(id):
    """Actualizar categoria existente"""
    user = get_current_user()

    categoria = execute_query(
        "SELECT * FROM categorias_repuestos WHERE id = %s AND activo = TRUE",
        (id,), fetch_one=True
    )

    if not categoria:
        flash('Categoria no encontrada', 'danger')
        return redirect(url_for('categorias.lista'))

    try:
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()

        if not nombre:
            flash('El nombre de la categoria es obligatorio', 'warning')
            return redirect(url_for('categorias.editar', id=id))

        # Verificar que no exista otra categoria con el mismo nombre (excluyendo la actual)
        existente = execute_query(
            "SELECT id FROM categorias_repuestos WHERE nombre = %s AND activo = TRUE AND id != %s",
            (nombre, id), fetch_one=True
        )

        if existente:
            flash('Ya existe otra categoria con ese nombre', 'warning')
            return redirect(url_for('categorias.editar', id=id))

        # Guardar datos anteriores para audit
        datos_anteriores = {
            'nombre': categoria['nombre'],
            'descripcion': categoria['descripcion']
        }

        # Determinar campos modificados
        campos_modificados = []
        if categoria['nombre'] != nombre:
            campos_modificados.append('nombre')
        if categoria['descripcion'] != descripcion:
            campos_modificados.append('descripcion')

        execute_query("""
            UPDATE categorias_repuestos
            SET nombre = %s, descripcion = %s, updated_by = %s, updated_at = NOW()
            WHERE id = %s
        """, (nombre, descripcion, user['id'], id), commit=True)

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='categorias_repuestos',
            registro_id=str(id),
            accion='ACTUALIZAR',
            tipo_cambio='INVENTARIO',
            datos_anteriores=datos_anteriores,
            datos_nuevos={
                'nombre': nombre,
                'descripcion': descripcion
            },
            campos_modificados=campos_modificados
        )

        flash('Categoria actualizada exitosamente', 'success')
        return redirect(url_for('categorias.lista'))

    except Exception as e:
        logger.error(f"Error actualizando categoria: {e}")
        flash('Error al actualizar la categoria', 'danger')
        return redirect(url_for('categorias.editar', id=id))


@categorias_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@role_required('ADMINISTRADOR', 'ALMACENISTA')
def eliminar(id):
    """Eliminar (soft delete) categoria - solo si no tiene repuestos activos"""
    user = get_current_user()

    categoria = execute_query(
        "SELECT * FROM categorias_repuestos WHERE id = %s AND activo = TRUE",
        (id,), fetch_one=True
    )

    if not categoria:
        flash('Categoria no encontrada', 'danger')
        return redirect(url_for('categorias.lista'))

    # Verificar que no tenga repuestos activos asociados
    repuestos_activos = execute_query(
        "SELECT COUNT(*) as count FROM repuestos WHERE categoria_id = %s AND activo = TRUE",
        (id,), fetch_one=True
    )['count']

    if repuestos_activos > 0:
        flash(f'No se puede eliminar la categoria. Tiene {repuestos_activos} repuesto(s) activo(s) asociado(s).', 'warning')
        return redirect(url_for('categorias.lista'))

    try:
        execute_query("""
            UPDATE categorias_repuestos
            SET activo = FALSE, updated_by = %s, updated_at = NOW()
            WHERE id = %s
        """, (user['id'], id), commit=True)

        # Registrar en audit log
        registrar_audit_log(
            usuario_id=user['id'],
            tabla='categorias_repuestos',
            registro_id=str(id),
            accion='ELIMINAR',
            tipo_cambio='INVENTARIO',
            datos_anteriores={
                'nombre': categoria['nombre'],
                'activo': True
            },
            datos_nuevos={
                'activo': False
            }
        )

        flash('Categoria eliminada exitosamente', 'success')

    except Exception as e:
        logger.error(f"Error eliminando categoria: {e}")
        flash('Error al eliminar la categoria', 'danger')

    return redirect(url_for('categorias.lista'))


# ==================== API ENDPOINTS ====================

@categorias_bp.route('/api/lista')
@login_required
def api_lista():
    """Retorna lista de categorias activas en formato JSON para dropdowns"""
    categorias = execute_query(
        "SELECT id, nombre, descripcion FROM categorias_repuestos WHERE activo = TRUE ORDER BY nombre ASC",
        fetch_all=True
    )

    return jsonify([dict(c) for c in categorias])
