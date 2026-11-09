#!/usr/bin/env python3
"""
cargar_resultados.py
Lee la salida del job de Hadoop (/data/output/resultado/part-*) e inserta
los registros en PostgreSQL.

Se ejecuta DENTRO del contenedor api, que es el unico que tiene a la vez
el driver de Postgres y acceso a la red interna:

    docker compose exec api python /app/scripts/cargar_resultados.py

La carga es idempotente (INSERT ... ON CONFLICT DO UPDATE): se puede
volver a correr las veces que haga falta sin duplicar filas ni tener que
vaciar la tabla antes.
"""

import glob
import os
import sys

import psycopg2
import psycopg2.extras

DIRECTORIO_SALIDA = os.getenv("RESULTADOS_DIR", "/data/output/resultado")
TABLA = "ticket_promedio_tienda"

CONEXION = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "ventas"),
    "user": os.getenv("POSTGRES_USER", "datamart"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

INSERTAR = f"""
    INSERT INTO {TABLA} (tienda, ticket_promedio, ingreso_total, num_registros)
    VALUES %s
    ON CONFLICT (tienda) DO UPDATE SET
        ticket_promedio = EXCLUDED.ticket_promedio,
        ingreso_total   = EXCLUDED.ingreso_total,
        num_registros   = EXCLUDED.num_registros,
        cargado_en      = now()
"""


def leer_salida(directorio):
    """Devuelve las filas del job. Lee todos los part-* por si hubiera
    mas de un reducer, y salta las lineas vacias o mal formadas."""
    archivos = sorted(glob.glob(os.path.join(directorio, "part-*")))
    if not archivos:
        sys.exit(f"ERROR: no se encontro ningun archivo part-* en {directorio}.\n"
                 f"       Ejecuta primero el job de MapReduce.")

    filas = []
    descartadas = 0
    for ruta in archivos:
        with open(ruta) as f:
            for linea in f:
                partes = linea.rstrip("\n").split("\t")
                if len(partes) != 4:
                    if linea.strip():
                        descartadas += 1
                    continue
                tienda, ticket, ingreso, registros = partes
                try:
                    filas.append((tienda, float(ticket), float(ingreso), int(registros)))
                except ValueError:
                    descartadas += 1

    print(f"Archivos leidos: {', '.join(os.path.basename(a) for a in archivos)}")
    print(f"Filas validas:   {len(filas)}")
    if descartadas:
        print(f"Filas ignoradas: {descartadas}")
    return filas


def main():
    filas = leer_salida(DIRECTORIO_SALIDA)

    try:
        conexion = psycopg2.connect(**CONEXION)
    except psycopg2.OperationalError as e:
        sys.exit(f"ERROR: no se pudo conectar a PostgreSQL ({e.args[0].strip()})")

    try:
        with conexion:
            with conexion.cursor() as cur:
                psycopg2.extras.execute_values(cur, INSERTAR, filas, page_size=500)
                insertadas = cur.rowcount
            with conexion.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {TABLA}")
                total = cur.fetchone()[0]
    finally:
        conexion.close()

    print(f"Filas cargadas:  {insertadas}")
    print(f"Total en tabla {TABLA}: {total}")


if __name__ == "__main__":
    main()
