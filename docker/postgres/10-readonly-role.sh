#!/bin/sh
# Creates the role the API connects with. It can read the analytics tables and nothing else.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v ro_password="$QUERYA_RO_PASSWORD" <<-'SQL'
	CREATE ROLE querya_ro LOGIN PASSWORD :'ro_password'
	  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
	ALTER ROLE querya_ro SET default_transaction_read_only = on;
	ALTER ROLE querya_ro SET statement_timeout = '5s';
	REVOKE ALL ON SCHEMA public FROM PUBLIC;
	GRANT CONNECT ON DATABASE :"DBNAME" TO querya_ro;
	GRANT USAGE ON SCHEMA public TO querya_ro;
	GRANT SELECT ON ALL TABLES IN SCHEMA public TO querya_ro;
	ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO querya_ro;
SQL
