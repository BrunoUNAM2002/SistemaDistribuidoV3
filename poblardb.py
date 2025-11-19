import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'emergencias.db')

def poblar_datos_reales():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        print("🧹 Limpiando base de datos...")
        # Borramos tabla de usuarios si existe
        cursor.execute("DROP TABLE IF EXISTS USUARIOS_SISTEMA")
        
        cursor.execute("DELETE FROM VISITAS_EMERGENCIA")
        cursor.execute("DELETE FROM CAMAS_ATENCION")
        cursor.execute("DELETE FROM DOCTORES")
        cursor.execute("DELETE FROM TRABAJADORES_SOCIALES")
        cursor.execute("DELETE FROM PACIENTES")
        cursor.execute("DELETE FROM sqlite_sequence") 

        # --- CREAR TABLA DE USUARIOS (Solo para este script de población) ---
        # En el script principal init_db también debe estar, pero aquí aseguramos para insertar
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS USUARIOS_SISTEMA (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,  -- 'DOCTOR' o 'SOCIAL'
            id_personal INTEGER -- ID vinculado a tabla DOCTORES o TRABAJADORES_SOCIALES
        )
        """)

        # --- PACIENTES ---
        pacientes = [
            ('Gerardo Martínez', 34, 'M', '555-0192'),
            ('Lucía Fernández', 28, 'F', '555-1283'),
            ('Pedro N.', 8, 'M', 'Sin contacto')
        ]
        cursor.executemany("INSERT INTO PACIENTES (nombre, edad, sexo, contacto) VALUES (?, ?, ?, ?)", pacientes)

        # --- DOCTORES ---
        doctores = [
            ('Dr. Ricardo Mendiola', 1, 1),
            ('Dra. Elena Vázquez', 1, 0),
            ('Dr. Samuel Kim', 1, 1)
        ]
        cursor.executemany("INSERT INTO DOCTORES (nombre, sala_id, disponible) VALUES (?, ?, ?)", doctores)

        # --- TRABAJO SOCIAL ---
        # ID 1 será Lic. Roberto Gómez
        cursor.execute("INSERT INTO TRABAJADORES_SOCIALES (nombre, sala_id, activo) VALUES ('Lic. Roberto Gómez', 1, 1)")

        # --- CAMAS ---
        cursor.execute("INSERT INTO CAMAS_ATENCION (numero, sala_id, ocupada, paciente_id) VALUES (101, 1, 1, 1)")
        cursor.execute("INSERT INTO CAMAS_ATENCION (numero, sala_id, ocupada, paciente_id) VALUES (102, 1, 1, 2)")
        cursor.execute("INSERT INTO CAMAS_ATENCION (numero, sala_id, ocupada, paciente_id) VALUES (103, 1, 1, 3)")
        for i in range(104, 111):
            cursor.execute("INSERT INTO CAMAS_ATENCION (numero, sala_id, ocupada, paciente_id) VALUES (?, 1, 0, NULL)", (i,))

        # --- VISITAS ---
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        visitas = [
            ('URG-2025-001', 1, 2, 1, None, 1, timestamp, 'En Tratamiento'),
            ('URG-2025-002', 2, 3, 2, 1, 1, timestamp, 'En Observación')
        ]
        cursor.executemany("INSERT INTO VISITAS_EMERGENCIA (folio, paciente_id, doctor_id, cama_id, trabajador_social_id, sala_id, timestamp, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", visitas)

        # --- 🔐 USUARIOS DEL SISTEMA (LOGIN) ---
        print("🔐 Creando usuarios de acceso...")
        usuarios = [
            # Username, Password, Rol, ID_Personal
            ('social1', '1234', 'SOCIAL', 1),      # El Lic. Roberto Gómez
            ('doc_ricardo', 'doctor1', 'DOCTOR', 1), # Dr. Ricardo
            ('doc_elena', 'doctor2', 'DOCTOR', 2)    # Dra. Elena
        ]
        cursor.executemany("INSERT INTO USUARIOS_SISTEMA (username, password, rol, id_personal) VALUES (?, ?, ?, ?)", usuarios)

        conn.commit()
        print("\n✅ Base de datos actualizada con Usuarios y Roles.")
        print("Usuario Trabajo Social: 'social1' / pass: '1234'")
        print("Usuario Doctor: 'doc_ricardo' / pass: 'doctor1'")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    poblar_datos_reales()