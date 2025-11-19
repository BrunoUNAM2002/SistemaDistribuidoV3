import socket
import threading
from datetime import datetime
import sqlite3
import json
import os

# --- Configuración de Rutas ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_SCHEMA_PATH = os.path.join(BASE_DIR, 'schema2.sql')
DB_PATH = os.path.join(BASE_DIR, 'emergencias.db')

# --- Configuración de Red ---
SERVER_PORT = 5555 
NODOS_REMOTOS = [
    # ('192.168.X.X', 5555), <--- Agrega aquí las IPs de tus clones cuando los tengas
]

# --- Flag de Cierre ---
shutdown_event = threading.Event()

# --- Funciones de Base de Datos ---

def init_db():
    print(f"Inicializando la base de datos en: {DB_PATH}")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Solo intentamos crear si no existe, leyendo el schema
        if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
             print(f"Leyendo 'planos' desde: {SQL_SCHEMA_PATH}")
             with open(SQL_SCHEMA_PATH, 'r') as f:
                sql_script = f.read()
             cursor.executescript(sql_script)
             print("Tablas creadas.")
        
        conn.commit()
        print(f"¡Conexión a BD exitosa!")

    except Exception as e:
        print(f"Nota: {e}") # Puede fallar si la tabla ya existe, es normal.
    finally:
        if conn: conn.close()

def ejecutar_transaccion(comando):
    """ Ejecuta un comando SQL generado localmente o recibido por red """
    print(f"[BD Local] Ejecutando: {comando['accion']} en {comando['tabla']}")
    # Aquí iría la lógica para convertir el JSON a SQL (INSERT/UPDATE)
    # Por ahora es un placeholder funcional para la demo.

# --- Funciones de Red (Middleware) ---

def propagar_transaccion(comando_json):
    if not NODOS_REMOTOS:
        return # No hacer nada si no hay nodos configurados
        
    print(f"Propagando a {len(NODOS_REMOTOS)} nodos...")
    for (ip, puerto) in NODOS_REMOTOS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((ip, puerto))
                s.sendall(comando_json.encode('utf-8'))
                s.recv(1024) # Esperar ACK
        except Exception as e:
            print(f"Error al propagar a {ip}: {e}")

def handle_client(client_socket, client_address):
    try:
        message = client_socket.recv(1024).decode('utf-8')
        if message:
            comando = json.loads(message)
            print(f"Transacción recibida de {client_address}: {comando}")
            ejecutar_transaccion(comando)
            client_socket.send("OK".encode('utf-8'))
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        client_socket.close()

def server(server_port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', server_port))
    server_socket.listen(5)
    server_socket.settimeout(1.0)
    
    while not shutdown_event.is_set():
        try:
            client_socket, client_address = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            thread.daemon = True
            thread.start()
        except socket.timeout:
            continue
        except Exception:
            pass
    server_socket.close()

# --- FUNCIONES DE LA APLICACIÓN (VISUALIZACIÓN) ---

def ver_pacientes_locales():
    print("\n--- 🤕 PACIENTES Y SU MÉDICO ASIGNADO ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # SQL AVANZADO:
    # Unimos la tabla PACIENTES (p) con VISITAS (v) y luego con DOCTORES (d)
    query = """
        SELECT p.id, p.nombre, p.edad, d.nombre
        FROM PACIENTES p
        LEFT JOIN VISITAS_EMERGENCIA v ON p.id = v.paciente_id
        LEFT JOIN DOCTORES d ON v.doctor_id = d.id
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("   (Sin registros)")
    
    for r in rows:
        # r[0]=id, r[1]=nombre_paciente, r[2]=edad, r[3]=nombre_doctor
        
        if r[3]: # Si r[3] no es None, hay un doctor asignado
            estado_medico = f"✅ Atendido por: {r[3]}"
        else:
            estado_medico = "⚠️ ESPERANDO ASIGNACIÓN"
            
        print(f"   ID: {r[0]} | {r[1]} ({r[2]} años) -> {estado_medico}")

#Ver doctores locales 

def ver_doctores_locales():
    print("\n--- 👨‍⚕️ DOCTORES ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, disponible FROM DOCTORES")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: print("   (Sin registros)")
    for r in rows:
        estado = "Disponible" if r[2] == 1 else "Ocupado"
        print(f"   ID: {r[0]} | {r[1]} - {estado}")

def ver_camas_locales():
    print("\n--- 🛏️ ESTADO DE CAMAS ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Hacemos un LEFT JOIN para ver el nombre del paciente si la cama está ocupada
    query = """
        SELECT c.numero, c.ocupada, p.nombre 
        FROM CAMAS_ATENCION c
        LEFT JOIN PACIENTES p ON c.paciente_id = p.id
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: print("   (Sin registros)")
    for r in rows:
        # r[0]=numero, r[1]=ocupada, r[2]=nombre_paciente
        if r[1] == 1:
            estado = f"OCUPADA por: {r[2]}"
        else:
            estado = "LIBRE"
        print(f"   Cama {r[0]}: {estado}")

def ver_trabajadores_sociales():
    print("\n--- TRABAJADORES SOCIALES ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, activo FROM TRABAJADORES_SOCIALES")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: print("   (Sin registros)")
    for r in rows:
        estado = "Activo" if r[2] == 1 else "Inactivo"
        print(f"   ID: {r[0]} | {r[1]} ({estado})")

def asignar_doctor():
    print("\n--- ASIGNAR DOCTOR A PACIENTE ---")
    
    # 1. Pedimos los IDs
    try:
        ver_pacientes_locales() # Mostramos la lista para que el usuario sepa qué ID elegir
        id_paciente = int(input("\nIngrese ID del Paciente: "))
        
        print("\n--- Doctores Disponibles ---")
        ver_doctores_locales()
        id_doctor = int(input("Ingrese ID del Doctor a asignar: "))
    except ValueError:
        print("Error: Debes ingresar números válidos.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 2. Verificamos si el doctor está realmente disponible
        cursor.execute("SELECT disponible, nombre FROM DOCTORES WHERE id = ?", (id_doctor,))
        doctor_data = cursor.fetchone()
        
        if not doctor_data:
            print("Error: El doctor no existe.")
            return
            
        if doctor_data[0] == 0:
            print(f"Error: El {doctor_data[1]} ya está OCUPADO con otro paciente.")
            return

        # 3. Realizamos la ASIGNACIÓN (Son 2 pasos en la BD)
        
        # Paso A: Actualizamos la visita médica del paciente
        # (Asumimos que ya existe una visita creada al registrar al paciente, si no, habría que crearla)
        # Nota: Si no hay visita abierta, esto no hará nada, pero para este ejemplo asumimos que sí.
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Verificamos si el paciente ya tiene visita
        cursor.execute("SELECT folio FROM VISITAS_EMERGENCIA WHERE paciente_id = ?", (id_paciente,))
        visita = cursor.fetchone()
        
        if visita:
            # Actualizamos visita existente
            cursor.execute("""
                UPDATE VISITAS_EMERGENCIA 
                SET doctor_id = ?, estado = 'En Consulta' 
                WHERE paciente_id = ?
            """, (id_doctor, id_paciente))
        else:
            # Creamos nueva visita si no tenía
            folio = f"URG-{id_paciente}-{id_doctor}"
            cursor.execute("""
                INSERT INTO VISITAS_EMERGENCIA (folio, paciente_id, doctor_id, sala_id, timestamp, estado)
                VALUES (?, ?, ?, 1, ?, 'En Consulta')
            """, (folio, id_paciente, id_doctor, timestamp))

        # Paso B: Marcamos al doctor como OCUPADO
        cursor.execute("UPDATE DOCTORES SET disponible = 0 WHERE id = ?", (id_doctor,))
        
        conn.commit()
        
        print(f"\n¡Éxito! El {doctor_data[1]} ha sido asignado al paciente {id_paciente}.")
        
        # Paso 4: Propagamos el cambio (JSON simple para notificar)
        comando = {
            "accion": "ASIGNAR_DOCTOR",
            "datos": {"paciente_id": id_paciente, "doctor_id": id_doctor}
        }
        propagar_transaccion(json.dumps(comando))

    except Exception as e:
        print(f"Error al asignar: {e}")
        conn.rollback()
    finally:
        conn.close()


def ver_visitas_emergencia():
    print("\n--- HISTORIAL DE VISITAS (Bitácora) ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Seleccionamos Folio, Estado y Fecha
    cursor.execute("SELECT folio, estado, timestamp, paciente_id FROM VISITAS_EMERGENCIA")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: print("   (Sin registros)")
    for r in rows:
        print(f"   {r[0]} | Estado: {r[1]}")
        print(f"      Fecha: {r[2]} | Paciente ID: {r[3]}")
        print("      " + "-"*30)

def registrar_nuevo_paciente():
    print("\n[Nuevo Ingreso]")
    try:
        nombre = input("Nombre: ")
        edad = int(input("Edad: "))
        contacto = input("Contacto: ")
        
        comando = {
            "accion": "INSERTAR",
            "tabla": "PACIENTES",
            "datos": {"nombre": nombre, "edad": edad, "contacto": contacto}
        }
        
        ejecutar_transaccion(comando) # Simulado
        # Aquí deberías hacer el INSERT real en BD local también si quieres persistencia inmediata
        
        print("Paciente procesado localmente.")
        propagar_transaccion(json.dumps(comando))
        
    except ValueError:
        print("Error: Edad inválida.")

# --- Función Principal ---

def main():
    init_db()
    
    t = threading.Thread(target=server, args=(SERVER_PORT,))
    t.daemon = True
    t.start()
    
    print(f"\nNODO ACTIVO - Puerto {SERVER_PORT}")
    print("Sistema de Gestión Distribuida v1.0")

    try:
        while True:
            print("\n" + "="*30)
            print("       MENÚ PRINCIPAL")
            print("="*30)
            print("1. Registrar Nuevo Paciente")
            print("2. Ver Pacientes")
            print("3. Ver Doctores")
            print("4. Ver Camas")
            print("5. Ver Trabajadores Sociales")
            print("6. Ver Visitas (Bitácora)")
            print("9. Salir")
            print("-" * 30)
            
            op = input("Opción > ")

            if op == '1': registrar_nuevo_paciente()
            elif op == '2': ver_pacientes_locales()
            elif op == '3': ver_doctores_locales()
            elif op == '4': ver_camas_locales()
            elif op == '5': ver_trabajadores_sociales()
            elif op == '6': ver_visitas_emergencia()
            elif op == '9': 
                print("Cerrando sistema..."); shutdown_event.set(); break
            else: print("Opción no válida.")
            
    except KeyboardInterrupt:
        shutdown_event.set()

    print("Esperando cierre de hilos...")
    threading.Event().wait(1)

if __name__ == "__main__":
    main()