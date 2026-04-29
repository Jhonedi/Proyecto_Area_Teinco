// Sistema de Inventario - JavaScript Principal

$(document).ready(function() {
    // Cargar badges de notificaciones
    loadAlertasCount();
    loadMensajesCount();

    // Actualizar badges cada 60 segundos
    setInterval(loadAlertasCount, 60000);
    setInterval(loadMensajesCount, 60000);

    // Confirmar eliminaciones
    $(document).on('click', '.btn-delete', function(e) {
        if (!confirm('¿Está seguro de que desea eliminar este registro?')) {
            e.preventDefault();
        }
    });

    // Filas de tabla clicables: agregar data-href="<url>" al <tr> para navegación
    $(document).on('click', 'tr[data-href]', function(e) {
        // No navegar si se hizo clic en un botón, enlace o formulario dentro de la fila
        if (!$(e.target).closest('a, button, form, input, select, textarea, label').length) {
            window.location.href = $(this).data('href');
        }
    });

    // Auto-hide alerts después de 5 segundos
    setTimeout(function() {
        $('.alert.alert-dismissible').fadeOut('slow');
    }, 5000);

    // Inicializar tooltips de Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (el) {
        return new bootstrap.Tooltip(el);
    });

    // Formato COP para elementos con clase .currency
    $('.currency').each(function() {
        const value = parseFloat($(this).text());
        if (!isNaN(value)) {
            $(this).text(formatCOP(value));
        }
    });
});

// ==================== BADGES DE NOTIFICACIONES ====================

function loadAlertasCount() {
    $.ajax({
        url: '/alertas/api/count',
        method: 'GET',
        success: function(data) {
            const count = data.count || 0;
            const badge = $('#alertas-count');
            if (count > 0) {
                badge.text(count).removeClass('d-none');
            } else {
                badge.addClass('d-none');
            }
        },
        error: function() {
            // Silencioso - el usuario puede no estar logueado
        }
    });
}

function loadMensajesCount() {
    $.ajax({
        url: '/mensajes/api/no-leidos',
        method: 'GET',
        success: function(data) {
            const count = data.no_leidos || 0;
            const badge = $('#mensajes-count');
            if (count > 0) {
                badge.text(count).removeClass('d-none');
            } else {
                badge.addClass('d-none');
            }
        },
        error: function() {
            // Silencioso
        }
    });
}

// ==================== ALERTAS ====================

function marcarAlertaLeida(alertaId, callback) {
    $.ajax({
        url: '/alertas/' + alertaId + '/marcar-leida',
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        success: function() {
            loadAlertasCount();
            if (typeof callback === 'function') callback();
        },
        error: function(error) {
            console.error('Error marcando alerta:', error);
        }
    });
}

$(document).on('click', '.marcar-leida-btn', function(e) {
    e.preventDefault();
    const alertaId = $(this).data('alerta-id');
    const row = $(this).closest('tr');
    marcarAlertaLeida(alertaId, function() {
        row.removeClass('table-warning');
    });
});

// ==================== REPUESTOS ====================

function searchRepuestos(query) {
    $.ajax({
        url: '/api/repuestos/buscar',
        method: 'GET',
        data: { q: query },
        success: function(repuestos) {
            displayRepuestosResults(repuestos);
        },
        error: function(error) {
            console.error('Error buscando repuestos:', error);
        }
    });
}

function displayRepuestosResults(repuestos) {
    const resultsContainer = $('#repuestos-results');
    resultsContainer.empty();

    if (repuestos.length === 0) {
        resultsContainer.append('<div class="list-group-item text-muted">No se encontraron repuestos</div>');
        return;
    }

    repuestos.forEach(function(repuesto) {
        const disponible = (repuesto.cantidad_actual || 0) - (repuesto.cantidad_reservada || 0);
        const item = `
            <a href="#" class="list-group-item list-group-item-action"
               data-repuesto-id="${repuesto.id}"
               data-repuesto-codigo="${repuesto.codigo}"
               data-repuesto-nombre="${repuesto.nombre}"
               data-repuesto-precio="${repuesto.precio_venta}"
               data-repuesto-stock="${disponible}">
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${repuesto.codigo}</strong> - ${repuesto.nombre}
                        ${repuesto.categoria_nombre ? '<br><small class="text-muted">' + repuesto.categoria_nombre + '</small>' : ''}
                    </div>
                    <div class="text-end">
                        <span class="badge bg-secondary">Stock: ${disponible}</span><br>
                        <small>${formatCOPMoneda(repuesto.precio_venta)}</small>
                    </div>
                </div>
            </a>
        `;
        resultsContainer.append(item);
    });
}

function loadRepuestosDetalle(id) {
    const modal = $('#modalDetalleRepuesto');
    const body = modal.find('.modal-body');
    body.html('<div class="text-center py-4"><div class="spinner-border text-primary"></div><p class="mt-2">Cargando...</p></div>');
    modal.modal('show');

    $.ajax({
        url: '/api/repuestos/' + id + '/detalle',
        method: 'GET',
        success: function(data) {
            let html = `
                <div class="row">
                    <div class="col-md-6">
                        <dl class="row">
                            <dt class="col-5">Código:</dt><dd class="col-7"><code>${data.codigo}</code></dd>
                            <dt class="col-5">Nombre:</dt><dd class="col-7">${data.nombre}</dd>
                            <dt class="col-5">Categoría:</dt><dd class="col-7">${data.categoria_nombre || '-'}</dd>
                            <dt class="col-5">Ubicación:</dt><dd class="col-7">${data.ubicacion_fisica || '-'}</dd>
                            <dt class="col-5">Precio:</dt><dd class="col-7"><strong>${formatCOPMoneda(data.precio_venta)}</strong></dd>
                            <dt class="col-5">Stock actual:</dt><dd class="col-7"><span class="badge bg-${data.cantidad_actual === 0 ? 'danger' : data.cantidad_actual <= data.cantidad_minima ? 'warning' : 'success'}">${data.cantidad_actual}</span></dd>
                            <dt class="col-5">Stock mínimo:</dt><dd class="col-7">${data.cantidad_minima}</dd>
                            <dt class="col-5">Reservado:</dt><dd class="col-7">${data.cantidad_reservada || 0}</dd>
                        </dl>
                    </div>`;

            if (data.imagenes && data.imagenes.length > 0) {
                html += `<div class="col-md-6">
                    <div id="carouselDetalle" class="carousel slide" data-bs-ride="carousel">
                        <div class="carousel-inner">`;
                data.imagenes.forEach(function(img, i) {
                    html += `<div class="carousel-item ${i === 0 ? 'active' : ''}">
                        <img src="/uploads/repuestos/${img.ruta_archivo}" class="d-block w-100" style="max-height:200px;object-fit:contain">
                    </div>`;
                });
                html += `</div>
                    ${data.imagenes.length > 1 ? '<button class="carousel-control-prev" type="button" data-bs-target="#carouselDetalle" data-bs-slide="prev"><span class="carousel-control-prev-icon"></span></button><button class="carousel-control-next" type="button" data-bs-target="#carouselDetalle" data-bs-slide="next"><span class="carousel-control-next-icon"></span></button>' : ''}
                </div></div>`;
            }

            html += '</div>';

            if (data.descripcion_detallada) {
                html += `<hr><h6>Descripción Detallada</h6><p>${data.descripcion_detallada}</p>`;
            }

            if (data.compatibilidad && data.compatibilidad.length > 0) {
                html += '<hr><h6>Compatibilidad</h6><ul>';
                data.compatibilidad.forEach(function(c) { html += `<li>${c}</li>`; });
                html += '</ul>';
            }

            if (data.equivalentes && data.equivalentes.length > 0) {
                html += '<hr><h6>Equivalentes</h6><ul>';
                data.equivalentes.forEach(function(e) { html += `<li><code>${e.codigo}</code> - ${e.nombre}</li>`; });
                html += '</ul>';
            }

            body.html(html);
        },
        error: function() {
            body.html('<div class="alert alert-danger">Error al cargar el detalle del repuesto</div>');
        }
    });
}

function loadRepuestosPorCategoria(categoriaId, targetSelect) {
    const url = categoriaId ? '/api/repuestos/por-categoria/' + categoriaId : '/api/repuestos/buscar?q=';
    $(targetSelect).html('<option value="">Cargando...</option>').prop('disabled', true);
    $.ajax({
        url: url,
        success: function(repuestos) {
            $(targetSelect).html('<option value="">Seleccione repuesto...</option>');
            repuestos.forEach(function(r) {
                const disponible = (r.cantidad_actual || 0) - (r.cantidad_reservada || 0);
                $(targetSelect).append(`<option value="${r.codigo}" data-precio="${r.precio_venta}" data-stock="${disponible}">${r.codigo} - ${r.nombre} (Stock: ${disponible})</option>`);
            });
            $(targetSelect).prop('disabled', false);
        },
        error: function() {
            $(targetSelect).html('<option value="">Error cargando repuestos</option>').prop('disabled', false);
        }
    });
}

// ==================== VEHÍCULOS ====================

function loadVehiculosCliente(clienteId) {
    $.ajax({
        url: '/api/vehiculos-cliente/' + clienteId,
        method: 'GET',
        success: function(vehiculos) {
            const select = $('#vehiculo_cliente_id, #vehiculo_id');
            select.empty().append('<option value="">Seleccione un vehículo</option>');
            vehiculos.forEach(function(vehiculo) {
                select.append(`<option value="${vehiculo.placa}">${vehiculo.placa} - ${vehiculo.marca} ${vehiculo.modelo} ${vehiculo.anio || ''}</option>`);
            });
            select.prop('disabled', false);
        },
        error: function(error) {
            console.error('Error cargando vehículos:', error);
        }
    });
}

$(document).on('change', '#cliente_id', function() {
    const clienteId = $(this).val();
    if (clienteId) {
        loadVehiculosCliente(clienteId);
    }
});

// ==================== FORMATO COLOMBIANO ====================

function formatCOP(value) {
    return new Intl.NumberFormat('es-CO', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value || 0);
}

function formatCOPMoneda(value) {
    return new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value || 0);
}

// Alias para compatibilidad
function formatCurrency(value) {
    return formatCOPMoneda(value);
}

// ==================== UTILIDADES ====================

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-CO', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
    });
}

function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
        form.classList.add('was-validated');
        return false;
    }
    return true;
}

function showLoading(containerId) {
    $(`#${containerId}`).html(`
        <div class="spinner-container">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
        </div>
    `);
}

// ==================== FACTURACIÓN ====================

function calcularTotalFactura() {
    let subtotal = 0;
    $('.item-factura').each(function() {
        const precio = parseFloat($(this).data('precio')) || 0;
        const cantidad = parseInt($(this).find('.cantidad-input').val()) || 0;
        subtotal += precio * cantidad;
    });

    const iva = subtotal * 0.19;
    const total = subtotal + iva;

    $('#subtotal').text(formatCOPMoneda(subtotal));
    $('#iva').text(formatCOPMoneda(iva));
    $('#total').text(formatCOPMoneda(total));
}

$(document).on('change', '.cantidad-input', function() {
    calcularTotalFactura();
});

// ==================== BÚSQUEDA EN TIEMPO REAL ====================

$('#repuesto-search').on('input', debounce(function() {
    const query = $(this).val();
    if (query.length >= 2) {
        searchRepuestos(query);
    }
}, 300));

// ==================== EXPORTS ====================

window.tallerInventario = {
    loadAlertasCount,
    loadMensajesCount,
    searchRepuestos,
    marcarAlertaLeida,
    loadVehiculosCliente,
    loadRepuestosDetalle,
    loadRepuestosPorCategoria,
    formatCOP,
    formatCOPMoneda,
    formatCurrency,
    formatDate,
    validateForm,
    showLoading,
    calcularTotalFactura
};
