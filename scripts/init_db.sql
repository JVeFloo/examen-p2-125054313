-- ============================================================
--  Tabla donde se cargan los resultados del job de MapReduce.
--  Postgres ejecuta este archivo automaticamente la PRIMERA vez
--  que se crea el volumen db_data (docker-entrypoint-initdb.d).
--  Por eso, tras un `docker compose down -v`, vuelve a correr.
-- ============================================================

CREATE TABLE IF NOT EXISTS ticket_promedio_tienda (
    tienda          VARCHAR(10)   PRIMARY KEY,
    ticket_promedio NUMERIC(14,2) NOT NULL CHECK (ticket_promedio >= 0),
    ingreso_total   NUMERIC(18,2) NOT NULL CHECK (ingreso_total   >= 0),
    num_registros   BIGINT        NOT NULL CHECK (num_registros   >= 0),
    cargado_en      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

COMMENT ON TABLE  ticket_promedio_tienda  IS
    'Ticket promedio por tienda calculado con Hadoop MapReduce (matricula 125054313)';
COMMENT ON COLUMN ticket_promedio_tienda.ticket_promedio IS
    'Ingreso promedio por registro de venta: SUM(cantidad*precio_unitario)/COUNT(*)';

-- Orden habitual de consulta: ranking de tiendas por ticket
CREATE INDEX IF NOT EXISTS idx_ticket_promedio
    ON ticket_promedio_tienda (ticket_promedio DESC);
