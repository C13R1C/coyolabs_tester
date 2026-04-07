--
-- PostgreSQL database dump
--

\restrict bgjThpoXxfdahqJrylSVX9JGL1QKjwdSAxidVpBEesimgJ8zjtL3NFKeN6kgR9f

-- Dumped from database version 18.2
-- Dumped by pg_dump version 18.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: set_updated_at_print3d_jobs(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at_print3d_jobs() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_updated_at_print3d_jobs() OWNER TO postgres;

--
-- Name: validate_user_career_level(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validate_user_career_level() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Si ambos vienen NULL, permite (por ejemplo perfiles incompletos)
  IF NEW.career_id IS NULL OR NEW.academic_level_id IS NULL THEN
    RETURN NEW;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM career_level_rules r
    WHERE r.career_id = NEW.career_id
      AND r.academic_level_id = NEW.academic_level_id
  ) THEN
    RAISE EXCEPTION 'Combinación carrera/nivel inválida (career_id=%, academic_level_id=%)',
      NEW.career_id, NEW.academic_level_id;
  END IF;

  RETURN NEW;
END;
$$;


ALTER FUNCTION public.validate_user_career_level() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: academic_levels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.academic_levels (
    id integer NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(120) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.academic_levels OWNER TO postgres;

--
-- Name: academic_levels_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.academic_levels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.academic_levels_id_seq OWNER TO postgres;

--
-- Name: academic_levels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.academic_levels_id_seq OWNED BY public.academic_levels.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: career_level_rules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.career_level_rules (
    career_id integer NOT NULL,
    academic_level_id integer NOT NULL
);


ALTER TABLE public.career_level_rules OWNER TO postgres;

--
-- Name: careers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.careers (
    id integer NOT NULL,
    name character varying(160) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.careers OWNER TO postgres;

--
-- Name: careers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.careers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.careers_id_seq OWNER TO postgres;

--
-- Name: careers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.careers_id_seq OWNED BY public.careers.id;


--
-- Name: critical_action_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.critical_action_requests (
    id integer NOT NULL,
    requester_id integer NOT NULL,
    target_user_id integer NOT NULL,
    action_type character varying(50) NOT NULL,
    reason text,
    status character varying(20) DEFAULT 'PENDING'::character varying NOT NULL,
    reviewed_by integer,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying])::text[])))
);


ALTER TABLE public.critical_action_requests OWNER TO postgres;

--
-- Name: critical_action_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.critical_action_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.critical_action_requests_id_seq OWNER TO postgres;

--
-- Name: critical_action_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.critical_action_requests_id_seq OWNED BY public.critical_action_requests.id;


--
-- Name: debts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.debts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    material_id integer,
    status character varying(20) NOT NULL,
    reason text,
    amount numeric(10,2),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    closed_at timestamp without time zone,
    ticket_id integer,
    CONSTRAINT ck_debts_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'PAID'::character varying, 'CANCELLED'::character varying])::text[])))
);


ALTER TABLE public.debts OWNER TO postgres;

--
-- Name: debts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.debts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.debts_id_seq OWNER TO postgres;

--
-- Name: debts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.debts_id_seq OWNED BY public.debts.id;


--
-- Name: forum_comments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forum_comments (
    id integer NOT NULL,
    post_id integer NOT NULL,
    content text NOT NULL,
    is_anonymous boolean DEFAULT false NOT NULL,
    is_hidden boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    author_id integer NOT NULL,
    hidden_by integer,
    hidden_at timestamp without time zone
);


ALTER TABLE public.forum_comments OWNER TO postgres;

--
-- Name: forum_comments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.forum_comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.forum_comments_id_seq OWNER TO postgres;

--
-- Name: forum_comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.forum_comments_id_seq OWNED BY public.forum_comments.id;


--
-- Name: forum_posts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.forum_posts (
    id integer NOT NULL,
    title character varying(200) NOT NULL,
    content text NOT NULL,
    category character varying(50) DEFAULT 'GENERAL'::character varying NOT NULL,
    is_anonymous boolean DEFAULT false NOT NULL,
    is_hidden boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    author_id integer NOT NULL,
    hidden_by integer,
    hidden_at timestamp without time zone
);


ALTER TABLE public.forum_posts OWNER TO postgres;

--
-- Name: forum_posts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.forum_posts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.forum_posts_id_seq OWNER TO postgres;

--
-- Name: forum_posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.forum_posts_id_seq OWNED BY public.forum_posts.id;


--
-- Name: inventory_request_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory_request_items (
    id integer NOT NULL,
    ticket_id integer NOT NULL,
    material_id integer NOT NULL,
    quantity_requested integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.inventory_request_items OWNER TO postgres;

--
-- Name: inventory_request_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_request_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_request_items_id_seq OWNER TO postgres;

--
-- Name: inventory_request_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_request_items_id_seq OWNED BY public.inventory_request_items.id;


--
-- Name: inventory_request_tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory_request_tickets (
    id integer NOT NULL,
    user_id integer NOT NULL,
    request_date date NOT NULL,
    status character varying(30) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    ready_at timestamp without time zone,
    closed_at timestamp without time zone,
    notes text,
    CONSTRAINT ck_inventory_request_status CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'READY'::character varying, 'CLOSED'::character varying])::text[])))
);


ALTER TABLE public.inventory_request_tickets OWNER TO postgres;

--
-- Name: inventory_request_tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_request_tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_request_tickets_id_seq OWNER TO postgres;

--
-- Name: inventory_request_tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_request_tickets_id_seq OWNED BY public.inventory_request_tickets.id;


--
-- Name: lab_tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lab_tickets (
    id integer NOT NULL,
    reservation_id integer,
    owner_user_id integer,
    room character varying(120),
    date date,
    status character varying(30) DEFAULT 'OPEN'::character varying,
    opened_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    closed_at timestamp without time zone,
    opened_by_user_id integer,
    closed_by_user_id integer,
    notes text
);


ALTER TABLE public.lab_tickets OWNER TO postgres;

--
-- Name: lab_tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lab_tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_tickets_id_seq OWNER TO postgres;

--
-- Name: lab_tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lab_tickets_id_seq OWNED BY public.lab_tickets.id;


--
-- Name: labs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.labs (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.labs OWNER TO postgres;

--
-- Name: labs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.labs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.labs_id_seq OWNER TO postgres;

--
-- Name: labs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.labs_id_seq OWNED BY public.labs.id;


--
-- Name: logbook_events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.logbook_events (
    id integer NOT NULL,
    user_id integer,
    material_id integer,
    action character varying(80) NOT NULL,
    description text,
    metadata_json text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    module character varying(50),
    entity_label character varying(160)
);


ALTER TABLE public.logbook_events OWNER TO postgres;

--
-- Name: logbook_events_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.logbook_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.logbook_events_id_seq OWNER TO postgres;

--
-- Name: logbook_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.logbook_events_id_seq OWNED BY public.logbook_events.id;


--
-- Name: lost_found; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lost_found (
    id integer NOT NULL,
    reported_by_user_id integer,
    material_id integer,
    title character varying(160) NOT NULL,
    description text,
    location character varying(160),
    evidence_ref character varying(255),
    status character varying(20) NOT NULL,
    admin_note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone
);


ALTER TABLE public.lost_found OWNER TO postgres;

--
-- Name: lost_found_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lost_found_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lost_found_id_seq OWNER TO postgres;

--
-- Name: lost_found_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lost_found_id_seq OWNED BY public.lost_found.id;


--
-- Name: materials; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.materials (
    id integer NOT NULL,
    lab_id integer NOT NULL,
    name text NOT NULL,
    location text,
    status text,
    pieces_text text,
    pieces_qty integer,
    brand text,
    model text,
    code text,
    serial text,
    image_ref text,
    tutorial_url text,
    notes text,
    source_file text,
    source_sheet text,
    source_row integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    category character varying(80),
    career_id integer
);


ALTER TABLE public.materials OWNER TO postgres;

--
-- Name: materials_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.materials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.materials_id_seq OWNER TO postgres;

--
-- Name: materials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.materials_id_seq OWNED BY public.materials.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(150) NOT NULL,
    message text NOT NULL,
    link character varying(255),
    is_read boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.notifications OWNER TO postgres;

--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notifications_id_seq OWNER TO postgres;

--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: permissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.permissions (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(255)
);


ALTER TABLE public.permissions OWNER TO postgres;

--
-- Name: permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.permissions_id_seq OWNER TO postgres;

--
-- Name: permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.permissions_id_seq OWNED BY public.permissions.id;


--
-- Name: print3d_jobs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.print3d_jobs (
    id integer NOT NULL,
    requester_user_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    file_ref text NOT NULL,
    original_filename character varying(255) NOT NULL,
    file_size_bytes bigint NOT NULL,
    status character varying(50) DEFAULT 'REQUESTED'::character varying NOT NULL,
    grams_estimated numeric(10,2),
    price_per_gram numeric(10,2),
    total_estimated numeric(10,2),
    admin_note text,
    quoted_by_user_id integer,
    ready_notified_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.print3d_jobs OWNER TO postgres;

--
-- Name: print3d_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.print3d_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.print3d_jobs_id_seq OWNER TO postgres;

--
-- Name: print3d_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.print3d_jobs_id_seq OWNED BY public.print3d_jobs.id;


--
-- Name: profile_change_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.profile_change_requests (
    id integer NOT NULL,
    user_id integer NOT NULL,
    request_type character varying(30) NOT NULL,
    requested_phone character varying(30),
    requested_full_name character varying(150),
    requested_matricula character varying(30),
    requested_career_id integer,
    requested_academic_level_id integer,
    reason text,
    status character varying(20) DEFAULT 'PENDING'::character varying NOT NULL,
    reviewed_by integer,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_profile_change_requests_request_type CHECK (((request_type)::text = ANY ((ARRAY['PHONE_CHANGE'::character varying, 'PROFILE_CHANGE'::character varying])::text[]))),
    CONSTRAINT ck_profile_change_requests_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying])::text[])))
);


ALTER TABLE public.profile_change_requests OWNER TO postgres;

--
-- Name: profile_change_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.profile_change_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.profile_change_requests_id_seq OWNER TO postgres;

--
-- Name: profile_change_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.profile_change_requests_id_seq OWNED BY public.profile_change_requests.id;


--
-- Name: reservation_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reservation_items (
    id integer NOT NULL,
    reservation_id integer NOT NULL,
    material_id integer NOT NULL,
    quantity_requested integer DEFAULT 1 NOT NULL,
    notes text
);


ALTER TABLE public.reservation_items OWNER TO postgres;

--
-- Name: reservation_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reservation_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reservation_items_id_seq OWNER TO postgres;

--
-- Name: reservation_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reservation_items_id_seq OWNED BY public.reservation_items.id;


--
-- Name: reservations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reservations (
    id integer NOT NULL,
    user_id integer NOT NULL,
    room character varying(80) NOT NULL,
    date date NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    purpose text,
    status character varying(20) NOT NULL,
    admin_note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    group_name character varying(50) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    teacher_name character varying(120) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    subject character varying(120) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    signed boolean DEFAULT false NOT NULL,
    exit_time time without time zone,
    teacher_comments text,
    subject_id integer,
    signature_ref text,
    CONSTRAINT ck_reservations_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'IN_PROGRESS'::character varying, 'COMPLETED'::character varying])::text[])))
);


ALTER TABLE public.reservations OWNER TO postgres;

--
-- Name: reservations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reservations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reservations_id_seq OWNER TO postgres;

--
-- Name: reservations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reservations_id_seq OWNED BY public.reservations.id;


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.role_permissions (
    id integer NOT NULL,
    role character varying(20) NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.role_permissions OWNER TO postgres;

--
-- Name: role_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.role_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.role_permissions_id_seq OWNER TO postgres;

--
-- Name: role_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.role_permissions_id_seq OWNED BY public.role_permissions.id;


--
-- Name: software; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.software (
    id integer NOT NULL,
    lab_id integer,
    name character varying(160) NOT NULL,
    version character varying(60),
    license_type character varying(60),
    notes text,
    update_requested boolean NOT NULL,
    update_note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone
);


ALTER TABLE public.software OWNER TO postgres;

--
-- Name: software_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.software_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.software_id_seq OWNER TO postgres;

--
-- Name: software_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.software_id_seq OWNED BY public.software.id;


--
-- Name: subjects; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.subjects (
    id integer NOT NULL,
    career_id integer NOT NULL,
    level character varying(10) NOT NULL,
    quarter integer NOT NULL,
    name character varying(160) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    academic_level_id integer
);


ALTER TABLE public.subjects OWNER TO postgres;

--
-- Name: subjects_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.subjects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subjects_id_seq OWNER TO postgres;

--
-- Name: subjects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.subjects_id_seq OWNED BY public.subjects.id;


--
-- Name: teacher_academic_loads; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.teacher_academic_loads (
    id integer NOT NULL,
    teacher_id integer NOT NULL,
    subject_id integer NOT NULL,
    group_code character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.teacher_academic_loads OWNER TO postgres;

--
-- Name: teacher_academic_loads_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.teacher_academic_loads_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.teacher_academic_loads_id_seq OWNER TO postgres;

--
-- Name: teacher_academic_loads_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.teacher_academic_loads_id_seq OWNED BY public.teacher_academic_loads.id;


--
-- Name: ticket_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_items (
    id integer NOT NULL,
    ticket_id integer,
    material_id integer,
    quantity_requested integer DEFAULT 0,
    quantity_delivered integer DEFAULT 0,
    quantity_returned integer DEFAULT 0,
    status character varying(30) DEFAULT 'REQUESTED'::character varying,
    notes text,
    CONSTRAINT ck_ticket_items_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'DELIVERED'::character varying, 'RETURNED'::character varying])::text[])))
);


ALTER TABLE public.ticket_items OWNER TO postgres;

--
-- Name: ticket_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ticket_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ticket_items_id_seq OWNER TO postgres;

--
-- Name: ticket_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ticket_items_id_seq OWNED BY public.ticket_items.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    is_verified boolean NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    verified_at timestamp without time zone,
    profile_completed boolean DEFAULT false NOT NULL,
    full_name character varying(150),
    matricula character varying(30),
    career character varying(120),
    career_year integer,
    phone character varying(30),
    professor_subjects text,
    is_active boolean DEFAULT true NOT NULL,
    is_banned boolean DEFAULT false NOT NULL,
    career_id integer,
    academic_level character varying(10),
    academic_level_id integer,
    profile_data_confirmed boolean DEFAULT false NOT NULL,
    profile_confirmed_at timestamp without time zone,
    current_quarter integer,
    email_verification_code character varying(6),
    email_verification_expires_at timestamp without time zone,
    verification_sent_at timestamp without time zone,
    verify_token_version integer DEFAULT 1,
    email_change_count integer DEFAULT 0,
    email_change_window_started_at timestamp without time zone,
    CONSTRAINT check_current_quarter CHECK (((current_quarter >= 1) AND (current_quarter <= 12)))
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: academic_levels id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.academic_levels ALTER COLUMN id SET DEFAULT nextval('public.academic_levels_id_seq'::regclass);


--
-- Name: careers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.careers ALTER COLUMN id SET DEFAULT nextval('public.careers_id_seq'::regclass);


--
-- Name: critical_action_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.critical_action_requests ALTER COLUMN id SET DEFAULT nextval('public.critical_action_requests_id_seq'::regclass);


--
-- Name: debts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debts ALTER COLUMN id SET DEFAULT nextval('public.debts_id_seq'::regclass);


--
-- Name: forum_comments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_comments ALTER COLUMN id SET DEFAULT nextval('public.forum_comments_id_seq'::regclass);


--
-- Name: forum_posts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_posts ALTER COLUMN id SET DEFAULT nextval('public.forum_posts_id_seq'::regclass);


--
-- Name: inventory_request_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_items ALTER COLUMN id SET DEFAULT nextval('public.inventory_request_items_id_seq'::regclass);


--
-- Name: inventory_request_tickets id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_tickets ALTER COLUMN id SET DEFAULT nextval('public.inventory_request_tickets_id_seq'::regclass);


--
-- Name: lab_tickets id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lab_tickets ALTER COLUMN id SET DEFAULT nextval('public.lab_tickets_id_seq'::regclass);


--
-- Name: labs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.labs ALTER COLUMN id SET DEFAULT nextval('public.labs_id_seq'::regclass);


--
-- Name: logbook_events id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.logbook_events ALTER COLUMN id SET DEFAULT nextval('public.logbook_events_id_seq'::regclass);


--
-- Name: lost_found id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lost_found ALTER COLUMN id SET DEFAULT nextval('public.lost_found_id_seq'::regclass);


--
-- Name: materials id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.materials ALTER COLUMN id SET DEFAULT nextval('public.materials_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: permissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions ALTER COLUMN id SET DEFAULT nextval('public.permissions_id_seq'::regclass);


--
-- Name: print3d_jobs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.print3d_jobs ALTER COLUMN id SET DEFAULT nextval('public.print3d_jobs_id_seq'::regclass);


--
-- Name: profile_change_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profile_change_requests ALTER COLUMN id SET DEFAULT nextval('public.profile_change_requests_id_seq'::regclass);


--
-- Name: reservation_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservation_items ALTER COLUMN id SET DEFAULT nextval('public.reservation_items_id_seq'::regclass);


--
-- Name: reservations id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservations ALTER COLUMN id SET DEFAULT nextval('public.reservations_id_seq'::regclass);


--
-- Name: role_permissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions ALTER COLUMN id SET DEFAULT nextval('public.role_permissions_id_seq'::regclass);


--
-- Name: software id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.software ALTER COLUMN id SET DEFAULT nextval('public.software_id_seq'::regclass);


--
-- Name: subjects id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subjects ALTER COLUMN id SET DEFAULT nextval('public.subjects_id_seq'::regclass);


--
-- Name: teacher_academic_loads id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher_academic_loads ALTER COLUMN id SET DEFAULT nextval('public.teacher_academic_loads_id_seq'::regclass);


--
-- Name: ticket_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_items ALTER COLUMN id SET DEFAULT nextval('public.ticket_items_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: academic_levels; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.academic_levels (id, code, name, is_active, created_at) FROM stdin;
1	TSU	Técnico Superior Universitario	t	2026-03-27 22:35:33.112334
2	ING	Ingeniería	t	2026-03-27 22:35:33.112334
3	LIC	Licenciatura	t	2026-03-27 22:35:33.112334
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
3fa529b8f6a0
\.


--
-- Data for Name: career_level_rules; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.career_level_rules (career_id, academic_level_id) FROM stdin;
1	1
2	1
3	1
4	1
5	1
6	1
7	1
1	2
2	2
3	2
4	2
5	2
6	2
7	2
1	3
2	3
3	3
4	3
5	3
6	3
7	3
\.


--
-- Data for Name: careers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.careers (id, name, created_at) FROM stdin;
1	ING. EN MECATRÓNICA	2026-03-27 22:35:33.144122
2	LIC. EN ADMINISTRACIÓN	2026-03-27 22:35:33.144122
3	ING. EN TECNOLOGÍAS DE LA INFORMACIÓN E INNOVACIÓN DIGITAL	2026-03-27 22:35:33.144122
4	ING. EN LOGÍSTICA INTERNACIONAL	2026-03-27 22:35:33.144122
5	ING INDUSTRIAL	2026-03-27 22:35:33.144122
6	LIC. EN ARQUITECTURA	2026-03-27 22:35:33.144122
7	LIC EN CONTADURÍA	2026-03-27 22:35:33.144122
\.


--
-- Data for Name: critical_action_requests; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.critical_action_requests (id, requester_id, target_user_id, action_type, reason, status, reviewed_by, reviewed_at, created_at) FROM stdin;
\.


--
-- Data for Name: debts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.debts (id, user_id, material_id, status, reason, amount, created_at, closed_at, ticket_id) FROM stdin;
6	4	162	PENDING	Faltante de 1 unidad(es) en ticket #2 - Test 161	1.00	2026-04-06 19:21:20.177023	\N	2
\.


--
-- Data for Name: forum_comments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.forum_comments (id, post_id, content, is_anonymous, is_hidden, created_at, updated_at, author_id, hidden_by, hidden_at) FROM stdin;
\.


--
-- Data for Name: forum_posts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.forum_posts (id, title, content, category, is_anonymous, is_hidden, created_at, updated_at, author_id, hidden_by, hidden_at) FROM stdin;
\.


--
-- Data for Name: inventory_request_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.inventory_request_items (id, ticket_id, material_id, quantity_requested, created_at) FROM stdin;
\.


--
-- Data for Name: inventory_request_tickets; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.inventory_request_tickets (id, user_id, request_date, status, created_at, updated_at, ready_at, closed_at, notes) FROM stdin;
\.


--
-- Data for Name: lab_tickets; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.lab_tickets (id, reservation_id, owner_user_id, room, date, status, opened_at, closed_at, opened_by_user_id, closed_by_user_id, notes) FROM stdin;
1	3	4	B004	2026-04-06	CLOSED	2026-04-06 15:29:12.140945	2026-04-06 18:31:35.830053	1	1	Ticket generado desde reserva #3
2	4	4	B003	2026-04-06	CLOSED_WITH_DEBT	2026-04-06 18:40:48.148011	2026-04-06 19:21:20.204727	1	1	Ticket generado desde reserva #4
3	4	4	B003	2026-04-06	CLOSED	2026-04-06 19:21:35.572614	2026-04-06 19:21:57.627061	1	1	Ticket generado desde reserva #4
\.


--
-- Data for Name: labs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.labs (id, name, created_at) FROM stdin;
2	Procesos Industriales	2026-04-06 11:27:31.474159
3	Química	2026-04-06 11:27:31.474159
4	Mecatrónica	2026-04-06 11:27:31.474159
5	Logística	2026-04-06 11:27:31.474159
6	Admón	2026-04-06 11:27:31.474159
7	Redes y Soporte	2026-04-06 11:27:31.474159
\.


--
-- Data for Name: logbook_events; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.logbook_events (id, user_id, material_id, action, description, metadata_json, created_at, module, entity_label) FROM stdin;
1	1	\N	PASSWORD_CHANGED	Cambio de contraseña realizado por el usuario	{"self_service": true}	2026-04-04 23:41:39.552928	PROFILE	User #1
2	1	\N	PASSWORD_CHANGED	Cambio de contraseña realizado por el usuario	{"self_service": true}	2026-04-04 23:41:48.228203	PROFILE	User #1
3	1	\N	PROFILE_UPDATED	Actualización de perfil por el usuario	{"changed_fields": ["full_name", "phone"], "blocked_fields_attempted": []}	2026-04-05 00:38:29.789107	PROFILE	User #1
4	1	1	MATERIAL_CREATED	Material creado: Test 1	{"material_id": 1, "lab_id": 5, "career_id": 4, "status": "Disponible", "category": "HERRAMIENTA"}	2026-04-06 11:48:08.24488	INVENTORY	Material #1
5	1	1	MATERIAL_UPDATED	Material actualizado: Test 1	{"material_id": 1, "career_id": 4, "old_status": "Disponible", "new_status": "Disponible", "category": "HERRAMIENTA"}	2026-04-06 11:49:55.41063	INVENTORY	Material #1
6	1	\N	USER_UPDATED	superadmin@utpn.edu.mx actualizó usuario student@test.com	{"user_id": 4, "old": {"email": "student@test.com", "full_name": "Test Student", "matricula": "20230001", "phone": "6561111111", "role": "STUDENT", "is_active": true, "is_banned": false}, "new_role": "TEACHER"}	2026-04-06 12:05:14.449878	USERS	AdminAction by superadmin@utpn.edu.mx
7	1	\N	USER_UPDATED	superadmin@utpn.edu.mx actualizó usuario student@test.com	{"user_id": 4, "old": {"email": "student@test.com", "full_name": "Test Student", "matricula": "20230001", "phone": "6561111111", "role": "TEACHER", "is_active": true, "is_banned": false}, "new_role": "STUDENT"}	2026-04-06 12:05:29.735353	USERS	AdminAction by superadmin@utpn.edu.mx
8	1	\N	PASSWORD_CHANGED	Cambio de contraseña realizado por el usuario	{"self_service": true}	2026-04-06 12:13:20.598549	PROFILE	User #1
9	1	\N	PROFILE_UPDATED	Actualización de perfil por el usuario	{"changed_fields": ["full_name", "phone"], "blocked_fields_attempted": []}	2026-04-06 12:14:10.696808	PROFILE	User #1
10	4	\N	RESERVATION_CREATED	Reserva creada para B002 2026-04-06 15:30:00-16:00:00	{"reservation_id": 2, "room": "B002", "status": "PENDING"}	2026-04-06 15:05:45.276113	RESERVATIONS	Reservation #2
11	1	\N	RESERVATION_REJECTED	Reserva #2 rechazada	{"reservation_id": 2, "target_user_id": 4}	2026-04-06 15:08:46.428889	RESERVATIONS	Reservation #2
12	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 2, "entity_id": 2, "result": "success"}	2026-04-06 15:09:19.09443	NOTIFICATIONS	Notification #2
13	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 2, "entity_id": 2, "result": "success"}	2026-04-06 15:09:21.821187	NOTIFICATIONS	Notification #2
14	1	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 1, "entity_id": 1, "result": "success"}	2026-04-06 15:09:35.624825	NOTIFICATIONS	Notification #1
15	4	\N	RESERVATION_CREATED	Reserva creada para B004 2026-04-06 15:30:00-16:00:00	{"reservation_id": 3, "room": "B004", "status": "PENDING"}	2026-04-06 15:28:28.064147	RESERVATIONS	Reservation #3
16	1	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 1, "entity_id": 1, "result": "success"}	2026-04-06 15:28:39.794147	NOTIFICATIONS	Notification #1
17	1	\N	RESERVATION_APPROVED	Reserva #3 aprobada	{"reservation_id": 3, "target_user_id": 4}	2026-04-06 15:28:49.29609	RESERVATIONS	Reservation #3
18	1	\N	LAB_TICKET_OPENED	Ticket abierto desde reserva #3	{"ticket_id": 1, "reservation_id": 3, "owner_user_id": 4}	2026-04-06 15:29:12.140945	LAB_TICKETS	LabTicket #1
19	4	162	LAB_TICKET_ITEM_REQUESTED_BY_USER	Usuario agregó material al ticket activo #1	{"ticket_id": 1, "material_id": 162, "quantity_added": 2}	2026-04-06 16:00:15.424544	LAB_TICKETS	LabTicket #1
20	4	163	LAB_TICKET_ITEM_REQUESTED_BY_USER	Usuario agregó material al ticket activo #1	{"ticket_id": 1, "material_id": 163, "quantity_added": 2}	2026-04-06 16:00:29.964435	LAB_TICKETS	LabTicket #1
21	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 8, "entity_id": 8, "result": "success"}	2026-04-06 17:42:11.526416	NOTIFICATIONS	Notification #8
22	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 5, "entity_id": 5, "result": "success"}	2026-04-06 17:42:12.566824	NOTIFICATIONS	Notification #5
23	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 4, "entity_id": 4, "result": "success"}	2026-04-06 17:42:15.18189	NOTIFICATIONS	Notification #4
24	1	\N	LAB_TICKET_CLOSED	Ticket #1 cerrado con estado CLOSED	{"ticket_id": 1, "entity_id": 1, "result": "success", "owner_user_id": 4, "previous_status": "OPEN", "new_status": "CLOSED", "created_debt_ids": []}	2026-04-06 18:31:35.827245	LAB_TICKETS	LabTicket #1
25	4	\N	RESERVATION_CREATED	Reserva creada para B003 2026-04-06 19:00:00-19:30:00	{"reservation_id": 4, "room": "B003", "status": "PENDING"}	2026-04-06 18:38:33.438913	RESERVATIONS	Reservation #4
26	1	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 12, "entity_id": 12, "result": "success"}	2026-04-06 18:38:52.952651	NOTIFICATIONS	Notification #12
27	1	\N	RESERVATION_APPROVED	Reserva #4 aprobada	{"reservation_id": 4, "target_user_id": 4}	2026-04-06 18:38:55.975309	RESERVATIONS	Reservation #4
28	1	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 12, "entity_id": 12, "result": "success"}	2026-04-06 18:39:22.049373	NOTIFICATIONS	Notification #12
29	1	\N	LAB_TICKET_OPENED	Ticket abierto desde reserva #4	{"ticket_id": 2, "reservation_id": 4, "owner_user_id": 4}	2026-04-06 18:40:48.148011	LAB_TICKETS	LabTicket #2
30	4	162	LAB_TICKET_ITEM_REQUESTED_BY_USER	Usuario agregó material al ticket activo #2	{"ticket_id": 2, "material_id": 162, "quantity_added": 2}	2026-04-06 18:41:04.51845	LAB_TICKETS	LabTicket #2
31	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 18, "entity_id": 18, "result": "success"}	2026-04-06 18:41:47.445095	NOTIFICATIONS	Notification #18
32	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 17, "entity_id": 17, "result": "success"}	2026-04-06 18:41:48.331426	NOTIFICATIONS	Notification #17
33	4	\N	NOTIFICATION_MARKED_READ	Usuario marcó notificación como leída	{"notification_id": 18, "entity_id": 18, "result": "success"}	2026-04-06 18:42:05.421795	NOTIFICATIONS	Notification #18
34	1	162	DEBT_CREATED	Adeudo generado automáticamente por faltante en ticket #2	{"debt_id": 6, "entity_id": 6, "result": "success", "ticket_id": 2, "target_user_id": 4, "material_id": 162, "missing_qty": 1, "origin": "LAB_TICKET_CLOSE"}	2026-04-06 19:21:20.177023	DEBTS	Debt #6
35	1	\N	LAB_TICKET_CLOSED	Ticket #2 cerrado con estado CLOSED_WITH_DEBT	{"ticket_id": 2, "entity_id": 2, "result": "success", "owner_user_id": 4, "previous_status": "READY_FOR_PICKUP", "new_status": "CLOSED_WITH_DEBT", "created_debt_ids": [6]}	2026-04-06 19:21:20.177023	LAB_TICKETS	LabTicket #2
36	1	\N	LAB_TICKET_OPENED	Ticket abierto desde reserva #4	{"ticket_id": 3, "reservation_id": 4, "owner_user_id": 4}	2026-04-06 19:21:35.572614	LAB_TICKETS	LabTicket #3
37	1	\N	LAB_TICKET_CLOSED	Ticket #3 cerrado con estado CLOSED	{"ticket_id": 3, "entity_id": 3, "result": "success", "owner_user_id": 4, "previous_status": "OPEN", "new_status": "CLOSED", "created_debt_ids": []}	2026-04-06 19:21:57.623851	LAB_TICKETS	LabTicket #3
\.


--
-- Data for Name: lost_found; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.lost_found (id, reported_by_user_id, material_id, title, description, location, evidence_ref, status, admin_note, created_at, updated_at) FROM stdin;
1	1	\N	Curriculum	Negra	\N	uploads\\lostfound/a29908485c66435e8f215bb551b61909.png	REPORTED	\N	2026-04-06 11:38:05.917132	\N
\.


--
-- Data for Name: materials; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.materials (id, lab_id, name, location, status, pieces_text, pieces_qty, brand, model, code, serial, image_ref, tutorial_url, notes, source_file, source_sheet, source_row, created_at, updated_at, category, career_id) FROM stdin;
1	5	Test 1	aqui	Disponible	2	2	Test 1	Test 1	123	321	\N	https://www.steren.com.mx/adaptador-usb-a-ethernet-rj45.html	buen estado	\N	\N	\N	2026-04-06 11:48:08.24488	2026-04-06 11:49:55.41063	HERRAMIENTA	4
2	2	Test 1	Estante A	Disponible	Piezas varias	5	TestBrand	Model-1	CODE-1	SERIAL-1	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
3	2	Test 2	Estante A	Disponible	Piezas varias	4	TestBrand	Model-2	CODE-2	SERIAL-2	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
4	2	Test 3	Estante A	Disponible	Piezas varias	4	TestBrand	Model-3	CODE-3	SERIAL-3	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
5	2	Test 4	Estante A	Disponible	Piezas varias	3	TestBrand	Model-4	CODE-4	SERIAL-4	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
6	2	Test 5	Estante A	Disponible	Piezas varias	1	TestBrand	Model-5	CODE-5	SERIAL-5	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
7	2	Test 6	Estante A	Disponible	Piezas varias	3	TestBrand	Model-6	CODE-6	SERIAL-6	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
8	2	Test 7	Estante A	Disponible	Piezas varias	5	TestBrand	Model-7	CODE-7	SERIAL-7	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
9	2	Test 8	Estante A	Disponible	Piezas varias	2	TestBrand	Model-8	CODE-8	SERIAL-8	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
10	2	Test 9	Estante A	Disponible	Piezas varias	4	TestBrand	Model-9	CODE-9	SERIAL-9	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
11	2	Test 10	Estante A	Disponible	Piezas varias	4	TestBrand	Model-10	CODE-10	SERIAL-10	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	1
12	2	Test 11	Estante A	Disponible	Piezas varias	1	TestBrand	Model-11	CODE-11	SERIAL-11	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
13	2	Test 12	Estante A	Disponible	Piezas varias	4	TestBrand	Model-12	CODE-12	SERIAL-12	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
14	2	Test 13	Estante A	Disponible	Piezas varias	4	TestBrand	Model-13	CODE-13	SERIAL-13	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
15	2	Test 14	Estante A	Disponible	Piezas varias	4	TestBrand	Model-14	CODE-14	SERIAL-14	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
16	2	Test 15	Estante A	Disponible	Piezas varias	4	TestBrand	Model-15	CODE-15	SERIAL-15	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
17	2	Test 16	Estante A	Disponible	Piezas varias	3	TestBrand	Model-16	CODE-16	SERIAL-16	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
18	2	Test 17	Estante A	Disponible	Piezas varias	3	TestBrand	Model-17	CODE-17	SERIAL-17	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
19	2	Test 18	Estante A	Disponible	Piezas varias	4	TestBrand	Model-18	CODE-18	SERIAL-18	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
20	2	Test 19	Estante A	Disponible	Piezas varias	2	TestBrand	Model-19	CODE-19	SERIAL-19	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
21	2	Test 20	Estante A	Disponible	Piezas varias	4	TestBrand	Model-20	CODE-20	SERIAL-20	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	2
22	2	Test 21	Estante A	Disponible	Piezas varias	2	TestBrand	Model-21	CODE-21	SERIAL-21	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
23	2	Test 22	Estante A	Disponible	Piezas varias	3	TestBrand	Model-22	CODE-22	SERIAL-22	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
24	2	Test 23	Estante A	Disponible	Piezas varias	2	TestBrand	Model-23	CODE-23	SERIAL-23	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
25	2	Test 24	Estante A	Disponible	Piezas varias	2	TestBrand	Model-24	CODE-24	SERIAL-24	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
26	2	Test 25	Estante A	Disponible	Piezas varias	3	TestBrand	Model-25	CODE-25	SERIAL-25	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
27	2	Test 26	Estante A	Disponible	Piezas varias	2	TestBrand	Model-26	CODE-26	SERIAL-26	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
28	2	Test 27	Estante A	Disponible	Piezas varias	4	TestBrand	Model-27	CODE-27	SERIAL-27	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
29	2	Test 28	Estante A	Disponible	Piezas varias	4	TestBrand	Model-28	CODE-28	SERIAL-28	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
30	2	Test 29	Estante A	Disponible	Piezas varias	4	TestBrand	Model-29	CODE-29	SERIAL-29	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
31	2	Test 30	Estante A	Disponible	Piezas varias	2	TestBrand	Model-30	CODE-30	SERIAL-30	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	3
32	2	Test 31	Estante A	Disponible	Piezas varias	4	TestBrand	Model-31	CODE-31	SERIAL-31	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
33	2	Test 32	Estante A	Disponible	Piezas varias	4	TestBrand	Model-32	CODE-32	SERIAL-32	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
34	2	Test 33	Estante A	Disponible	Piezas varias	3	TestBrand	Model-33	CODE-33	SERIAL-33	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
35	2	Test 34	Estante A	Disponible	Piezas varias	3	TestBrand	Model-34	CODE-34	SERIAL-34	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
36	2	Test 35	Estante A	Disponible	Piezas varias	2	TestBrand	Model-35	CODE-35	SERIAL-35	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
37	2	Test 36	Estante A	Disponible	Piezas varias	4	TestBrand	Model-36	CODE-36	SERIAL-36	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
38	2	Test 37	Estante A	Disponible	Piezas varias	2	TestBrand	Model-37	CODE-37	SERIAL-37	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
39	2	Test 38	Estante A	Disponible	Piezas varias	1	TestBrand	Model-38	CODE-38	SERIAL-38	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
40	2	Test 39	Estante A	Disponible	Piezas varias	3	TestBrand	Model-39	CODE-39	SERIAL-39	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
41	2	Test 40	Estante A	Disponible	Piezas varias	5	TestBrand	Model-40	CODE-40	SERIAL-40	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	4
42	2	Test 41	Estante A	Disponible	Piezas varias	4	TestBrand	Model-41	CODE-41	SERIAL-41	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
43	2	Test 42	Estante A	Disponible	Piezas varias	2	TestBrand	Model-42	CODE-42	SERIAL-42	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
44	2	Test 43	Estante A	Disponible	Piezas varias	1	TestBrand	Model-43	CODE-43	SERIAL-43	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
45	2	Test 44	Estante A	Disponible	Piezas varias	4	TestBrand	Model-44	CODE-44	SERIAL-44	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
46	2	Test 45	Estante A	Disponible	Piezas varias	4	TestBrand	Model-45	CODE-45	SERIAL-45	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
47	2	Test 46	Estante A	Disponible	Piezas varias	5	TestBrand	Model-46	CODE-46	SERIAL-46	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
48	2	Test 47	Estante A	Disponible	Piezas varias	4	TestBrand	Model-47	CODE-47	SERIAL-47	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
49	2	Test 48	Estante A	Disponible	Piezas varias	4	TestBrand	Model-48	CODE-48	SERIAL-48	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
50	2	Test 49	Estante A	Disponible	Piezas varias	1	TestBrand	Model-49	CODE-49	SERIAL-49	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
51	2	Test 50	Estante A	Disponible	Piezas varias	3	TestBrand	Model-50	CODE-50	SERIAL-50	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	5
52	2	Test 51	Estante A	Disponible	Piezas varias	1	TestBrand	Model-51	CODE-51	SERIAL-51	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
53	2	Test 52	Estante A	Disponible	Piezas varias	3	TestBrand	Model-52	CODE-52	SERIAL-52	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
54	2	Test 53	Estante A	Disponible	Piezas varias	4	TestBrand	Model-53	CODE-53	SERIAL-53	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
55	2	Test 54	Estante A	Disponible	Piezas varias	4	TestBrand	Model-54	CODE-54	SERIAL-54	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
56	2	Test 55	Estante A	Disponible	Piezas varias	3	TestBrand	Model-55	CODE-55	SERIAL-55	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
57	2	Test 56	Estante A	Disponible	Piezas varias	3	TestBrand	Model-56	CODE-56	SERIAL-56	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
58	2	Test 57	Estante A	Disponible	Piezas varias	4	TestBrand	Model-57	CODE-57	SERIAL-57	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
59	2	Test 58	Estante A	Disponible	Piezas varias	4	TestBrand	Model-58	CODE-58	SERIAL-58	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
60	2	Test 59	Estante A	Disponible	Piezas varias	2	TestBrand	Model-59	CODE-59	SERIAL-59	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
61	2	Test 60	Estante A	Disponible	Piezas varias	2	TestBrand	Model-60	CODE-60	SERIAL-60	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	6
62	2	Test 61	Estante A	Disponible	Piezas varias	2	TestBrand	Model-61	CODE-61	SERIAL-61	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
63	2	Test 62	Estante A	Disponible	Piezas varias	3	TestBrand	Model-62	CODE-62	SERIAL-62	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
64	2	Test 63	Estante A	Disponible	Piezas varias	1	TestBrand	Model-63	CODE-63	SERIAL-63	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
65	2	Test 64	Estante A	Disponible	Piezas varias	2	TestBrand	Model-64	CODE-64	SERIAL-64	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
66	2	Test 65	Estante A	Disponible	Piezas varias	4	TestBrand	Model-65	CODE-65	SERIAL-65	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
67	2	Test 66	Estante A	Disponible	Piezas varias	5	TestBrand	Model-66	CODE-66	SERIAL-66	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
68	2	Test 67	Estante A	Disponible	Piezas varias	1	TestBrand	Model-67	CODE-67	SERIAL-67	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
69	2	Test 68	Estante A	Disponible	Piezas varias	1	TestBrand	Model-68	CODE-68	SERIAL-68	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
70	2	Test 69	Estante A	Disponible	Piezas varias	3	TestBrand	Model-69	CODE-69	SERIAL-69	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
71	2	Test 70	Estante A	Disponible	Piezas varias	1	TestBrand	Model-70	CODE-70	SERIAL-70	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	HERRAMIENTA	7
72	3	Test 71	Estante A	Disponible	Piezas varias	4	TestBrand	Model-71	CODE-71	SERIAL-71	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
73	3	Test 72	Estante A	Disponible	Piezas varias	2	TestBrand	Model-72	CODE-72	SERIAL-72	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
74	3	Test 73	Estante A	Disponible	Piezas varias	5	TestBrand	Model-73	CODE-73	SERIAL-73	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
75	3	Test 74	Estante A	Disponible	Piezas varias	3	TestBrand	Model-74	CODE-74	SERIAL-74	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
76	3	Test 75	Estante A	Disponible	Piezas varias	4	TestBrand	Model-75	CODE-75	SERIAL-75	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
77	3	Test 76	Estante A	Disponible	Piezas varias	5	TestBrand	Model-76	CODE-76	SERIAL-76	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
78	3	Test 77	Estante A	Disponible	Piezas varias	4	TestBrand	Model-77	CODE-77	SERIAL-77	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
79	3	Test 78	Estante A	Disponible	Piezas varias	4	TestBrand	Model-78	CODE-78	SERIAL-78	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
80	3	Test 79	Estante A	Disponible	Piezas varias	4	TestBrand	Model-79	CODE-79	SERIAL-79	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
81	3	Test 80	Estante A	Disponible	Piezas varias	4	TestBrand	Model-80	CODE-80	SERIAL-80	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	1
82	3	Test 81	Estante A	Disponible	Piezas varias	3	TestBrand	Model-81	CODE-81	SERIAL-81	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
83	3	Test 82	Estante A	Disponible	Piezas varias	2	TestBrand	Model-82	CODE-82	SERIAL-82	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
84	3	Test 83	Estante A	Disponible	Piezas varias	3	TestBrand	Model-83	CODE-83	SERIAL-83	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
85	3	Test 84	Estante A	Disponible	Piezas varias	5	TestBrand	Model-84	CODE-84	SERIAL-84	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
86	3	Test 85	Estante A	Disponible	Piezas varias	4	TestBrand	Model-85	CODE-85	SERIAL-85	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
87	3	Test 86	Estante A	Disponible	Piezas varias	1	TestBrand	Model-86	CODE-86	SERIAL-86	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
88	3	Test 87	Estante A	Disponible	Piezas varias	2	TestBrand	Model-87	CODE-87	SERIAL-87	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
89	3	Test 88	Estante A	Disponible	Piezas varias	2	TestBrand	Model-88	CODE-88	SERIAL-88	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
90	3	Test 89	Estante A	Disponible	Piezas varias	3	TestBrand	Model-89	CODE-89	SERIAL-89	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
91	3	Test 90	Estante A	Disponible	Piezas varias	2	TestBrand	Model-90	CODE-90	SERIAL-90	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	2
92	3	Test 91	Estante A	Disponible	Piezas varias	2	TestBrand	Model-91	CODE-91	SERIAL-91	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
93	3	Test 92	Estante A	Disponible	Piezas varias	2	TestBrand	Model-92	CODE-92	SERIAL-92	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
94	3	Test 93	Estante A	Disponible	Piezas varias	3	TestBrand	Model-93	CODE-93	SERIAL-93	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
95	3	Test 94	Estante A	Disponible	Piezas varias	3	TestBrand	Model-94	CODE-94	SERIAL-94	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
96	3	Test 95	Estante A	Disponible	Piezas varias	4	TestBrand	Model-95	CODE-95	SERIAL-95	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
97	3	Test 96	Estante A	Disponible	Piezas varias	3	TestBrand	Model-96	CODE-96	SERIAL-96	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
98	3	Test 97	Estante A	Disponible	Piezas varias	4	TestBrand	Model-97	CODE-97	SERIAL-97	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
99	3	Test 98	Estante A	Disponible	Piezas varias	4	TestBrand	Model-98	CODE-98	SERIAL-98	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
100	3	Test 99	Estante A	Disponible	Piezas varias	1	TestBrand	Model-99	CODE-99	SERIAL-99	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
101	3	Test 100	Estante A	Disponible	Piezas varias	4	TestBrand	Model-100	CODE-100	SERIAL-100	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	3
102	3	Test 101	Estante A	Disponible	Piezas varias	2	TestBrand	Model-101	CODE-101	SERIAL-101	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
103	3	Test 102	Estante A	Disponible	Piezas varias	4	TestBrand	Model-102	CODE-102	SERIAL-102	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
104	3	Test 103	Estante A	Disponible	Piezas varias	3	TestBrand	Model-103	CODE-103	SERIAL-103	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
105	3	Test 104	Estante A	Disponible	Piezas varias	2	TestBrand	Model-104	CODE-104	SERIAL-104	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
106	3	Test 105	Estante A	Disponible	Piezas varias	5	TestBrand	Model-105	CODE-105	SERIAL-105	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
107	3	Test 106	Estante A	Disponible	Piezas varias	1	TestBrand	Model-106	CODE-106	SERIAL-106	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
108	3	Test 107	Estante A	Disponible	Piezas varias	3	TestBrand	Model-107	CODE-107	SERIAL-107	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
109	3	Test 108	Estante A	Disponible	Piezas varias	3	TestBrand	Model-108	CODE-108	SERIAL-108	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
110	3	Test 109	Estante A	Disponible	Piezas varias	3	TestBrand	Model-109	CODE-109	SERIAL-109	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
111	3	Test 110	Estante A	Disponible	Piezas varias	5	TestBrand	Model-110	CODE-110	SERIAL-110	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	4
112	3	Test 111	Estante A	Disponible	Piezas varias	2	TestBrand	Model-111	CODE-111	SERIAL-111	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
113	3	Test 112	Estante A	Disponible	Piezas varias	3	TestBrand	Model-112	CODE-112	SERIAL-112	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
114	3	Test 113	Estante A	Disponible	Piezas varias	5	TestBrand	Model-113	CODE-113	SERIAL-113	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
115	3	Test 114	Estante A	Disponible	Piezas varias	5	TestBrand	Model-114	CODE-114	SERIAL-114	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
116	3	Test 115	Estante A	Disponible	Piezas varias	2	TestBrand	Model-115	CODE-115	SERIAL-115	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
117	3	Test 116	Estante A	Disponible	Piezas varias	3	TestBrand	Model-116	CODE-116	SERIAL-116	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
118	3	Test 117	Estante A	Disponible	Piezas varias	1	TestBrand	Model-117	CODE-117	SERIAL-117	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
119	3	Test 118	Estante A	Disponible	Piezas varias	3	TestBrand	Model-118	CODE-118	SERIAL-118	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
120	3	Test 119	Estante A	Disponible	Piezas varias	2	TestBrand	Model-119	CODE-119	SERIAL-119	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
121	3	Test 120	Estante A	Disponible	Piezas varias	5	TestBrand	Model-120	CODE-120	SERIAL-120	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	5
122	3	Test 121	Estante A	Disponible	Piezas varias	5	TestBrand	Model-121	CODE-121	SERIAL-121	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
123	3	Test 122	Estante A	Disponible	Piezas varias	3	TestBrand	Model-122	CODE-122	SERIAL-122	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
124	3	Test 123	Estante A	Disponible	Piezas varias	3	TestBrand	Model-123	CODE-123	SERIAL-123	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
125	3	Test 124	Estante A	Disponible	Piezas varias	3	TestBrand	Model-124	CODE-124	SERIAL-124	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
126	3	Test 125	Estante A	Disponible	Piezas varias	5	TestBrand	Model-125	CODE-125	SERIAL-125	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
127	3	Test 126	Estante A	Disponible	Piezas varias	2	TestBrand	Model-126	CODE-126	SERIAL-126	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
128	3	Test 127	Estante A	Disponible	Piezas varias	1	TestBrand	Model-127	CODE-127	SERIAL-127	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
129	3	Test 128	Estante A	Disponible	Piezas varias	3	TestBrand	Model-128	CODE-128	SERIAL-128	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
130	3	Test 129	Estante A	Disponible	Piezas varias	4	TestBrand	Model-129	CODE-129	SERIAL-129	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
131	3	Test 130	Estante A	Disponible	Piezas varias	4	TestBrand	Model-130	CODE-130	SERIAL-130	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	6
132	3	Test 131	Estante A	Disponible	Piezas varias	3	TestBrand	Model-131	CODE-131	SERIAL-131	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
133	3	Test 132	Estante A	Disponible	Piezas varias	3	TestBrand	Model-132	CODE-132	SERIAL-132	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
134	3	Test 133	Estante A	Disponible	Piezas varias	4	TestBrand	Model-133	CODE-133	SERIAL-133	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
135	3	Test 134	Estante A	Disponible	Piezas varias	2	TestBrand	Model-134	CODE-134	SERIAL-134	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
136	3	Test 135	Estante A	Disponible	Piezas varias	2	TestBrand	Model-135	CODE-135	SERIAL-135	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
137	3	Test 136	Estante A	Disponible	Piezas varias	4	TestBrand	Model-136	CODE-136	SERIAL-136	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
138	3	Test 137	Estante A	Disponible	Piezas varias	5	TestBrand	Model-137	CODE-137	SERIAL-137	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
139	3	Test 138	Estante A	Disponible	Piezas varias	2	TestBrand	Model-138	CODE-138	SERIAL-138	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
140	3	Test 139	Estante A	Disponible	Piezas varias	5	TestBrand	Model-139	CODE-139	SERIAL-139	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
141	3	Test 140	Estante A	Disponible	Piezas varias	2	TestBrand	Model-140	CODE-140	SERIAL-140	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	QUIMICO	7
142	4	Test 141	Estante A	Disponible	Piezas varias	3	TestBrand	Model-141	CODE-141	SERIAL-141	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
143	4	Test 142	Estante A	Disponible	Piezas varias	4	TestBrand	Model-142	CODE-142	SERIAL-142	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
144	4	Test 143	Estante A	Disponible	Piezas varias	3	TestBrand	Model-143	CODE-143	SERIAL-143	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
145	4	Test 144	Estante A	Disponible	Piezas varias	2	TestBrand	Model-144	CODE-144	SERIAL-144	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
146	4	Test 145	Estante A	Disponible	Piezas varias	3	TestBrand	Model-145	CODE-145	SERIAL-145	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
147	4	Test 146	Estante A	Disponible	Piezas varias	1	TestBrand	Model-146	CODE-146	SERIAL-146	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
148	4	Test 147	Estante A	Disponible	Piezas varias	3	TestBrand	Model-147	CODE-147	SERIAL-147	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
149	4	Test 148	Estante A	Disponible	Piezas varias	4	TestBrand	Model-148	CODE-148	SERIAL-148	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
150	4	Test 149	Estante A	Disponible	Piezas varias	4	TestBrand	Model-149	CODE-149	SERIAL-149	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
151	4	Test 150	Estante A	Disponible	Piezas varias	2	TestBrand	Model-150	CODE-150	SERIAL-150	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	1
152	4	Test 151	Estante A	Disponible	Piezas varias	1	TestBrand	Model-151	CODE-151	SERIAL-151	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
153	4	Test 152	Estante A	Disponible	Piezas varias	5	TestBrand	Model-152	CODE-152	SERIAL-152	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
154	4	Test 153	Estante A	Disponible	Piezas varias	4	TestBrand	Model-153	CODE-153	SERIAL-153	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
155	4	Test 154	Estante A	Disponible	Piezas varias	4	TestBrand	Model-154	CODE-154	SERIAL-154	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
156	4	Test 155	Estante A	Disponible	Piezas varias	1	TestBrand	Model-155	CODE-155	SERIAL-155	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
157	4	Test 156	Estante A	Disponible	Piezas varias	2	TestBrand	Model-156	CODE-156	SERIAL-156	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
158	4	Test 157	Estante A	Disponible	Piezas varias	3	TestBrand	Model-157	CODE-157	SERIAL-157	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
159	4	Test 158	Estante A	Disponible	Piezas varias	3	TestBrand	Model-158	CODE-158	SERIAL-158	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
160	4	Test 159	Estante A	Disponible	Piezas varias	3	TestBrand	Model-159	CODE-159	SERIAL-159	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
161	4	Test 160	Estante A	Disponible	Piezas varias	4	TestBrand	Model-160	CODE-160	SERIAL-160	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	2
164	4	Test 163	Estante A	Disponible	Piezas varias	4	TestBrand	Model-163	CODE-163	SERIAL-163	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
165	4	Test 164	Estante A	Disponible	Piezas varias	2	TestBrand	Model-164	CODE-164	SERIAL-164	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
166	4	Test 165	Estante A	Disponible	Piezas varias	5	TestBrand	Model-165	CODE-165	SERIAL-165	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
167	4	Test 166	Estante A	Disponible	Piezas varias	1	TestBrand	Model-166	CODE-166	SERIAL-166	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
168	4	Test 167	Estante A	Disponible	Piezas varias	5	TestBrand	Model-167	CODE-167	SERIAL-167	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
169	4	Test 168	Estante A	Disponible	Piezas varias	3	TestBrand	Model-168	CODE-168	SERIAL-168	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
170	4	Test 169	Estante A	Disponible	Piezas varias	3	TestBrand	Model-169	CODE-169	SERIAL-169	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
171	4	Test 170	Estante A	Disponible	Piezas varias	4	TestBrand	Model-170	CODE-170	SERIAL-170	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	3
172	4	Test 171	Estante A	Disponible	Piezas varias	5	TestBrand	Model-171	CODE-171	SERIAL-171	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
173	4	Test 172	Estante A	Disponible	Piezas varias	5	TestBrand	Model-172	CODE-172	SERIAL-172	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
174	4	Test 173	Estante A	Disponible	Piezas varias	4	TestBrand	Model-173	CODE-173	SERIAL-173	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
175	4	Test 174	Estante A	Disponible	Piezas varias	2	TestBrand	Model-174	CODE-174	SERIAL-174	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
176	4	Test 175	Estante A	Disponible	Piezas varias	3	TestBrand	Model-175	CODE-175	SERIAL-175	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
177	4	Test 176	Estante A	Disponible	Piezas varias	2	TestBrand	Model-176	CODE-176	SERIAL-176	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
178	4	Test 177	Estante A	Disponible	Piezas varias	4	TestBrand	Model-177	CODE-177	SERIAL-177	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
179	4	Test 178	Estante A	Disponible	Piezas varias	1	TestBrand	Model-178	CODE-178	SERIAL-178	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
180	4	Test 179	Estante A	Disponible	Piezas varias	4	TestBrand	Model-179	CODE-179	SERIAL-179	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
181	4	Test 180	Estante A	Disponible	Piezas varias	2	TestBrand	Model-180	CODE-180	SERIAL-180	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	4
182	4	Test 181	Estante A	Disponible	Piezas varias	4	TestBrand	Model-181	CODE-181	SERIAL-181	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
183	4	Test 182	Estante A	Disponible	Piezas varias	2	TestBrand	Model-182	CODE-182	SERIAL-182	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
184	4	Test 183	Estante A	Disponible	Piezas varias	4	TestBrand	Model-183	CODE-183	SERIAL-183	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
185	4	Test 184	Estante A	Disponible	Piezas varias	3	TestBrand	Model-184	CODE-184	SERIAL-184	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
186	4	Test 185	Estante A	Disponible	Piezas varias	2	TestBrand	Model-185	CODE-185	SERIAL-185	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
187	4	Test 186	Estante A	Disponible	Piezas varias	1	TestBrand	Model-186	CODE-186	SERIAL-186	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
188	4	Test 187	Estante A	Disponible	Piezas varias	5	TestBrand	Model-187	CODE-187	SERIAL-187	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
189	4	Test 188	Estante A	Disponible	Piezas varias	1	TestBrand	Model-188	CODE-188	SERIAL-188	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
190	4	Test 189	Estante A	Disponible	Piezas varias	3	TestBrand	Model-189	CODE-189	SERIAL-189	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
191	4	Test 190	Estante A	Disponible	Piezas varias	3	TestBrand	Model-190	CODE-190	SERIAL-190	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	5
192	4	Test 191	Estante A	Disponible	Piezas varias	2	TestBrand	Model-191	CODE-191	SERIAL-191	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
193	4	Test 192	Estante A	Disponible	Piezas varias	2	TestBrand	Model-192	CODE-192	SERIAL-192	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
194	4	Test 193	Estante A	Disponible	Piezas varias	2	TestBrand	Model-193	CODE-193	SERIAL-193	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
195	4	Test 194	Estante A	Disponible	Piezas varias	4	TestBrand	Model-194	CODE-194	SERIAL-194	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
196	4	Test 195	Estante A	Disponible	Piezas varias	4	TestBrand	Model-195	CODE-195	SERIAL-195	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
197	4	Test 196	Estante A	Disponible	Piezas varias	2	TestBrand	Model-196	CODE-196	SERIAL-196	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
198	4	Test 197	Estante A	Disponible	Piezas varias	4	TestBrand	Model-197	CODE-197	SERIAL-197	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
199	4	Test 198	Estante A	Disponible	Piezas varias	3	TestBrand	Model-198	CODE-198	SERIAL-198	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
200	4	Test 199	Estante A	Disponible	Piezas varias	1	TestBrand	Model-199	CODE-199	SERIAL-199	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
201	4	Test 200	Estante A	Disponible	Piezas varias	3	TestBrand	Model-200	CODE-200	SERIAL-200	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	6
202	4	Test 201	Estante A	Disponible	Piezas varias	3	TestBrand	Model-201	CODE-201	SERIAL-201	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
203	4	Test 202	Estante A	Disponible	Piezas varias	3	TestBrand	Model-202	CODE-202	SERIAL-202	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
204	4	Test 203	Estante A	Disponible	Piezas varias	3	TestBrand	Model-203	CODE-203	SERIAL-203	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
205	4	Test 204	Estante A	Disponible	Piezas varias	5	TestBrand	Model-204	CODE-204	SERIAL-204	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
206	4	Test 205	Estante A	Disponible	Piezas varias	3	TestBrand	Model-205	CODE-205	SERIAL-205	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
207	4	Test 206	Estante A	Disponible	Piezas varias	2	TestBrand	Model-206	CODE-206	SERIAL-206	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
208	4	Test 207	Estante A	Disponible	Piezas varias	2	TestBrand	Model-207	CODE-207	SERIAL-207	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
209	4	Test 208	Estante A	Disponible	Piezas varias	5	TestBrand	Model-208	CODE-208	SERIAL-208	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
210	4	Test 209	Estante A	Disponible	Piezas varias	1	TestBrand	Model-209	CODE-209	SERIAL-209	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
211	4	Test 210	Estante A	Disponible	Piezas varias	1	TestBrand	Model-210	CODE-210	SERIAL-210	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	ELECTRONICA	7
212	5	Test 211	Estante A	Disponible	Piezas varias	2	TestBrand	Model-211	CODE-211	SERIAL-211	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
213	5	Test 212	Estante A	Disponible	Piezas varias	3	TestBrand	Model-212	CODE-212	SERIAL-212	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
214	5	Test 213	Estante A	Disponible	Piezas varias	5	TestBrand	Model-213	CODE-213	SERIAL-213	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
215	5	Test 214	Estante A	Disponible	Piezas varias	4	TestBrand	Model-214	CODE-214	SERIAL-214	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
216	5	Test 215	Estante A	Disponible	Piezas varias	3	TestBrand	Model-215	CODE-215	SERIAL-215	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
217	5	Test 216	Estante A	Disponible	Piezas varias	2	TestBrand	Model-216	CODE-216	SERIAL-216	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
218	5	Test 217	Estante A	Disponible	Piezas varias	4	TestBrand	Model-217	CODE-217	SERIAL-217	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
219	5	Test 218	Estante A	Disponible	Piezas varias	3	TestBrand	Model-218	CODE-218	SERIAL-218	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
220	5	Test 219	Estante A	Disponible	Piezas varias	1	TestBrand	Model-219	CODE-219	SERIAL-219	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
221	5	Test 220	Estante A	Disponible	Piezas varias	4	TestBrand	Model-220	CODE-220	SERIAL-220	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	1
222	5	Test 221	Estante A	Disponible	Piezas varias	1	TestBrand	Model-221	CODE-221	SERIAL-221	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
223	5	Test 222	Estante A	Disponible	Piezas varias	5	TestBrand	Model-222	CODE-222	SERIAL-222	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
224	5	Test 223	Estante A	Disponible	Piezas varias	1	TestBrand	Model-223	CODE-223	SERIAL-223	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
225	5	Test 224	Estante A	Disponible	Piezas varias	3	TestBrand	Model-224	CODE-224	SERIAL-224	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
226	5	Test 225	Estante A	Disponible	Piezas varias	3	TestBrand	Model-225	CODE-225	SERIAL-225	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
227	5	Test 226	Estante A	Disponible	Piezas varias	4	TestBrand	Model-226	CODE-226	SERIAL-226	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
228	5	Test 227	Estante A	Disponible	Piezas varias	3	TestBrand	Model-227	CODE-227	SERIAL-227	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
229	5	Test 228	Estante A	Disponible	Piezas varias	1	TestBrand	Model-228	CODE-228	SERIAL-228	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
230	5	Test 229	Estante A	Disponible	Piezas varias	2	TestBrand	Model-229	CODE-229	SERIAL-229	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
231	5	Test 230	Estante A	Disponible	Piezas varias	4	TestBrand	Model-230	CODE-230	SERIAL-230	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	2
232	5	Test 231	Estante A	Disponible	Piezas varias	3	TestBrand	Model-231	CODE-231	SERIAL-231	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
233	5	Test 232	Estante A	Disponible	Piezas varias	5	TestBrand	Model-232	CODE-232	SERIAL-232	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
234	5	Test 233	Estante A	Disponible	Piezas varias	5	TestBrand	Model-233	CODE-233	SERIAL-233	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
235	5	Test 234	Estante A	Disponible	Piezas varias	5	TestBrand	Model-234	CODE-234	SERIAL-234	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
236	5	Test 235	Estante A	Disponible	Piezas varias	2	TestBrand	Model-235	CODE-235	SERIAL-235	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
237	5	Test 236	Estante A	Disponible	Piezas varias	5	TestBrand	Model-236	CODE-236	SERIAL-236	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
238	5	Test 237	Estante A	Disponible	Piezas varias	2	TestBrand	Model-237	CODE-237	SERIAL-237	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
239	5	Test 238	Estante A	Disponible	Piezas varias	3	TestBrand	Model-238	CODE-238	SERIAL-238	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
240	5	Test 239	Estante A	Disponible	Piezas varias	4	TestBrand	Model-239	CODE-239	SERIAL-239	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
241	5	Test 240	Estante A	Disponible	Piezas varias	4	TestBrand	Model-240	CODE-240	SERIAL-240	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	3
242	5	Test 241	Estante A	Disponible	Piezas varias	5	TestBrand	Model-241	CODE-241	SERIAL-241	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
243	5	Test 242	Estante A	Disponible	Piezas varias	4	TestBrand	Model-242	CODE-242	SERIAL-242	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
244	5	Test 243	Estante A	Disponible	Piezas varias	4	TestBrand	Model-243	CODE-243	SERIAL-243	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
245	5	Test 244	Estante A	Disponible	Piezas varias	4	TestBrand	Model-244	CODE-244	SERIAL-244	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
246	5	Test 245	Estante A	Disponible	Piezas varias	4	TestBrand	Model-245	CODE-245	SERIAL-245	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
247	5	Test 246	Estante A	Disponible	Piezas varias	5	TestBrand	Model-246	CODE-246	SERIAL-246	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
248	5	Test 247	Estante A	Disponible	Piezas varias	3	TestBrand	Model-247	CODE-247	SERIAL-247	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
249	5	Test 248	Estante A	Disponible	Piezas varias	2	TestBrand	Model-248	CODE-248	SERIAL-248	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
250	5	Test 249	Estante A	Disponible	Piezas varias	2	TestBrand	Model-249	CODE-249	SERIAL-249	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
251	5	Test 250	Estante A	Disponible	Piezas varias	4	TestBrand	Model-250	CODE-250	SERIAL-250	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	4
252	5	Test 251	Estante A	Disponible	Piezas varias	3	TestBrand	Model-251	CODE-251	SERIAL-251	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
253	5	Test 252	Estante A	Disponible	Piezas varias	3	TestBrand	Model-252	CODE-252	SERIAL-252	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
254	5	Test 253	Estante A	Disponible	Piezas varias	1	TestBrand	Model-253	CODE-253	SERIAL-253	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
255	5	Test 254	Estante A	Disponible	Piezas varias	4	TestBrand	Model-254	CODE-254	SERIAL-254	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
256	5	Test 255	Estante A	Disponible	Piezas varias	2	TestBrand	Model-255	CODE-255	SERIAL-255	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
257	5	Test 256	Estante A	Disponible	Piezas varias	2	TestBrand	Model-256	CODE-256	SERIAL-256	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
258	5	Test 257	Estante A	Disponible	Piezas varias	3	TestBrand	Model-257	CODE-257	SERIAL-257	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
259	5	Test 258	Estante A	Disponible	Piezas varias	2	TestBrand	Model-258	CODE-258	SERIAL-258	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
260	5	Test 259	Estante A	Disponible	Piezas varias	3	TestBrand	Model-259	CODE-259	SERIAL-259	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
261	5	Test 260	Estante A	Disponible	Piezas varias	4	TestBrand	Model-260	CODE-260	SERIAL-260	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	5
262	5	Test 261	Estante A	Disponible	Piezas varias	3	TestBrand	Model-261	CODE-261	SERIAL-261	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
263	5	Test 262	Estante A	Disponible	Piezas varias	4	TestBrand	Model-262	CODE-262	SERIAL-262	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
264	5	Test 263	Estante A	Disponible	Piezas varias	2	TestBrand	Model-263	CODE-263	SERIAL-263	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
265	5	Test 264	Estante A	Disponible	Piezas varias	2	TestBrand	Model-264	CODE-264	SERIAL-264	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
266	5	Test 265	Estante A	Disponible	Piezas varias	2	TestBrand	Model-265	CODE-265	SERIAL-265	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
267	5	Test 266	Estante A	Disponible	Piezas varias	5	TestBrand	Model-266	CODE-266	SERIAL-266	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
268	5	Test 267	Estante A	Disponible	Piezas varias	2	TestBrand	Model-267	CODE-267	SERIAL-267	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
269	5	Test 268	Estante A	Disponible	Piezas varias	3	TestBrand	Model-268	CODE-268	SERIAL-268	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
270	5	Test 269	Estante A	Disponible	Piezas varias	1	TestBrand	Model-269	CODE-269	SERIAL-269	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
271	5	Test 270	Estante A	Disponible	Piezas varias	2	TestBrand	Model-270	CODE-270	SERIAL-270	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	6
272	5	Test 271	Estante A	Disponible	Piezas varias	4	TestBrand	Model-271	CODE-271	SERIAL-271	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
273	5	Test 272	Estante A	Disponible	Piezas varias	3	TestBrand	Model-272	CODE-272	SERIAL-272	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
274	5	Test 273	Estante A	Disponible	Piezas varias	4	TestBrand	Model-273	CODE-273	SERIAL-273	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
275	5	Test 274	Estante A	Disponible	Piezas varias	1	TestBrand	Model-274	CODE-274	SERIAL-274	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
276	5	Test 275	Estante A	Disponible	Piezas varias	2	TestBrand	Model-275	CODE-275	SERIAL-275	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
277	5	Test 276	Estante A	Disponible	Piezas varias	1	TestBrand	Model-276	CODE-276	SERIAL-276	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
278	5	Test 277	Estante A	Disponible	Piezas varias	2	TestBrand	Model-277	CODE-277	SERIAL-277	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
279	5	Test 278	Estante A	Disponible	Piezas varias	2	TestBrand	Model-278	CODE-278	SERIAL-278	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
280	5	Test 279	Estante A	Disponible	Piezas varias	2	TestBrand	Model-279	CODE-279	SERIAL-279	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
281	5	Test 280	Estante A	Disponible	Piezas varias	3	TestBrand	Model-280	CODE-280	SERIAL-280	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	LOGISTICA	7
282	6	Test 281	Estante A	Disponible	Piezas varias	3	TestBrand	Model-281	CODE-281	SERIAL-281	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
283	6	Test 282	Estante A	Disponible	Piezas varias	4	TestBrand	Model-282	CODE-282	SERIAL-282	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
284	6	Test 283	Estante A	Disponible	Piezas varias	3	TestBrand	Model-283	CODE-283	SERIAL-283	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
285	6	Test 284	Estante A	Disponible	Piezas varias	2	TestBrand	Model-284	CODE-284	SERIAL-284	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
286	6	Test 285	Estante A	Disponible	Piezas varias	4	TestBrand	Model-285	CODE-285	SERIAL-285	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
287	6	Test 286	Estante A	Disponible	Piezas varias	4	TestBrand	Model-286	CODE-286	SERIAL-286	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
288	6	Test 287	Estante A	Disponible	Piezas varias	3	TestBrand	Model-287	CODE-287	SERIAL-287	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
289	6	Test 288	Estante A	Disponible	Piezas varias	2	TestBrand	Model-288	CODE-288	SERIAL-288	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
290	6	Test 289	Estante A	Disponible	Piezas varias	4	TestBrand	Model-289	CODE-289	SERIAL-289	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
291	6	Test 290	Estante A	Disponible	Piezas varias	4	TestBrand	Model-290	CODE-290	SERIAL-290	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	1
292	6	Test 291	Estante A	Disponible	Piezas varias	3	TestBrand	Model-291	CODE-291	SERIAL-291	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
293	6	Test 292	Estante A	Disponible	Piezas varias	4	TestBrand	Model-292	CODE-292	SERIAL-292	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
294	6	Test 293	Estante A	Disponible	Piezas varias	4	TestBrand	Model-293	CODE-293	SERIAL-293	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
295	6	Test 294	Estante A	Disponible	Piezas varias	2	TestBrand	Model-294	CODE-294	SERIAL-294	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
296	6	Test 295	Estante A	Disponible	Piezas varias	3	TestBrand	Model-295	CODE-295	SERIAL-295	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
297	6	Test 296	Estante A	Disponible	Piezas varias	4	TestBrand	Model-296	CODE-296	SERIAL-296	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
298	6	Test 297	Estante A	Disponible	Piezas varias	3	TestBrand	Model-297	CODE-297	SERIAL-297	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
299	6	Test 298	Estante A	Disponible	Piezas varias	1	TestBrand	Model-298	CODE-298	SERIAL-298	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
300	6	Test 299	Estante A	Disponible	Piezas varias	4	TestBrand	Model-299	CODE-299	SERIAL-299	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
301	6	Test 300	Estante A	Disponible	Piezas varias	3	TestBrand	Model-300	CODE-300	SERIAL-300	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	2
302	6	Test 301	Estante A	Disponible	Piezas varias	5	TestBrand	Model-301	CODE-301	SERIAL-301	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
303	6	Test 302	Estante A	Disponible	Piezas varias	2	TestBrand	Model-302	CODE-302	SERIAL-302	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
304	6	Test 303	Estante A	Disponible	Piezas varias	3	TestBrand	Model-303	CODE-303	SERIAL-303	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
305	6	Test 304	Estante A	Disponible	Piezas varias	5	TestBrand	Model-304	CODE-304	SERIAL-304	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
306	6	Test 305	Estante A	Disponible	Piezas varias	2	TestBrand	Model-305	CODE-305	SERIAL-305	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
307	6	Test 306	Estante A	Disponible	Piezas varias	4	TestBrand	Model-306	CODE-306	SERIAL-306	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
308	6	Test 307	Estante A	Disponible	Piezas varias	2	TestBrand	Model-307	CODE-307	SERIAL-307	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
309	6	Test 308	Estante A	Disponible	Piezas varias	4	TestBrand	Model-308	CODE-308	SERIAL-308	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
310	6	Test 309	Estante A	Disponible	Piezas varias	4	TestBrand	Model-309	CODE-309	SERIAL-309	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
311	6	Test 310	Estante A	Disponible	Piezas varias	2	TestBrand	Model-310	CODE-310	SERIAL-310	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	3
312	6	Test 311	Estante A	Disponible	Piezas varias	5	TestBrand	Model-311	CODE-311	SERIAL-311	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
313	6	Test 312	Estante A	Disponible	Piezas varias	1	TestBrand	Model-312	CODE-312	SERIAL-312	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
314	6	Test 313	Estante A	Disponible	Piezas varias	2	TestBrand	Model-313	CODE-313	SERIAL-313	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
315	6	Test 314	Estante A	Disponible	Piezas varias	4	TestBrand	Model-314	CODE-314	SERIAL-314	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
316	6	Test 315	Estante A	Disponible	Piezas varias	3	TestBrand	Model-315	CODE-315	SERIAL-315	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
317	6	Test 316	Estante A	Disponible	Piezas varias	4	TestBrand	Model-316	CODE-316	SERIAL-316	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
318	6	Test 317	Estante A	Disponible	Piezas varias	1	TestBrand	Model-317	CODE-317	SERIAL-317	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
319	6	Test 318	Estante A	Disponible	Piezas varias	3	TestBrand	Model-318	CODE-318	SERIAL-318	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
320	6	Test 319	Estante A	Disponible	Piezas varias	2	TestBrand	Model-319	CODE-319	SERIAL-319	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
321	6	Test 320	Estante A	Disponible	Piezas varias	5	TestBrand	Model-320	CODE-320	SERIAL-320	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	4
322	6	Test 321	Estante A	Disponible	Piezas varias	3	TestBrand	Model-321	CODE-321	SERIAL-321	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
323	6	Test 322	Estante A	Disponible	Piezas varias	3	TestBrand	Model-322	CODE-322	SERIAL-322	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
324	6	Test 323	Estante A	Disponible	Piezas varias	3	TestBrand	Model-323	CODE-323	SERIAL-323	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
325	6	Test 324	Estante A	Disponible	Piezas varias	3	TestBrand	Model-324	CODE-324	SERIAL-324	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
326	6	Test 325	Estante A	Disponible	Piezas varias	2	TestBrand	Model-325	CODE-325	SERIAL-325	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
327	6	Test 326	Estante A	Disponible	Piezas varias	2	TestBrand	Model-326	CODE-326	SERIAL-326	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
328	6	Test 327	Estante A	Disponible	Piezas varias	5	TestBrand	Model-327	CODE-327	SERIAL-327	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
329	6	Test 328	Estante A	Disponible	Piezas varias	3	TestBrand	Model-328	CODE-328	SERIAL-328	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
330	6	Test 329	Estante A	Disponible	Piezas varias	3	TestBrand	Model-329	CODE-329	SERIAL-329	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
331	6	Test 330	Estante A	Disponible	Piezas varias	2	TestBrand	Model-330	CODE-330	SERIAL-330	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	5
332	6	Test 331	Estante A	Disponible	Piezas varias	3	TestBrand	Model-331	CODE-331	SERIAL-331	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
333	6	Test 332	Estante A	Disponible	Piezas varias	2	TestBrand	Model-332	CODE-332	SERIAL-332	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
334	6	Test 333	Estante A	Disponible	Piezas varias	3	TestBrand	Model-333	CODE-333	SERIAL-333	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
335	6	Test 334	Estante A	Disponible	Piezas varias	2	TestBrand	Model-334	CODE-334	SERIAL-334	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
336	6	Test 335	Estante A	Disponible	Piezas varias	5	TestBrand	Model-335	CODE-335	SERIAL-335	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
337	6	Test 336	Estante A	Disponible	Piezas varias	4	TestBrand	Model-336	CODE-336	SERIAL-336	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
338	6	Test 337	Estante A	Disponible	Piezas varias	3	TestBrand	Model-337	CODE-337	SERIAL-337	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
339	6	Test 338	Estante A	Disponible	Piezas varias	1	TestBrand	Model-338	CODE-338	SERIAL-338	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
340	6	Test 339	Estante A	Disponible	Piezas varias	1	TestBrand	Model-339	CODE-339	SERIAL-339	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
341	6	Test 340	Estante A	Disponible	Piezas varias	2	TestBrand	Model-340	CODE-340	SERIAL-340	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	6
342	6	Test 341	Estante A	Disponible	Piezas varias	4	TestBrand	Model-341	CODE-341	SERIAL-341	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
343	6	Test 342	Estante A	Disponible	Piezas varias	3	TestBrand	Model-342	CODE-342	SERIAL-342	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
344	6	Test 343	Estante A	Disponible	Piezas varias	4	TestBrand	Model-343	CODE-343	SERIAL-343	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
345	6	Test 344	Estante A	Disponible	Piezas varias	3	TestBrand	Model-344	CODE-344	SERIAL-344	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
346	6	Test 345	Estante A	Disponible	Piezas varias	2	TestBrand	Model-345	CODE-345	SERIAL-345	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
347	6	Test 346	Estante A	Disponible	Piezas varias	1	TestBrand	Model-346	CODE-346	SERIAL-346	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
348	6	Test 347	Estante A	Disponible	Piezas varias	4	TestBrand	Model-347	CODE-347	SERIAL-347	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
349	6	Test 348	Estante A	Disponible	Piezas varias	2	TestBrand	Model-348	CODE-348	SERIAL-348	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
350	6	Test 349	Estante A	Disponible	Piezas varias	4	TestBrand	Model-349	CODE-349	SERIAL-349	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
351	6	Test 350	Estante A	Disponible	Piezas varias	4	TestBrand	Model-350	CODE-350	SERIAL-350	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	OFICINA	7
352	7	Test 351	Estante A	Disponible	Piezas varias	2	TestBrand	Model-351	CODE-351	SERIAL-351	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
353	7	Test 352	Estante A	Disponible	Piezas varias	3	TestBrand	Model-352	CODE-352	SERIAL-352	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
354	7	Test 353	Estante A	Disponible	Piezas varias	1	TestBrand	Model-353	CODE-353	SERIAL-353	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
355	7	Test 354	Estante A	Disponible	Piezas varias	2	TestBrand	Model-354	CODE-354	SERIAL-354	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
356	7	Test 355	Estante A	Disponible	Piezas varias	2	TestBrand	Model-355	CODE-355	SERIAL-355	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
357	7	Test 356	Estante A	Disponible	Piezas varias	2	TestBrand	Model-356	CODE-356	SERIAL-356	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
358	7	Test 357	Estante A	Disponible	Piezas varias	2	TestBrand	Model-357	CODE-357	SERIAL-357	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
359	7	Test 358	Estante A	Disponible	Piezas varias	5	TestBrand	Model-358	CODE-358	SERIAL-358	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
360	7	Test 359	Estante A	Disponible	Piezas varias	1	TestBrand	Model-359	CODE-359	SERIAL-359	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
361	7	Test 360	Estante A	Disponible	Piezas varias	3	TestBrand	Model-360	CODE-360	SERIAL-360	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	1
362	7	Test 361	Estante A	Disponible	Piezas varias	1	TestBrand	Model-361	CODE-361	SERIAL-361	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
363	7	Test 362	Estante A	Disponible	Piezas varias	3	TestBrand	Model-362	CODE-362	SERIAL-362	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
364	7	Test 363	Estante A	Disponible	Piezas varias	1	TestBrand	Model-363	CODE-363	SERIAL-363	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
365	7	Test 364	Estante A	Disponible	Piezas varias	1	TestBrand	Model-364	CODE-364	SERIAL-364	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
366	7	Test 365	Estante A	Disponible	Piezas varias	5	TestBrand	Model-365	CODE-365	SERIAL-365	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
367	7	Test 366	Estante A	Disponible	Piezas varias	2	TestBrand	Model-366	CODE-366	SERIAL-366	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
368	7	Test 367	Estante A	Disponible	Piezas varias	5	TestBrand	Model-367	CODE-367	SERIAL-367	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
369	7	Test 368	Estante A	Disponible	Piezas varias	4	TestBrand	Model-368	CODE-368	SERIAL-368	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
370	7	Test 369	Estante A	Disponible	Piezas varias	1	TestBrand	Model-369	CODE-369	SERIAL-369	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
371	7	Test 370	Estante A	Disponible	Piezas varias	3	TestBrand	Model-370	CODE-370	SERIAL-370	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	2
372	7	Test 371	Estante A	Disponible	Piezas varias	4	TestBrand	Model-371	CODE-371	SERIAL-371	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
373	7	Test 372	Estante A	Disponible	Piezas varias	3	TestBrand	Model-372	CODE-372	SERIAL-372	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
374	7	Test 373	Estante A	Disponible	Piezas varias	2	TestBrand	Model-373	CODE-373	SERIAL-373	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
375	7	Test 374	Estante A	Disponible	Piezas varias	5	TestBrand	Model-374	CODE-374	SERIAL-374	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
376	7	Test 375	Estante A	Disponible	Piezas varias	2	TestBrand	Model-375	CODE-375	SERIAL-375	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
377	7	Test 376	Estante A	Disponible	Piezas varias	2	TestBrand	Model-376	CODE-376	SERIAL-376	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
378	7	Test 377	Estante A	Disponible	Piezas varias	4	TestBrand	Model-377	CODE-377	SERIAL-377	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
379	7	Test 378	Estante A	Disponible	Piezas varias	4	TestBrand	Model-378	CODE-378	SERIAL-378	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
380	7	Test 379	Estante A	Disponible	Piezas varias	2	TestBrand	Model-379	CODE-379	SERIAL-379	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
381	7	Test 380	Estante A	Disponible	Piezas varias	2	TestBrand	Model-380	CODE-380	SERIAL-380	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	3
382	7	Test 381	Estante A	Disponible	Piezas varias	4	TestBrand	Model-381	CODE-381	SERIAL-381	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
383	7	Test 382	Estante A	Disponible	Piezas varias	5	TestBrand	Model-382	CODE-382	SERIAL-382	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
384	7	Test 383	Estante A	Disponible	Piezas varias	5	TestBrand	Model-383	CODE-383	SERIAL-383	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
385	7	Test 384	Estante A	Disponible	Piezas varias	4	TestBrand	Model-384	CODE-384	SERIAL-384	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
386	7	Test 385	Estante A	Disponible	Piezas varias	2	TestBrand	Model-385	CODE-385	SERIAL-385	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
387	7	Test 386	Estante A	Disponible	Piezas varias	2	TestBrand	Model-386	CODE-386	SERIAL-386	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
388	7	Test 387	Estante A	Disponible	Piezas varias	2	TestBrand	Model-387	CODE-387	SERIAL-387	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
389	7	Test 388	Estante A	Disponible	Piezas varias	5	TestBrand	Model-388	CODE-388	SERIAL-388	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
390	7	Test 389	Estante A	Disponible	Piezas varias	3	TestBrand	Model-389	CODE-389	SERIAL-389	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
391	7	Test 390	Estante A	Disponible	Piezas varias	3	TestBrand	Model-390	CODE-390	SERIAL-390	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	4
392	7	Test 391	Estante A	Disponible	Piezas varias	5	TestBrand	Model-391	CODE-391	SERIAL-391	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
393	7	Test 392	Estante A	Disponible	Piezas varias	2	TestBrand	Model-392	CODE-392	SERIAL-392	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
394	7	Test 393	Estante A	Disponible	Piezas varias	1	TestBrand	Model-393	CODE-393	SERIAL-393	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
395	7	Test 394	Estante A	Disponible	Piezas varias	1	TestBrand	Model-394	CODE-394	SERIAL-394	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
396	7	Test 395	Estante A	Disponible	Piezas varias	4	TestBrand	Model-395	CODE-395	SERIAL-395	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
397	7	Test 396	Estante A	Disponible	Piezas varias	5	TestBrand	Model-396	CODE-396	SERIAL-396	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
398	7	Test 397	Estante A	Disponible	Piezas varias	4	TestBrand	Model-397	CODE-397	SERIAL-397	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
399	7	Test 398	Estante A	Disponible	Piezas varias	4	TestBrand	Model-398	CODE-398	SERIAL-398	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
400	7	Test 399	Estante A	Disponible	Piezas varias	3	TestBrand	Model-399	CODE-399	SERIAL-399	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
401	7	Test 400	Estante A	Disponible	Piezas varias	2	TestBrand	Model-400	CODE-400	SERIAL-400	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	5
402	7	Test 401	Estante A	Disponible	Piezas varias	2	TestBrand	Model-401	CODE-401	SERIAL-401	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
403	7	Test 402	Estante A	Disponible	Piezas varias	3	TestBrand	Model-402	CODE-402	SERIAL-402	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
404	7	Test 403	Estante A	Disponible	Piezas varias	1	TestBrand	Model-403	CODE-403	SERIAL-403	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
405	7	Test 404	Estante A	Disponible	Piezas varias	3	TestBrand	Model-404	CODE-404	SERIAL-404	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
406	7	Test 405	Estante A	Disponible	Piezas varias	4	TestBrand	Model-405	CODE-405	SERIAL-405	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
407	7	Test 406	Estante A	Disponible	Piezas varias	1	TestBrand	Model-406	CODE-406	SERIAL-406	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
408	7	Test 407	Estante A	Disponible	Piezas varias	4	TestBrand	Model-407	CODE-407	SERIAL-407	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
409	7	Test 408	Estante A	Disponible	Piezas varias	4	TestBrand	Model-408	CODE-408	SERIAL-408	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
410	7	Test 409	Estante A	Disponible	Piezas varias	4	TestBrand	Model-409	CODE-409	SERIAL-409	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
411	7	Test 410	Estante A	Disponible	Piezas varias	3	TestBrand	Model-410	CODE-410	SERIAL-410	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	6
412	7	Test 411	Estante A	Disponible	Piezas varias	2	TestBrand	Model-411	CODE-411	SERIAL-411	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
413	7	Test 412	Estante A	Disponible	Piezas varias	3	TestBrand	Model-412	CODE-412	SERIAL-412	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
414	7	Test 413	Estante A	Disponible	Piezas varias	4	TestBrand	Model-413	CODE-413	SERIAL-413	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
415	7	Test 414	Estante A	Disponible	Piezas varias	2	TestBrand	Model-414	CODE-414	SERIAL-414	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
416	7	Test 415	Estante A	Disponible	Piezas varias	3	TestBrand	Model-415	CODE-415	SERIAL-415	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
417	7	Test 416	Estante A	Disponible	Piezas varias	5	TestBrand	Model-416	CODE-416	SERIAL-416	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
418	7	Test 417	Estante A	Disponible	Piezas varias	1	TestBrand	Model-417	CODE-417	SERIAL-417	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
419	7	Test 418	Estante A	Disponible	Piezas varias	2	TestBrand	Model-418	CODE-418	SERIAL-418	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
420	7	Test 419	Estante A	Disponible	Piezas varias	2	TestBrand	Model-419	CODE-419	SERIAL-419	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
421	7	Test 420	Estante A	Disponible	Piezas varias	2	TestBrand	Model-420	CODE-420	SERIAL-420	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	\N	REDES	7
163	4	Test 162	Estante A	Disponible	Piezas varias	3	TestBrand	Model-162	CODE-162	SERIAL-162	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	2026-04-06 18:31:34.412824	ELECTRONICA	3
162	4	Test 161	Estante A	Disponible	Piezas varias	3	TestBrand	Model-161	CODE-161	SERIAL-161	\N	\N	Material de prueba	\N	\N	\N	2026-04-06 12:00:04.23819	2026-04-06 18:42:11.330363	ELECTRONICA	3
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notifications (id, user_id, title, message, link, is_read, created_at) FROM stdin;
2	4	Reservación rechazada	Tu reservación #2 fue rechazada.	/reservations/my	t	2026-04-06 15:08:46.428889
1	1	Nueva reserva pendiente	El usuario student@test.com creó la reserva #2 para B002 el 2026-04-06.	/reservations/admin	t	2026-04-06 15:05:45.276113
3	1	Nueva reserva pendiente	El usuario student@test.com creó la reserva #3 para B004 el 2026-04-06.	/reservations/admin	f	2026-04-06 15:28:28.064147
6	1	Solicitud urgente en ticket activo	student@test.com agregó 2 de Test 161 al ticket #1.	/reservations/admin/tickets/1	f	2026-04-06 16:00:15.424544
7	1	Solicitud urgente en ticket activo	student@test.com agregó 2 de Test 162 al ticket #1.	/reservations/admin/tickets/1	f	2026-04-06 16:00:29.964435
8	4	Material listo para recoger	Hay material listo para recoger en tu ticket #1.	/reservations/my/3/ticket	t	2026-04-06 17:06:57.296516
5	4	Ticket de laboratorio abierto	Se abrió el ticket de tu reservación #3.	/reservations/my/3/ticket	t	2026-04-06 15:29:12.140945
4	4	Reservación aprobada	Tu reservación #3 fue aprobada.	/reservations/my	t	2026-04-06 15:28:49.29609
9	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #1.	/reservations/my/3/ticket	f	2026-04-06 18:31:22.077922
10	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #1.	/reservations/my/3/ticket	f	2026-04-06 18:31:34.412824
11	4	Ticket de reservación cerrado	Tu ticket #1 se cerró con estado CLOSED.	/reservations/my	f	2026-04-06 18:31:35.827245
12	1	Nueva reserva pendiente	El usuario student@test.com creó la reserva #4 para B003 el 2026-04-06.	/reservations/admin	t	2026-04-06 18:38:33.438913
13	4	Reservación aprobada	Tu reservación #4 fue aprobada.	/reservations/my	f	2026-04-06 18:38:55.975309
14	4	Ticket de laboratorio abierto	Se abrió el ticket de tu reservación #4.	/reservations/my/4/ticket	f	2026-04-06 18:40:48.148011
15	1	Solicitud urgente en ticket activo	student@test.com agregó 2 de Test 161 al ticket #2.	/reservations/admin/tickets/2	f	2026-04-06 18:41:04.51845
16	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 18:41:17.871048
18	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	t	2026-04-06 18:41:37.071295
17	4	Material listo para recoger	Hay material listo para recoger en tu ticket #2.	/reservations/my/4/ticket	t	2026-04-06 18:41:21.981645
19	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 18:42:11.330363
20	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 18:42:14.111968
21	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 18:42:24.939055
22	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 18:43:04.104116
23	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 19:04:58.974896
24	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 19:10:55.291996
25	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 19:11:06.055353
26	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 19:13:09.395418
27	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 19:13:15.463034
28	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #2.	/reservations/my/4/ticket	f	2026-04-06 19:21:19.200772
29	4	Ticket de reservación cerrado	Tu ticket #2 se cerró con estado CLOSED_WITH_DEBT.	/reservations/my	f	2026-04-06 19:21:20.177023
30	1	Adeudo generado por cierre de ticket	El ticket #2 cerró con adeudo. Revisa deudor y seguimiento.	/debts/admin	f	2026-04-06 19:21:20.177023
31	4	Ticket de laboratorio abierto	Se abrió el ticket de tu reservación #4.	/reservations/my/4/ticket	f	2026-04-06 19:21:35.572614
32	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #3.	/reservations/my/4/ticket	f	2026-04-06 19:21:54.60399
33	4	Ticket de reservación actualizado	Se actualizaron los materiales del ticket #3.	/reservations/my/4/ticket	f	2026-04-06 19:21:56.234237
34	4	Ticket de reservación cerrado	Tu ticket #3 se cerró con estado CLOSED.	/reservations/my	f	2026-04-06 19:21:57.623851
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.permissions (id, name, description) FROM stdin;
1	debts.view_own	View own debts
2	debts.view_all	View all debts
3	debts.create	Create debts
4	debts.close	Close debts
5	reports.view	View reports
6	reports.export	Export reports
7	inventory.view	View inventory
8	lostfound.view	View lost items
9	lostfound.manage	Manage lost items
10	reservations.create	Create reservations
11	reservations.approve	Approve reservations
12	software.view	View software
13	software.request	Request software
14	users.assign_roles	Assign roles
\.


--
-- Data for Name: print3d_jobs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.print3d_jobs (id, requester_user_id, title, description, file_ref, original_filename, file_size_bytes, status, grams_estimated, price_per_gram, total_estimated, admin_note, quoted_by_user_id, ready_notified_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: profile_change_requests; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.profile_change_requests (id, user_id, request_type, requested_phone, requested_full_name, requested_matricula, requested_career_id, requested_academic_level_id, reason, status, reviewed_by, reviewed_at, created_at) FROM stdin;
\.


--
-- Data for Name: reservation_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.reservation_items (id, reservation_id, material_id, quantity_requested, notes) FROM stdin;
1	4	162	4	\N
\.


--
-- Data for Name: reservations; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.reservations (id, user_id, room, date, start_time, end_time, purpose, status, admin_note, created_at, updated_at, group_name, teacher_name, subject, signed, exit_time, teacher_comments, subject_id, signature_ref) FROM stdin;
2	4	B002	2026-04-06	15:30:00	16:00:00	\N	REJECTED	\N	2026-04-06 15:05:45.276113	2026-04-06 15:08:46.428889	TRM51	Test Student	Programacion web	t	\N	\N	\N	uploads\\signatures/fe40ce85afa741c9991141fdae52b75b.png
3	4	B004	2026-04-06	15:30:00	16:00:00	test	APPROVED	si	2026-04-06 15:28:28.064147	2026-04-06 15:28:49.29609	TRM51	Test Student	test	t	\N	\N	\N	uploads\\signatures/5acf597e93654e129880fc1306a1ed21.png
4	4	B003	2026-04-06	19:00:00	19:30:00	\N	APPROVED	\N	2026-04-06 18:38:33.438913	2026-04-06 18:38:55.975309	TRM51	Test Student	test1	t	\N	\N	\N	uploads\\signatures/25e7cd990c874af1801fa2e9f51073bc.png
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.role_permissions (id, role, permission_id) FROM stdin;
1	STUDENT	1
2	STUDENT	7
3	STUDENT	8
4	STUDENT	12
5	TEACHER	1
6	TEACHER	7
7	TEACHER	8
8	TEACHER	10
9	TEACHER	12
10	TEACHER	13
11	STAFF	2
12	STAFF	5
13	STAFF	6
14	STAFF	7
15	STAFF	8
16	STAFF	12
17	ADMIN	1
18	ADMIN	2
19	ADMIN	3
20	ADMIN	4
21	ADMIN	5
22	ADMIN	6
23	ADMIN	7
24	ADMIN	8
25	ADMIN	9
26	ADMIN	10
27	ADMIN	11
28	ADMIN	12
29	ADMIN	13
30	ADMIN	14
31	SUPERADMIN	1
32	SUPERADMIN	2
33	SUPERADMIN	3
34	SUPERADMIN	4
35	SUPERADMIN	5
36	SUPERADMIN	6
37	SUPERADMIN	7
38	SUPERADMIN	8
39	SUPERADMIN	9
40	SUPERADMIN	10
41	SUPERADMIN	11
42	SUPERADMIN	12
43	SUPERADMIN	13
44	SUPERADMIN	14
48	STUDENT	10
\.


--
-- Data for Name: software; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.software (id, lab_id, name, version, license_type, notes, update_requested, update_note, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: subjects; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.subjects (id, career_id, level, quarter, name, is_active, created_at, academic_level_id) FROM stdin;
\.


--
-- Data for Name: teacher_academic_loads; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.teacher_academic_loads (id, teacher_id, subject_id, group_code, created_at) FROM stdin;
\.


--
-- Data for Name: ticket_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.ticket_items (id, ticket_id, material_id, quantity_requested, quantity_delivered, quantity_returned, status, notes) FROM stdin;
3	1	162	2	2	2	RETURNED	\N
4	1	163	2	2	2	RETURNED	\N
5	2	162	6	4	3	DELIVERED	\N
6	3	162	4	1	1	RETURNED	\N
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, email, password_hash, role, is_verified, created_at, verified_at, profile_completed, full_name, matricula, career, career_year, phone, professor_subjects, is_active, is_banned, career_id, academic_level, academic_level_id, profile_data_confirmed, profile_confirmed_at, current_quarter, email_verification_code, email_verification_expires_at, verification_sent_at, verify_token_version, email_change_count, email_change_window_started_at) FROM stdin;
4	student@test.com	scrypt:32768:8:1$DGSCWbKVzy0ryd2e$cd0e985ba0c1e092038c8658f415eeee1c0aaa5d12462b229fb5844083c09d28c7390cf821b36aca5c1186271545c8719164c8d4e2977db1db523ad2eccbb7c2	STUDENT	t	2026-04-06 12:03:32.792236	\N	t	Test Student	20230001	\N	\N	6561111111	\N	t	f	3	\N	1	t	\N	3	\N	\N	\N	1	0	\N
1	superadmin@utpn.edu.mx	scrypt:32768:8:1$hm9xyTVWt3IyOs5A$271121ac02ffd22a43e22ed015a44dd9ec03e31413d90de66ae2f76c47c3f036cd14c8f9734168cb88f78935f584aac858f055a08e9888c90805ae017c83aed5	SUPERADMIN	t	2026-04-04 21:42:54.095209	\N	t	s Gonzalez	\N	\N	\N	654534845	\N	t	f	\N	\N	\N	f	\N	\N	\N	\N	\N	1	0	\N
\.


--
-- Name: academic_levels_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.academic_levels_id_seq', 3, true);


--
-- Name: careers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.careers_id_seq', 7, true);


--
-- Name: critical_action_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.critical_action_requests_id_seq', 1, false);


--
-- Name: debts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.debts_id_seq', 6, true);


--
-- Name: forum_comments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.forum_comments_id_seq', 1, false);


--
-- Name: forum_posts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.forum_posts_id_seq', 1, false);


--
-- Name: inventory_request_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.inventory_request_items_id_seq', 1, false);


--
-- Name: inventory_request_tickets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.inventory_request_tickets_id_seq', 1, false);


--
-- Name: lab_tickets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.lab_tickets_id_seq', 3, true);


--
-- Name: labs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.labs_id_seq', 7, true);


--
-- Name: logbook_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.logbook_events_id_seq', 37, true);


--
-- Name: lost_found_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.lost_found_id_seq', 1, true);


--
-- Name: materials_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.materials_id_seq', 421, true);


--
-- Name: notifications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notifications_id_seq', 34, true);


--
-- Name: permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.permissions_id_seq', 14, true);


--
-- Name: print3d_jobs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.print3d_jobs_id_seq', 1, true);


--
-- Name: profile_change_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.profile_change_requests_id_seq', 1, false);


--
-- Name: reservation_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.reservation_items_id_seq', 1, true);


--
-- Name: reservations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.reservations_id_seq', 4, true);


--
-- Name: role_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.role_permissions_id_seq', 48, true);


--
-- Name: software_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.software_id_seq', 1, false);


--
-- Name: subjects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.subjects_id_seq', 1, false);


--
-- Name: teacher_academic_loads_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.teacher_academic_loads_id_seq', 1, false);


--
-- Name: ticket_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.ticket_items_id_seq', 6, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 4, true);


--
-- Name: academic_levels academic_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.academic_levels
    ADD CONSTRAINT academic_levels_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: career_level_rules career_level_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.career_level_rules
    ADD CONSTRAINT career_level_rules_pkey PRIMARY KEY (career_id, academic_level_id);


--
-- Name: careers careers_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.careers
    ADD CONSTRAINT careers_name_key UNIQUE (name);


--
-- Name: careers careers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.careers
    ADD CONSTRAINT careers_pkey PRIMARY KEY (id);


--
-- Name: critical_action_requests critical_action_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.critical_action_requests
    ADD CONSTRAINT critical_action_requests_pkey PRIMARY KEY (id);


--
-- Name: debts debts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debts
    ADD CONSTRAINT debts_pkey PRIMARY KEY (id);


--
-- Name: forum_comments forum_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_comments
    ADD CONSTRAINT forum_comments_pkey PRIMARY KEY (id);


--
-- Name: forum_posts forum_posts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_posts
    ADD CONSTRAINT forum_posts_pkey PRIMARY KEY (id);


--
-- Name: inventory_request_items inventory_request_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_items
    ADD CONSTRAINT inventory_request_items_pkey PRIMARY KEY (id);


--
-- Name: inventory_request_tickets inventory_request_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_tickets
    ADD CONSTRAINT inventory_request_tickets_pkey PRIMARY KEY (id);


--
-- Name: lab_tickets lab_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lab_tickets
    ADD CONSTRAINT lab_tickets_pkey PRIMARY KEY (id);


--
-- Name: labs labs_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.labs
    ADD CONSTRAINT labs_name_key UNIQUE (name);


--
-- Name: labs labs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.labs
    ADD CONSTRAINT labs_pkey PRIMARY KEY (id);


--
-- Name: logbook_events logbook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.logbook_events
    ADD CONSTRAINT logbook_events_pkey PRIMARY KEY (id);


--
-- Name: lost_found lost_found_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lost_found
    ADD CONSTRAINT lost_found_pkey PRIMARY KEY (id);


--
-- Name: materials materials_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_name_key UNIQUE (name);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: print3d_jobs print3d_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.print3d_jobs
    ADD CONSTRAINT print3d_jobs_pkey PRIMARY KEY (id);


--
-- Name: profile_change_requests profile_change_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profile_change_requests
    ADD CONSTRAINT profile_change_requests_pkey PRIMARY KEY (id);


--
-- Name: reservation_items reservation_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservation_items
    ADD CONSTRAINT reservation_items_pkey PRIMARY KEY (id);


--
-- Name: reservations reservations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- Name: software software_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.software
    ADD CONSTRAINT software_pkey PRIMARY KEY (id);


--
-- Name: subjects subjects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT subjects_pkey PRIMARY KEY (id);


--
-- Name: teacher_academic_loads teacher_academic_loads_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher_academic_loads
    ADD CONSTRAINT teacher_academic_loads_pkey PRIMARY KEY (id);


--
-- Name: ticket_items ticket_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_items
    ADD CONSTRAINT ticket_items_pkey PRIMARY KEY (id);


--
-- Name: academic_levels uq_academic_levels_code; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.academic_levels
    ADD CONSTRAINT uq_academic_levels_code UNIQUE (code);


--
-- Name: academic_levels uq_academic_levels_name; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.academic_levels
    ADD CONSTRAINT uq_academic_levels_name UNIQUE (name);


--
-- Name: inventory_request_items uq_inventory_request_item_ticket_material; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_items
    ADD CONSTRAINT uq_inventory_request_item_ticket_material UNIQUE (ticket_id, material_id);


--
-- Name: role_permissions uq_role_permission; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT uq_role_permission UNIQUE (role, permission_id);


--
-- Name: subjects uq_subject_catalog; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT uq_subject_catalog UNIQUE (career_id, level, quarter, name);


--
-- Name: teacher_academic_loads uq_teacher_subject_group; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher_academic_loads
    ADD CONSTRAINT uq_teacher_subject_group UNIQUE (teacher_id, subject_id, group_code);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_debts_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_debts_user ON public.debts USING btree (user_id);


--
-- Name: idx_lab_tickets_reservation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_lab_tickets_reservation_id ON public.lab_tickets USING btree (reservation_id);


--
-- Name: idx_notifications_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notifications_user ON public.notifications USING btree (user_id);


--
-- Name: idx_reservation_items_reservation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reservation_items_reservation_id ON public.reservation_items USING btree (reservation_id);


--
-- Name: idx_reservations_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reservations_date ON public.reservations USING btree (date);


--
-- Name: idx_reservations_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reservations_user ON public.reservations USING btree (user_id);


--
-- Name: idx_ticket_items_material; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ticket_items_material ON public.ticket_items USING btree (material_id);


--
-- Name: idx_ticket_items_ticket_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ticket_items_ticket_id ON public.ticket_items USING btree (ticket_id);


--
-- Name: ix_academic_levels_is_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_academic_levels_is_active ON public.academic_levels USING btree (is_active);


--
-- Name: ix_debts_ticket_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_debts_ticket_id ON public.debts USING btree (ticket_id);


--
-- Name: ix_forum_comments_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_forum_comments_created_at ON public.forum_comments USING btree (created_at DESC);


--
-- Name: ix_forum_comments_hidden; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_forum_comments_hidden ON public.forum_comments USING btree (is_hidden);


--
-- Name: ix_forum_comments_post_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_forum_comments_post_id ON public.forum_comments USING btree (post_id);


--
-- Name: ix_forum_posts_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_forum_posts_category ON public.forum_posts USING btree (category);


--
-- Name: ix_forum_posts_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_forum_posts_created_at ON public.forum_posts USING btree (created_at DESC);


--
-- Name: ix_forum_posts_hidden; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_forum_posts_hidden ON public.forum_posts USING btree (is_hidden);


--
-- Name: ix_inventory_request_tickets_request_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_inventory_request_tickets_request_date ON public.inventory_request_tickets USING btree (request_date);


--
-- Name: ix_inventory_request_tickets_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_inventory_request_tickets_status ON public.inventory_request_tickets USING btree (status);


--
-- Name: ix_inventory_request_tickets_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_inventory_request_tickets_user_id ON public.inventory_request_tickets USING btree (user_id);


--
-- Name: ix_logbook_events_module; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_logbook_events_module ON public.logbook_events USING btree (module);


--
-- Name: ix_materials_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_materials_category ON public.materials USING btree (category);


--
-- Name: ix_print3d_jobs_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_print3d_jobs_created_at ON public.print3d_jobs USING btree (created_at);


--
-- Name: ix_print3d_jobs_requester_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_print3d_jobs_requester_user_id ON public.print3d_jobs USING btree (requester_user_id);


--
-- Name: ix_print3d_jobs_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_print3d_jobs_status ON public.print3d_jobs USING btree (status);


--
-- Name: ix_profile_change_requests_request_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_profile_change_requests_request_type ON public.profile_change_requests USING btree (request_type);


--
-- Name: ix_profile_change_requests_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_profile_change_requests_status ON public.profile_change_requests USING btree (status);


--
-- Name: ix_profile_change_requests_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_profile_change_requests_user_id ON public.profile_change_requests USING btree (user_id);


--
-- Name: ix_reservations_subject_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_reservations_subject_id ON public.reservations USING btree (subject_id);


--
-- Name: ix_subjects_academic_level_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_subjects_academic_level_id ON public.subjects USING btree (academic_level_id);


--
-- Name: ix_subjects_career_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_subjects_career_id ON public.subjects USING btree (career_id);


--
-- Name: ix_subjects_level; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_subjects_level ON public.subjects USING btree (level);


--
-- Name: ix_teacher_academic_loads_subject_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_teacher_academic_loads_subject_id ON public.teacher_academic_loads USING btree (subject_id);


--
-- Name: ix_teacher_academic_loads_teacher_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_teacher_academic_loads_teacher_id ON public.teacher_academic_loads USING btree (teacher_id);


--
-- Name: ix_users_academic_level_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_users_academic_level_id ON public.users USING btree (academic_level_id);


--
-- Name: print3d_jobs trg_set_updated_at_print3d_jobs; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_set_updated_at_print3d_jobs BEFORE UPDATE ON public.print3d_jobs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at_print3d_jobs();


--
-- Name: users trg_validate_user_career_level; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_validate_user_career_level BEFORE INSERT OR UPDATE OF career_id, academic_level_id ON public.users FOR EACH ROW EXECUTE FUNCTION public.validate_user_career_level();


--
-- Name: career_level_rules career_level_rules_academic_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.career_level_rules
    ADD CONSTRAINT career_level_rules_academic_level_id_fkey FOREIGN KEY (academic_level_id) REFERENCES public.academic_levels(id) ON DELETE CASCADE;


--
-- Name: career_level_rules career_level_rules_career_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.career_level_rules
    ADD CONSTRAINT career_level_rules_career_id_fkey FOREIGN KEY (career_id) REFERENCES public.careers(id) ON DELETE CASCADE;


--
-- Name: debts debts_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debts
    ADD CONSTRAINT debts_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: debts debts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debts
    ADD CONSTRAINT debts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: debts fk_debts_ticket_id_lab_tickets; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.debts
    ADD CONSTRAINT fk_debts_ticket_id_lab_tickets FOREIGN KEY (ticket_id) REFERENCES public.lab_tickets(id);


--
-- Name: forum_comments fk_forum_comments_author; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_comments
    ADD CONSTRAINT fk_forum_comments_author FOREIGN KEY (author_id) REFERENCES public.users(id);


--
-- Name: forum_comments fk_forum_comments_hidden_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_comments
    ADD CONSTRAINT fk_forum_comments_hidden_by FOREIGN KEY (hidden_by) REFERENCES public.users(id);


--
-- Name: forum_comments fk_forum_comments_post; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_comments
    ADD CONSTRAINT fk_forum_comments_post FOREIGN KEY (post_id) REFERENCES public.forum_posts(id) ON DELETE CASCADE;


--
-- Name: forum_posts fk_forum_posts_author; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_posts
    ADD CONSTRAINT fk_forum_posts_author FOREIGN KEY (author_id) REFERENCES public.users(id);


--
-- Name: forum_posts fk_forum_posts_hidden_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_posts
    ADD CONSTRAINT fk_forum_posts_hidden_by FOREIGN KEY (hidden_by) REFERENCES public.users(id);


--
-- Name: forum_posts fk_hidden_by_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.forum_posts
    ADD CONSTRAINT fk_hidden_by_user FOREIGN KEY (hidden_by) REFERENCES public.users(id);


--
-- Name: materials fk_materials_career; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT fk_materials_career FOREIGN KEY (career_id) REFERENCES public.careers(id);


--
-- Name: print3d_jobs fk_print3d_jobs_quoted_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.print3d_jobs
    ADD CONSTRAINT fk_print3d_jobs_quoted_by FOREIGN KEY (quoted_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: print3d_jobs fk_print3d_jobs_requester; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.print3d_jobs
    ADD CONSTRAINT fk_print3d_jobs_requester FOREIGN KEY (requester_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: profile_change_requests fk_profile_change_requests_requested_academic_level_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profile_change_requests
    ADD CONSTRAINT fk_profile_change_requests_requested_academic_level_id FOREIGN KEY (requested_academic_level_id) REFERENCES public.academic_levels(id);


--
-- Name: profile_change_requests fk_profile_change_requests_requested_career_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profile_change_requests
    ADD CONSTRAINT fk_profile_change_requests_requested_career_id FOREIGN KEY (requested_career_id) REFERENCES public.careers(id);


--
-- Name: profile_change_requests fk_profile_change_requests_reviewed_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profile_change_requests
    ADD CONSTRAINT fk_profile_change_requests_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: profile_change_requests fk_profile_change_requests_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profile_change_requests
    ADD CONSTRAINT fk_profile_change_requests_user_id FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: critical_action_requests fk_requester; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.critical_action_requests
    ADD CONSTRAINT fk_requester FOREIGN KEY (requester_id) REFERENCES public.users(id);


--
-- Name: reservations fk_reservations_subject_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT fk_reservations_subject_id FOREIGN KEY (subject_id) REFERENCES public.subjects(id);


--
-- Name: critical_action_requests fk_reviewer; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.critical_action_requests
    ADD CONSTRAINT fk_reviewer FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: subjects fk_subjects_academic_level_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT fk_subjects_academic_level_id FOREIGN KEY (academic_level_id) REFERENCES public.academic_levels(id);


--
-- Name: critical_action_requests fk_target; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.critical_action_requests
    ADD CONSTRAINT fk_target FOREIGN KEY (target_user_id) REFERENCES public.users(id);


--
-- Name: users fk_users_academic_level_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_academic_level_id FOREIGN KEY (academic_level_id) REFERENCES public.academic_levels(id);


--
-- Name: users fk_users_career_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_career_id FOREIGN KEY (career_id) REFERENCES public.careers(id);


--
-- Name: inventory_request_items inventory_request_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_items
    ADD CONSTRAINT inventory_request_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: inventory_request_items inventory_request_items_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_items
    ADD CONSTRAINT inventory_request_items_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES public.inventory_request_tickets(id);


--
-- Name: inventory_request_tickets inventory_request_tickets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_request_tickets
    ADD CONSTRAINT inventory_request_tickets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: lab_tickets lab_tickets_closed_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lab_tickets
    ADD CONSTRAINT lab_tickets_closed_by_user_id_fkey FOREIGN KEY (closed_by_user_id) REFERENCES public.users(id);


--
-- Name: lab_tickets lab_tickets_opened_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lab_tickets
    ADD CONSTRAINT lab_tickets_opened_by_user_id_fkey FOREIGN KEY (opened_by_user_id) REFERENCES public.users(id);


--
-- Name: lab_tickets lab_tickets_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lab_tickets
    ADD CONSTRAINT lab_tickets_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.users(id);


--
-- Name: lab_tickets lab_tickets_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lab_tickets
    ADD CONSTRAINT lab_tickets_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservations(id);


--
-- Name: logbook_events logbook_events_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.logbook_events
    ADD CONSTRAINT logbook_events_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: logbook_events logbook_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.logbook_events
    ADD CONSTRAINT logbook_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: lost_found lost_found_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lost_found
    ADD CONSTRAINT lost_found_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: lost_found lost_found_reported_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lost_found
    ADD CONSTRAINT lost_found_reported_by_user_id_fkey FOREIGN KEY (reported_by_user_id) REFERENCES public.users(id);


--
-- Name: materials materials_lab_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_lab_id_fkey FOREIGN KEY (lab_id) REFERENCES public.labs(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: reservation_items reservation_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservation_items
    ADD CONSTRAINT reservation_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: reservation_items reservation_items_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservation_items
    ADD CONSTRAINT reservation_items_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservations(id) ON DELETE CASCADE;


--
-- Name: reservations reservations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;


--
-- Name: software software_lab_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.software
    ADD CONSTRAINT software_lab_id_fkey FOREIGN KEY (lab_id) REFERENCES public.labs(id);


--
-- Name: subjects subjects_career_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subjects
    ADD CONSTRAINT subjects_career_id_fkey FOREIGN KEY (career_id) REFERENCES public.careers(id);


--
-- Name: teacher_academic_loads teacher_academic_loads_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher_academic_loads
    ADD CONSTRAINT teacher_academic_loads_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subjects(id);


--
-- Name: teacher_academic_loads teacher_academic_loads_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher_academic_loads
    ADD CONSTRAINT teacher_academic_loads_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id);


--
-- Name: ticket_items ticket_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_items
    ADD CONSTRAINT ticket_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: ticket_items ticket_items_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_items
    ADD CONSTRAINT ticket_items_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES public.lab_tickets(id);


--
-- PostgreSQL database dump complete
--

\unrestrict bgjThpoXxfdahqJrylSVX9JGL1QKjwdSAxidVpBEesimgJ8zjtL3NFKeN6kgR9f

