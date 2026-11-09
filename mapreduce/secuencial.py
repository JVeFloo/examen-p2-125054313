#!/usr/bin/env python3
"""
secuencial.py
La MISMA pregunta (ticket promedio por tienda) resuelta en un solo
proceso, sin Hadoop, leyendo el archivo linea por linea.

Uso:
    python3 secuencial.py /data/input/ventas_125054313.csv

La salida va a stdout en el MISMO formato y el MISMO orden que el
reducer, para poder compararla con `diff`. El tiempo se reporta por
stderr para no contaminar esa comparacion.

Se usa la misma aritmetica en centavos enteros que el mapper, de modo
que los dos resultados deben coincidir exactamente, no "aproximadamente".
"""

import csv
import sys
import time

COL_TIENDA = 2
COL_CANTIDAD = 5
COL_PRECIO = 6
NUM_COLUMNAS = 8


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 secuencial.py <ruta_del_csv>")

    ruta = sys.argv[1]
    inicio = time.perf_counter()

    suma_por_tienda = {}
    conteo_por_tienda = {}
    procesados = descartadas = 0

    with open(ruta, newline="") as f:
        lector = csv.reader(f)
        for fila in lector:
            if not fila or fila[0] == "id":
                continue
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

            suma_por_tienda[tienda] = suma_por_tienda.get(tienda, 0) + centavos
            conteo_por_tienda[tienda] = conteo_por_tienda.get(tienda, 0) + 1
            procesados += 1

    # Hadoop ordena las claves alfabeticamente: aqui se replica ese orden
    for tienda in sorted(suma_por_tienda):
        centavos = suma_por_tienda[tienda]
        registros = conteo_por_tienda[tienda]
        print(f"{tienda}\t{centavos / registros / 100:.2f}"
              f"\t{centavos / 100:.2f}\t{registros}")

    transcurrido = time.perf_counter() - inicio
    sys.stderr.write(
        f"\n[secuencial] registros procesados: {procesados}\n"
        f"[secuencial] lineas descartadas:   {descartadas}\n"
        f"[secuencial] tiempo:               {transcurrido:.2f} s\n"
    )


if __name__ == "__main__":
    main()
