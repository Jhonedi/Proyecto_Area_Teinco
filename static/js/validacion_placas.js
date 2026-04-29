/**
 * Validación de placas vehiculares
 * Formatos soportados:
 * - Autos: ABC123 (3 letras + 3 números)
 * - Motos: ABC12D (3 letras + 2 números + 1 letra)
 */

function validarPlaca(placa) {
    // Eliminar espacios y convertir a mayúsculas
    placa = placa.trim().toUpperCase();
    
    // Patrón para autos: 3 letras + 3 números (ABC123)
    const patronAuto = /^[A-Z]{3}\d{3}$/;
    
    // Patrón para motos: 3 letras + 2 números + 1 letra (ABC12D)
    const patronMoto = /^[A-Z]{3}\d{2}[A-Z]$/;
    
    return patronAuto.test(placa) || patronMoto.test(placa);
}

function formatearPlaca(input) {
    let valor = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    input.value = valor;
}

function aplicarValidacionPlaca(idInput) {
    const input = document.getElementById(idInput);
    
    if (!input) return;
    
    // Aplicar formato en tiempo real
    input.addEventListener('input', function() {
        formatearPlaca(this);
    });
    
    // Validar al perder el foco
    input.addEventListener('blur', function() {
        const valor = this.value.trim();
        
        if (valor && !validarPlaca(valor)) {
            // Crear o actualizar mensaje de error
            let mensajeError = this.nextElementSibling;
            if (!mensajeError || !mensajeError.classList.contains('placa-error')) {
                mensajeError = document.createElement('small');
                mensajeError.className = 'form-text text-danger placa-error';
                this.parentNode.appendChild(mensajeError);
            }
            
            mensajeError.textContent = 'Formato inválido. Use ABC123 para autos o ABC12D para motos.';
            this.classList.add('is-invalid');
        } else {
            // Eliminar mensaje de error si existe
            const mensajeError = this.nextElementSibling;
            if (mensajeError && mensajeError.classList.contains('placa-error')) {
                mensajeError.remove();
            }
            this.classList.remove('is-invalid');
            if (valor) {
                this.classList.add('is-valid');
            }
        }
    });
    
    // Validar antes de enviar el formulario
    const form = input.closest('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const valor = input.value.trim();
            if (valor && !validarPlaca(valor)) {
                e.preventDefault();
                input.focus();
                alert('Por favor, ingrese una placa válida.\n\nFormatos aceptados:\n- Autos: ABC123 (3 letras + 3 números)\n- Motos: ABC12D (3 letras + 2 números + 1 letra)');
                return false;
            }
        });
    }
}

// Función para buscar vehículos por placa
function buscarVehiculoPorPlaca(placa, callback) {
    if (!placa || placa.length < 3) {
        callback([]);
        return;
    }
    
    fetch(`/api/vehiculos/buscar?placa=${encodeURIComponent(placa)}`)
        .then(response => response.json())
        .then(data => callback(data))
        .catch(error => {
            console.error('Error buscando vehículo:', error);
            callback([]);
        });
}

// Autocompletar placas
function aplicarAutocompletarPlaca(idInput, idResultados) {
    const input = document.getElementById(idInput);
    const resultados = document.getElementById(idResultados);
    
    if (!input || !resultados) return;
    
    let timeout = null;
    
    input.addEventListener('input', function() {
        clearTimeout(timeout);
        const valor = this.value.trim();
        
        if (valor.length < 3) {
            resultados.innerHTML = '';
            resultados.style.display = 'none';
            return;
        }
        
        timeout = setTimeout(() => {
            buscarVehiculoPorPlaca(valor, (vehiculos) => {
                if (vehiculos.length === 0) {
                    resultados.innerHTML = '';
                    resultados.style.display = 'none';
                    return;
                }
                
                let html = '<ul class="list-group">';
                vehiculos.forEach(vehiculo => {
                    html += `
                        <li class="list-group-item list-group-item-action" style="cursor: pointer;" 
                            data-vehiculo-id="${vehiculo.id}"
                            data-placa="${vehiculo.placa}"
                            data-cliente="${vehiculo.cliente}">
                            <strong>${vehiculo.placa}</strong> - ${vehiculo.marca} ${vehiculo.modelo}
                            <br><small class="text-muted">${vehiculo.cliente}</small>
                        </li>
                    `;
                });
                html += '</ul>';
                
                resultados.innerHTML = html;
                resultados.style.display = 'block';
                
                // Agregar eventos de clic a los resultados
                resultados.querySelectorAll('li').forEach(item => {
                    item.addEventListener('click', function() {
                        input.value = this.dataset.placa;
                        resultados.innerHTML = '';
                        resultados.style.display = 'none';
                        
                        // Disparar evento personalizado con los datos del vehículo
                        const evento = new CustomEvent('vehiculoSeleccionado', {
                            detail: {
                                id: this.dataset.vehiculoId,
                                placa: this.dataset.placa,
                                cliente: this.dataset.cliente
                            }
                        });
                        input.dispatchEvent(evento);
                    });
                });
            });
        }, 300);
    });
    
    // Cerrar resultados al hacer clic fuera
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !resultados.contains(e.target)) {
            resultados.innerHTML = '';
            resultados.style.display = 'none';
        }
    });
}
