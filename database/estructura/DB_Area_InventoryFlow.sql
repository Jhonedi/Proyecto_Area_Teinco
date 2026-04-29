-- ============================================================
-- DB_Area_InventoryFlow.sql  –  Solo Estructura
-- Base de datos InventoryFlow — sin datos de demostración
-- Incluye: estructura completa (27 tablas) + catálogo base
--   + 1 Super Usuario (contraseña: super123)
-- Importar: mysql -u root -p < estructura/DB_Area_InventoryFlow.sql
-- ============================================================

-- ============================================================
-- DB_Area_InventoryFlow.sql  –  v2
-- Base de datos de demostración InventoryFlow
-- Generada: 2026-04-02
-- Registros: ~10 000+
--   clientes            : 2 200
--   vehiculos_clientes  : ~4 800
--   solicitudes         :   600
--   items_solicitud     : ~1 500
--   movimientos         :   800
--   facturas            :   300
--   detalles_factura    :  ~700
--   alertas             :   150
-- ============================================================

DROP DATABASE IF EXISTS DB_Area_InventoryFlow;
CREATE DATABASE DB_Area_InventoryFlow
    CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
USE DB_Area_InventoryFlow;

SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';


-- ============================================================
-- SECCIÓN 1 – TABLAS BASE
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Tabla: roles
-- Descripción: Define los roles del sistema y sus permisos globales.
--   Orden jerárquico: 1=SUPER_USUARIO (máximo privilegio) … 5=TECNICO.
--   Los roles marcados como es_protegido no pueden eliminarse.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE roles (
    id                      INT         NOT NULL AUTO_INCREMENT
                            COMMENT 'PK autoincremental del rol',
    nombre                  VARCHAR(50) NOT NULL UNIQUE
                            COMMENT 'Nombre único del rol: SUPER_USUARIO, ADMINISTRADOR, ALMACENISTA, VENDEDOR, TECNICO',
    descripcion             TEXT
                            COMMENT 'Descripción de las responsabilidades del rol',
    es_protegido            BOOLEAN     DEFAULT FALSE
                            COMMENT 'TRUE = rol no puede eliminarse desde la interfaz',
    puede_aprobar_ajustes   BOOLEAN     DEFAULT FALSE
                            COMMENT 'Permite aprobar ajustes de inventario que requieren autorización',
    puede_gestionar_alertas BOOLEAN     DEFAULT FALSE
                            COMMENT 'Permite resolver, archivar y gestionar alertas de inventario',
    puede_ver_audit_log     BOOLEAN     DEFAULT FALSE
                            COMMENT 'Permite visualizar el log completo de auditoría',
    puede_generar_reportes  BOOLEAN     DEFAULT FALSE
                            COMMENT 'Permite generar reportes del sistema (ventas, inventario, etc.)',
    created_at              TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
                            COMMENT 'Fecha de creación del registro',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Roles del sistema con sus permisos globales. Orden jerárquico 1-5';

-- ──────────────────────────────────────────────────────────────
-- Tabla: usuarios
-- Descripción: Empleados del taller con acceso al sistema.
--   PK NATURAL: numero_documento (cédula o NIT).
--   Contraseña almacenada como hash bcrypt (nunca texto plano).
--   ultima_actividad controla el cierre de sesión por inactividad (30 min).
-- ──────────────────────────────────────────────────────────────
CREATE TABLE usuarios (
    numero_documento  VARCHAR(20)  NOT NULL
                      COMMENT 'PK Natural: cédula, NIT o documento de identidad del empleado',
    username          VARCHAR(50)  NOT NULL UNIQUE
                      COMMENT 'Nombre de usuario único para inicio de sesión',
    password_hash     VARCHAR(255) NOT NULL
                      COMMENT 'Hash bcrypt de la contraseña. Nunca se almacena en texto plano',
    nombre_completo   VARCHAR(100) NOT NULL
                      COMMENT 'Nombre y apellidos completos del empleado',
    email             VARCHAR(100) UNIQUE
                      COMMENT 'Correo electrónico institucional del usuario',
    rol_id            INT          NOT NULL
                      COMMENT 'FK al rol asignado. Define los permisos del usuario',
    activo            BOOLEAN      DEFAULT TRUE
                      COMMENT 'FALSE = usuario deshabilitado, no puede iniciar sesión',
    es_protegido      BOOLEAN      DEFAULT FALSE
                      COMMENT 'TRUE = no se puede eliminar ni desactivar desde la interfaz',
    ultima_actividad  TIMESTAMP    NULL
                      COMMENT 'Última acción registrada. Usado para timeout de sesión',
    created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                      COMMENT 'Fecha de creación del registro',
    updated_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                      COMMENT 'Fecha de última modificación',
    created_by        VARCHAR(20)  NULL
                      COMMENT 'Documento del usuario que creó este registro',
    updated_by        VARCHAR(20)  NULL
                      COMMENT 'Documento del usuario que realizó la última modificación',
    PRIMARY KEY (numero_documento),
    FOREIGN KEY (rol_id)      REFERENCES roles(id),
    FOREIGN KEY (created_by)  REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by)  REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    INDEX idx_usu_username (username) COMMENT 'Búsqueda rápida por username en el login'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Usuarios del sistema. PK natural = numero_documento. Autenticación RBAC con bcrypt';

-- ──────────────────────────────────────────────────────────────
-- Tabla: configuracion_sistema
-- Descripción: Parámetros configurables del sistema en clave-valor tipado.
--   Permite modificar comportamientos globales sin tocar el código fuente.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE configuracion_sistema (
    id          INT          NOT NULL AUTO_INCREMENT
                COMMENT 'PK autoincremental',
    clave       VARCHAR(100) NOT NULL UNIQUE
                COMMENT 'Nombre del parámetro. Ej: IVA_PORCENTAJE, SESSION_INACTIVITY_TIMEOUT',
    valor       TEXT
                COMMENT 'Valor del parámetro almacenado como cadena de texto',
    tipo        ENUM('STRING','INTEGER','DECIMAL','BOOLEAN','JSON') DEFAULT 'STRING'
                COMMENT 'Tipo de dato para conversión en la capa de aplicación',
    descripcion TEXT
                COMMENT 'Descripción del parámetro y su efecto en el sistema',
    updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                COMMENT 'Fecha de última modificación del parámetro',
    updated_by  VARCHAR(20)  NULL
                COMMENT 'Documento del usuario que modificó el parámetro',
    PRIMARY KEY (id),
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Parámetros globales configurables en formato clave-valor tipado. Sin tocar código';


-- ============================================================
-- SECCIÓN 2 – TABLAS DE VEHÍCULOS
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Tabla: marcas_vehiculos
-- Descripción: Catálogo de marcas de vehículos reconocidas.
--   15 marcas comunes en el mercado colombiano.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE marcas_vehiculos (
    id         INT         NOT NULL AUTO_INCREMENT
               COMMENT 'PK autoincremental de la marca',
    nombre     VARCHAR(50) NOT NULL UNIQUE
               COMMENT 'Nombre comercial de la marca. Ej: Toyota, Chevrolet, Renault',
    created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
               COMMENT 'Fecha de creación del registro',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Catálogo de 15 marcas de vehículos comunes en Colombia';

-- ──────────────────────────────────────────────────────────────
-- Tabla: modelos_vehiculos
-- Descripción: Modelos por marca con año de inicio y fin de producción.
--   Permite filtrar repuestos compatibles por modelo de vehículo.
--   UNIQUE(marca_id, nombre) evita duplicados.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE modelos_vehiculos (
    id          INT          NOT NULL AUTO_INCREMENT
                COMMENT 'PK autoincremental del modelo',
    marca_id    INT          NOT NULL
                COMMENT 'FK a la marca del vehículo',
    nombre      VARCHAR(100) NOT NULL
                COMMENT 'Nombre del modelo. Ej: Corolla, Spark, Duster, Kicks',
    anio_inicio INT
                COMMENT 'Año de inicio de fabricación del modelo',
    anio_fin    INT
                COMMENT 'Año final de producción. NULL = modelo actualmente vigente',
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                COMMENT 'Fecha de creación del registro',
    PRIMARY KEY (id),
    FOREIGN KEY (marca_id) REFERENCES marcas_vehiculos(id),
    UNIQUE KEY uk_modelo (marca_id, nombre)
                COMMENT 'Un modelo no puede repetirse para la misma marca'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Catálogo de modelos por marca con rango de años. Usado en compatibilidad de repuestos';

-- ──────────────────────────────────────────────────────────────
-- Tabla: clientes
-- Descripción: Clientes del taller automotriz.
--   PK NATURAL: numero_documento (CC, NIT, CE o PASAPORTE).
--   Un cliente puede tener uno o múltiples vehículos registrados.
--   Soft delete con campo activo.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE clientes (
    numero_documento  VARCHAR(20)  NOT NULL
                      COMMENT 'PK Natural: CC=Cédula, NIT=Empresa, CE=Extranjería, PASAPORTE',
    tipo_documento    ENUM('CC','NIT','CE','PASAPORTE') DEFAULT 'CC'
                      COMMENT 'Tipo de documento de identidad del cliente',
    nombre_completo   VARCHAR(200) NOT NULL
                      COMMENT 'Nombre completo de la persona o razón social de la empresa',
    telefono          VARCHAR(20)
                      COMMENT 'Teléfono de contacto en formato colombiano: 300 123 4567',
    email             VARCHAR(100)
                      COMMENT 'Correo electrónico del cliente para comunicaciones',
    direccion         TEXT
                      COMMENT 'Dirección física completa incluyendo ciudad',
    activo            BOOLEAN      DEFAULT TRUE
                      COMMENT 'FALSE = cliente inactivo, no aparece en formularios de nuevas ventas',
    created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                      COMMENT 'Fecha de primer registro del cliente',
    updated_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                      COMMENT 'Fecha de última actualización de sus datos',
    created_by        VARCHAR(20)  NULL
                      COMMENT 'Documento del usuario que registró al cliente',
    updated_by        VARCHAR(20)  NULL
                      COMMENT 'Documento del usuario que realizó la última modificación',
    PRIMARY KEY (numero_documento),
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Clientes del taller. PK natural = numero_documento. Personas y empresas. N vehículos';

-- ──────────────────────────────────────────────────────────────
-- Tabla: vehiculos_clientes
-- Descripción: Vehículos registrados en el taller asociados a un cliente.
--   PK NATURAL: placa del vehículo.
--   Formato colombiano: ABC123 (automóvil) / ABC12D (motocicleta).
--   Un cliente puede tener múltiples vehículos. Referencia cruzada
--   con modelos_vehiculos para filtrar repuestos compatibles.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE vehiculos_clientes (
    placa                 VARCHAR(10)  NOT NULL
                          COMMENT 'PK Natural: placa colombiana. ABC123=auto, ABC12D=moto',
    cliente_id            VARCHAR(20)  NOT NULL
                          COMMENT 'FK: numero_documento del propietario del vehículo',
    modelo_vehiculo_id    INT          NOT NULL
                          COMMENT 'FK: modelo del vehículo para compatibilidad de repuestos',
    anio                  INT
                          COMMENT 'Año modelo del vehículo',
    color                 VARCHAR(50)
                          COMMENT 'Color del vehículo',
    numero_motor          VARCHAR(100)
                          COMMENT 'Número de motor (identificación mecánica única)',
    numero_chasis         VARCHAR(100)
                          COMMENT 'Número de chasis o VIN del vehículo',
    kilometraje_actual    INT
                          COMMENT 'Kilometraje registrado en la última visita al taller',
    observaciones         TEXT
                          COMMENT 'Notas sobre el historial o estado del vehículo',
    activo                BOOLEAN      DEFAULT TRUE
                          COMMENT 'FALSE = vehículo dado de baja, vendido o destruido',
    created_at            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                          COMMENT 'Fecha de primer ingreso del vehículo al taller',
    updated_at            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                          COMMENT 'Fecha de última actualización',
    PRIMARY KEY (placa),
    FOREIGN KEY (cliente_id)         REFERENCES clientes(numero_documento),
    FOREIGN KEY (modelo_vehiculo_id) REFERENCES modelos_vehiculos(id),
    INDEX idx_veh_cliente (cliente_id)
                          COMMENT 'Búsqueda de vehículos por propietario',
    INDEX idx_veh_modelo  (modelo_vehiculo_id)
                          COMMENT 'Filtrado por modelo para compatibilidad de repuestos'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Vehículos de clientes. PK natural = placa. Un cliente puede tener N vehículos';


-- ============================================================
-- SECCIÓN 3 – TABLAS DE INVENTARIO
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Tabla: categorias_repuestos
-- ──────────────────────────────────────────────────────────────
CREATE TABLE categorias_repuestos (
    id          INT          NOT NULL AUTO_INCREMENT
                COMMENT 'PK autoincremental de la categoría',
    nombre      VARCHAR(100) NOT NULL UNIQUE
                COMMENT 'Nombre de la categoría. Ej: Filtros, Frenos, Motor',
    descripcion TEXT
                COMMENT 'Tipos de repuestos que incluye esta categoría',
    activo      BOOLEAN      DEFAULT TRUE
                COMMENT 'FALSE = categoría deshabilitada, no aparece en formularios',
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                COMMENT 'Fecha de creación',
    updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                COMMENT 'Fecha de última modificación',
    created_by  VARCHAR(20)  NULL
                COMMENT 'Documento del usuario que creó la categoría',
    updated_by  VARCHAR(20)  NULL
                COMMENT 'Documento del usuario que realizó la última modificación',
    PRIMARY KEY (id),
    FOREIGN KEY (created_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='15 categorías de clasificación de repuestos. Soft delete con campo activo';

-- ──────────────────────────────────────────────────────────────
-- Tabla: repuestos
-- Descripción: Catálogo principal de repuestos.
--   PK NATURAL: codigo (Ej: FILT-001, MOT-003).
--   cantidad_actual  = stock físico en bodega.
--   cantidad_reservada = bloqueado en solicitudes pendientes/aprobadas.
--   Stock disponible real = cantidad_actual - cantidad_reservada.
--   Alerta ALTA  : cantidad_actual <= cantidad_minima.
--   Alerta CRITICA: cantidad_actual = 0.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE repuestos (
    codigo                VARCHAR(50)   NOT NULL
                          COMMENT 'PK Natural: código único del repuesto. Formato PREFIJO-NNN. Ej: FILT-001',
    nombre                VARCHAR(200)  NOT NULL
                          COMMENT 'Nombre descriptivo del repuesto para búsqueda',
    descripcion           TEXT
                          COMMENT 'Descripción corta y aplicación del repuesto',
    descripcion_detallada TEXT
                          COMMENT 'Descripción extendida para la vista de detalle del catálogo',
    categoria_id          INT
                          COMMENT 'FK a la categoría (Motor, Frenos, Filtros, etc.)',
    precio_venta          DECIMAL(15,2) NOT NULL DEFAULT 0.00
                          COMMENT 'Precio de venta al público en pesos colombianos (COP)',
    cantidad_actual       INT           NOT NULL DEFAULT 0
                          COMMENT 'Stock físico real en bodega. Se modifica al confirmar movimientos',
    cantidad_reservada    INT           NOT NULL DEFAULT 0
                          COMMENT 'Unidades bloqueadas en solicitudes PENDIENTE o APROBADA',
    cantidad_minima       INT           NOT NULL DEFAULT 5
                          COMMENT 'Umbral mínimo de stock. Al llegar aquí se genera alerta ALTA',
    ubicacion_fisica      VARCHAR(100)
                          COMMENT 'Ubicación en bodega/estante. Ej: Estante A-1, Bodega B-2',
    marca_fabricante      VARCHAR(100)
                          COMMENT 'Fabricante del repuesto. Ej: Bosch, NGK, Monroe, Brembo',
    observaciones         TEXT
                          COMMENT 'Notas adicionales sobre el repuesto',
    activo                BOOLEAN       DEFAULT TRUE
                          COMMENT 'FALSE = repuesto descontinuado, no aparece en catálogo activo',
    created_at            TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                          COMMENT 'Fecha de creación en el catálogo',
    updated_at            TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                          COMMENT 'Fecha de última modificación',
    created_by            VARCHAR(20)   NULL
                          COMMENT 'Documento del usuario que creó el repuesto',
    updated_by            VARCHAR(20)   NULL
                          COMMENT 'Documento del usuario que realizó la última modificación',
    PRIMARY KEY (codigo),
    FOREIGN KEY (categoria_id) REFERENCES categorias_repuestos(id),
    FOREIGN KEY (created_by)   REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    FOREIGN KEY (updated_by)   REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    INDEX idx_rep_categoria (categoria_id)  COMMENT 'Filtrado rápido por categoría',
    INDEX idx_rep_cantidad  (cantidad_actual) COMMENT 'Consultas de stock bajo para alertas',
    INDEX idx_rep_nombre    (nombre(50))    COMMENT 'Búsqueda por nombre (LIKE)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Catálogo de repuestos. PK natural = codigo. Controla stock físico y reservado';


-- ============================================================
-- SECCIÓN 4 – TABLAS DE SOLICITUDES Y MOVIMIENTOS
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Tabla: tipos_movimiento
-- ──────────────────────────────────────────────────────────────
CREATE TABLE tipos_movimiento (
    id                  INT         NOT NULL AUTO_INCREMENT
                        COMMENT 'PK autoincremental del tipo',
    nombre              VARCHAR(50) NOT NULL UNIQUE
                        COMMENT 'Nombre del tipo. Ej: Compra, Venta, Ajuste Positivo',
    tipo                ENUM('ENTRADA','SALIDA') NOT NULL
                        COMMENT 'ENTRADA = incrementa stock. SALIDA = decrementa stock',
    descripcion         TEXT
                        COMMENT 'Descripción del caso de uso del tipo de movimiento',
    requiere_aprobacion BOOLEAN     DEFAULT FALSE
                        COMMENT 'TRUE = debe ser aprobado por ADMIN antes de afectar el stock',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Catálogo de tipos de movimiento. Define dirección y si requiere aprobación';

-- ──────────────────────────────────────────────────────────────
-- Tabla: solicitudes_repuestos
-- Descripción: Solicitudes de repuestos creadas por técnicos.
--   Flujo: PENDIENTE → APROBADA → ENTREGADA → FACTURADA.
--   Cada cambio de estado registra el usuario y la fecha.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE solicitudes_repuestos (
    id                INT          NOT NULL AUTO_INCREMENT
                      COMMENT 'PK autoincremental de la solicitud',
    numero_solicitud  VARCHAR(20)  NOT NULL UNIQUE
                      COMMENT 'Número de referencia único. Formato: SOL-YYYYMMDD-XXXX',
    tecnico_id        VARCHAR(20)  NOT NULL
                      COMMENT 'Documento del técnico que creó la solicitud',
    cliente_id        VARCHAR(20)  NOT NULL
                      COMMENT 'Documento del cliente dueño del vehículo en reparación',
    vehiculo_id       VARCHAR(10)  NOT NULL
                      COMMENT 'Placa del vehículo en servicio',
    estado            ENUM('PENDIENTE','APROBADA','RECHAZADA','ENTREGADA','FACTURADA','DEVOLUCION_PARCIAL','ANULADA') DEFAULT 'PENDIENTE'
                      COMMENT 'Estado actual en el flujo de aprobación y entrega',
    observaciones     TEXT
                      COMMENT 'Notas del técnico sobre la reparación o los repuestos requeridos',
    fecha_requerida   DATE         NULL
                      COMMENT 'Fecha en que el técnico necesita los repuestos para la reparación',
    aprobado_por      VARCHAR(20)  NULL
                      COMMENT 'Documento del almacenista que aprobó la solicitud',
    fecha_aprobacion  TIMESTAMP    NULL
                      COMMENT 'Fecha y hora exacta de la aprobación',
    entregado_por     VARCHAR(20)  NULL
                      COMMENT 'Documento del almacenista que entregó los repuestos físicamente',
    fecha_entrega     TIMESTAMP    NULL
                      COMMENT 'Fecha y hora de entrega de repuestos al técnico',
    facturado_por     VARCHAR(20)  NULL
                      COMMENT 'Documento del vendedor que generó la factura de cobro al cliente',
    fecha_facturacion TIMESTAMP    NULL
                      COMMENT 'Fecha y hora de generación de la factura',
    created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                      COMMENT 'Fecha de creación de la solicitud',
    updated_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                      COMMENT 'Fecha de última actualización',
    PRIMARY KEY (id),
    FOREIGN KEY (tecnico_id)    REFERENCES usuarios(numero_documento),
    FOREIGN KEY (cliente_id)    REFERENCES clientes(numero_documento),
    FOREIGN KEY (vehiculo_id)   REFERENCES vehiculos_clientes(placa),
    FOREIGN KEY (aprobado_por)  REFERENCES usuarios(numero_documento),
    FOREIGN KEY (entregado_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (facturado_por) REFERENCES usuarios(numero_documento),
    INDEX idx_sol_estado  (estado)      COMMENT 'Filtrado rápido por estado',
    INDEX idx_sol_tecnico (tecnico_id)  COMMENT 'Solicitudes por técnico',
    INDEX idx_sol_cliente (cliente_id)  COMMENT 'Historial de solicitudes por cliente',
    INDEX idx_sol_fecha   (created_at)  COMMENT 'Reportes por rango de fechas'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Solicitudes de repuestos. Flujo: PENDIENTE→APROBADA→ENTREGADA→FACTURADA';

-- ──────────────────────────────────────────────────────────────
-- Tabla: items_solicitud
-- ──────────────────────────────────────────────────────────────
CREATE TABLE items_solicitud (
    id                   INT           NOT NULL AUTO_INCREMENT
                         COMMENT 'PK autoincremental del ítem',
    solicitud_id         INT           NOT NULL
                         COMMENT 'FK a la solicitud padre. ON DELETE CASCADE',
    repuesto_id          VARCHAR(50)   NOT NULL
                         COMMENT 'FK al código del repuesto solicitado',
    cantidad_solicitada  INT           NOT NULL
                         COMMENT 'Unidades pedidas por el técnico',
    cantidad_aprobada    INT           DEFAULT 0
                         COMMENT 'Unidades aprobadas por el almacenista (puede ser < solicitada)',
    cantidad_entregada   INT           DEFAULT 0
                         COMMENT 'Unidades entregadas físicamente al técnico',
    cantidad_devuelta    INT           DEFAULT 0
                         COMMENT 'Unidades devueltas antes de la facturación',
    precio_unitario      DECIMAL(15,2) NOT NULL
                         COMMENT 'Precio histórico al momento de la solicitud. No varía con cambios del catálogo',
    estado               ENUM('RESERVADO','APROBADO','RECHAZADO','ENTREGADO','FACTURADO','DEVUELTO') DEFAULT 'RESERVADO'
                         COMMENT 'Estado del ítem individual dentro del flujo de solicitud',
    observaciones        TEXT
                         COMMENT 'Notas sobre el ítem (razón de rechazo o entrega parcial)',
    created_at           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                         COMMENT 'Fecha de creación del ítem',
    updated_at           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                         COMMENT 'Fecha de última actualización',
    PRIMARY KEY (id),
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes_repuestos(id) ON DELETE CASCADE,
    FOREIGN KEY (repuesto_id)  REFERENCES repuestos(codigo),
    INDEX idx_item_sol (solicitud_id) COMMENT 'Ítems por solicitud padre',
    INDEX idx_item_rep (repuesto_id)  COMMENT 'Solicitudes que contienen un repuesto específico'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Ítems de solicitudes. Precio histórico. Cantidades: solicitada ≥ aprobada ≥ entregada';

-- ──────────────────────────────────────────────────────────────
-- Tabla: movimientos_inventario
-- Descripción: Registro de todas las entradas y salidas de stock.
--   Cantidad siempre positiva; tipo_movimiento determina si suma o resta.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE movimientos_inventario (
    id                     INT           NOT NULL AUTO_INCREMENT
                           COMMENT 'PK autoincremental del movimiento',
    repuesto_id            VARCHAR(50)   NOT NULL
                           COMMENT 'FK: código del repuesto afectado',
    tipo_movimiento_id     INT           NOT NULL
                           COMMENT 'FK: tipo de movimiento (Compra, Venta, Ajuste, etc.)',
    cantidad               INT           NOT NULL
                           COMMENT 'Unidades del movimiento. Siempre positivo. El tipo define si suma o resta',
    precio_unitario        DECIMAL(15,2)
                           COMMENT 'Precio histórico unitario al momento del movimiento',
    usuario_id             VARCHAR(20)   NOT NULL
                           COMMENT 'Documento del usuario que registró el movimiento',
    tecnico_solicitante_id VARCHAR(20)   NULL
                           COMMENT 'Documento del técnico que originó la salida (si aplica)',
    vehiculo_cliente_id    VARCHAR(10)   NULL
                           COMMENT 'Placa del vehículo asociado al movimiento (si aplica)',
    solicitud_id           INT           NULL
                           COMMENT 'FK a la solicitud que originó este movimiento',
    estado                 ENUM('PENDIENTE','RESERVADO','APROBADO','ENTREGADO','FACTURADO','DEVUELTO','RECHAZADO','ANULADO') DEFAULT 'PENDIENTE'
                           COMMENT 'Estado del movimiento en su ciclo de vida',
    aprobado_por           VARCHAR(20)   NULL
                           COMMENT 'Documento del usuario que aprobó el movimiento (ajustes)',
    fecha_aprobacion       TIMESTAMP     NULL
                           COMMENT 'Fecha y hora de aprobación',
    motivo_rechazo         TEXT          NULL
                           COMMENT 'Razón del rechazo si el movimiento fue rechazado',
    observaciones          TEXT
                           COMMENT 'Notas adicionales sobre el movimiento',
    created_at             TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                           COMMENT 'Fecha de registro del movimiento',
    updated_at             TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                           COMMENT 'Fecha de última actualización',
    PRIMARY KEY (id),
    FOREIGN KEY (repuesto_id)            REFERENCES repuestos(codigo),
    FOREIGN KEY (tipo_movimiento_id)     REFERENCES tipos_movimiento(id),
    FOREIGN KEY (usuario_id)             REFERENCES usuarios(numero_documento),
    FOREIGN KEY (tecnico_solicitante_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (vehiculo_cliente_id)    REFERENCES vehiculos_clientes(placa),
    FOREIGN KEY (solicitud_id)           REFERENCES solicitudes_repuestos(id),
    FOREIGN KEY (aprobado_por)           REFERENCES usuarios(numero_documento),
    INDEX idx_mov_estado (estado)     COMMENT 'Filtrado por estado del movimiento',
    INDEX idx_mov_fecha  (created_at) COMMENT 'Reportes por rango de fechas'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Registro completo de entradas/salidas. Trazabilidad de usuario, vehículo y solicitud';


-- ============================================================
-- SECCIÓN 5 – TABLAS DE FACTURACIÓN
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Tabla: facturas
-- Descripción: Facturas emitidas a los clientes.
--   IVA Colombia = 19%. Soporta crédito y pagos mixtos.
--   numero_factura: FAC-YYYYMMDD-XXXX.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE facturas (
    id                  INT           NOT NULL AUTO_INCREMENT
                        COMMENT 'PK autoincremental de la factura',
    numero_factura      VARCHAR(50)   NOT NULL UNIQUE
                        COMMENT 'Número único de factura. Formato: FAC-YYYYMMDD-XXXX',
    cliente_id          VARCHAR(20)   NOT NULL
                        COMMENT 'FK: documento del cliente facturado',
    vehiculo_cliente_id VARCHAR(10)   NULL
                        COMMENT 'FK: placa del vehículo asociado a la factura',
    solicitud_id        INT           NULL
                        COMMENT 'FK: solicitud de origen de la factura (si aplica)',
    vendedor_id         VARCHAR(20)   NOT NULL
                        COMMENT 'Documento del vendedor que emitió la factura',
    subtotal            DECIMAL(15,2) NOT NULL DEFAULT 0.00
                        COMMENT 'Subtotal antes de impuestos y descuentos en COP',
    impuesto            DECIMAL(15,2) NOT NULL DEFAULT 0.00
                        COMMENT 'IVA 19% en COP',
    descuento           DECIMAL(15,2) NOT NULL DEFAULT 0.00
                        COMMENT 'Descuento total aplicado en COP',
    total               DECIMAL(15,2) NOT NULL DEFAULT 0.00
                        COMMENT 'Total = subtotal + impuesto - descuento',
    estado              ENUM('EN_ESPERA','PENDIENTE','PAGADA','ANULADA') DEFAULT 'EN_ESPERA'
                        COMMENT 'Estado de pago: EN_ESPERA=inicial, PENDIENTE=parcial, PAGADA=completa, ANULADA',
    metodo_pago         ENUM('EFECTIVO','TARJETA','TRANSFERENCIA','CREDITO','MIXTO') DEFAULT 'EFECTIVO'
                        COMMENT 'Método de pago de la factura',
    fecha_vencimiento   DATE          NULL
                        COMMENT 'Fecha límite de pago para facturas a CREDITO (30 días por defecto)',
    observaciones       TEXT
                        COMMENT 'Notas adicionales de la factura',
    anulado_por         VARCHAR(20)   NULL
                        COMMENT 'Documento del usuario que anuló la factura',
    fecha_anulacion     TIMESTAMP     NULL
                        COMMENT 'Fecha y hora de anulación',
    motivo_anulacion    TEXT          NULL
                        COMMENT 'Razón de la anulación',
    created_at          TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                        COMMENT 'Fecha de emisión de la factura',
    updated_at          TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        COMMENT 'Fecha de última actualización',
    PRIMARY KEY (id),
    FOREIGN KEY (cliente_id)          REFERENCES clientes(numero_documento),
    FOREIGN KEY (vehiculo_cliente_id) REFERENCES vehiculos_clientes(placa),
    FOREIGN KEY (solicitud_id)        REFERENCES solicitudes_repuestos(id),
    FOREIGN KEY (vendedor_id)         REFERENCES usuarios(numero_documento),
    FOREIGN KEY (anulado_por)         REFERENCES usuarios(numero_documento),
    INDEX idx_fac_estado  (estado)      COMMENT 'Filtrado por estado de pago',
    INDEX idx_fac_cliente (cliente_id)  COMMENT 'Historial de facturas por cliente',
    INDEX idx_fac_fecha   (created_at)  COMMENT 'Reportes de ventas por fecha'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Facturas emitidas. IVA 19%. Soporta crédito, pagos mixtos y anulación con trazabilidad';

-- ──────────────────────────────────────────────────────────────
-- Tabla: detalles_factura
-- ──────────────────────────────────────────────────────────────
CREATE TABLE detalles_factura (
    id                      INT           NOT NULL AUTO_INCREMENT
                            COMMENT 'PK autoincremental del detalle',
    factura_id              INT           NOT NULL
                            COMMENT 'FK a la factura padre. ON DELETE CASCADE',
    repuesto_id             VARCHAR(50)   NOT NULL
                            COMMENT 'FK: código del repuesto facturado',
    item_solicitud_id       INT           NULL
                            COMMENT 'FK al ítem de solicitud de origen (si aplica)',
    cantidad                INT           NOT NULL
                            COMMENT 'Unidades facturadas del repuesto',
    precio_unitario         DECIMAL(15,2) NOT NULL
                            COMMENT 'Precio histórico unitario al momento de la facturación',
    descuento               DECIMAL(15,2) DEFAULT 0.00
                            COMMENT 'Descuento aplicado a este ítem en COP',
    subtotal                DECIMAL(15,2) NOT NULL
                            COMMENT 'Subtotal del ítem: (precio × cantidad) − descuento',
    movimiento_inventario_id INT          NULL
                            COMMENT 'FK al movimiento de inventario generado por esta línea',
    created_at              TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                            COMMENT 'Fecha de creación del detalle',
    PRIMARY KEY (id),
    FOREIGN KEY (factura_id)               REFERENCES facturas(id)              ON DELETE CASCADE,
    FOREIGN KEY (repuesto_id)              REFERENCES repuestos(codigo),
    FOREIGN KEY (item_solicitud_id)        REFERENCES items_solicitud(id),
    FOREIGN KEY (movimiento_inventario_id) REFERENCES movimientos_inventario(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Líneas de detalle de facturas. Precio histórico garantiza consistencia en auditorías';


-- ============================================================
-- SECCIÓN 6 – TABLAS DE ALERTAS Y AUDITORÍA
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Tabla: alertas_inventario
-- Descripción: Alertas automáticas del sistema.
--   Flujo: NUEVA → EN_PROCESO → RESUELTA → ARCHIVADA.
--   Recordatorios diarios si no se resuelve en 24h.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE alertas_inventario (
    id                  INT       NOT NULL AUTO_INCREMENT
                        COMMENT 'PK autoincremental de la alerta',
    repuesto_id         VARCHAR(50) NULL
                        COMMENT 'FK: código del repuesto afectado. NULL para alertas del sistema',
    tipo_alerta         ENUM('STOCK_BAJO','AGOTADO','PROXIMAMENTE_AGOTADO','SOLICITUD_PENDIENTE','FACTURA_PENDIENTE','AJUSTE_PENDIENTE','SISTEMA') NOT NULL
                        COMMENT 'Categoría de la alerta generada automáticamente',
    nivel_prioridad     ENUM('BAJA','MEDIA','ALTA','CRITICA') NOT NULL
                        COMMENT 'ALTA = stock ≤ mínimo. CRITICA = stock = 0',
    mensaje             TEXT      NOT NULL
                        COMMENT 'Texto descriptivo para mostrar al usuario en el dashboard',
    datos_adicionales   JSON      NULL
                        COMMENT 'Datos extra en JSON: {stock_actual, stock_minimo, etc.}',
    estado              ENUM('NUEVA','EN_PROCESO','RESUELTA','ARCHIVADA') DEFAULT 'NUEVA'
                        COMMENT 'Estado: NUEVA=sin atender, EN_PROCESO=en gestión, RESUELTA, ARCHIVADA',
    atendida_por        VARCHAR(20) NULL
                        COMMENT 'Documento del usuario gestionando la alerta (estado EN_PROCESO)',
    fecha_atencion      TIMESTAMP NULL
                        COMMENT 'Fecha en que se comenzó a atender la alerta',
    resuelta_por        VARCHAR(20) NULL
                        COMMENT 'Documento del usuario que marcó la alerta como resuelta',
    fecha_resolucion    TIMESTAMP NULL
                        COMMENT 'Fecha de resolución de la alerta',
    archivada_por       VARCHAR(20) NULL
                        COMMENT 'Documento del usuario que archivó la alerta',
    fecha_archivado     TIMESTAMP NULL
                        COMMENT 'Fecha de archivado',
    ultimo_recordatorio TIMESTAMP NULL
                        COMMENT 'Fecha del último recordatorio enviado. Controla envío diario',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        COMMENT 'Fecha de generación de la alerta',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        COMMENT 'Fecha de última actualización',
    PRIMARY KEY (id),
    FOREIGN KEY (repuesto_id)  REFERENCES repuestos(codigo),
    FOREIGN KEY (atendida_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (resuelta_por) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (archivada_por)REFERENCES usuarios(numero_documento),
    INDEX idx_ale_estado    (estado)          COMMENT 'Filtrado de alertas activas',
    INDEX idx_ale_tipo      (tipo_alerta)     COMMENT 'Consultas por tipo de alerta',
    INDEX idx_ale_prioridad (nivel_prioridad) COMMENT 'Ordenamiento por prioridad'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Alertas automáticas. Flujo: NUEVA→EN_PROCESO→RESUELTA→ARCHIVADA. Recordatorio 24h';

-- ──────────────────────────────────────────────────────────────
-- Tabla: audit_log
-- Descripción: Log de auditoría completo del sistema.
--   BIGINT pk para soportar millones de registros a largo plazo.
--   Datos antes/después en JSON para trazabilidad total.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE audit_log (
    id                 BIGINT      NOT NULL AUTO_INCREMENT
                       COMMENT 'PK BIGINT para soporte de volumen alto de registros',
    usuario_id         VARCHAR(20) NULL
                       COMMENT 'Documento del usuario que realizó la acción. NULL = sistema',
    tabla_afectada     VARCHAR(100) NOT NULL
                       COMMENT 'Nombre de la tabla modificada. Ej: repuestos, facturas',
    registro_id        VARCHAR(100) NOT NULL
                       COMMENT 'PK del registro afectado (string o número)',
    accion             ENUM('CREAR','ACTUALIZAR','ELIMINAR','APROBAR','RECHAZAR','FACTURAR','ANULAR','AJUSTE','LOGIN','LOGOUT') NOT NULL
                       COMMENT 'Tipo de acción realizada',
    tipo_cambio        ENUM('INVENTARIO','USUARIO','CLIENTE','VEHICULO','FACTURA','SOLICITUD','ALERTA','CONFIGURACION','SESION','OTRO') NOT NULL
                       COMMENT 'Categoría del cambio para filtros en reportes de auditoría',
    datos_anteriores   JSON NULL
                       COMMENT 'Estado completo del registro antes del cambio en JSON',
    datos_nuevos       JSON NULL
                       COMMENT 'Estado completo del registro después del cambio en JSON',
    campos_modificados JSON NULL
                       COMMENT 'Lista de campos que cambiaron. Ej: ["precio_venta","cantidad_minima"]',
    ip_address         VARCHAR(45)  NULL
                       COMMENT 'Dirección IP del cliente. Soporta IPv6 (45 chars)',
    user_agent         TEXT         NULL
                       COMMENT 'User-Agent del navegador para identificación del dispositivo',
    created_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                       COMMENT 'Fecha y hora exacta de la acción auditada',
    PRIMARY KEY (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento) ON DELETE SET NULL,
    INDEX idx_aud_usuario (usuario_id)               COMMENT 'Historial de acciones por usuario',
    INDEX idx_aud_tabla   (tabla_afectada, registro_id(20)) COMMENT 'Historial de un registro',
    INDEX idx_aud_accion  (accion)                   COMMENT 'Filtrado por tipo de acción',
    INDEX idx_aud_tipo    (tipo_cambio)              COMMENT 'Filtrado por categoría',
    INDEX idx_aud_fecha   (created_at)               COMMENT 'Reportes por rango de fechas'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Log de auditoría. BIGINT pk. JSON antes/después. Trazabilidad total del sistema';


-- ============================================================
-- SECCION COMPLEMENTARIA – TABLAS ADICIONALES DE LA APLICACION
-- ============================================================

-- Imagenes de repuestos
CREATE TABLE IF NOT EXISTS imagenes_repuestos (
    id              INT          NOT NULL AUTO_INCREMENT
                    COMMENT 'PK autoincremental',
    repuesto_id     VARCHAR(50)  NOT NULL
                    COMMENT 'FK al repuesto',
    nombre_archivo  VARCHAR(255) NOT NULL,
    ruta_archivo    VARCHAR(500) NOT NULL,
    es_principal    BOOLEAN      DEFAULT FALSE,
    orden           INT          DEFAULT 0,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    created_by      VARCHAR(20)  NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo) ON DELETE CASCADE,
    FOREIGN KEY (created_by)  REFERENCES usuarios(numero_documento) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Imagenes de repuestos. Multiples fotos por repuesto';

-- Compatibilidad repuesto-modelo de vehiculo
CREATE TABLE IF NOT EXISTS repuestos_compatibilidad (
    id                  INT         NOT NULL AUTO_INCREMENT,
    repuesto_id         VARCHAR(50) NOT NULL,
    modelo_vehiculo_id  INT         NOT NULL,
    observaciones       TEXT,
    created_at          TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY unique_compatibilidad (repuesto_id, modelo_vehiculo_id),
    FOREIGN KEY (repuesto_id)        REFERENCES repuestos(codigo) ON DELETE CASCADE,
    FOREIGN KEY (modelo_vehiculo_id) REFERENCES modelos_vehiculos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- Repuestos equivalentes/alternativos
CREATE TABLE IF NOT EXISTS repuestos_equivalentes (
    id                  INT          NOT NULL AUTO_INCREMENT,
    repuesto_id         VARCHAR(50)  NOT NULL,
    marca_equivalente   VARCHAR(100) NOT NULL,
    codigo_equivalente  VARCHAR(50),
    observaciones       TEXT,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (repuesto_id) REFERENCES repuestos(codigo) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- Historial de ajustes de inventario (con aprobacion)
CREATE TABLE IF NOT EXISTS historial_ajustes_inventario (
    id                INT         NOT NULL AUTO_INCREMENT,
    repuesto_id       VARCHAR(50) NOT NULL,
    cantidad_anterior INT         NOT NULL,
    cantidad_nueva    INT         NOT NULL,
    diferencia        INT         NOT NULL,
    usuario_id        VARCHAR(20) NOT NULL,
    motivo            TEXT,
    estado            ENUM('PENDIENTE','APROBADO','RECHAZADO') DEFAULT 'PENDIENTE',
    aprobado_por      VARCHAR(20) NULL,
    fecha_aprobacion  TIMESTAMP   NULL,
    motivo_rechazo    TEXT        NULL,
    created_at        TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_haj_estado   (estado),
    INDEX idx_haj_repuesto (repuesto_id),
    FOREIGN KEY (repuesto_id)  REFERENCES repuestos(codigo),
    FOREIGN KEY (usuario_id)   REFERENCES usuarios(numero_documento),
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(numero_documento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Ajustes de inventario con flujo de aprobacion';

-- Historial de cambios de estado de alertas
CREATE TABLE IF NOT EXISTS historial_alertas (
    id              INT          NOT NULL AUTO_INCREMENT,
    alerta_id       INT          NOT NULL,
    estado_anterior ENUM('NUEVA','EN_PROCESO','RESUELTA','ARCHIVADA') NULL,
    estado_nuevo    ENUM('NUEVA','EN_PROCESO','RESUELTA','ARCHIVADA') NOT NULL,
    accion          VARCHAR(100) NOT NULL,
    usuario_id      VARCHAR(20)  NOT NULL,
    observaciones   TEXT,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (alerta_id)  REFERENCES alertas_inventario(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- Notificaciones personales por usuario (marca leida/no leida)
CREATE TABLE IF NOT EXISTS notificaciones_usuarios (
    id                          INT         NOT NULL AUTO_INCREMENT,
    usuario_id                  VARCHAR(20) NOT NULL,
    alerta_id                   INT         NOT NULL,
    leida                       BOOLEAN     DEFAULT FALSE,
    leida_at                    TIMESTAMP   NULL,
    ultimo_recordatorio_enviado DATE        NULL,
    created_at                  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY unique_usuario_alerta (usuario_id, alerta_id),
    INDEX idx_not_usuario (usuario_id, leida),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (alerta_id)  REFERENCES alertas_inventario(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Notificaciones individuales. Controla estado leida/no leida por usuario';

-- Mensajes internos entre usuarios
CREATE TABLE IF NOT EXISTS mensajes_internos (
    id               INT          NOT NULL AUTO_INCREMENT,
    remitente_id     VARCHAR(20)  NOT NULL,
    destinatario_id  VARCHAR(20)  NOT NULL,
    asunto           VARCHAR(200) NOT NULL,
    mensaje          TEXT         NOT NULL,
    alerta_id        INT          NULL,
    solicitud_id     INT          NULL,
    factura_id       INT          NULL,
    leido            BOOLEAN      DEFAULT FALSE,
    leido_at         TIMESTAMP    NULL,
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_men_destinatario (destinatario_id, leido),
    INDEX idx_men_remitente    (remitente_id),
    FOREIGN KEY (remitente_id)    REFERENCES usuarios(numero_documento),
    FOREIGN KEY (destinatario_id) REFERENCES usuarios(numero_documento),
    FOREIGN KEY (alerta_id)       REFERENCES alertas_inventario(id)    ON DELETE SET NULL,
    FOREIGN KEY (solicitud_id)    REFERENCES solicitudes_repuestos(id) ON DELETE SET NULL,
    FOREIGN KEY (factura_id)      REFERENCES facturas(id)              ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- Pagos de facturas (parciales o metodos mixtos)
CREATE TABLE IF NOT EXISTS pagos_factura (
    id            INT           NOT NULL AUTO_INCREMENT,
    factura_id    INT           NOT NULL,
    monto         DECIMAL(15,2) NOT NULL,
    metodo_pago   ENUM('EFECTIVO','TARJETA','TRANSFERENCIA') NOT NULL,
    referencia    VARCHAR(100)  NULL,
    observaciones TEXT,
    recibido_por  VARCHAR(20)   NOT NULL,
    created_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (factura_id)   REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (recibido_por) REFERENCES usuarios(numero_documento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- Codigos de descuento
CREATE TABLE IF NOT EXISTS codigos_descuento (
    codigo        VARCHAR(20)   NOT NULL,
    descripcion   VARCHAR(200)  NOT NULL,
    tipo          ENUM('PORCENTAJE','FIJO') NOT NULL DEFAULT 'PORCENTAJE',
    valor         DECIMAL(10,2) NOT NULL,
    activo        BOOLEAN       DEFAULT TRUE,
    created_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
  COMMENT='Codigos de descuento para facturacion (porcentaje o valor fijo)';

-- Reportes generados
CREATE TABLE IF NOT EXISTS reportes_generados (
    id             INT          NOT NULL AUTO_INCREMENT,
    tipo_reporte   ENUM('INVENTARIO','VENTAS','MOVIMIENTOS','ALERTAS','USUARIOS','CLIENTES','GENERAL') NOT NULL,
    nombre         VARCHAR(200) NOT NULL,
    descripcion    TEXT,
    periodo_inicio DATE         NOT NULL,
    periodo_fin    DATE         NOT NULL,
    parametros     JSON         NULL,
    datos          JSON         NULL,
    ruta_archivo   VARCHAR(500) NULL,
    generado_por   VARCHAR(20)  NOT NULL,
    created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_rep_tipo  (tipo_reporte),
    INDEX idx_rep_fecha (created_at),
    FOREIGN KEY (generado_por) REFERENCES usuarios(numero_documento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- DATOS DE CATÁLOGO BASE (requeridos para el funcionamiento)
-- ============================================================

INSERT INTO roles (id,nombre,descripcion,es_protegido,puede_aprobar_ajustes,puede_gestionar_alertas,puede_ver_audit_log,puede_generar_reportes) VALUES
(1,'SUPER_USUARIO','Control total del sistema. No puede eliminarse.',TRUE,TRUE,TRUE,TRUE,TRUE),
(2,'ADMINISTRADOR','Control total excepto funciones exclusivas de Super Usuario.',FALSE,TRUE,TRUE,TRUE,TRUE),
(3,'ALMACENISTA','Gestión de inventario, entradas, salidas y aprobación de solicitudes.',FALSE,FALSE,TRUE,FALSE,TRUE),
(4,'VENDEDOR','Confirmación de ventas y facturación al cliente.',FALSE,FALSE,FALSE,FALSE,TRUE),
(5,'TECNICO','Creación de solicitudes. No modifica inventario directamente.',FALSE,FALSE,FALSE,FALSE,FALSE);

INSERT INTO tipos_movimiento (id,nombre,tipo,descripcion,requiere_aprobacion) VALUES
(1,'Compra','ENTRADA','Movimiento entrada: Compra',0),
(2,'Ajuste Positivo','ENTRADA','Movimiento entrada: Ajuste Positivo',1),
(3,'Devolución Cliente','ENTRADA','Movimiento entrada: Devolución Cliente',0),
(4,'Devolución Técnico','ENTRADA','Movimiento entrada: Devolución Técnico',0),
(5,'Venta','SALIDA','Movimiento salida: Venta',0),
(6,'Solicitud Técnico','SALIDA','Movimiento salida: Solicitud Técnico',0),
(7,'Uso Interno','SALIDA','Movimiento salida: Uso Interno',0),
(8,'Ajuste Negativo','SALIDA','Movimiento salida: Ajuste Negativo',1),
(9,'Garantía','SALIDA','Movimiento salida: Garantía',0);

INSERT INTO usuarios (numero_documento,username,password_hash,nombre_completo,email,rol_id,es_protegido) VALUES
('0000000001','superusuario','$2b$12$CbCcIoCBWjKOLJ6cAIvG7.z2uaC6yDAHQCToTYNbKdigtWTwszTay','Super Usuario del Sistema','super@inventoryflow.com',1,1);

INSERT INTO configuracion_sistema (clave,valor,tipo,descripcion) VALUES
('SESSION_INACTIVITY_TIMEOUT','30','INTEGER','Minutos de inactividad antes de cerrar sesión'),
('IVA_PORCENTAJE','19.00','DECIMAL','IVA colombiano aplicado en facturas'),
('PREFIJO_SOLICITUD','SOL','STRING','Prefijo números de solicitud: SOL-YYYYMMDD-XXXX'),
('PREFIJO_FACTURA','FAC','STRING','Prefijo números de factura: FAC-YYYYMMDD-XXXX'),
('RECORDATORIO_ALERTA_HORAS','24','INTEGER','Horas entre recordatorios de alertas no resueltas'),
('DIAS_VENCIMIENTO_CREDITO','30','INTEGER','Días por defecto para vencimiento de crédito'),
('EMPRESA_NOMBRE','InventoryFlow Demo','STRING','Nombre de la empresa'),
('EMPRESA_NIT','900000000-0','STRING','NIT de la empresa'),
('EMPRESA_CIUDAD','Bogotá','STRING','Ciudad de operación'),
('IVA_PORCENTAJE_DISPLAY','19%','STRING','IVA en formato de visualización');

INSERT INTO marcas_vehiculos (id,nombre) VALUES
(1,'Chevrolet'),
(2,'Ford'),
(3,'Nissan'),
(4,'Toyota'),
(5,'Mazda'),
(6,'Honda'),
(7,'Hyundai'),
(8,'Kia'),
(9,'Volkswagen'),
(10,'Renault'),
(11,'Mitsubishi'),
(12,'Suzuki'),
(13,'Jeep'),
(14,'BMW'),
(15,'Mercedes-Benz');

INSERT INTO modelos_vehiculos (id,marca_id,nombre,anio_inicio,anio_fin) VALUES
(1,1,'Spark',2010,NULL),
(2,1,'Aveo',2010,NULL),
(3,1,'Cruze',2011,NULL),
(4,1,'Sail',2013,NULL),
(5,1,'Captiva',2010,NULL),
(6,1,'Tracker',2017,NULL),
(7,1,'Onix',2020,NULL),
(8,1,'Cobalt',2012,NULL),
(9,2,'Fiesta',2010,NULL),
(10,2,'Focus',2010,NULL),
(11,2,'Fusion',2010,NULL),
(12,2,'Escape',2010,NULL),
(13,2,'Explorer',2010,NULL),
(14,2,'EcoSport',2013,NULL),
(15,2,'Ranger',2012,NULL),
(16,3,'Sentra',2010,NULL),
(17,3,'Versa',2010,NULL),
(18,3,'March',2010,NULL),
(19,3,'Kicks',2017,NULL),
(20,3,'X-Trail',2010,NULL),
(21,3,'Frontier',2010,NULL),
(22,3,'Murano',2010,NULL),
(23,4,'Corolla',2010,NULL),
(24,4,'Yaris',2010,NULL),
(25,4,'Hilux',2010,NULL),
(26,4,'Prado',2010,NULL),
(27,4,'RAV4',2010,NULL),
(28,4,'Fortuner',2012,NULL),
(29,4,'Camry',2010,NULL),
(30,4,'Avanza',2012,NULL),
(31,5,'Mazda 2',2010,NULL),
(32,5,'Mazda 3',2010,NULL),
(33,5,'Mazda 6',2010,NULL),
(34,5,'CX-3',2015,NULL),
(35,5,'CX-5',2012,NULL),
(36,5,'CX-9',2016,NULL),
(37,5,'BT-50',2011,NULL),
(38,6,'Civic',2010,NULL),
(39,6,'Accord',2010,NULL),
(40,6,'CR-V',2010,NULL),
(41,6,'City',2010,NULL),
(42,6,'HR-V',2015,NULL),
(43,6,'Pilot',2010,NULL),
(44,6,'Jazz',2010,NULL),
(45,7,'Tucson',2010,NULL),
(46,7,'Santa Fe',2010,NULL),
(47,7,'Elantra',2010,NULL),
(48,7,'Accent',2010,NULL),
(49,7,'Creta',2017,NULL),
(50,7,'Venue',2020,NULL),
(51,7,'Ioniq',2017,NULL),
(52,8,'Sportage',2010,NULL),
(53,8,'Sorento',2010,NULL),
(54,8,'Rio',2010,NULL),
(55,8,'Picanto',2010,NULL),
(56,8,'Stonic',2018,NULL),
(57,8,'Seltos',2020,NULL),
(58,8,'Carnival',2010,NULL),
(59,9,'Golf',2010,NULL),
(60,9,'Jetta',2010,NULL),
(61,9,'Passat',2010,NULL),
(62,9,'Tiguan',2010,NULL),
(63,9,'Polo',2010,NULL),
(64,9,'T-Cross',2019,NULL),
(65,9,'Touareg',2010,NULL),
(66,10,'Logan',2010,NULL),
(67,10,'Sandero',2010,NULL),
(68,10,'Duster',2010,NULL),
(69,10,'Stepway',2013,NULL),
(70,10,'Kwid',2017,NULL),
(71,10,'Captur',2016,NULL),
(72,10,'Koleos',2010,NULL),
(73,11,'Outlander',2010,NULL),
(74,11,'Eclipse Cross',2018,NULL),
(75,11,'Lancer',2010,NULL),
(76,11,'Montero',2010,NULL),
(77,11,'L200',2010,NULL),
(78,12,'Swift',2010,NULL),
(79,12,'Vitara',2010,NULL),
(80,12,'S-Cross',2014,NULL);

INSERT INTO modelos_vehiculos (id,marca_id,nombre,anio_inicio,anio_fin) VALUES
(81,12,'Jimny',2018,NULL),
(82,12,'Ciaz',2015,NULL),
(83,12,'Grand Vitara',2010,NULL),
(84,13,'Grand Cherokee',2010,NULL),
(85,13,'Compass',2010,NULL),
(86,13,'Renegade',2014,NULL),
(87,13,'Cherokee',2010,NULL),
(88,13,'Wrangler',2010,NULL),
(89,14,'Serie 3',2010,NULL),
(90,14,'Serie 5',2010,NULL),
(91,14,'X1',2010,NULL),
(92,14,'X3',2010,NULL),
(93,14,'X5',2010,NULL),
(94,14,'Serie 1',2010,NULL),
(95,15,'Clase C',2010,NULL),
(96,15,'Clase E',2010,NULL),
(97,15,'GLA',2014,NULL),
(98,15,'GLC',2015,NULL),
(99,15,'Clase A',2012,NULL),
(100,15,'Clase B',2012,NULL);

INSERT INTO categorias_repuestos (id,nombre,descripcion) VALUES
(1,'Motor','Repuestos para el motor del vehículo'),
(2,'Transmisión','Repuestos de caja de cambios y transmisión'),
(3,'Suspensión','Repuestos del sistema de suspensión'),
(4,'Frenos','Repuestos del sistema de frenos'),
(5,'Eléctrico','Repuestos eléctricos y electrónicos'),
(6,'Filtros','Filtros de aire, aceite, combustible y cabina'),
(7,'Lubricantes','Aceites y lubricantes'),
(8,'Carrocería','Repuestos de carrocería y estructura'),
(9,'Iluminación','Luces y sistema de iluminación'),
(10,'Neumáticos','Llantas y neumáticos'),
(11,'Refrigeración','Sistema de refrigeración del motor'),
(12,'Escape','Sistema de escape'),
(13,'Dirección','Sistema de dirección'),
(14,'Combustible','Sistema de combustible'),
(15,'Accesorios','Accesorios y complementos varios');

