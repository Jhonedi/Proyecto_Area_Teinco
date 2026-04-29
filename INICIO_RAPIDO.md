# Guía de Inicio Rápido — InventoryFlow

## 1. Cargar la Base de Datos

El archivo `database/InventoryFlow_BD_Completa.sql` contiene **toda** la estructura (27 tablas) y los datos de demostración en un único script. Solo hay que importarlo una vez.

**Opción A — línea de comandos:**
```bash
mysql -u root -p < database/InventoryFlow_BD_Completa.sql
```

**Opción B — phpMyAdmin:**
1. Abrir `http://localhost/phpmyadmin`
2. Pestaña **Importar** → seleccionar `database/InventoryFlow_BD_Completa.sql`
3. Clic en **Continuar**

> El script crea automáticamente la base de datos `DB_Area_InventoryFlow` con sus 27 tablas y ~12 000 registros de demo.

---

## 2. Configurar Credenciales de MySQL

```bash
copy .env.example .env
```

Editar `.env`:
```env
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=root
MYSQL_PASSWORD=tu_contraseña
MYSQL_DB=DB_Area_InventoryFlow
```

Si no se crea `.env`, se usarán los valores por defecto de `config.py` (localhost, puerto 3307, root sin contraseña).

---

## 3. Iniciar la Aplicación

**Método simple (Windows):**
```bash
inicio.bat
```

**Método manual:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## 4. Acceder al Sistema

Navegador: **http://localhost:5000**

| Campo | Valor |
|-------|-------|
| Usuario | `admin` |
| Contraseña | `admin123` |

---

## 5. Primeros Pasos

### Como Administrador
1. Ir a **Usuarios** → crear Almacenista, Vendedor y Técnico
2. Explorar el **Dashboard** — los datos de demo ya están cargados
3. Revisar **Alertas** activas

### Como Almacenista
1. **Movimientos** → Entrada de Inventario para registrar compras
2. **Solicitudes** → revisar y aprobar solicitudes de técnicos
3. **Alertas** → gestionar stock bajo/agotado

### Como Vendedor
1. **Facturación** → confirmar ventas pendientes al recibir pago
2. Aplicar códigos de descuento si aplica
3. Generar y entregar factura

### Como Técnico
1. **Repuestos** → consultar disponibilidad
2. **Solicitudes** → Nueva Solicitud para pedir repuestos al almacenista

---

## Checklist de Configuración

- [ ] MySQL/MariaDB corriendo en puerto 3307
- [ ] `database/InventoryFlow_BD_Completa.sql` importado correctamente
- [ ] Base de datos `DB_Area_InventoryFlow` visible en phpMyAdmin (27 tablas)
- [ ] `.env` configurado con contraseña correcta
- [ ] Entorno virtual activado
- [ ] `pip install -r requirements.txt` ejecutado sin errores
- [ ] `python app.py` inicia sin errores
- [ ] Login funciona con `admin` / `admin123`
- [ ] Dashboard carga con estadísticas

---

## Solución de Problemas

| Error | Solución |
|-------|---------|
| `Can't connect to MySQL` | Verificar que MySQL corre en el puerto 3307 |
| `Unknown database 'DB_Area_InventoryFlow'` | Importar `InventoryFlow_BD_Completa.sql` |
| `ModuleNotFoundError` | Activar venv y ejecutar `pip install -r requirements.txt` |
| No carga el dashboard | Ver mensajes de error en la consola de Python |
| No puedo iniciar sesión | Confirmar que la BD se importó completa |
