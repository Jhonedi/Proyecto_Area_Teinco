# InventoryFlow — Sistema de Inventario para Taller Automotriz

Sistema web completo para la gestión de inventario de repuestos en talleres de mantenimiento automotriz. Incluye control de roles, alertas automáticas de stock, módulo de facturación y trazabilidad completa mediante log de auditoría.

---

## Características

### Roles del Sistema (RBAC)

| Rol | Permisos |
|-----|---------|
| **SUPER_USUARIO** | Privilegios máximos, administración total |
| **ADMINISTRADOR** | Control total, gestión de usuarios, aprobación de ajustes |
| **ALMACENISTA** | Gestión de inventario, entradas/salidas, alertas |
| **VENDEDOR** | Confirmación de ventas y facturación |
| **TECNICO** | Solicitud de repuestos (lectura) |

### Módulos

- Gestión completa de repuestos (CRUD con imágenes y compatibilidad por vehículo)
- Entradas y salidas de inventario con flujo de aprobación
- Alertas automáticas de stock bajo/agotado con notificaciones por usuario
- Solicitudes de repuestos por técnicos con flujo de aprobación
- Ajustes de inventario con autorización de administrador
- Clientes y vehículos (placas colombianas ABC123/ABC12D)
- Facturación con códigos de descuento e IVA (19%)
- Dashboard con estadísticas en tiempo real
- Mensajería interna entre usuarios
- Log de auditoría completo (IP, user-agent, cambios antes/después)
- Reportes del sistema

---

## Requisitos Previos

- Python 3.8 o superior
- MySQL 5.7+ o MariaDB
- pip

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd InventoryFlow
```

### 2. Crear y activar el entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
copy .env.example .env
```

Editar `.env` con los datos de tu servidor MySQL:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=root
MYSQL_PASSWORD=tu_contraseña
MYSQL_DB=DB_Area_InventoryFlow
SECRET_KEY=clave-secreta-segura
FLASK_DEBUG=0
```

> Si no creas el `.env`, la aplicación usa los valores por defecto de `config.py` (localhost, puerto 3307, root sin contraseña).

### 5. Cargar la base de datos

El archivo `database/InventoryFlow_BD_Completa.sql` contiene **toda** la estructura (27 tablas) y los datos de demostración (~12 000 registros) en un único script.

**Opción A — línea de comandos:**
```bash
mysql -u root -p < database/InventoryFlow_BD_Completa.sql
```

**Opción B — phpMyAdmin:**
1. Abrir `http://localhost/phpmyadmin`
2. Pestaña **Importar** → seleccionar `database/InventoryFlow_BD_Completa.sql`
3. Clic en **Continuar**

> El script crea automáticamente la base de datos `DB_Area_InventoryFlow`.

### 6. Ejecutar la aplicación

```bash
# Windows — script automático
inicio.bat

# O manual
python app.py
```

Acceder en: **http://localhost:5000**

---

## Credenciales por Defecto

| Campo | Valor |
|-------|-------|
| Usuario | `admin` |
| Contraseña | `admin123` |

> Cambiar inmediatamente en producción.

---

## Estructura del Proyecto

```
InventoryFlow/
│
├── app.py                          # Aplicación principal Flask (rutas core)
├── config.py                       # Configuración (BD, sesión, uploads, IVA)
├── database.py                     # Conexión MySQL y ejecución de queries
├── auth.py                         # Autenticación, RBAC y audit logging
├── requirements.txt                # Dependencias Python
├── .env.example                    # Plantilla de variables de entorno
├── .gitignore
├── inicio.bat                      # Script de inicio rápido (Windows)
│
├── database/
│   └── InventoryFlow_BD_Completa.sql  # Base de datos completa (estructura + datos)
│
├── routes/
│   ├── __init__.py                 # Registro de blueprints
│   ├── solicitudes.py              # Solicitudes de repuestos
│   ├── facturacion.py              # Módulo de facturación
│   ├── alertas.py                  # Sistema de alertas
│   ├── reportes.py                 # Generación de reportes
│   ├── categorias.py               # Gestión de categorías
│   ├── mensajes.py                 # Mensajería interna
│   └── audit.py                    # Log de auditoría
│
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   ├── js/validacion_placas.js
│   └── uploads/                    # Imágenes de repuestos (excluido de Git)
│
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── repuestos/
    ├── movimientos/
    ├── solicitudes/
    ├── facturacion/
    ├── alertas/
    ├── usuarios/
    ├── clientes/
    ├── vehiculos/
    ├── categorias/
    ├── descuentos/
    ├── mensajes/
    ├── audit/
    └── reportes/
```

---

## Base de Datos

### Tablas (27 en total)

| Tabla | Descripción | Registros demo |
|-------|-------------|---------------|
| `roles` | Roles del sistema (5 roles) | 5 |
| `usuarios` | Empleados con acceso al sistema | 9 |
| `configuracion_sistema` | Parámetros globales clave-valor | 10 |
| `marcas_vehiculos` | 15 marcas colombianas | 15 |
| `modelos_vehiculos` | Modelos por marca | 100 |
| `clientes` | Clientes del taller | 2 200 |
| `vehiculos_clientes` | Vehículos registrados | ~4 800 |
| `categorias_repuestos` | Categorías de repuestos | 15 |
| `repuestos` | Catálogo de repuestos | 68 |
| `tipos_movimiento` | Tipos de entrada/salida | 9 |
| `solicitudes_repuestos` | Solicitudes de técnicos | 600 |
| `items_solicitud` | Ítems de solicitudes | ~1 500 |
| `movimientos_inventario` | Entradas y salidas | 800 |
| `facturas` | Facturas de venta | 300 |
| `detalles_factura` | Líneas de facturas | ~700 |
| `alertas_inventario` | Alertas de stock | 150 |
| `audit_log` | Log de auditoría | 120 |
| `imagenes_repuestos` | Imágenes de repuestos | — |
| `repuestos_compatibilidad` | Compatibilidad repuesto-vehículo | — |
| `repuestos_equivalentes` | Repuestos alternativos | — |
| `historial_ajustes_inventario` | Ajustes con aprobación | — |
| `historial_alertas` | Cambios de estado en alertas | — |
| `notificaciones_usuarios` | Notificaciones por usuario | auto |
| `mensajes_internos` | Mensajería interna | — |
| `pagos_factura` | Pagos de facturas | — |
| `codigos_descuento` | Códigos de descuento | — |
| `reportes_generados` | Reportes exportados | — |

---

## API Endpoints (JSON)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/repuestos/buscar` | Búsqueda de repuestos |
| GET | `/api/repuestos/por-categoria/<id>` | Filtrar por categoría |
| GET | `/api/repuestos/<codigo>/detalle` | Detalle completo de repuesto |
| GET | `/api/vehiculos-cliente/<id>` | Vehículos de un cliente |
| GET | `/api/marcas/<id>/modelos` | Modelos de una marca |
| POST | `/api/marcas/nueva` | Crear nueva marca |
| POST | `/api/modelos/nuevo` | Crear nuevo modelo |
| GET | `/api/descuentos/<codigo>` | Consultar código de descuento |
| GET | `/api/notificaciones` | Notificaciones del usuario actual |
| GET | `/api/notificaciones/count` | Contador de notificaciones |
| POST | `/api/alertas/marcar-leida/<id>` | Marcar notificación como leída |

---

## Seguridad

- Contraseñas hasheadas con bcrypt (nunca texto plano)
- Control de acceso basado en roles (RBAC) con decoradores
- Timeout de sesión por inactividad (30 minutos)
- Queries parametrizadas (prevención SQL injection)
- Log de auditoría con IP y user-agent
- Usuarios y roles protegidos con flag `es_protegido`

---

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.8+ / Flask 3.0 |
| Base de datos | MySQL 5.7+ / MariaDB + PyMySQL |
| Autenticación | bcrypt |
| Frontend | Bootstrap 5, jQuery 3.6, Bootstrap Icons |
| Env vars | python-dotenv |

---

## Solución de Problemas

| Error | Solución |
|-------|---------|
| `Can't connect to MySQL` | Verificar que MySQL esté en el puerto 3307 y revisar credenciales en `.env` |
| `Unknown database` | Importar `database/InventoryFlow_BD_Completa.sql` |
| `ModuleNotFoundError` | Activar el entorno virtual: `venv\Scripts\activate` y ejecutar `pip install -r requirements.txt` |
| No puedo iniciar sesión | Confirmar que la BD se importó completa — usar `admin` / `admin123` |
| Puerto 5000 ocupado | Cambiar el puerto al final de `app.py` |
