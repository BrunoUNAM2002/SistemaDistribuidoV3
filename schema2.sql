-- Habilita el uso de claves foráneas en SQLite (importante)
PRAGMA foreign_keys = ON;

-- 1. TABLA DE PACIENTES
-- Almacena la información demográfica de los pacientes. 
-- Es una tabla maestra.
CREATE TABLE IF NOT EXISTS PACIENTES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    edad INTEGER,
    sexo TEXT,
    contacto TEXT
);

-- 2. TABLA DE DOCTORES
-- Catálogo de personal médico.
CREATE TABLE IF NOT EXISTS DOCTORES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    especialidad TEXT,
    sala_id INTEGER,         -- Sala a la que está asignado (ej: 1, 2, 3, 4)
    disponible INTEGER DEFAULT 1 -- 1 para true (disponible), 0 para false (ocupado)
);

-- 3. TABLA DE TRABAJADORES SOCIALES
-- Catálogo de personal de trabajo social.
CREATE TABLE IF NOT EXISTS TRABAJADORES_SOCIALES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    sala_id INTEGER,         -- Sala a la que está asignado
    activo INTEGER DEFAULT 1   -- 1 para true (activo), 0 para false (inactivo)
);

-- 4. TABLA DE CAMAS DE ATENCIÓN
-- Representa el estado de un recurso físico (camas).
-- Esta es una tabla de "estado".
CREATE TABLE IF NOT EXISTS CAMAS_ATENCION (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL,      -- El número visible de la cama (ej: 101, 102)
    sala_id INTEGER NOT NULL,     -- Sala a la que pertenece la cama
    ocupada INTEGER DEFAULT 0,  -- 1 para true (ocupada), 0 para false (libre)
    paciente_id INTEGER UNIQUE, -- Qué paciente la ocupa (si hay uno)
                                -- UNIQUE asegura que un paciente no esté en 2 camas
    
    FOREIGN KEY (paciente_id) REFERENCES PACIENTES(id)
);

-- 5. TABLA DE VISITAS DE EMERGENCIA (EL CORAZÓN DEL SISTEMA)
-- Esta es la tabla "transaccional" principal.
-- Cada registro es un evento de emergencia.
CREATE TABLE IF NOT EXISTS VISITAS_EMERGENCIA (
    folio TEXT PRIMARY KEY,       -- El ID de la visita (PK, como especificaste)
    paciente_id INTEGER NOT NULL,
    doctor_id INTEGER,
    cama_id INTEGER,
    trabajador_social_id INTEGER,
    sala_id INTEGER NOT NULL,     -- Sala que gestiona esta emergencia
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- Cuándo se registró
    estado TEXT,                  -- Ej: 'En espera', 'En triaje', 'Hospitalizado', 'Alta'
    
    -- Definición de todas las relaciones (claves foráneas)
    FOREIGN KEY (paciente_id) REFERENCES PACIENTES(id),
    FOREIGN KEY (doctor_id) REFERENCES DOCTORES(id),
    FOREIGN KEY (cama_id) REFERENCES CAMAS_ATENCION(id),
    FOREIGN KEY (trabajador_social_id) REFERENCES TRABAJADORES_SOCIALES(id)
);