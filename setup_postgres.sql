-- FOReporting v2 PostgreSQL Setup
-- Run this with: psql -U postgres -f setup_postgres.sql

-- Create the system user with proper permissions
DROP USER IF EXISTS system;
CREATE USER system WITH 
    PASSWORD 'BreslauerPlatz4' 
    CREATEDB 
    SUPERUSER;

-- Create the database
DROP DATABASE IF EXISTS foreporting_db;
CREATE DATABASE foreporting_db 
    OWNER system 
    ENCODING 'UTF8';

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE foreporting_db TO system;

-- Show the created user
\du system

-- Show the created database
\l foreporting_db