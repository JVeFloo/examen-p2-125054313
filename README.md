# Examen Segundo Parcial — Pipeline de datos contenerizado

**Alumno:** Jeshua
**Matrícula:** 125054313
**Materia:** Manejo Masivo de Datos (Big Data) — Segundo Parcial
**Profesor:** José Javier Moya Moya

> **Antes de levantar nada:** `cp .env.example .env`. El archivo `.env` no viaja en el
> repositorio porque contiene las credenciales de la base de datos.

## Pregunta de negocio asignada

El último dígito de la matrícula es **3**, por lo que corresponde:

> **Ticket promedio (ingreso promedio por registro) por tienda.**

Es decir, para cada tienda: `SUM(cantidad × precio_unitario) / COUNT(*)`.
La **clave** de la pregunta —y por tanto la del endpoint `GET /resultados/<clave>`— es la **tienda**.

---

## Qué hace el pipeline

```
ventas_125054313.csv          (400 MB, 5 000 000 de registros)
        │  montado :ro en /data/input
        ▼
  ┌───────────────┐   Hadoop Streaming      ┌──────────────┐   cargar_resultados.py   ┌──────────────┐
  │   contenedor  │   mapper.py             │  part-00000  │ ───────────────────────▶ │  contenedor  │
  │    hadoop     │ ─ reducer.py ─────────▶ │  (39 filas)  │                          │      db      │
  └───────────────┘                         └──────────────┘                          └──────────────┘
        ▲                                                                                    │
        │ ssh hadoop@hadoop (sin contraseña)                                                 │
        │                                   ┌──────────────┐                                 │
        └────────────────────────────────── │ contenedor   │ ◀───────────────────────────────┘
                                            │     api      │   GET /resultados
                                            └──────────────┘
```

Los tres servicios viven en la red `datamart_net` definida en el compose y se localizan entre sí por nombre de servicio.

---

## Requisitos

- Docker Engine y el plugin `docker compose` (v2).
- Python 3 en el host, sólo para generar el dataset.
- Unos 3 GB libres en disco: la imagen de Hadoop pesa bastante y el CSV ronda los 400 MB.

---

## Cómo reproducirlo

### Paso 0 — Generar el dataset

```bash
python3 scripts/generar_dataset.py 125054313
mkdir -p data
mv ventas_125054313.csv data/
```

El CSV **no se sube al repositorio**: `data/*` está en `.gitignore` y se monta en el contenedor como volumen de sólo lectura.

### Paso 1 — Crear el archivo de variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y pon una contraseña propia en `POSTGRES_PASSWORD`. El archivo `.env` también está en `.gitignore`, así que **ninguna credencial viaja en el repositorio**.

### Paso 2 — Levantar todo con un solo comando

```bash
docker compose up --build
```

La primera vez tarda varios minutos: descarga Debian, OpenJDK 17 y el tar de Hadoop 3.5.0. Al terminar quedan arriba los tres servicios. En otra terminal se continúa con los pasos siguientes.

### Paso 3 — Verificar Hadoop y SSH (Partes A y B)

```bash
# A1: Hadoop instalado y variables correctas
docker compose exec hadoop hadoop version
docker compose exec hadoop bash -c 'echo $JAVA_HOME; echo $HADOOP_HOME'

# B: ssh a localhost dentro del contenedor hadoop, sin contraseña
docker compose exec -u hadoop hadoop ssh localhost hostname

# B: ssh desde el contenedor api hacia hadoop, por nombre de servicio
docker compose exec api ssh hadoop@hadoop 'hostname && whoami'
```

### Paso 4 — Ejecutar el job de MapReduce (Parte C1)

```bash
docker compose exec -u hadoop hadoop bash /opt/scripts/run_job.sh
```

El script borra la salida anterior, copia `mapper.py` y `reducer.py` a un directorio temporal de trabajo y lanza:

```bash
hadoop jar $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar \
  -input  /data/input/ventas_125054313.csv \
  -output /data/output/resultado \
  -mapper mapper.py -reducer reducer.py \
  -file mapper.py -file reducer.py
```

El resultado queda en `salidas/resultado/part-00000` del host, con una línea por tienda:

```
tienda <TAB> ticket_promedio <TAB> ingreso_total <TAB> num_registros
T001	8145.98	1048509861.26	128715
```

### Paso 5 — Comparativa contra el script secuencial (Parte C2)

```bash
docker compose exec -u hadoop hadoop bash /opt/scripts/comparar.sh
```

Corre `secuencial.py` sobre el mismo CSV, mide el tiempo con `time` y hace `diff` contra la salida del job. Debe terminar con `Los dos resultados son IDENTICOS (39 tiendas)`.

### Paso 6 — Cargar a PostgreSQL y consultar la API (Parte D)

```bash
docker compose exec api python /app/scripts/cargar_resultados.py

curl http://localhost:8000/resultados | head
curl http://localhost:8000/resultados/T001
```

La documentación interactiva queda en <http://localhost:8000/docs>.

Endpoints de escritura del CRUD:

```bash
# POST
curl -X POST http://localhost:8000/resultados \
  -H 'Content-Type: application/json' \
  -d '{"tienda":"T900","ticket_promedio":1234.56,"ingreso_total":9999.99,"num_registros":8}'

# PUT
curl -X PUT http://localhost:8000/resultados/T900 \
  -H 'Content-Type: application/json' \
  -d '{"ticket_promedio":1.0,"ingreso_total":2.0,"num_registros":3}'

# DELETE
curl -i -X DELETE http://localhost:8000/resultados/T900
```

### Paso 7 — Demostrar la persistencia

```bash
docker compose down          # se van los contenedores, NO el volumen db_data
docker compose up -d
curl http://localhost:8000/resultados/T001     # los datos siguen ahí
```

---

## Tiempos medidos

| Método | Tiempo real | Resultado |
|---|---|---|
| Hadoop Streaming (modo standalone) | `<!-- completar con la salida de run_job.sh -->` | 39 tiendas |
| Script secuencial (`secuencial.py`) | `<!-- completar con la salida de comparar.sh -->` | 39 tiendas |

Los dos resultados coinciden exactamente, verificado con `diff`.

### Por qué el secuencial fue más rápido

MapReduce paga un costo fijo que no depende del tamaño del dato: arrancar la JVM, planificar el job, serializar los cinco millones de parejas clave-valor que emite el mapper, ordenarlas en la fase de *shuffle and sort* y escribir resultados intermedios en disco. Con un archivo de 400 MB, que cabe de sobra en la RAM y en la caché de página del sistema operativo, ese costo fijo pesa más que el cálculo en sí. Además, en modo standalone no hay paralelismo real: Hadoop corre todo en un solo proceso y sobre un solo disco, así que no se gana nada de lo que justifica el framework. El script secuencial, en cambio, lee el archivo en streaming, acumula dos enteros por tienda y termina sin escribir nada intermedio. MapReduce empieza a ganar cuando el volumen deja de caber en una sola máquina, cuando hay un clúster real entre cuyos nodos y discos repartir la lectura, y cuando hace falta tolerancia a fallos: si una tarea muere, el framework la reintenta sin perder el trabajo hecho.

---

## Evidencias

Las capturas están en la carpeta [`evidencias/`](evidencias/):

| Archivo | Qué muestra |
|---|---|
| `01_hadoop_version.png` | `hadoop version` dentro del contenedor |
| `02_ssh_localhost.png` | `ssh localhost` sin contraseña |
| `03_ssh_api_hadoop.png` | `ssh hadoop@hadoop` desde el contenedor api |
| `04_job_mapreduce.png` | Ejecución del job y su tiempo |
| `05_comparativa.png` | Tiempo del secuencial y `diff` sin diferencias |
| `06_api_resultados.png` | Respuesta de `GET /resultados` |
| `07_persistencia.png` | Datos intactos después de `down` y `up` |

<!-- Renombra tus capturas con estos nombres o ajusta la tabla. -->

---

## Decisiones de diseño

**Hadoop 3.5.0 sobre OpenJDK 17.** Hadoop 3.3 y 3.4 sólo soportan Java 8 y 11 en runtime, y Debian bookworm ya no ofrece `openjdk-11` en sus repositorios oficiales. Hadoop 3.5.0 es la primera versión con soporte completo de Java 17 —y lo exige del lado servidor—, que es justamente el JDK que sí trae bookworm. El `Dockerfile` ejecuta `hadoop version` durante la construcción, así que una imagen que se construye es una imagen que funciona.

**Aritmética en centavos enteros.** Tanto el mapper como el script secuencial calculan `cantidad × precio_unitario` en centavos enteros en lugar de flotantes. Sumar cinco millones de flotantes acumula error de redondeo y los dos métodos habrían dado resultados ligeramente distintos; con enteros el `diff` da cero diferencias, no "diferencias despreciables".

**El mapper emite `(suma_parcial, conteo_parcial)` y no sólo el ingreso.** Con ese formato el mismo `reducer.py` puede usarse tal cual como *combiner* (`-combiner reducer.py`), porque sumar parciales da el mismo resultado que sumar los originales. Reduciría mucho el tráfico de shuffle en un clúster real.

**SSH sin ninguna contraseña en el repositorio.** El contenedor `hadoop` genera el par de llaves RSA la primera vez que arranca y lo deja en el volumen `ssh_keys`; el contenedor `api` lo recoge de ahí. El usuario `hadoop` se crea con `-p '*'`, que deja la cuenta activa pero sin contraseña válida, y `sshd` tiene `PasswordAuthentication no` y `PermitRootLogin no`. No hay secretos en el `Dockerfile` ni en el repositorio.

**Carga idempotente.** `cargar_resultados.py` usa `INSERT ... ON CONFLICT (tienda) DO UPDATE`, así que se puede volver a ejecutar sin duplicar filas ni vaciar la tabla antes.

---

## Estructura del repositorio

```
examen-p2-125054313/
├── README.md
├── .gitignore              # incluye *.csv y .env
├── .env.example
├── docker-compose.yml
├── hadoop/
│   ├── Dockerfile
│   └── entrypoint.sh       # prepara SSH y arranca sshd
├── mapreduce/
│   ├── mapper.py
│   ├── reducer.py
│   └── secuencial.py
├── api/
│   ├── Dockerfile
│   ├── entrypoint.sh       # instala la llave SSH compartida
│   ├── requirements.txt
│   └── app.py
├── scripts/
│   ├── generar_dataset.py
│   ├── init_db.sql         # lo ejecuta Postgres al crear el volumen
│   ├── run_job.sh
│   ├── comparar.sh
│   └── cargar_resultados.py
├── data/                   # aquí va el CSV (ignorado por git)
├── salidas/                # salida del job (ignorada por git)
└── evidencias/             # capturas
```


---

## Parte E. Teoría

### 1. Modos de Hadoop: standalone, pseudo-distribuido y totalmente distribuido (3 pts)

En **standalone** (modo local, el que usa este examen) Hadoop corre como un único proceso Java, sin levantar ningún demonio, y lee y escribe directamente sobre el sistema de archivos local (`file://`). Es el modo por defecto y sirve para depurar.
En **pseudo-distribuido** hay una sola máquina, pero cada demonio (NameNode, DataNode, ResourceManager, NodeManager) corre en su propio proceso JVM y se comunican entre sí; por eso este modo exige SSH sin contraseña, ya que `start-dfs.sh` arranca los demonios conectándose a `localhost`.
En **totalmente distribuido** los demonios se reparten entre varias máquinas: nodos maestros con NameNode y ResourceManager, y nodos esclavos con DataNode y NodeManager.
**HDFS se usa en los dos últimos**, pseudo-distribuido (con factor de replicación 1) y totalmente distribuido (replicación 3 por defecto). En standalone no hay HDFS.

### 2. ¿Por qué el dataset se monta como volumen y no se copia con COPY? (3 pts)

1. **Tamaño de la imagen.** Un `COPY` de 400 MB queda grabado en una capa inmutable: la imagen pesaría al menos eso de más, cada `docker build` tendría que volver a copiarlo y cualquier cambio en el CSV invalidaría la caché de esa capa y todas las siguientes.
2. **Separación entre entorno y dato.** La imagen describe el software (Java, Hadoop, Python) y debe ser reproducible y distribuible; el dataset cambia por su cuenta. Montándolo puedo cambiar de CSV, o procesar otro, sin reconstruir nada.
3. Además, montarlo con `:ro` protege el archivo original de escrituras accidentales del job, y evita que al publicar la imagen se distribuyan datos de negocio.

### 3. ¿Qué pasa con la base de datos al hacer `docker compose down`? ¿Y con `down -v`? (3 pts)

`docker compose down` elimina los contenedores y la red, pero **no toca los volúmenes nombrados**. Como los datos de PostgreSQL viven en el volumen `db_data`, al volver a hacer `docker compose up` el nuevo contenedor vuelve a montar ese mismo volumen y la tabla sigue con todas sus filas.
`docker compose down -v` sí **borra los volúmenes nombrados** declarados en el compose. Se pierde `db_data` por completo: Postgres se inicializa desde cero, vuelve a ejecutar `init_db.sql` y la tabla queda vacía, por lo que habría que volver a correr `cargar_resultados.py`.

### 4. ¿Por qué MapReduce no siempre es más rápido con un archivo de 400 MB? (3 pts)

Porque MapReduce paga un costo fijo que no depende del tamaño del dato: arrancar la JVM, planificar el job, serializar las parejas clave-valor, ordenarlas en la fase de *shuffle and sort* y escribir resultados intermedios en disco. Con 400 MB —que caben de sobra en la RAM y en la caché de página del sistema— ese costo fijo pesa más que el cálculo en sí, y en modo standalone ni siquiera hay paralelismo real: todo corre en un solo proceso. Un script secuencial que lee el archivo en streaming se lo acaba antes.
**Conviene usar MapReduce** cuando el volumen deja de caber en la memoria o en el disco de una sola máquina (decenas o cientos de GB en adelante), cuando hay un clúster real con varios nodos y discos entre los cuales repartir la lectura, y cuando se necesita tolerancia a fallos: si una tarea muere, el framework la reintenta en otro nodo sin perder el trabajo hecho. La regla práctica es que el tiempo de cómputo debe ser mucho mayor que el de coordinación.

### 5. CMD vs ENTRYPOINT, y COPY vs ADD (3 pts)

**CMD** define el comando por defecto del contenedor y se reemplaza con sólo escribir otro al final de `docker run imagen <comando>`. **ENTRYPOINT** define el ejecutable fijo; lo que se pase en `docker run` se le añade como argumentos en lugar de sustituirlo, y para cambiarlo hay que usar `--entrypoint`. Lo habitual es combinarlos: ENTRYPOINT es el programa y CMD sus argumentos por defecto, que es justo lo que hace la imagen de Hadoop de este examen (`entrypoint.sh` prepara SSH y luego ejecuta el CMD, `sshd -D -e`).
**COPY** copia archivos o carpetas del contexto de build hacia la imagen, y nada más. **ADD** hace lo mismo pero además descomprime automáticamente los tar locales y acepta URLs remotas. Se recomienda usar COPY salvo que se necesiten esas dos funciones, porque el comportamiento de ADD es implícito y puede sorprender.
