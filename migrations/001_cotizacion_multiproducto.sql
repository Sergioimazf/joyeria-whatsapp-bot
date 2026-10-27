-- MIGRACIÓN PROPUESTA. NO ejecutar en producción sin revisión y aprobación.
-- Mantiene la tabla actual intacta. Cada cotización podrá incluir hasta 20 renglones.
-- El encabezado permanece en public.solicitudes_cotizacion.

BEGIN;

CREATE TABLE IF NOT EXISTS public.solicitudes_cotizacion_items (
    folio VARCHAR(48) NOT NULL
        REFERENCES public.solicitudes_cotizacion(folio) ON DELETE RESTRICT,
    posicion SMALLINT NOT NULL CHECK (posicion BETWEEN 1 AND 20),
    producto VARCHAR(200) NOT NULL,
    referencia VARCHAR(100),
    cantidad INTEGER NOT NULL CHECK (cantidad BETWEEN 1 AND 100000),
    PRIMARY KEY (folio, posicion)
);

-- El bot necesita consultar y añadir renglones, nunca borrarlos ni editarlos.
GRANT SELECT, INSERT
    ON TABLE public.solicitudes_cotizacion_items TO carnevali_rw;

COMMIT;
