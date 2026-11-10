#!/usr/bin/env python3
"""
mapper.py
Pregunta asignada (matricula 125054313, ultimo digito 3):
    Ticket promedio (ingreso promedio por registro) por TIENDA.

Lee el CSV de ventas por stdin y emite, por cada registro valido:

    tienda <TAB> ingreso_en_centavos <TAB> 1

Dos decisiones importantes:

1) El ingreso se maneja en CENTAVOS ENTEROS (cantidad * precio * 100).
   Asi la suma es exacta y coincide al centavo con la del script
   secuencial, sin errores de punto flotante al acumular 5 millones
   de valores.

2) Cada registro se emite con un conteo de 1, ademas del ingreso. Asi
   los valores son sumables: ingreso y conteo parciales se pueden
   agregar en cualquier orden. Ojo: el reducer de este examen NO sirve
   como combiner, porque su salida (4 campos, con el promedio ya
   calculado) no tiene el formato de la salida del mapper (3 campos).
   Un combiner tendria que emitir de nuevo
   tienda <TAB> centavos <TAB> conteo.
"""

import csv
import sys

# Columnas del CSV:
# 0 id | 1 fecha_hora | 2 tienda | 3 categoria | 4 producto
# 5 cantidad | 6 precio_unitario | 7 metodo_pago
COL_TIENDA = 2
COL_CANTIDAD = 5
COL_PRECIO = 6
NUM_COLUMNAS = 8


def main():
    procesados = 0
    encabezados = 0
    descartadas = 0

    for fila in csv.reader(sys.stdin):
        # --- Encabezado: se ignora sin romper el job ---
        if not fila or fila[0] == "id":
            encabezados += 1
            continue

        # --- Lineas mal formadas: se cuentan y se saltan ---
        if len(fila) != NUM_COLUMNAS:
            descartadas += 1
            continue

        try:
            tienda = fila[COL_TIENDA].strip()
            cantidad = int(fila[COL_CANTIDAD])
            centavos = cantidad * int(round(float(fila[COL_PRECIO]) * 100))
        except ValueError:
            descartadas += 1
            continue

        if not tienda or cantidad < 0:
            descartadas += 1
            continue

        sys.stdout.write(f"{tienda}\t{centavos}\t1\n")
        procesados += 1

    # Contadores de Hadoop: viajan por stderr, no ensucian la salida.
    # Se emiten una sola vez al final para no frenar el job.
    sys.stderr.write(f"reporter:counter:mapper,registros_procesados,{procesados}\n")
    sys.stderr.write(f"reporter:counter:mapper,encabezados_ignorados,{encabezados}\n")
    sys.stderr.write(f"reporter:counter:mapper,lineas_mal_formadas,{descartadas}\n")


if __name__ == "__main__":
    main()
