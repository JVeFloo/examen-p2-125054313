#!/usr/bin/env python3
"""
app.py - API REST del pipeline DataMart (FastAPI)

Expone los resultados del job de MapReduce que estan guardados en
PostgreSQL. Pregunta de negocio (matricula 125054313, ultimo digito 3):
ticket promedio por tienda, es decir, el ingreso promedio por registro
de venta en cada tienda.

Endpoints
    GET    /                     informacion de la API
    GET    /health               estado del servicio y de la conexion a la BD
    GET    /resultados           todos los registros
    GET    /resultados/{tienda}  filtro por la clave de la pregunta (la tienda)
    POST   /resultados           alta de un registro
    PUT    /resultados/{tienda}  reemplazo de un registro
    DELETE /resultados/{tienda}  baja de un registro

La documentacion interactiva queda en  http://localhost:8000/docs
"""

import os
from contextlib import contextmanager
from datetime import datetime

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

TABLA = "ticket_promedio_tienda"
COLUMNAS = "tienda, ticket_promedio, ingreso_total, num_registros, cargado_en"

# Las credenciales llegan por variables de entorno desde el archivo .env:
# nunca estan escritas en el codigo ni en la imagen.
CONEXION = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "ventas"),
    "user": os.getenv("POSTGRES_USER", "datamart"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

app = FastAPI(
    title="DataMart - Ticket promedio por tienda",
    description="Resultados del job de Hadoop MapReduce sobre las ventas de DataMart.",
    version="1.0.0",
)


# ------------------------------------------------------------------
#  Modelos
# ------------------------------------------------------------------
class TicketEntrada(BaseModel):
    ticket_promedio: float = Field(..., ge=0, description="Ingreso promedio por registro")
    ingreso_total: float = Field(..., ge=0, description="Suma de cantidad * precio_unitario")
    num_registros: int = Field(..., ge=0, description="Numero de ventas de la tienda")


class TicketNuevo(TicketEntrada):
    tienda: str = Field(..., min_length=1, max_length=10, examples=["T040"])


class TicketSalida(TicketEntrada):
    tienda: str
    cargado_en: datetime


# ------------------------------------------------------------------
#  Acceso a datos
# ------------------------------------------------------------------
@contextmanager
def abrir_conexion():
    """Abre una conexion, hace commit si todo sale bien y rollback si no."""
    try:
        conexion = psycopg2.connect(**CONEXION)
    except psycopg2.OperationalError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible: {e.args[0].strip()}",
        )
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def consultar(sql, parametros=(), una_fila=False):
    with abrir_conexion() as conexion:
        with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, parametros)
            return cur.fetchone() if una_fila else cur.fetchall()


def ejecutar(sql, parametros=()):
    """Para INSERT / UPDATE / DELETE. Devuelve el numero de filas afectadas."""
    with abrir_conexion() as conexion:
        with conexion.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.rowcount


# ------------------------------------------------------------------
#  Endpoints de lectura
# ------------------------------------------------------------------
@app.get("/", tags=["info"])
def raiz():
    return {
        "api": "DataMart - ticket promedio por tienda",
        "matricula": os.getenv("MATRICULA", "125054313"),
        "pregunta": "Ticket promedio (ingreso promedio por registro) por tienda",
        "documentacion": "/docs",
    }


@app.get("/health", tags=["info"])
def salud():
    fila = consultar(f"SELECT COUNT(*) AS filas FROM {TABLA}", una_fila=True)
    return {"estado": "ok", "base_de_datos": "conectada", "filas_en_tabla": fila["filas"]}


@app.get("/resultados", response_model=list[TicketSalida], tags=["resultados"])
def listar_resultados(
    limite: int = Query(100, ge=1, le=1000, description="Maximo de filas a devolver"),
    orden: str = Query("tienda", pattern="^(tienda|ticket_promedio|ingreso_total|num_registros)$"),
):
    """Todos los registros de la tabla."""
    # 'orden' esta restringido por el patron de arriba, por eso se puede
    # interpolar sin riesgo de inyeccion SQL; los valores van parametrizados.
    direccion = "ASC" if orden == "tienda" else "DESC"
    return consultar(
        f"SELECT {COLUMNAS} FROM {TABLA} ORDER BY {orden} {direccion} LIMIT %s",
        (limite,),
    )


@app.get("/resultados/{tienda}", response_model=TicketSalida, tags=["resultados"])
def obtener_resultado(tienda: str = Path(..., description="Clave de la pregunta: la tienda, por ejemplo T001")):
    """Filtro por la clave de la pregunta asignada: la tienda."""
    fila = consultar(
        f"SELECT {COLUMNAS} FROM {TABLA} WHERE tienda = %s", (tienda.upper(),), una_fila=True
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe la tienda {tienda}")
    return fila


# ------------------------------------------------------------------
#  Endpoints de escritura (CRUD)
# ------------------------------------------------------------------
@app.post("/resultados", response_model=TicketSalida,
          status_code=status.HTTP_201_CREATED, tags=["resultados"])
def crear_resultado(datos: TicketNuevo):
    existe = consultar(f"SELECT 1 FROM {TABLA} WHERE tienda = %s",
                       (datos.tienda.upper(),), una_fila=True)
    if existe:
        raise HTTPException(status.HTTP_409_CONFLICT, f"La tienda {datos.tienda} ya existe")

    return consultar(
        f"""INSERT INTO {TABLA} (tienda, ticket_promedio, ingreso_total, num_registros)
            VALUES (%s, %s, %s, %s) RETURNING {COLUMNAS}""",
        (datos.tienda.upper(), datos.ticket_promedio, datos.ingreso_total, datos.num_registros),
        una_fila=True,
    )


@app.put("/resultados/{tienda}", response_model=TicketSalida, tags=["resultados"])
def actualizar_resultado(tienda: str, datos: TicketEntrada):
    fila = consultar(
        f"""UPDATE {TABLA}
               SET ticket_promedio = %s, ingreso_total = %s,
                   num_registros = %s, cargado_en = now()
             WHERE tienda = %s
         RETURNING {COLUMNAS}""",
        (datos.ticket_promedio, datos.ingreso_total, datos.num_registros, tienda.upper()),
        una_fila=True,
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe la tienda {tienda}")
    return fila


@app.delete("/resultados/{tienda}", status_code=status.HTTP_204_NO_CONTENT, tags=["resultados"])
def borrar_resultado(tienda: str):
    borradas = ejecutar(f"DELETE FROM {TABLA} WHERE tienda = %s", (tienda.upper(),))
    if borradas == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe la tienda {tienda}")
