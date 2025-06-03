DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'test_db') THEN
        CREATE DATABASE test_db;
    END IF;
END
$$;

\c test_db;


CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    price INTEGER,
    count INTEGER,
    sales INTEGER
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER
);

CREATE TABLE IF NOT EXISTS outbox (
    id SERIAL PRIMARY KEY,
    cid TEXT NOT NULL UNIQUE,
    request_type TEXT NOT NULL,
    request_data JSON NOT NULL,
    status_request TEXT NOT NULL
);

GRANT ALL PRIVILEGES ON DATABASE test_db TO postgres;
ALTER DATABASE test_db OWNER TO postgres;
