-- Script para corregir la contraseña del usuario admin
-- Password: admin123

USE taller_inventario;

UPDATE usuarios 
SET password_hash = '$2b$12$Y2AGfKQsLpKfPOHK5ZO/gOYwgznuQbT6gOI3mOQ8EySTMrwm3GP56'
WHERE username = 'admin';

SELECT 'Password actualizado correctamente' AS mensaje;
