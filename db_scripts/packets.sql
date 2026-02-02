-- Table: public.packets

DROP TABLE IF EXISTS public.packets;

CREATE TABLE IF NOT EXISTS public.packets
(
    id integer NOT NULL DEFAULT nextval('packets_id_seq'::regclass),
    call_id character varying COLLATE pg_catalog."default",
    sequence integer NOT NULL,
    data text COLLATE pg_catalog."default" NOT NULL,
    "timestamp" double precision NOT NULL,
    CONSTRAINT packets_pkey PRIMARY KEY (id),
    CONSTRAINT uq_call_sequence UNIQUE (call_id, sequence),
    CONSTRAINT packets_call_id_fkey FOREIGN KEY (call_id)
        REFERENCES public.calls (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.packets
    OWNER to postgres;
-- Index: ix_packets_call_id

-- DROP INDEX IF EXISTS public.ix_packets_call_id;

CREATE INDEX IF NOT EXISTS ix_packets_call_id
    ON public.packets USING btree
    (call_id COLLATE pg_catalog."default" ASC NULLS LAST)
    WITH (fillfactor=100, deduplicate_items=True)
    TABLESPACE pg_default;