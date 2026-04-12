-- Drop existing enum and table if they exist
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS user_role CASCADE;

-- Create user_role enum
CREATE TYPE user_role AS ENUM ('admin', 'finance', 'accounting');

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    family_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    role user_role NOT NULL DEFAULT 'accounting',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- Insert default admin user (password: admin123)
INSERT INTO users (
    username, email, password_hash, 
    first_name, family_name, full_name, 
    role, is_active
) VALUES (
    'admin', 
    'admin@brightwaves.com',
    '$2b$12$RG1zCq5rx08iIDbTqy8B4eovrv5KytFdztatQliZHddGabEuqNRd2',
    'Admin',
    'User',
    'Admin User',
    'admin',
    1
);
