-- Datos de Prueba para Sistema de Inventario de Taller Automotriz
-- Ejecutar después de crear la base de datos con schema_v3.sql
-- PKs naturales: usuarios(numero_documento), clientes(numero_documento),
--                vehiculos_clientes(placa), repuestos(codigo)

USE taller_inventario;

-- ==================== USUARIOS ADICIONALES ====================
-- Contraseña para todos: pass123
-- Roles en schema_v3: 1=SUPER_USUARIO, 2=ADMINISTRADOR, 3=ALMACENISTA, 4=VENDEDOR, 5=TECNICO
INSERT INTO usuarios (numero_documento, username, password_hash, nombre_completo, email, rol_id) VALUES
('8050010001', 'almacenista1', '$2b$12$LQv3c1yqBwlVHpPx8fCv5uTeVF8z/TJ.cKo9lYz/h2SqKTK8lBvMu', 'Carlos Mendoza', 'carlos.mendoza@taller.com', 3),
('2060020002', 'vendedor1',   '$2b$12$LQv3c1yqBwlVHpPx8fCv5uTeVF8z/TJ.cKo9lYz/h2SqKTK8lBvMu', 'María Rodríguez', 'maria.rodriguez@taller.com', 4),
('1090030003', 'tecnico1',    '$2b$12$LQv3c1yqBwlVHpPx8fCv5uTeVF8z/TJ.cKo9lYz/h2SqKTK8lBvMu', 'Juan Pérez', 'juan.perez@taller.com', 5),
('3070040004', 'tecnico2',    '$2b$12$LQv3c1yqBwlVHpPx8fCv5uTeVF8z/TJ.cKo9lYz/h2SqKTK8lBvMu', 'Ana García', 'ana.garcia@taller.com', 5);

-- ==================== MODELOS DE VEHÍCULOS ====================
-- Chevrolet
INSERT INTO modelos_vehiculos (marca_id, nombre, anio_inicio, anio_fin) VALUES
(1, 'Spark', 2010, NULL),
(1, 'Aveo', 2010, NULL),
(1, 'Cruze', 2011, NULL),
(1, 'Sail', 2013, NULL),
(1, 'Captiva', 2010, NULL);

-- Ford
INSERT INTO modelos_vehiculos (marca_id, nombre, anio_inicio, anio_fin) VALUES
(2, 'Fiesta', 2010, NULL),
(2, 'Focus', 2010, NULL),
(2, 'Fusion', 2010, NULL),
(2, 'Escape', 2010, NULL),
(2, 'Explorer', 2010, NULL);

-- Nissan
INSERT INTO modelos_vehiculos (marca_id, nombre, anio_inicio, anio_fin) VALUES
(3, 'Sentra', 2010, NULL),
(3, 'Versa', 2010, NULL),
(3, 'March', 2010, NULL),
(3, 'Kicks', 2017, NULL),
(3, 'X-Trail', 2010, NULL);

-- Toyota
INSERT INTO modelos_vehiculos (marca_id, nombre, anio_inicio, anio_fin) VALUES
(4, 'Corolla', 2010, NULL),
(4, 'Yaris', 2010, NULL),
(4, 'Hilux', 2010, NULL),
(4, 'Prado', 2010, NULL),
(4, 'RAV4', 2010, NULL);

-- Honda
INSERT INTO modelos_vehiculos (marca_id, nombre, anio_inicio, anio_fin) VALUES
(6, 'Civic', 2010, NULL),
(6, 'Accord', 2010, NULL),
(6, 'CR-V', 2010, NULL),
(6, 'City', 2010, NULL),
(6, 'HR-V', 2015, NULL);

-- Mazda
INSERT INTO modelos_vehiculos (marca_id, nombre, anio_inicio, anio_fin) VALUES
(5, 'Mazda 2', 2010, NULL),
(5, 'Mazda 3', 2010, NULL),
(5, 'Mazda 6', 2010, NULL),
(5, 'CX-3', 2015, NULL),
(5, 'CX-5', 2012, NULL);

-- ==================== CLIENTES ====================
INSERT INTO clientes (tipo_documento, numero_documento, nombre_completo, telefono, email, direccion) VALUES
('CC',  '1234567890',  'Pedro Martínez López',          '3001234567', 'pedro.martinez@email.com',   'Calle 45 #23-12, Bogotá'),
('CC',  '9876543210',  'Laura Gómez Ruiz',               '3109876543', 'laura.gomez@email.com',       'Carrera 15 #67-89, Medellín'),
('NIT', '900123456-1', 'Transportes Rápidos S.A.S.',     '3201112233', 'info@transportesrapidos.com', 'Avenida 68 #45-30, Bogotá'),
('CC',  '1122334455',  'Andrés Ramírez Castro',          '3156677889', 'andres.ramirez@email.com',    'Calle 100 #15-20, Bogotá'),
('CC',  '5544332211',  'Sofía Hernández Díaz',           '3187654321', 'sofia.hernandez@email.com',   'Carrera 7 #32-45, Bogotá'),
('NIT', '800234567-2', 'Comercializadora del Sur Ltda.', '3124455667', 'ventas@comsur.com',           'Calle 19 #3-45, Cali'),
('CC',  '6677889900',  'Roberto Sánchez Mora',           '3198765432', 'roberto.sanchez@email.com',   'Transversal 45 #12-34, Barranquilla'),
('CC',  '2233445566',  'Carolina Vargas Torres',         '3165544332', 'carolina.vargas@email.com',   'Diagonal 27 #78-90, Cartagena');

-- ==================== VEHÍCULOS DE CLIENTES ====================
-- PK es placa; cliente_id = numero_documento del cliente
INSERT INTO vehiculos_clientes (placa, cliente_id, modelo_vehiculo_id, anio, color, kilometraje_actual) VALUES
('ABC123', '1234567890',  1,  2018, 'Rojo',  45000),
('DEF456', '1234567890',  11, 2020, 'Blanco',25000),
('GHI789', '9876543210',  16, 2019, 'Negro', 38000),
('JKL012', '900123456-1', 18, 2021, 'Gris',  50000),
('MNO345', '900123456-1', 18, 2020, 'Blanco',65000),
('PQR678', '900123456-1', 18, 2019, 'Azul',  80000),
('STU901', '1122334455',  6,  2017, 'Plata', 55000),
('VWX234', '5544332211',  26, 2022, 'Rojo',  15000),
('YZA567', '800234567-2', 3,  2016, 'Negro', 90000),
('BCD890', '6677889900',  21, 2021, 'Blanco',32000),
('EFG123', '2233445566',  13, 2020, 'Azul',  28000);

-- Motos
INSERT INTO vehiculos_clientes (placa, cliente_id, modelo_vehiculo_id, anio, color, kilometraje_actual) VALUES
('HIJ45K', '1234567890', 26, 2021, 'Negro', 12000),
('LMN67P', '1122334455', 26, 2020, 'Rojo',  18000);

-- ==================== REPUESTOS ====================
-- Filtros
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('FILT-001', 'Filtro de Aceite',      'Filtro de aceite para motores gasolina', 6, 25000, 45, 10, 'Estante A-1', 'Mann Filter'),
('FILT-002', 'Filtro de Aire',        'Filtro de aire para vehículos livianos', 6, 35000, 30, 10, 'Estante A-2', 'K&N'),
('FILT-003', 'Filtro de Combustible', 'Filtro de combustible diesel',           6, 45000, 20,  8, 'Estante A-3', 'Bosch'),
('FILT-004', 'Filtro de Cabina',      'Filtro de aire acondicionado',           6, 30000, 25, 10, 'Estante A-4', 'Fram');

-- Lubricantes
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('ACE-001', 'Aceite Motor 20W-50', 'Aceite mineral para motor 4L',           7,  65000, 50, 15, 'Bodega B-1', 'Mobil'),
('ACE-002', 'Aceite Motor 10W-40', 'Aceite semisintético 4L',                7,  85000, 40, 15, 'Bodega B-1', 'Castrol'),
('ACE-003', 'Aceite Motor 5W-30',  'Aceite sintético 4L',                    7, 120000, 25, 10, 'Bodega B-1', 'Shell'),
('ACE-004', 'Aceite Transmisión ATF', 'Aceite para transmisión automática',  7,  95000, 15,  8, 'Bodega B-2', 'Valvoline');

-- Frenos
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('FRE-001', 'Pastillas de Freno Delanteras', 'Pastillas freno disco delantero', 4,  85000, 20, 8, 'Estante C-1', 'Brembo'),
('FRE-002', 'Pastillas de Freno Traseras',   'Pastillas freno disco trasero',   4,  75000, 18, 8, 'Estante C-1', 'Brembo'),
('FRE-003', 'Disco de Freno Delantero',      'Disco freno ventilado',           4, 125000, 12, 5, 'Estante C-2', 'ATE'),
('FRE-004', 'Líquido de Frenos DOT 4',       'Líquido de frenos 500ml',         4,  28000, 30, 10,'Estante C-3', 'Ate');

-- Suspensión
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('SUS-001', 'Amortiguador Delantero', 'Amortiguador telescópico delantero',       3, 185000, 10, 4, 'Estante D-1', 'Monroe'),
('SUS-002', 'Amortiguador Trasero',   'Amortiguador telescópico trasero',         3, 165000, 12, 4, 'Estante D-1', 'Monroe'),
('SUS-003', 'Terminal de Dirección',  'Terminal dirección exterior',              3,  55000, 15, 6, 'Estante D-2', 'TRW'),
('SUS-004', 'Rótula Suspensión',      'Rótula inferior brazo suspensión',         3,  75000,  8, 4, 'Estante D-2', 'Moog');

-- Motor
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('MOT-001', 'Bujía de Encendido',   'Bujía iridio larga duración',     1,  35000, 40, 15, 'Estante E-1', 'NGK'),
('MOT-002', 'Correa de Distribución','Kit correa distribución completo',1, 245000,  8,  3, 'Estante E-2', 'Gates'),
('MOT-003', 'Bomba de Agua',         'Bomba de agua refrigeración',     1, 155000,  6,  3, 'Estante E-3', 'Dolz'),
('MOT-004', 'Termostato',            'Termostato motor refrigeración',  1,  45000, 12,  5, 'Estante E-3', 'Wahler');

-- Eléctrico
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('ELE-001', 'Batería 12V 45Ah',       'Batería libre mantenimiento', 5, 295000, 10, 4, 'Bodega F-1', 'MAC'),
('ELE-002', 'Batería 12V 60Ah',       'Batería libre mantenimiento', 5, 385000,  8, 3, 'Bodega F-1', 'MAC'),
('ELE-003', 'Alternador Reconstruido','Alternador 90A',              5, 425000,  3, 2, 'Bodega F-2', 'Bosch'),
('ELE-004', 'Motor de Arranque',      'Motor arranque reconstruido', 5, 385000,  4, 2, 'Bodega F-2', 'Bosch');

-- Neumáticos
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('NEU-001', 'Llanta 175/70 R13', 'Llanta radial vehículo liviano',   10, 185000, 15, 8, 'Bodega G-1', 'Michelin'),
('NEU-002', 'Llanta 185/65 R14', 'Llanta radial vehículo liviano',   10, 215000, 12, 8, 'Bodega G-1', 'Michelin'),
('NEU-003', 'Llanta 195/60 R15', 'Llanta radial vehículo liviano',   10, 245000, 10, 6, 'Bodega G-1', 'Goodyear'),
('NEU-004', 'Llanta 205/55 R16', 'Llanta radial alto rendimiento',   10, 285000,  8, 6, 'Bodega G-1', 'Bridgestone');

-- Iluminación
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('LUZ-001', 'Bombilla H4 12V 55W', 'Bombilla halógena estándar',  9,  18000, 25, 10, 'Estante H-1', 'Philips'),
('LUZ-002', 'Bombilla H7 12V 55W', 'Bombilla halógena estándar',  9,  18000, 22, 10, 'Estante H-1', 'Philips'),
('LUZ-003', 'Kit Luces LED H4',    'Kit conversión LED 6000K',    9, 145000,  5,  3, 'Estante H-2', 'Philips'),
('LUZ-004', 'Faro Delantero Derecho','Faro completo lado derecho', 9, 285000,  3,  2, 'Estante H-3', 'Depo');

-- Accesorios
INSERT INTO repuestos (codigo, nombre, descripcion, categoria_id, precio_venta, cantidad_actual, cantidad_minima, ubicacion_fisica, marca_fabricante) VALUES
('ACC-001', 'Limpia Parabrisas 18"',    'Escobilla limpiaparabrisas',   15,  35000, 20, 8, 'Estante I-1', 'Bosch'),
('ACC-002', 'Limpia Parabrisas 20"',    'Escobilla limpiaparabrisas',   15,  38000, 18, 8, 'Estante I-1', 'Bosch'),
('ACC-003', 'Espejo Retrovisor Izquierdo','Espejo lateral lado conductor',15,125000,  4, 2, 'Estante I-2', 'TYC'),
('ACC-004', 'Tapete Universal',          'Juego 4 tapetes caucho',       15,  65000, 10, 5, 'Estante I-3', 'WeatherTech');

-- ==================== ALGUNOS MOVIMIENTOS DE INVENTARIO ====================
-- repuesto_id = codigo del repuesto (VARCHAR)
-- usuario_id  = numero_documento del usuario (VARCHAR)
-- tecnico_solicitante_id = numero_documento del técnico (VARCHAR)
-- vehiculo_cliente_id = placa del vehículo (VARCHAR)

-- Entradas (Tipo 1: Compra)
-- usuario_id='0000000002' = admin
INSERT INTO movimientos_inventario (repuesto_id, tipo_movimiento_id, cantidad, precio_unitario, usuario_id, estado, observaciones, created_at) VALUES
('FILT-001', 1, 50, 18000, '0000000002', 'CONFIRMADO', 'Compra mensual proveedor principal', '2025-01-10 10:30:00'),
('FILT-002', 1, 40, 25000, '0000000002', 'CONFIRMADO', 'Compra mensual proveedor principal', '2025-01-10 10:30:00'),
('ACE-001',  1, 60, 45000, '0000000002', 'CONFIRMADO', 'Compra lubricantes',                  '2025-01-15 14:00:00'),
('FRE-001',  1, 30, 60000, '0000000002', 'CONFIRMADO', 'Compra pastillas de freno',           '2025-01-20 11:00:00');

-- Salidas (Tipo 4: Venta)
-- usuario_id='8050010001'=almacenista1, tecnico='1090030003'=tecnico1, '3070040004'=tecnico2
-- vehiculo_cliente_id = placa del vehículo
INSERT INTO movimientos_inventario (repuesto_id, tipo_movimiento_id, cantidad, usuario_id, tecnico_solicitante_id, vehiculo_cliente_id, estado, observaciones, created_at) VALUES
('FILT-001', 4, 5, '8050010001', '1090030003', 'ABC123', 'CONFIRMADO', 'Cambio de aceite y filtros', '2025-02-01 09:00:00'),
('FILT-002', 4, 5, '8050010001', '1090030003', 'ABC123', 'CONFIRMADO', 'Cambio de aceite y filtros', '2025-02-01 09:00:00'),
('ACE-001',  4, 2, '8050010001', '1090030003', 'ABC123', 'CONFIRMADO', 'Cambio de aceite',           '2025-02-01 09:00:00'),
('FRE-001',  4, 4, '8050010001', '1090030003', 'GHI789', 'CONFIRMADO', 'Cambio pastillas freno',     '2025-02-05 10:30:00'),
('MOT-001',  4, 4, '8050010001', '3070040004', 'DEF456', 'CONFIRMADO', 'Cambio bujías',              '2025-02-08 15:00:00');

-- ==================== CREAR ALGUNAS ALERTAS ====================
-- repuesto_id = codigo del repuesto (VARCHAR)
INSERT INTO alertas_inventario (repuesto_id, tipo_alerta, nivel_prioridad, mensaje) VALUES
('SUS-004', 'STOCK_BAJO', 'ALTA', 'El repuesto Rótula Suspensión (SUS-004) tiene stock bajo: 8 unidades'),
('ELE-003', 'STOCK_BAJO', 'ALTA', 'El repuesto Alternador Reconstruido (ELE-003) tiene stock bajo: 3 unidades'),
('ELE-004', 'STOCK_BAJO', 'ALTA', 'El repuesto Motor de Arranque (ELE-004) tiene stock bajo: 4 unidades');

-- ==================== NOTIFICACIONES PARA USUARIOS ====================
-- usuario_id = numero_documento del usuario
-- '0000000001' = superusuario, '0000000002' = admin
INSERT INTO notificaciones_usuarios (usuario_id, alerta_id) VALUES
('0000000001', 1), ('0000000001', 2), ('0000000001', 3),  -- Super usuario recibe todas
('0000000002', 1), ('0000000002', 2), ('0000000002', 3);  -- Admin recibe todas

-- ==================== ESTADÍSTICAS ====================
SELECT 'Datos de prueba cargados exitosamente!' as mensaje;
SELECT
    'Total Clientes: ' as descripcion,
    COUNT(*) as cantidad
FROM clientes;

SELECT
    'Total Vehículos: ' as descripcion,
    COUNT(*) as cantidad
FROM vehiculos_clientes;

SELECT
    'Total Repuestos: ' as descripcion,
    COUNT(*) as cantidad
FROM repuestos;

SELECT
    'Total Movimientos: ' as descripcion,
    COUNT(*) as cantidad
FROM movimientos_inventario;

SELECT
    'Total Alertas Activas: ' as descripcion,
    COUNT(*) as cantidad
FROM alertas_inventario
WHERE estado IN ('NUEVA', 'EN_PROCESO');
