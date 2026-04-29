-- Migración de la base de datos del Taller Automotriz de V1/V2 a V3
-- IMPORTANTE: Ejecutar con precaución. Hacer backup antes de ejecutar.
-- Este script es idempotente - puede ejecutarse múltiples veces sin problemas.

USE taller_inventario;

-- ==================== FASE 1: MODIFICAR TABLAS EXISTENTES ====================

-- 1.1 Tabla roles: agregar campos de permisos y protección
ALTER TABLE roles ADD COLUMN IF NOT EXISTS es_protegido BOOLEAN DEFAULT FALSE COMMENT 'Roles protegidos no pueden ser eliminados';
ALTER TABLE roles ADD COLUMN IF NOT EXISTS puede_aprobar_ajustes BOOLEAN DEFAULT FALSE;
ALTER TABLE roles ADD COLUMN IF NOT EXISTS puede_gestionar_alertas BOOLEAN DEFAULT FALSE;
ALTER TABLE roles ADD COLUMN IF NOT EXISTS puede_ver_audit_log BOOLEAN DEFAULT FALSE;
ALTER TABLE roles ADD COLUMN IF NOT EXISTS puede_generar_reportes BOOLEAN DEFAULT FALSE;

-- 1.2 Tabla usuarios: agregar campos de protección y actividad
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS es_protegido BOOLEAN DEFAULT FALSE COMMENT 'Usuarios protegidos no pueden ser eliminados';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultima_actividad TIMESTAMP NULL COMMENT 'Última actividad para control de sesión';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS created_by INT NULL;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS updated_by INT NULL;

-- 1.3 Tabla repuestos: agregar campos de reserva y descripción detallada
ALTER TABLE repuestos ADD COLUMN IF NOT EXISTS descripcion_detallada TEXT COMMENT 'Descripción extendida para vista de detalle';
ALTER TABLE repuestos ADD COLUMN IF NOT EXISTS cantidad_reservada INT NOT NULL DEFAULT 0 COMMENT 'Stock reservado en solicitudes pendientes';
ALTER TABLE repuestos ADD COLUMN IF NOT EXISTS created_by INT NULL;
ALTER TABLE repuestos ADD COLUMN IF NOT EXISTS updated_by INT NULL;
ALTER TABLE repuestos MODIFY COLUMN precio_venta DECIMAL(15, 2) NOT NULL DEFAULT 0.00;

-- 1.4 Tabla categorias_repuestos: agregar campos de auditoría
ALTER TABLE categorias_repuestos ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;
ALTER TABLE categorias_repuestos ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE categorias_repuestos ADD COLUMN IF NOT EXISTS created_by INT NULL;
ALTER TABLE categorias_repuestos ADD COLUMN IF NOT EXISTS updated_by INT NULL;

-- 1.5 Tabla alertas_inventario: reestructurar completamente
-- Primero modificar el repuesto_id para permitir NULL (alertas del sistema)
ALTER TABLE alertas_inventario MODIFY COLUMN repuesto_id INT NULL COMMENT 'NULL para alertas generales del sistema';

-- Cambiar los estados del ENUM
ALTER TABLE alertas_inventario MODIFY COLUMN tipo_alerta ENUM('STOCK_BAJO', 'AGOTADO', 'PROXIMAMENTE_AGOTADO', 'SOLICITUD_PENDIENTE', 'FACTURA_PENDIENTE', 'AJUSTE_PENDIENTE', 'SISTEMA') NOT NULL;

-- Migrar datos existentes antes de cambiar el enum de estado
UPDATE alertas_inventario SET estado = 'NUEVA' WHERE estado = 'ACTIVA';
UPDATE alertas_inventario SET estado = 'NUEVA' WHERE estado = 'LEIDA';
-- RESUELTA permanece igual

ALTER TABLE alertas_inventario MODIFY COLUMN estado ENUM('NUEVA', 'EN_PROCESO', 'RESUELTA', 'ARCHIVADA') DEFAULT 'NUEVA';

-- Agregar nuevos campos
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS datos_adicionales JSON NULL COMMENT 'Datos extra en formato JSON';
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS atendida_por INT NULL COMMENT 'Usuario que está atendiendo';
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS fecha_atencion TIMESTAMP NULL;
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS resuelta_por INT NULL;
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS fecha_resolucion TIMESTAMP NULL;
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS archivada_por INT NULL;
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS fecha_archivado TIMESTAMP NULL;
ALTER TABLE alertas_inventario ADD COLUMN IF NOT EXISTS ultimo_recordatorio TIMESTAMP NULL COMMENT 'Último recordatorio enviado';

-- 1.6 Tabla notificaciones_usuarios: agregar campo de recordatorio
ALTER TABLE notificaciones_usuarios ADD COLUMN IF NOT EXISTS ultimo_recordatorio_enviado DATE NULL COMMENT 'Para controlar recordatorio diario';
-- Agregar constraint unique si no existe
-- (ignorar error si ya existe)
ALTER TABLE notificaciones_usuarios ADD UNIQUE KEY unique_usuario_alerta (usuario_id, alerta_id);

-- 1.7 Tabla movimientos_inventario: expandir estados y agregar referencias
ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS solicitud_id INT NULL COMMENT 'Referencia a solicitud si aplica';
ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS factura_id INT NULL COMMENT 'Referencia a factura si aplica';
ALTER TABLE movimientos_inventario MODIFY COLUMN estado ENUM('PENDIENTE', 'CONFIRMADO', 'CANCELADO', 'RESERVADO', 'APROBADO', 'ENTREGADO', 'FACTURADO', 'DEVUELTO', 'RECHAZADO', 'ANULADO') DEFAULT 'PENDIENTE';
ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS aprobado_por INT NULL;
ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS fecha_aprobacion TIMESTAMP NULL;
ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS motivo_rechazo TEXT NULL;
ALTER TABLE movimientos_inventario MODIFY COLUMN precio_unitario DECIMAL(15, 2);

-- 1.8 Tabla facturas: expandir estados y agregar campos
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS solicitud_id INT NULL COMMENT 'Solicitud origen de la factura';
ALTER TABLE facturas MODIFY COLUMN estado ENUM('EN_ESPERA', 'PENDIENTE', 'PAGADA', 'ANULADA') DEFAULT 'EN_ESPERA';
ALTER TABLE facturas MODIFY COLUMN metodo_pago ENUM('EFECTIVO', 'TARJETA', 'TRANSFERENCIA', 'CREDITO', 'MIXTO') DEFAULT 'EFECTIVO';
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS descuento DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE NULL COMMENT 'Para pagos a crédito';
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS anulado_por INT NULL;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS fecha_anulacion TIMESTAMP NULL;
ALTER TABLE facturas ADD COLUMN IF NOT EXISTS motivo_anulacion TEXT NULL;
ALTER TABLE facturas MODIFY COLUMN subtotal DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE facturas MODIFY COLUMN impuesto DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE facturas MODIFY COLUMN total DECIMAL(15, 2) NOT NULL DEFAULT 0.00;

-- 1.9 Tabla detalles_factura: agregar referencias
ALTER TABLE detalles_factura ADD COLUMN IF NOT EXISTS item_solicitud_id INT NULL COMMENT 'Referencia al ítem de solicitud';
ALTER TABLE detalles_factura ADD COLUMN IF NOT EXISTS descuento DECIMAL(15, 2) DEFAULT 0.00;
ALTER TABLE detalles_factura MODIFY COLUMN precio_unitario DECIMAL(15, 2) NOT NULL;
ALTER TABLE detalles_factura MODIFY COLUMN subtotal DECIMAL(15, 2) NOT NULL;

-- 1.10 Tabla historial_ajustes_inventario: agregar flujo de aprobación
ALTER TABLE historial_ajustes_inventario ADD COLUMN IF NOT EXISTS estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') DEFAULT 'APROBADO';
ALTER TABLE historial_ajustes_inventario ADD COLUMN IF NOT EXISTS aprobado_por INT NULL COMMENT 'Admin/SuperUsuario que aprueba';
ALTER TABLE historial_ajustes_inventario ADD COLUMN IF NOT EXISTS fecha_aprobacion TIMESTAMP NULL;
ALTER TABLE historial_ajustes_inventario ADD COLUMN IF NOT EXISTS motivo_rechazo TEXT NULL;

-- 1.11 Tabla tipos_movimiento: agregar campo de aprobación
ALTER TABLE tipos_movimiento ADD COLUMN IF NOT EXISTS requiere_aprobacion BOOLEAN DEFAULT FALSE;

-- ==================== FASE 2: CREAR TABLAS NUEVAS ====================

-- 2.1 Configuración del sistema
CREATE TABLE IF NOT EXISTS configuracion_sistema (
    id INT PRIMARY KEY AUTO_INCREMENT,
    clave VARCHAR(100) NOT NULL UNIQUE,
    valor TEXT,
    tipo ENUM('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'JSON') DEFAULT 'STRING',
    descripcion TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT NULL
) ENGINE=InnoDB;

-- 2.2 Imágenes de repuestos
CREATE TABLE IF NOT EXISTS imagenes_repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id INT NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_archivo VARCHAR(500) NOT NULL,
    es_principal BOOLEAN DEFAULT FALSE,
    orden INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT NULL,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 2.3 Solicitudes de repuestos
CREATE TABLE IF NOT EXISTS solicitudes_repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_solicitud VARCHAR(20) NOT NULL UNIQUE COMMENT 'Formato: SOL-YYYYMMDD-XXXX',
    tecnico_id INT NOT NULL COMMENT 'Técnico que crea la solicitud',
    cliente_id INT NOT NULL,
    vehiculo_id INT NOT NULL,
    estado ENUM('PENDIENTE', 'APROBADA', 'RECHAZADA', 'ENTREGADA', 'FACTURADA', 'DEVOLUCION_PARCIAL', 'ANULADA') DEFAULT 'PENDIENTE',
    observaciones TEXT,
    fecha_requerida DATE NULL COMMENT 'Fecha en que se necesitan los repuestos',
    aprobado_por INT NULL COMMENT 'Almacenista que aprueba',
    fecha_aprobacion TIMESTAMP NULL,
    entregado_por INT NULL COMMENT 'Almacenista que entrega',
    fecha_entrega TIMESTAMP NULL,
    facturado_por INT NULL COMMENT 'Vendedor que factura',
    fecha_facturacion TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (tecnico_id) REFERENCES usuarios(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos_clientes(id),
    INDEX idx_estado (estado),
    INDEX idx_tecnico (tecnico_id),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- 2.4 Ítems de solicitud
CREATE TABLE IF NOT EXISTS items_solicitud (
    id INT PRIMARY KEY AUTO_INCREMENT,
    solicitud_id INT NOT NULL,
    repuesto_id INT NOT NULL,
    cantidad_solicitada INT NOT NULL,
    cantidad_aprobada INT DEFAULT 0 COMMENT 'Cantidad aprobada por almacenista',
    cantidad_entregada INT DEFAULT 0 COMMENT 'Cantidad realmente entregada',
    cantidad_devuelta INT DEFAULT 0 COMMENT 'Cantidad devuelta antes de facturar',
    precio_unitario DECIMAL(15, 2) NOT NULL COMMENT 'Precio al momento de la solicitud',
    estado ENUM('RESERVADO', 'APROBADO', 'RECHAZADO', 'ENTREGADO', 'FACTURADO', 'DEVUELTO') DEFAULT 'RESERVADO',
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes_repuestos(id) ON DELETE CASCADE,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id),
    INDEX idx_solicitud (solicitud_id),
    INDEX idx_repuesto (repuesto_id)
) ENGINE=InnoDB;

-- 2.5 Pagos de factura
CREATE TABLE IF NOT EXISTS pagos_factura (
    id INT PRIMARY KEY AUTO_INCREMENT,
    factura_id INT NOT NULL,
    monto DECIMAL(15, 2) NOT NULL,
    metodo_pago ENUM('EFECTIVO', 'TARJETA', 'TRANSFERENCIA') NOT NULL,
    referencia VARCHAR(100) NULL COMMENT 'Número de transacción o referencia',
    observaciones TEXT,
    recibido_por INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (recibido_por) REFERENCES usuarios(id)
) ENGINE=InnoDB;

-- 2.6 Historial de alertas
CREATE TABLE IF NOT EXISTS historial_alertas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    alerta_id INT NOT NULL,
    estado_anterior ENUM('NUEVA', 'EN_PROCESO', 'RESUELTA', 'ARCHIVADA') NULL,
    estado_nuevo ENUM('NUEVA', 'EN_PROCESO', 'RESUELTA', 'ARCHIVADA') NOT NULL,
    accion VARCHAR(100) NOT NULL COMMENT 'Descripción de la acción realizada',
    usuario_id INT NOT NULL,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alerta_id) REFERENCES alertas_inventario(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

-- 2.7 Mensajes internos
CREATE TABLE IF NOT EXISTS mensajes_internos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    remitente_id INT NOT NULL,
    destinatario_id INT NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    mensaje TEXT NOT NULL,
    alerta_id INT NULL COMMENT 'Si el mensaje está relacionado con una alerta',
    solicitud_id INT NULL COMMENT 'Si el mensaje está relacionado con una solicitud',
    factura_id INT NULL COMMENT 'Si el mensaje está relacionado con una factura',
    leido BOOLEAN DEFAULT FALSE,
    leido_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (remitente_id) REFERENCES usuarios(id),
    FOREIGN KEY (destinatario_id) REFERENCES usuarios(id),
    INDEX idx_destinatario (destinatario_id, leido),
    INDEX idx_remitente (remitente_id)
) ENGINE=InnoDB;

-- 2.8 Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT NULL COMMENT 'NULL para acciones del sistema',
    tabla_afectada VARCHAR(100) NOT NULL,
    registro_id INT NOT NULL COMMENT 'ID del registro afectado',
    accion ENUM('CREAR', 'ACTUALIZAR', 'ELIMINAR', 'APROBAR', 'RECHAZAR', 'FACTURAR', 'ANULAR', 'AJUSTE', 'LOGIN', 'LOGOUT') NOT NULL,
    tipo_cambio ENUM('INVENTARIO', 'USUARIO', 'CLIENTE', 'VEHICULO', 'FACTURA', 'SOLICITUD', 'ALERTA', 'CONFIGURACION', 'SESION', 'OTRO') NOT NULL,
    datos_anteriores JSON NULL COMMENT 'Estado anterior del registro',
    datos_nuevos JSON NULL COMMENT 'Estado nuevo del registro',
    campos_modificados JSON NULL COMMENT 'Lista de campos que cambiaron',
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usuario (usuario_id),
    INDEX idx_tabla (tabla_afectada, registro_id),
    INDEX idx_accion (accion),
    INDEX idx_tipo (tipo_cambio),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- 2.9 Reportes generados
CREATE TABLE IF NOT EXISTS reportes_generados (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tipo_reporte ENUM('INVENTARIO', 'VENTAS', 'MOVIMIENTOS', 'ALERTAS', 'USUARIOS', 'CLIENTES', 'GENERAL') NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    parametros JSON NULL COMMENT 'Parámetros usados para generar el reporte',
    datos JSON NULL COMMENT 'Datos del reporte en formato JSON',
    ruta_archivo VARCHAR(500) NULL COMMENT 'Ruta al archivo generado',
    generado_por INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generado_por) REFERENCES usuarios(id),
    INDEX idx_tipo (tipo_reporte),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- ==================== FASE 3: DATOS INICIALES ====================

-- 3.1 Insertar rol SUPER_USUARIO si no existe
INSERT IGNORE INTO roles (nombre, descripcion, es_protegido, puede_aprobar_ajustes, puede_gestionar_alertas, puede_ver_audit_log, puede_generar_reportes) VALUES
('SUPER_USUARIO', 'Control total del sistema. No puede ser eliminado ni modificado excepto por otro Super Usuario.', TRUE, TRUE, TRUE, TRUE, TRUE);

-- 3.2 Actualizar permisos de roles existentes
UPDATE roles SET puede_aprobar_ajustes = TRUE, puede_gestionar_alertas = TRUE, puede_ver_audit_log = TRUE, puede_generar_reportes = TRUE WHERE nombre = 'ADMINISTRADOR';
UPDATE roles SET puede_gestionar_alertas = TRUE, puede_generar_reportes = TRUE WHERE nombre = 'ALMACENISTA';
UPDATE roles SET puede_generar_reportes = TRUE WHERE nombre = 'VENDEDOR';
UPDATE roles SET es_protegido = TRUE WHERE nombre = 'SUPER_USUARIO';

-- 3.3 Insertar configuración del sistema
INSERT IGNORE INTO configuracion_sistema (clave, valor, tipo, descripcion) VALUES
('SESSION_INACTIVITY_TIMEOUT', '30', 'INTEGER', 'Minutos de inactividad antes de cerrar sesión automáticamente'),
('IVA_PORCENTAJE', '19.00', 'DECIMAL', 'Porcentaje de IVA aplicable'),
('PREFIJO_SOLICITUD', 'SOL', 'STRING', 'Prefijo para números de solicitud'),
('PREFIJO_FACTURA', 'FAC', 'STRING', 'Prefijo para números de factura'),
('RECORDATORIO_ALERTA_HORAS', '24', 'INTEGER', 'Horas entre recordatorios de alertas no resueltas'),
('DIAS_VENCIMIENTO_CREDITO', '30', 'INTEGER', 'Días por defecto para vencimiento de facturas a crédito');

-- 3.4 Insertar tipos de movimiento nuevos
INSERT IGNORE INTO tipos_movimiento (nombre, tipo, descripcion, requiere_aprobacion) VALUES
('Devolución Técnico', 'ENTRADA', 'Repuesto devuelto por técnico antes de facturar', FALSE),
('Solicitud Técnico', 'SALIDA', 'Salida por solicitud de técnico', FALSE);

-- 3.5 Actualizar tipos que requieren aprobación
UPDATE tipos_movimiento SET requiere_aprobacion = TRUE WHERE nombre IN ('Ajuste Positivo', 'Ajuste Negativo');

-- 3.6 Insertar usuario Super Usuario si no existe
-- Password: super123 (CAMBIAR EN PRODUCCIÓN)
INSERT IGNORE INTO usuarios (username, password_hash, nombre_completo, email, rol_id, es_protegido)
SELECT 'superusuario', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xvMqvRfPEOaY1G', 'Super Usuario del Sistema', 'super@taller.com', r.id, TRUE
FROM roles r WHERE r.nombre = 'SUPER_USUARIO';

-- ==================== FASE 4: ÍNDICES ADICIONALES ====================

CREATE INDEX IF NOT EXISTS idx_repuestos_nombre ON repuestos(nombre);
CREATE INDEX IF NOT EXISTS idx_clientes_documento ON clientes(numero_documento);
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);

-- ==================== FASE 5: VISTAS ====================

-- Vista de stock disponible
CREATE OR REPLACE VIEW v_stock_disponible AS
SELECT
    r.id, r.codigo, r.nombre,
    r.cantidad_actual as stock_fisico,
    r.cantidad_reservada as stock_reservado,
    (r.cantidad_actual - r.cantidad_reservada) as stock_disponible,
    r.cantidad_minima, r.precio_venta,
    c.nombre as categoria
FROM repuestos r
LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
WHERE r.activo = TRUE;

-- Vista de solicitudes pendientes
CREATE OR REPLACE VIEW v_solicitudes_pendientes AS
SELECT
    s.id, s.numero_solicitud, s.estado, s.created_at, s.fecha_requerida,
    u.nombre_completo as tecnico,
    c.nombre_completo as cliente,
    v.placa,
    COUNT(i.id) as total_items,
    SUM(i.cantidad_solicitada * i.precio_unitario) as valor_total
FROM solicitudes_repuestos s
JOIN usuarios u ON s.tecnico_id = u.id
JOIN clientes c ON s.cliente_id = c.id
JOIN vehiculos_clientes v ON s.vehiculo_id = v.id
LEFT JOIN items_solicitud i ON s.id = i.solicitud_id
WHERE s.estado IN ('PENDIENTE', 'APROBADA')
GROUP BY s.id, s.numero_solicitud, s.estado, s.created_at, s.fecha_requerida,
         u.nombre_completo, c.nombre_completo, v.placa;

-- Vista de facturas por estado
CREATE OR REPLACE VIEW v_facturas_estado AS
SELECT
    f.id, f.numero_factura, f.estado, f.total, f.created_at,
    c.nombre_completo as cliente,
    v.placa,
    u.nombre_completo as vendedor
FROM facturas f
JOIN clientes c ON f.cliente_id = c.id
LEFT JOIN vehiculos_clientes v ON f.vehiculo_cliente_id = v.id
JOIN usuarios u ON f.vendedor_id = u.id;

-- Vista de alertas activas
CREATE OR REPLACE VIEW v_alertas_activas AS
SELECT
    a.id, a.tipo_alerta, a.nivel_prioridad, a.mensaje, a.estado, a.created_at,
    r.codigo as repuesto_codigo, r.nombre as repuesto_nombre,
    u.nombre_completo as atendida_por_nombre
FROM alertas_inventario a
LEFT JOIN repuestos r ON a.repuesto_id = r.id
LEFT JOIN usuarios u ON a.atendida_por = u.id
WHERE a.estado IN ('NUEVA', 'EN_PROCESO');
