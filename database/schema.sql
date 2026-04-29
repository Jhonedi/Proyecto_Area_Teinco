-- Base de datos para Sistema de Inventario de Taller Automotriz
-- Charset: UTF-8 para soporte completo de español

CREATE DATABASE IF NOT EXISTS taller_inventario CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
USE taller_inventario;

-- Tabla de roles
CREATE TABLE roles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla de usuarios
CREATE TABLE usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    rol_id INT NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (rol_id) REFERENCES roles(id)
) ENGINE=InnoDB;

-- Tabla de marcas de vehículos
CREATE TABLE marcas_vehiculos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla de modelos de vehículos
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

-- Tabla de categorías de repuestos
CREATE TABLE categorias_repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla de repuestos
CREATE TABLE repuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    categoria_id INT,
    precio_venta DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    cantidad_actual INT NOT NULL DEFAULT 0,
    cantidad_minima INT NOT NULL DEFAULT 5,
    ubicacion_fisica VARCHAR(100),
    marca_fabricante VARCHAR(100),
    observaciones TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (categoria_id) REFERENCES categorias_repuestos(id)
) ENGINE=InnoDB;

-- Tabla de compatibilidad de repuestos con vehículos
CREATE TABLE repuestos_compatibilidad (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id INT NOT NULL,
    modelo_vehiculo_id INT NOT NULL,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id) ON DELETE CASCADE,
    FOREIGN KEY (modelo_vehiculo_id) REFERENCES modelos_vehiculos(id),
    UNIQUE KEY unique_compatibilidad (repuesto_id, modelo_vehiculo_id)
) ENGINE=InnoDB;

-- Tabla de marcas equivalentes de repuestos
CREATE TABLE repuestos_equivalentes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id INT NOT NULL,
    marca_equivalente VARCHAR(100) NOT NULL,
    codigo_equivalente VARCHAR(50),
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Tabla de clientes
CREATE TABLE clientes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tipo_documento ENUM('CC', 'NIT', 'CE', 'PASAPORTE') DEFAULT 'CC',
    numero_documento VARCHAR(20) NOT NULL UNIQUE,
    nombre_completo VARCHAR(200) NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(100),
    direccion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla de vehículos de clientes
CREATE TABLE vehiculos_clientes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    placa VARCHAR(20) NOT NULL UNIQUE,
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
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (modelo_vehiculo_id) REFERENCES modelos_vehiculos(id)
) ENGINE=InnoDB;

-- Tabla de tipos de movimiento de inventario
CREATE TABLE tipos_movimiento (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    tipo ENUM('ENTRADA', 'SALIDA') NOT NULL,
    descripcion TEXT
) ENGINE=InnoDB;

-- Tabla de movimientos de inventario
CREATE TABLE movimientos_inventario (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id INT NOT NULL,
    tipo_movimiento_id INT NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10, 2),
    usuario_id INT NOT NULL,
    tecnico_solicitante_id INT,
    vehiculo_cliente_id INT,
    numero_factura VARCHAR(50),
    estado ENUM('PENDIENTE', 'CONFIRMADO', 'CANCELADO') DEFAULT 'PENDIENTE',
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id),
    FOREIGN KEY (tipo_movimiento_id) REFERENCES tipos_movimiento(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (tecnico_solicitante_id) REFERENCES usuarios(id),
    FOREIGN KEY (vehiculo_cliente_id) REFERENCES vehiculos_clientes(id)
) ENGINE=InnoDB;

-- Tabla de facturas
CREATE TABLE facturas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_factura VARCHAR(50) NOT NULL UNIQUE,
    cliente_id INT NOT NULL,
    vehiculo_cliente_id INT,
    vendedor_id INT NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    impuesto DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    total DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    estado ENUM('PENDIENTE', 'PAGADA', 'ANULADA') DEFAULT 'PENDIENTE',
    metodo_pago ENUM('EFECTIVO', 'TARJETA', 'TRANSFERENCIA', 'CREDITO') DEFAULT 'EFECTIVO',
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (vehiculo_cliente_id) REFERENCES vehiculos_clientes(id),
    FOREIGN KEY (vendedor_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

-- Tabla de detalles de factura
CREATE TABLE detalles_factura (
    id INT PRIMARY KEY AUTO_INCREMENT,
    factura_id INT NOT NULL,
    repuesto_id INT NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    movimiento_inventario_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id),
    FOREIGN KEY (movimiento_inventario_id) REFERENCES movimientos_inventario(id)
) ENGINE=InnoDB;

-- Tabla de alertas de inventario
CREATE TABLE alertas_inventario (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repuesto_id INT NOT NULL,
    tipo_alerta ENUM('STOCK_BAJO', 'AGOTADO', 'PROXIMAMENTE_AGOTADO') NOT NULL,
    nivel_prioridad ENUM('BAJA', 'MEDIA', 'ALTA', 'CRITICA') NOT NULL,
    mensaje TEXT NOT NULL,
    estado ENUM('ACTIVA', 'LEIDA', 'RESUELTA') DEFAULT 'ACTIVA',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(id)
) ENGINE=InnoDB;

-- Tabla de notificaciones a usuarios
CREATE TABLE notificaciones_usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    alerta_id INT NOT NULL,
    leida BOOLEAN DEFAULT FALSE,
    leida_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (alerta_id) REFERENCES alertas_inventario(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Índices para mejorar el rendimiento
CREATE INDEX idx_repuestos_codigo ON repuestos(codigo);
CREATE INDEX idx_repuestos_categoria ON repuestos(categoria_id);
CREATE INDEX idx_repuestos_cantidad ON repuestos(cantidad_actual);
CREATE INDEX idx_movimientos_repuesto ON movimientos_inventario(repuesto_id);
CREATE INDEX idx_movimientos_fecha ON movimientos_inventario(created_at);
CREATE INDEX idx_movimientos_estado ON movimientos_inventario(estado);
CREATE INDEX idx_alertas_estado ON alertas_inventario(estado);
CREATE INDEX idx_alertas_tipo ON alertas_inventario(tipo_alerta);
CREATE INDEX idx_facturas_numero ON facturas(numero_factura);
CREATE INDEX idx_facturas_cliente ON facturas(cliente_id);
CREATE INDEX idx_notificaciones_usuario ON notificaciones_usuarios(usuario_id, leida);

-- Insertar roles predeterminados
INSERT INTO roles (nombre, descripcion) VALUES
('ADMINISTRADOR', 'Control total del sistema'),
('ALMACENISTA', 'Gestión de inventario, entradas y salidas'),
('VENDEDOR', 'Confirmación de ventas y facturación'),
('TECNICO', 'Consulta de información de repuestos (solo lectura)');

-- Insertar tipos de movimiento predeterminados
INSERT INTO tipos_movimiento (nombre, tipo, descripcion) VALUES
('Compra', 'ENTRADA', 'Entrada de repuestos por compra'),
('Ajuste Positivo', 'ENTRADA', 'Ajuste de inventario (aumento)'),
('Devolución Cliente', 'ENTRADA', 'Repuesto devuelto por cliente'),
('Venta', 'SALIDA', 'Salida de repuesto por venta'),
('Uso Interno', 'SALIDA', 'Repuesto usado en taller'),
('Ajuste Negativo', 'SALIDA', 'Ajuste de inventario (disminución)'),
('Garantía', 'SALIDA', 'Salida por garantía');

-- Insertar usuario administrador por defecto
-- Password: admin123 (debe cambiarse en producción)
INSERT INTO usuarios (username, password_hash, nombre_completo, email, rol_id) VALUES
('admin', '$2b$12$Y2AGfKQsLpKfPOHK5ZO/gOYwgznuQbT6gOI3mOQ8EySTMrwm3GP56', 'Administrador del Sistema', 'admin@taller.com', 1);

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
