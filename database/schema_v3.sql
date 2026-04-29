-- Base de datos para Sistema de Inventario de Taller Automotriz - Versión 3
-- Charset: UTF-8 para soporte completo de español
-- PKs NATURALES: usuarios(numero_documento), clientes(numero_documento),
--                vehiculos_clientes(placa), repuestos(codigo)

CREATE DATABASE IF NOT EXISTS taller_inventario CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
USE taller_inventario;

-- ==================== TABLAS BASE ====================

-- Tabla de roles (PKs enteras, orden jerárquico: 1=SUPER_USUARIO ... 5=TECNICO)
CREATE TABLE roles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT,
    es_protegido BOOLEAN DEFAULT FALSE COMMENT 'Roles protegidos no pueden ser eliminados',
    puede_aprobar_ajustes BOOLEAN DEFAULT FALSE,
    puede_gestionar_alertas BOOLEAN DEFAULT FALSE,
    puede_ver_audit_log BOOLEAN DEFAULT FALSE,
    puede_generar_reportes BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla de usuarios — PK NATURAL: numero_documento
CREATE TABLE usuarios (
    numero_documento VARCHAR(20) NOT NULL PRIMARY KEY COMMENT 'Cédula, NIT o documento de identidad',
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    rol_id INT NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    es_protegido BOOLEAN DEFAULT FALSE COMMENT 'Usuarios protegidos no pueden ser eliminados',
    ultima_actividad TIMESTAMP NULL COMMENT 'Última actividad para control de sesión',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL,
    updated_by VARCHAR(20) NULL,
    FOREIGN KEY (rol_id) REFERENCES roles(id),
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Tabla de configuración del sistema
CREATE TABLE configuracion_sistema (
    id INT PRIMARY KEY AUTO_INCREMENT,
    clave VARCHAR(100) NOT NULL UNIQUE,
    valor TEXT,
    tipo ENUM('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'JSON') DEFAULT 'STRING',
    descripcion TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(20) NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ==================== TABLAS DE VEHÍCULOS ====================

CREATE TABLE marcas_vehiculos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE modelos_vehiculos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    marca_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    anio_inicio INT,
    anio_fin INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (marca_id) REFERENCES marcas_vehiculos(id),
    UNIQUE KEY unique_modelo (marca_id, nombre)
) ENGINE=InnoDB;

-- ==================== TABLAS DE REPUESTOS ====================

CREATE TABLE categorias_repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL,
    updated_by VARCHAR(20) NULL,
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Tabla de repuestos — PK NATURAL: codigo
CREATE TABLE repuestos (
    codigo VARCHAR(50) NOT NULL PRIMARY KEY COMMENT 'Código único del repuesto (ej: FILT-001)',
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    descripcion_detallada TEXT COMMENT 'Descripción extendida para vista de detalle',
    categoria_id INT,
    precio_venta DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    cantidad_actual INT NOT NULL DEFAULT 0 COMMENT 'Stock físico real',
    cantidad_reservada INT NOT NULL DEFAULT 0 COMMENT 'Stock reservado en solicitudes pendientes',
    cantidad_minima INT NOT NULL DEFAULT 5,
    ubicacion_fisica VARCHAR(100),
    marca_fabricante VARCHAR(100),
    observaciones TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL,
    updated_by VARCHAR(20) NULL,
    FOREIGN KEY (categoria_id) REFERENCES categorias_repuestos(id),
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Tabla de imágenes de repuestos
CREATE TABLE imagenes_repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id VARCHAR(50) NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_archivo VARCHAR(500) NOT NULL,
    es_principal BOOLEAN DEFAULT FALSE,
    orden INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE repuestos_compatibilidad (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id VARCHAR(50) NOT NULL,
    modelo_vehiculo_id INT NOT NULL,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo) ON DELETE CASCADE,
    FOREIGN KEY (modelo_vehiculo_id) REFERENCES modelos_vehiculos(id),
    UNIQUE KEY unique_compatibilidad (repuesto_id, modelo_vehiculo_id)
) ENGINE=InnoDB;

CREATE TABLE repuestos_equivalentes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id VARCHAR(50) NOT NULL,
    marca_equivalente VARCHAR(100) NOT NULL,
    codigo_equivalente VARCHAR(50),
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ==================== TABLAS DE CLIENTES Y VEHÍCULOS ====================

-- Tabla de clientes — PK NATURAL: numero_documento
CREATE TABLE clientes (
    numero_documento VARCHAR(20) NOT NULL PRIMARY KEY COMMENT 'CC, NIT, CE o PASAPORTE',
    tipo_documento ENUM('CC', 'NIT', 'CE', 'PASAPORTE') DEFAULT 'CC',
    nombre_completo VARCHAR(200) NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(100),
    direccion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(20) NULL,
    updated_by VARCHAR(20) NULL,
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Tabla de vehículos — PK NATURAL: placa
CREATE TABLE vehiculos_clientes (
    placa VARCHAR(10) NOT NULL PRIMARY KEY COMMENT 'Formato: ABC123 (autos) o ABC12D (motos)',
    cliente_id VARCHAR(20) NOT NULL,
    modelo_vehiculo_id INT NOT NULL,
    anio INT,
    color VARCHAR(50),
    numero_motor VARCHAR(100),
    numero_chasis VARCHAR(100),
    kilometraje_actual INT,
    observaciones TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(numero_documento),
    FOREIGN KEY (modelo_vehiculo_id) REFERENCES modelos_vehiculos(id)
) ENGINE=InnoDB;

-- ==================== SISTEMA DE SOLICITUDES DE REPUESTOS ====================

-- Solicitudes creadas por técnicos
CREATE TABLE solicitudes_repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_solicitud VARCHAR(20) NOT NULL UNIQUE COMMENT 'Formato: SOL-YYYYMMDD-XXXX',
    tecnico_id VARCHAR(20) NOT NULL COMMENT 'Técnico que crea la solicitud',
    cliente_id VARCHAR(20) NOT NULL,
    vehiculo_id VARCHAR(10) NOT NULL,
    estado ENUM('PENDIENTE', 'APROBADA', 'RECHAZADA', 'ENTREGADA', 'FACTURADA', 'DEVOLUCION_PARCIAL', 'ANULADA') DEFAULT 'PENDIENTE',
    observaciones TEXT,
    fecha_requerida DATE NULL COMMENT 'Fecha en que se necesitan los repuestos',
    -- Control de flujo
    aprobado_por VARCHAR(20) NULL COMMENT 'Almacenista que aprueba',
    fecha_aprobacion TIMESTAMP NULL,
    entregado_por VARCHAR(20) NULL COMMENT 'Almacenista que entrega',
    fecha_entrega TIMESTAMP NULL,
    facturado_por VARCHAR(20) NULL COMMENT 'Vendedor que factura',
    fecha_facturacion TIMESTAMP NULL,
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (tecnico_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (cliente_id) REFERENCES clientes(numero_documento),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos_clientes(placa),
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (entregado_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (facturado_por) REFERENCES usuarios(numero_documento),
    INDEX idx_estado (estado),
    INDEX idx_tecnico (tecnico_id),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- Ítems de cada solicitud
CREATE TABLE items_solicitud (
    id INT PRIMARY KEY AUTO_INCREMENT,
    solicitud_id INT NOT NULL,
    repuesto_id VARCHAR(50) NOT NULL,
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
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo),
    INDEX idx_solicitud (solicitud_id),
    INDEX idx_repuesto (repuesto_id)
) ENGINE=InnoDB;

-- ==================== MOVIMIENTOS DE INVENTARIO ====================

CREATE TABLE tipos_movimiento (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    tipo ENUM('ENTRADA', 'SALIDA') NOT NULL,
    descripcion TEXT,
    requiere_aprobacion BOOLEAN DEFAULT FALSE
) ENGINE=InnoDB;

-- Estados expandidos para movimientos
CREATE TABLE movimientos_inventario (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id VARCHAR(50) NOT NULL,
    tipo_movimiento_id INT NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(15, 2),
    usuario_id VARCHAR(20) NOT NULL COMMENT 'Usuario que registró el movimiento',
    tecnico_solicitante_id VARCHAR(20) NULL,
    vehiculo_cliente_id VARCHAR(10) NULL,
    solicitud_id INT NULL COMMENT 'Referencia a solicitud si aplica',
    factura_id INT NULL COMMENT 'Referencia a factura si aplica',
    -- Estados expandidos
    estado ENUM('PENDIENTE', 'RESERVADO', 'APROBADO', 'ENTREGADO', 'FACTURADO', 'DEVUELTO', 'RECHAZADO', 'ANULADO') DEFAULT 'PENDIENTE',
    -- Control de flujo
    aprobado_por VARCHAR(20) NULL,
    fecha_aprobacion TIMESTAMP NULL,
    motivo_rechazo TEXT NULL,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo),
    FOREIGN KEY (tipo_movimiento_id) REFERENCES tipos_movimiento(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (tecnico_solicitante_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (vehiculo_cliente_id) REFERENCES vehiculos_clientes(placa),
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes_repuestos(id),
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(numero_documento),
    INDEX idx_estado (estado),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- Historial de ajustes de inventario (con aprobación)
CREATE TABLE historial_ajustes_inventario (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id VARCHAR(50) NOT NULL,
    cantidad_anterior INT NOT NULL,
    cantidad_nueva INT NOT NULL,
    diferencia INT NOT NULL,
    usuario_id VARCHAR(20) NOT NULL COMMENT 'Usuario que solicita el ajuste',
    motivo TEXT,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') DEFAULT 'PENDIENTE',
    aprobado_por VARCHAR(20) NULL COMMENT 'Admin/SuperUsuario que aprueba',
    fecha_aprobacion TIMESTAMP NULL,
    motivo_rechazo TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(numero_documento),
    INDEX idx_estado (estado),
    INDEX idx_repuesto (repuesto_id)
) ENGINE=InnoDB;

-- ==================== MÓDULO DE VENTAS Y FACTURACIÓN ====================

CREATE TABLE facturas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_factura VARCHAR(50) NOT NULL UNIQUE,
    cliente_id VARCHAR(20) NOT NULL,
    vehiculo_cliente_id VARCHAR(10) NULL,
    solicitud_id INT NULL COMMENT 'Solicitud origen de la factura',
    vendedor_id VARCHAR(20) NOT NULL,
    subtotal DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    impuesto DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    descuento DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    -- Estados expandidos
    estado ENUM('EN_ESPERA', 'PENDIENTE', 'PAGADA', 'ANULADA') DEFAULT 'EN_ESPERA',
    metodo_pago ENUM('EFECTIVO', 'TARJETA', 'TRANSFERENCIA', 'CREDITO', 'MIXTO') DEFAULT 'EFECTIVO',
    fecha_vencimiento DATE NULL COMMENT 'Para pagos a crédito',
    observaciones TEXT,
    -- Control de cambios
    anulado_por VARCHAR(20) NULL,
    fecha_anulacion TIMESTAMP NULL,
    motivo_anulacion TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(numero_documento),
    FOREIGN KEY (vehiculo_cliente_id) REFERENCES vehiculos_clientes(placa),
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes_repuestos(id),
    FOREIGN KEY (vendedor_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (anulado_por) REFERENCES usuarios(numero_documento),
    INDEX idx_estado (estado),
    INDEX idx_cliente (cliente_id),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

CREATE TABLE detalles_factura (
    id INT PRIMARY KEY AUTO_INCREMENT,
    factura_id INT NOT NULL,
    repuesto_id VARCHAR(50) NOT NULL,
    item_solicitud_id INT NULL COMMENT 'Referencia al ítem de solicitud',
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(15, 2) NOT NULL,
    descuento DECIMAL(15, 2) DEFAULT 0.00,
    subtotal DECIMAL(15, 2) NOT NULL,
    movimiento_inventario_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo),
    FOREIGN KEY (item_solicitud_id) REFERENCES items_solicitud(id),
    FOREIGN KEY (movimiento_inventario_id) REFERENCES movimientos_inventario(id)
) ENGINE=InnoDB;

-- Pagos de facturas (para pagos parciales o mixtos)
CREATE TABLE pagos_factura (
    id INT PRIMARY KEY AUTO_INCREMENT,
    factura_id INT NOT NULL,
    monto DECIMAL(15, 2) NOT NULL,
    metodo_pago ENUM('EFECTIVO', 'TARJETA', 'TRANSFERENCIA') NOT NULL,
    referencia VARCHAR(100) NULL COMMENT 'Número de transacción o referencia',
    observaciones TEXT,
    recibido_por VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (recibido_por) REFERENCES usuarios(numero_documento)
) ENGINE=InnoDB;

-- ==================== SISTEMA DE ALERTAS MEJORADO ====================

CREATE TABLE alertas_inventario (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id VARCHAR(50) NULL COMMENT 'NULL para alertas generales del sistema',
    tipo_alerta ENUM('STOCK_BAJO', 'AGOTADO', 'PROXIMAMENTE_AGOTADO', 'SOLICITUD_PENDIENTE', 'FACTURA_PENDIENTE', 'AJUSTE_PENDIENTE', 'SISTEMA') NOT NULL,
    nivel_prioridad ENUM('BAJA', 'MEDIA', 'ALTA', 'CRITICA') NOT NULL,
    mensaje TEXT NOT NULL,
    datos_adicionales JSON NULL COMMENT 'Datos extra en formato JSON',
    -- Estados mejorados
    estado ENUM('NUEVA', 'EN_PROCESO', 'RESUELTA', 'ARCHIVADA') DEFAULT 'NUEVA',
    -- Control de flujo
    atendida_por VARCHAR(20) NULL COMMENT 'Usuario que está atendiendo la alerta',
    fecha_atencion TIMESTAMP NULL,
    resuelta_por VARCHAR(20) NULL,
    fecha_resolucion TIMESTAMP NULL,
    archivada_por VARCHAR(20) NULL,
    fecha_archivado TIMESTAMP NULL,
    -- Recordatorios
    ultimo_recordatorio TIMESTAMP NULL COMMENT 'Último recordatorio enviado',
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo),
    FOREIGN KEY (atendida_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (resuelta_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (archivada_por) REFERENCES usuarios(numero_documento),
    INDEX idx_estado (estado),
    INDEX idx_tipo (tipo_alerta),
    INDEX idx_prioridad (nivel_prioridad)
) ENGINE=InnoDB;

-- Historial de cambios de alertas
CREATE TABLE historial_alertas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    alerta_id INT NOT NULL,
    estado_anterior ENUM('NUEVA', 'EN_PROCESO', 'RESUELTA', 'ARCHIVADA') NULL,
    estado_nuevo ENUM('NUEVA', 'EN_PROCESO', 'RESUELTA', 'ARCHIVADA') NOT NULL,
    accion VARCHAR(100) NOT NULL COMMENT 'Descripción de la acción realizada',
    usuario_id VARCHAR(20) NOT NULL,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alerta_id) REFERENCES alertas_inventario(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento)
) ENGINE=InnoDB;

-- Notificaciones a usuarios (marca personal de leída)
CREATE TABLE notificaciones_usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    usuario_id VARCHAR(20) NOT NULL,
    alerta_id INT NOT NULL,
    leida BOOLEAN DEFAULT FALSE,
    leida_at TIMESTAMP NULL,
    ultimo_recordatorio_enviado DATE NULL COMMENT 'Para controlar recordatorio diario',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (alerta_id) REFERENCES alertas_inventario(id) ON DELETE CASCADE,
    UNIQUE KEY unique_usuario_alerta (usuario_id, alerta_id)
) ENGINE=InnoDB;

-- ==================== MENSAJES INTERNOS ====================

CREATE TABLE mensajes_internos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    remitente_id VARCHAR(20) NOT NULL,
    destinatario_id VARCHAR(20) NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    mensaje TEXT NOT NULL,
    alerta_id INT NULL COMMENT 'Si el mensaje está relacionado con una alerta',
    solicitud_id INT NULL COMMENT 'Si el mensaje está relacionado con una solicitud',
    factura_id INT NULL COMMENT 'Si el mensaje está relacionado con una factura',
    leido BOOLEAN DEFAULT FALSE,
    leido_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (remitente_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (destinatario_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (alerta_id) REFERENCES alertas_inventario(id) ON DELETE SET NULL,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes_repuestos(id) ON DELETE SET NULL,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE SET NULL,
    INDEX idx_destinatario (destinatario_id, leido),
    INDEX idx_remitente (remitente_id)
) ENGINE=InnoDB;

-- ==================== AUDIT LOG ====================

CREATE TABLE audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    usuario_id VARCHAR(20) NULL COMMENT 'NULL para acciones del sistema',
    tabla_afectada VARCHAR(100) NOT NULL,
    registro_id VARCHAR(100) NOT NULL COMMENT 'PK del registro afectado (puede ser string o número)',
    accion ENUM('CREAR', 'ACTUALIZAR', 'ELIMINAR', 'APROBAR', 'RECHAZAR', 'FACTURAR', 'ANULAR', 'AJUSTE', 'LOGIN', 'LOGOUT') NOT NULL,
    tipo_cambio ENUM('INVENTARIO', 'USUARIO', 'CLIENTE', 'VEHICULO', 'FACTURA', 'SOLICITUD', 'ALERTA', 'CONFIGURACION', 'SESION', 'OTRO') NOT NULL,
    datos_anteriores JSON NULL COMMENT 'Estado anterior del registro',
    datos_nuevos JSON NULL COMMENT 'Estado nuevo del registro',
    campos_modificados JSON NULL COMMENT 'Lista de campos que cambiaron',
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    INDEX idx_usuario (usuario_id),
    INDEX idx_tabla (tabla_afectada, registro_id(20)),
    INDEX idx_accion (accion),
    INDEX idx_tipo (tipo_cambio),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- ==================== REPORTES PERIÓDICOS ====================

CREATE TABLE reportes_generados (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tipo_reporte ENUM('INVENTARIO', 'VENTAS', 'MOVIMIENTOS', 'ALERTAS', 'USUARIOS', 'CLIENTES', 'GENERAL') NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    parametros JSON NULL COMMENT 'Parámetros usados para generar el reporte',
    datos JSON NULL COMMENT 'Datos del reporte en formato JSON',
    ruta_archivo VARCHAR(500) NULL COMMENT 'Ruta al archivo generado (PDF, Excel, etc.)',
    generado_por VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generado_por) REFERENCES usuarios(numero_documento),
    INDEX idx_tipo (tipo_reporte),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB;

-- ==================== ÍNDICES ADICIONALES ====================

CREATE INDEX idx_repuestos_categoria ON repuestos(categoria_id);
CREATE INDEX idx_repuestos_cantidad ON repuestos(cantidad_actual);
CREATE INDEX idx_repuestos_nombre ON repuestos(nombre);
CREATE INDEX idx_usuarios_username ON usuarios(username);

-- ==================== DATOS INICIALES ====================

-- Insertar roles predeterminados (orden jerárquico: 1=SUPER_USUARIO ... 5=TECNICO)
INSERT INTO roles (nombre, descripcion, es_protegido, puede_aprobar_ajustes, puede_gestionar_alertas, puede_ver_audit_log, puede_generar_reportes) VALUES
('SUPER_USUARIO', 'Control total del sistema. No puede ser eliminado ni modificado excepto por otro Super Usuario.', TRUE, TRUE, TRUE, TRUE, TRUE),
('ADMINISTRADOR', 'Control total del sistema excepto funciones exclusivas de Super Usuario', FALSE, TRUE, TRUE, TRUE, TRUE),
('ALMACENISTA', 'Gestión de inventario, entradas, salidas y aprobación de solicitudes', FALSE, FALSE, TRUE, FALSE, TRUE),
('VENDEDOR', 'Confirmación de ventas y facturación', FALSE, FALSE, FALSE, FALSE, TRUE),
('TECNICO', 'Creación de solicitudes de repuestos (no puede modificar inventario directamente)', FALSE, FALSE, FALSE, FALSE, FALSE);

-- Insertar tipos de movimiento predeterminados
INSERT INTO tipos_movimiento (nombre, tipo, descripcion, requiere_aprobacion) VALUES
('Compra', 'ENTRADA', 'Entrada de repuestos por compra', FALSE),
('Ajuste Positivo', 'ENTRADA', 'Ajuste de inventario (aumento)', TRUE),
('Devolución Cliente', 'ENTRADA', 'Repuesto devuelto por cliente', FALSE),
('Devolución Técnico', 'ENTRADA', 'Repuesto devuelto por técnico antes de facturar', FALSE),
('Venta', 'SALIDA', 'Salida de repuesto por venta/facturación', FALSE),
('Solicitud Técnico', 'SALIDA', 'Salida por solicitud de técnico', FALSE),
('Uso Interno', 'SALIDA', 'Repuesto usado en taller', FALSE),
('Ajuste Negativo', 'SALIDA', 'Ajuste de inventario (disminución)', TRUE),
('Garantía', 'SALIDA', 'Salida por garantía', FALSE);

-- Insertar usuario Super Usuario por defecto
-- Password: super123 (debe cambiarse inmediatamente en producción)
INSERT INTO usuarios (numero_documento, username, password_hash, nombre_completo, email, rol_id, es_protegido) VALUES
('0000000001', 'superusuario', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xvMqvRfPEOaY1G', 'Super Usuario del Sistema', 'super@taller.com', 1, TRUE);

-- Insertar usuario administrador por defecto
-- Password: admin123 (debe cambiarse en producción)
INSERT INTO usuarios (numero_documento, username, password_hash, nombre_completo, email, rol_id) VALUES
('0000000002', 'admin', '$2b$12$Y2AGfKQsLpKfPOHK5ZO/gOYwgznuQbT6gOI3mOQ8EySTMrwm3GP56', 'Administrador del Sistema', 'admin@taller.com', 2);

-- ==================== CÓDIGOS DE DESCUENTO ====================

CREATE TABLE IF NOT EXISTS codigos_descuento (
    codigo VARCHAR(20) PRIMARY KEY,
    descripcion VARCHAR(200) NOT NULL,
    tipo ENUM('PORCENTAJE', 'FIJO') NOT NULL DEFAULT 'PORCENTAJE',
    valor DECIMAL(10,2) NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Insertar configuración inicial del sistema
INSERT INTO configuracion_sistema (clave, valor, tipo, descripcion) VALUES
('SESSION_INACTIVITY_TIMEOUT', '30', 'INTEGER', 'Minutos de inactividad antes de cerrar sesión automáticamente'),
('FORMATO_NUMERO_MILES', '''', 'STRING', 'Separador de miles (apóstrofe)'),
('FORMATO_NUMERO_DECIMALES', ',', 'STRING', 'Separador de decimales (coma)'),
('IVA_PORCENTAJE', '19.00', 'DECIMAL', 'Porcentaje de IVA aplicable'),
('PREFIJO_SOLICITUD', 'SOL', 'STRING', 'Prefijo para números de solicitud'),
('PREFIJO_FACTURA', 'FAC', 'STRING', 'Prefijo para números de factura'),
('RECORDATORIO_ALERTA_HORAS', '24', 'INTEGER', 'Horas entre recordatorios de alertas no resueltas'),
('DIAS_VENCIMIENTO_CREDITO', '30', 'INTEGER', 'Días por defecto para vencimiento de facturas a crédito'),
('EMPRESA_NOMBRE', 'Taller Automotriz', 'STRING', 'Nombre de la empresa para facturas y reportes'),
('EMPRESA_NIT', '900000000-0', 'STRING', 'NIT o RUT de la empresa'),
('EMPRESA_DIRECCION', 'Dirección del taller', 'STRING', 'Dirección física de la empresa'),
('EMPRESA_TELEFONO', '601 0000000', 'STRING', 'Teléfono de contacto de la empresa'),
('EMPRESA_EMAIL', 'taller@email.com', 'STRING', 'Correo electrónico de la empresa'),
('EMPRESA_CIUDAD', 'Bogotá', 'STRING', 'Ciudad de la empresa'),
('EMPRESA_REGIMEN', 'Régimen Común', 'STRING', 'Régimen fiscal (Común, Simplificado, etc.)')
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion);

-- Insertar categorías de repuestos comunes
INSERT INTO categorias_repuestos (nombre, descripcion) VALUES
('Motor', 'Repuestos relacionados con el motor'),
('Transmisión', 'Repuestos de caja de cambios y transmisión'),
('Suspensión', 'Repuestos de sistema de suspensión'),
('Frenos', 'Repuestos de sistema de frenos'),
('Eléctrico', 'Repuestos eléctricos y electrónicos'),
('Filtros', 'Filtros de aire, aceite, combustible, etc.'),
('Lubricantes', 'Aceites y lubricantes'),
('Carrocería', 'Repuestos de carrocería'),
('Iluminación', 'Luces y sistema de iluminación'),
('Neumáticos', 'Llantas y neumáticos'),
('Refrigeración', 'Sistema de refrigeración'),
('Escape', 'Sistema de escape'),
('Dirección', 'Sistema de dirección'),
('Combustible', 'Sistema de combustible'),
('Accesorios', 'Accesorios varios');

-- Insertar algunas marcas de vehículos comunes en Latinoamérica
INSERT INTO marcas_vehiculos (nombre) VALUES
('Chevrolet'), ('Ford'), ('Nissan'), ('Toyota'), ('Mazda'),
('Honda'), ('Hyundai'), ('Kia'), ('Volkswagen'), ('Renault'),
('Mitsubishi'), ('Suzuki'), ('Jeep'), ('BMW'), ('Mercedes-Benz');

-- ==================== TRIGGERS PARA AUDIT LOG ====================

DELIMITER //

-- Trigger para auditar cambios en repuestos
CREATE TRIGGER audit_repuestos_update
AFTER UPDATE ON repuestos
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (usuario_id, tabla_afectada, registro_id, accion, tipo_cambio, datos_anteriores, datos_nuevos)
    VALUES (
        NEW.updated_by,
        'repuestos',
        NEW.codigo,
        'ACTUALIZAR',
        'INVENTARIO',
        JSON_OBJECT('codigo', OLD.codigo, 'nombre', OLD.nombre, 'cantidad_actual', OLD.cantidad_actual, 'precio_venta', OLD.precio_venta),
        JSON_OBJECT('codigo', NEW.codigo, 'nombre', NEW.nombre, 'cantidad_actual', NEW.cantidad_actual, 'precio_venta', NEW.precio_venta)
    );
END//

-- Trigger para auditar nuevos usuarios
CREATE TRIGGER audit_usuarios_insert
AFTER INSERT ON usuarios
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (usuario_id, tabla_afectada, registro_id, accion, tipo_cambio, datos_nuevos)
    VALUES (
        NEW.created_by,
        'usuarios',
        NEW.numero_documento,
        'CREAR',
        'USUARIO',
        JSON_OBJECT('username', NEW.username, 'nombre_completo', NEW.nombre_completo, 'rol_id', NEW.rol_id)
    );
END//

-- Trigger para auditar cambios en usuarios
CREATE TRIGGER audit_usuarios_update
AFTER UPDATE ON usuarios
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (usuario_id, tabla_afectada, registro_id, accion, tipo_cambio, datos_anteriores, datos_nuevos)
    VALUES (
        NEW.updated_by,
        'usuarios',
        NEW.numero_documento,
        'ACTUALIZAR',
        'USUARIO',
        JSON_OBJECT('username', OLD.username, 'nombre_completo', OLD.nombre_completo, 'activo', OLD.activo, 'rol_id', OLD.rol_id),
        JSON_OBJECT('username', NEW.username, 'nombre_completo', NEW.nombre_completo, 'activo', NEW.activo, 'rol_id', NEW.rol_id)
    );
END//

-- Trigger para auditar facturas
CREATE TRIGGER audit_facturas_update
AFTER UPDATE ON facturas
FOR EACH ROW
BEGIN
    DECLARE accion_tipo VARCHAR(20);
    SET accion_tipo = CASE
        WHEN NEW.estado = 'ANULADA' AND OLD.estado != 'ANULADA' THEN 'ANULAR'
        WHEN NEW.estado = 'PAGADA' AND OLD.estado != 'PAGADA' THEN 'FACTURAR'
        ELSE 'ACTUALIZAR'
    END;

    INSERT INTO audit_log (usuario_id, tabla_afectada, registro_id, accion, tipo_cambio, datos_anteriores, datos_nuevos)
    VALUES (
        COALESCE(NEW.anulado_por, NEW.vendedor_id),
        'facturas',
        CAST(NEW.id AS CHAR),
        accion_tipo,
        'FACTURA',
        JSON_OBJECT('numero_factura', OLD.numero_factura, 'estado', OLD.estado, 'total', OLD.total),
        JSON_OBJECT('numero_factura', NEW.numero_factura, 'estado', NEW.estado, 'total', NEW.total)
    );
END//

DELIMITER ;

-- ==================== VISTAS ÚTILES ====================

-- Vista de stock disponible (físico - reservado)
CREATE VIEW v_stock_disponible AS
SELECT
    r.codigo,
    r.nombre,
    r.cantidad_actual as stock_fisico,
    r.cantidad_reservada as stock_reservado,
    (r.cantidad_actual - r.cantidad_reservada) as stock_disponible,
    r.cantidad_minima,
    r.precio_venta,
    c.nombre as categoria
FROM repuestos r
LEFT JOIN categorias_repuestos c ON r.categoria_id = c.id
WHERE r.activo = TRUE
ORDER BY r.codigo ASC;

-- Vista de solicitudes pendientes para almacenista
CREATE VIEW v_solicitudes_pendientes AS
SELECT
    s.id,
    s.numero_solicitud,
    s.estado,
    s.created_at,
    s.fecha_requerida,
    u.nombre_completo as tecnico,
    c.nombre_completo as cliente,
    v.placa,
    COUNT(i.id) as total_items,
    SUM(i.cantidad_solicitada * i.precio_unitario) as valor_total
FROM solicitudes_repuestos s
JOIN usuarios u ON s.tecnico_id = u.numero_documento
JOIN clientes c ON s.cliente_id = c.numero_documento
JOIN vehiculos_clientes v ON s.vehiculo_id = v.placa
LEFT JOIN items_solicitud i ON s.id = i.solicitud_id
WHERE s.estado IN ('PENDIENTE', 'APROBADA')
GROUP BY s.id;

-- Vista de facturas por estado
CREATE VIEW v_facturas_estado AS
SELECT
    f.id,
    f.numero_factura,
    f.estado,
    f.total,
    f.created_at,
    c.nombre_completo as cliente,
    v.placa,
    u.nombre_completo as vendedor
FROM facturas f
JOIN clientes c ON f.cliente_id = c.numero_documento
LEFT JOIN vehiculos_clientes v ON f.vehiculo_cliente_id = v.placa
JOIN usuarios u ON f.vendedor_id = u.numero_documento;

-- Vista de alertas activas con detalles
CREATE VIEW v_alertas_activas AS
SELECT
    a.id,
    a.tipo_alerta,
    a.nivel_prioridad,
    a.mensaje,
    a.estado,
    a.created_at,
    r.codigo as repuesto_codigo,
    r.nombre as repuesto_nombre,
    u.nombre_completo as atendida_por_nombre
FROM alertas_inventario a
LEFT JOIN repuestos r ON a.repuesto_id = r.codigo
LEFT JOIN usuarios u ON a.atendida_por = u.numero_documento
WHERE a.estado IN ('NUEVA', 'EN_PROCESO');
