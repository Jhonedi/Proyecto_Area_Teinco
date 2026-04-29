import pymysql
from pymysql.cursors import DictCursor
from flask import g, current_app
import logging

logger = logging.getLogger(__name__)

def get_db():
    """Obtiene una conexión a la base de datos"""
    if 'db' not in g:
        try:
            g.db = pymysql.connect(
                host=current_app.config['MYSQL_HOST'],
                user=current_app.config['MYSQL_USER'],
                password=current_app.config['MYSQL_PASSWORD'],
                database=current_app.config['MYSQL_DB'],
                port=current_app.config['MYSQL_PORT'],
                charset=current_app.config['MYSQL_CHARSET'],
                cursorclass=DictCursor,
                autocommit=False
            )
        except Exception as e:
            logger.error(f"Error conectando a la base de datos: {e}")
            raise
    return g.db

def close_db(e=None):
    """Cierra la conexión a la base de datos"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    """Inicializa la base de datos con la aplicación Flask"""
    app.teardown_appcontext(close_db)

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """
    Ejecuta una consulta SQL
    
    Args:
        query: Consulta SQL a ejecutar
        params: Parámetros para la consulta (tupla o dict)
        fetch_one: Si True, retorna un solo resultado
        fetch_all: Si True, retorna todos los resultados
        commit: Si True, hace commit de la transacción
    
    Returns:
        Resultado de la consulta según los parámetros
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute(query, params or ())
        
        if commit:
            db.commit()
            return cursor.lastrowid if cursor.lastrowid else True
        
        if fetch_one:
            return cursor.fetchone()
        
        if fetch_all:
            return cursor.fetchall()
        
        return cursor.lastrowid
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error ejecutando query: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        raise
    
    finally:
        cursor.close()

def execute_many(query, params_list):
    """
    Ejecuta una consulta múltiple veces con diferentes parámetros
    
    Args:
        query: Consulta SQL a ejecutar
        params_list: Lista de tuplas con parámetros
    
    Returns:
        True si se ejecutó correctamente
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.executemany(query, params_list)
        db.commit()
        return True
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error ejecutando query múltiple: {e}")
        raise
    
    finally:
        cursor.close()
