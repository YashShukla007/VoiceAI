-- Table: public.calls

DROP TABLE IF EXISTS public.calls;

CREATE TABLE IF NOT EXISTS public.calls
(
    id character varying COLLATE pg_catalog."default" NOT NULL,
    state character varying COLLATE pg_catalog."default" NOT NULL,
    last_sequence integer,
    transcript text COLLATE pg_catalog."default",
    sentiment character varying COLLATE pg_catalog."default",
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    CONSTRAINT calls_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.calls
    OWNER to postgres;