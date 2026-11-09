#!/usr/bin/env python3
"""
reducer.py
Ticket promedio por tienda.

Hadoop entrega las lineas YA ORDENADAS por clave, asi que basta con
acumular mientras la tienda no cambie y emitir al detectar el corte.
El reducer nunca guarda las 5 millones de filas en memoria: solo lleva
dos enteros (suma y conteo) de la tienda que esta procesando.

Entrada:  tienda <TAB> centavos <TAB> conteo
Salida:   tienda <TAB> ticket_promedio <TAB> ingreso_total <TAB> num_registros
"""

import sys


def emitir(tienda, centavos, registros):
    if tienda is None or registros == 0:
        return
    ticket_promedio = centavos / registros / 100
    ingreso_total = centavos / 100
    sys.stdout.write(
        f"{tienda}\t{ticket_promedio:.2f}\t{ingreso_total:.2f}\t{registros}\n"
    )


def main():
    tienda_actual = None
    suma_centavos = 0
    num_registros = 0

    for linea in sys.stdin:
        partes = linea.rstrip("\n").split("\t")
        if len(partes) != 3:
            continue
        tienda, centavos, conteo = partes
        try:
            centavos = int(centavos)
            conteo = int(conteo)
        except ValueError:
            continue

        # Cambio de clave: cerramos la tienda anterior
        if tienda != tienda_actual:
            emitir(tienda_actual, suma_centavos, num_registros)
            tienda_actual = tienda
            suma_centavos = 0
            num_registros = 0

        suma_centavos += centavos
        num_registros += conteo

    # Ultima tienda del flujo
    emitir(tienda_actual, suma_centavos, num_registros)


if __name__ == "__main__":
    main()
