import socket
import threading
from datetime import datetime
import sqlite3
import json
import os
import getpass
import time
import random

# --- Configuración de Rutas ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_SCHEMA_PATH = os.path.join(BASE_DIR, 'schema2.sql')
DB_PATH = os.path.join(BASE_DIR, 'emergencias.db')

# --- Configuración de Red ---
SERVER_PORT = 5555
NODOS_REMOTOS = [
    # ('192.168.95.131', 5555),
    # ('192.168.95.132', 5555),
]

# --- Flag de Cierre ---
shutdown_event = threading.Event()

# ==========================================
#      SISTEMA DE BLOQUEOS DISTRIBUIDOS
# ==========================================

bloqueos_locales = {}
lock_bloqueos = threading.Lock()

def verificar_recurso_local(recurso_tipo, recurso_id):
    """Verifica si un recurso está disponible LOCALMENTE"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if recurso_tipo == "DOCTOR":
            cursor.execute("SELECT disponible FROM DOCTORES WHERE id = ?", (recurso_id,))
            resultado = cursor.fetchone()
            return resultado and resultado[0] == 1
            
        elif recurso_tipo == "CAMA":
            cursor.execute("SELECT ocupada FROM CAMAS_ATENCION WHERE id = ?", (recurso_id,))
            resultado = cursor.fetchone()
            return resultado and resultado[0] == 0
    finally:
        conn.close()

def solicitar_bloqueo_distribuido(recurso_tipo, recurso_id):
    """Solicita bloqueo distribuido"""
    print(f"🔒 Solicitando bloqueo para {recurso_tipo} {recurso_id}...")
    
    # Verificar localmente primero
    if not verificar_recurso_local(recurso_tipo, recurso_id):
        print(f"❌ {recurso_tipo} {recurso_id} no disponible localmente")
        return False
    
    # Bloquear localmente
    with lock_bloqueos:
        clave = f"{recurso_tipo}_{recurso_id}"
        if clave in bloqueos_locales:
            print(f"❌ {recurso_tipo} {recurso_id} ya está bloqueado localmente")
            return False
        bloqueos_locales[clave] = datetime.now()
    
    # Solicitar bloqueo en otros nodos
    confirmaciones = 0
    comando = {
        "accion": "SOLICITAR_BLOQUEO",
        "recurso_tipo": recurso_tipo,
        "recurso_id": recurso_id,
        "solicitante": SERVER_PORT
    }
    
    for (ip, puerto) in NODOS_REMOTOS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((ip, puerto))
                s.sendall(json.dumps(comando).encode('utf-8'))
                respuesta = s.recv(1024).decode('utf-8')
                if respuesta == "BLOQUEO_OK":
                    confirmaciones += 1
                    print(f"   ✅ {ip} aprobó bloqueo")
                else:
                    print(f"   ❌ {ip} rechazó bloqueo")
        except Exception as e:
            print(f"   ⚠️  {ip} no respondió: {e}")
    
    # Si la mayoría aprobó o no hay otros nodos
    if confirmaciones >= len(NODOS_REMOTOS) // 2 or not NODOS_REMOTOS:
        print(f"🎉 Bloqueo concedido para {recurso_tipo} {recurso_id}")
        return True
    else:
        print(f"❌ Bloqueo rechazado para {recurso_tipo} {recurso_id}")
        # Liberar bloqueo local
        with lock_bloqueos:
            clave = f"{recurso_tipo}_{recurso_id}"
            if clave in bloqueos_locales:
                del bloqueos_locales[clave]
        return False

def liberar_bloqueo_distribuido(recurso_tipo, recurso_id):
    """Libera bloqueo distribuido"""
    # Liberar localmente
    with lock_bloqueos:
        clave = f"{recurso_tipo}_{recurso_id}"
        if clave in bloqueos_locales:
            del bloqueos_locales[clave]
    
    # Liberar en otros nodos
    comando = {
        "accion": "LIBERAR_BLOQUEO",
        "recurso_tipo": recurso_tipo,
        "recurso_id": recurso_id
    }
    
    for (ip, puerto) in NODOS_REMOTOS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((ip, puerto))
                s.sendall(json.dumps(comando).encode('utf-8'))
        except:
            continue
    
    print(f"🔓 Bloqueo liberado para {recurso_tipo} {recurso_id}")

# ==========================================
#      GESTIÓN DE BASE DE DATOS
# ==========================================

def init_db():
    print(f"Verificando base de datos en: {DB_PATH}")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS USUARIOS_SISTEMA (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            id_personal INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS CONSECUTIVOS_VISITAS (
            sala_id INTEGER PRIMARY KEY,
            ultimo_consecutivo INTEGER DEFAULT 0
        )
        """)

        if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 100:
            if os.path.exists(SQL_SCHEMA_PATH):
                with open(SQL_SCHEMA_PATH, 'r') as f:
                    sql_script = f.read()
                cursor.executescript(sql_script)

        conn.commit()
    except Exception as e:
        print(f"Nota DB: {e}")
    finally:
        if conn:
            conn.close()

def ejecutar_transaccion_local(comando):
    """ Ejecuta SQL localmente """
    print(f"[BD Local] Ejecutando: {comando['accion']}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if comando['accion'] == "INSERTAR_PACIENTE":
            datos = comando['datos']
            cursor.execute(
                "INSERT INTO PACIENTES (nombre, edad, contacto) VALUES (?, ?, ?)",
                (datos['nombre'], datos['edad'], datos.get('contacto', ''))
            )
            paciente_id = cursor.lastrowid
            conn.commit()
            return paciente_id
            
        elif comando['accion'] == "ASIGNAR_RECURSOS":
            datos = comando['datos']
            # Ocupar doctor
            cursor.execute("UPDATE DOCTORES SET disponible = 0 WHERE id = ?", (datos['doctor_id'],))
            # Ocupar cama
            cursor.execute("UPDATE CAMAS_ATENCION SET ocupada = 1, paciente_id = ? WHERE id = ?", 
                         (datos['paciente_id'], datos['cama_id']))
            # Crear visita
            cursor.execute("""
                INSERT INTO VISITAS_EMERGENCIA 
                (folio, paciente_id, doctor_id, cama_id, sala_id, timestamp, estado) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datos['folio'], datos['paciente_id'], datos['doctor_id'], 
                  datos['cama_id'], SERVER_PORT, datetime.now(), 'En tratamiento'))
            
            conn.commit()
            return True
            
        elif comando['accion'] == "CERRAR_VISITA":
            datos = comando['datos']
            folio = datos['folio']
            
            # Obtener información de la visita
            cursor.execute("SELECT doctor_id, cama_id FROM VISITAS_EMERGENCIA WHERE folio = ?", (folio,))
            visita = cursor.fetchone()
            
            if visita:
                doctor_id, cama_id = visita
                
                # Liberar doctor
                cursor.execute("UPDATE DOCTORES SET disponible = 1 WHERE id = ?", (doctor_id,))
                
                # Liberar cama
                cursor.execute("UPDATE CAMAS_ATENCION SET ocupada = 0, paciente_id = NULL WHERE id = ?", (cama_id,))
                
                # Cerrar visita
                cursor.execute("UPDATE VISITAS_EMERGENCIA SET estado = 'Cerrada' WHERE folio = ?", (folio,))
                
                conn.commit()
                print(f"✅ Visita {folio} cerrada - Doctor {doctor_id} y Cama {cama_id} liberados")
                return True
            else:
                print(f"❌ Visita {folio} no encontrada")
                return False
            
        elif comando['accion'] == "INCREMENTAR_CONSECUTIVO":  # NUEVO
            # Incrementar consecutivo local
            cursor.execute("SELECT ultimo_consecutivo FROM CONSECUTIVOS_VISITAS WHERE sala_id = ?", (SERVER_PORT,))
            resultado = cursor.fetchone()
            if resultado:
                nuevo_consecutivo = resultado[0] + 1
                cursor.execute("UPDATE CONSECUTIVOS_VISITAS SET ultimo_consecutivo = ? WHERE sala_id = ?", 
                             (nuevo_consecutivo, SERVER_PORT))
                conn.commit()
                return nuevo_consecutivo
            else:
                cursor.execute("INSERT INTO CONSECUTIVOS_VISITAS (sala_id, ultimo_consecutivo) VALUES (?, 1)", 
                             (SERVER_PORT,))
                conn.commit()
                return 1
            
        conn.commit()
    except Exception as e:
        print(f"❌ Error ejecutando transacción local: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
#      SISTEMA DE CONSENSO
# ==========================================

def propagar_transaccion_con_consenso(comando):
    """Propaga transacción con consenso"""
    if not NODOS_REMOTOS:
        # Si no hay otros nodos, ejecutar directamente
        return ejecutar_transaccion_local(comando)

    comando_json = json.dumps(comando)
    confirmaciones = 0
    total_nodos = len(NODOS_REMOTOS)

    print(f"🔄 Buscando consenso para: {comando['accion']}")

    for (ip, puerto) in NODOS_REMOTOS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((ip, puerto))
                s.sendall(comando_json.encode('utf-8'))
                respuesta = s.recv(1024).decode('utf-8')
                if respuesta == "CONSENSO_OK":
                    confirmaciones += 1
                    print(f"   ✅ {ip}:{puerto} aceptó")
                else:
                    print(f"   ❌ {ip}:{puerto} rechazó: {respuesta}")
        except Exception as e:
            print(f"   ⚠️  {ip}:{puerto} no respondió: {e}")

    # Si la mayoría aceptó
    umbral_consenso = (total_nodos // 2) + 1
    if confirmaciones >= umbral_consenso:
        # Ejecutar localmente
        resultado = ejecutar_transaccion_local(comando)
        if resultado:
            print(f"🎉 CONSENSO ALCANZADO ({confirmaciones}/{total_nodos} nodos)")
            return True
        else:
            print("❌ Error ejecutando transacción local después del consenso")
            return False
    else:
        print(f"❌ CONSENSO FALLADO ({confirmaciones}/{total_nodos} nodos)")
        return False

# ==========================================
#      GENERACIÓN DE FOLIO EXACTO (NUEVO)
# ==========================================

def obtener_siguiente_consecutivo():
    """Obtiene el siguiente número consecutivo para visitas"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT ultimo_consecutivo FROM CONSECUTIVOS_VISITAS WHERE sala_id = ?", (SERVER_PORT,))
        resultado = cursor.fetchone()
        
        if resultado:
            nuevo_consecutivo = resultado[0] + 1
            # Actualizar consecutivo localmente primero
            cursor.execute("UPDATE CONSECUTIVOS_VISITAS SET ultimo_consecutivo = ? WHERE sala_id = ?", 
                         (nuevo_consecutivo, SERVER_PORT))
            conn.commit()
            
            # Propagarlo a otros nodos con consenso
            comando = {
                "accion": "INCREMENTAR_CONSECUTIVO",
                "datos": {}
            }
            propagar_transaccion_con_consenso(comando)
            
            return nuevo_consecutivo
        else:
            # Primera vez, inicializar
            cursor.execute("INSERT INTO CONSECUTIVOS_VISITAS (sala_id, ultimo_consecutivo) VALUES (?, 1)", 
                         (SERVER_PORT,))
            conn.commit()
            return 1
    finally:
        conn.close()

def generar_folio_exacto(paciente_id, doctor_id, sala_id):  # NUEVO
    """Genera folio según formato: IDPACIENTE+IDDOCTOR+SALADEEMERGENCIA+IDconsecutivoVISITA"""
    consecutivo = obtener_siguiente_consecutivo()
    folio = f"{paciente_id}{doctor_id}{sala_id}{consecutivo}"
    print(f"📄 Folio generado: {folio} (Formato: Paciente+Doctor+Sala+Consecutivo)")
    return folio

# ==========================================
#      DISTRIBUCIÓN AUTOMÁTICA (NUEVO)
# ==========================================

def encontrar_doctor_disponible():
    """Encuentra el primer doctor disponible"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, nombre FROM DOCTORES WHERE disponible = 1 ORDER BY id LIMIT 1")
        doctor = cursor.fetchone()
        return doctor
    finally:
        conn.close()

def encontrar_cama_disponible():
    """Encuentra la primera cama disponible"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, numero FROM CAMAS_ATENCION WHERE ocupada = 0 ORDER BY id LIMIT 1")
        cama = cursor.fetchone()
        return cama
    finally:
        conn.close()

def distribuir_visita_automaticamente(paciente_id):  # NUEVO
    """Distribuye automáticamente una visita a recursos disponibles"""
    print("🤖 DISTRIBUCIÓN AUTOMÁTICA ACTIVADA...")
    
    # Encontrar recursos disponibles
    doctor = encontrar_doctor_disponible()
    if not doctor:
        print("❌ No hay doctores disponibles para asignación automática")
        return None
    
    cama = encontrar_cama_disponible()
    if not cama:
        print("❌ No hay camas disponibles para asignación automática")
        return None
    
    doctor_id, doctor_nombre = doctor
    cama_id, cama_numero = cama
    
    print(f"   👨‍⚕️ Doctor asignado automáticamente: {doctor_nombre} (ID: {doctor_id})")
    print(f"   🛏️ Cama asignada automáticamente: {cama_numero} (ID: {cama_id})")
    
    # Solicitar bloqueos con exclusión mutua
    if not solicitar_bloqueo_distribuido("DOCTOR", doctor_id):
        print("❌ No se pudo bloquear el doctor en distribución automática")
        return None
        
    if not solicitar_bloqueo_distribuido("CAMA", cama_id):
        print("❌ No se pudo bloquear la cama en distribución automática")
        liberar_bloqueo_distribuido("DOCTOR", doctor_id)
        return None
    
    # Generar folio exacto
    folio = generar_folio_exacto(paciente_id, doctor_id, SERVER_PORT)
    
    # Ejecutar asignación con consenso
    comando = {
        "accion": "ASIGNAR_RECURSOS",
        "datos": {
            "folio": folio,
            "paciente_id": paciente_id,
            "doctor_id": doctor_id,
            "cama_id": cama_id
        }
    }
    
    if propagar_transaccion_con_consenso(comando):
        print(f"✅ DISTRIBUCIÓN AUTOMÁTICA EXITOSA - Folio: {folio}")
        liberar_bloqueo_distribuido("DOCTOR", doctor_id)
        liberar_bloqueo_distribuido("CAMA", cama_id)
        return folio
    else:
        print("❌ Error en distribución automática")
        liberar_bloqueo_distribuido("DOCTOR", doctor_id)
        liberar_bloqueo_distribuido("CAMA", cama_id)
        return None

# ==========================================
#      MANEJO DE CLIENTES
# ==========================================

def handle_client(client_socket, client_address):
    try:
        message = client_socket.recv(1024).decode('utf-8')
        if message:
            comando = json.loads(message)
            
            # Manejar solicitudes de bloqueo
            if comando.get('accion') == 'SOLICITAR_BLOQUEO':
                recurso_tipo = comando['recurso_tipo']
                recurso_id = comando['recurso_id']
                
                # Verificar si el recurso está disponible localmente
                if verificar_recurso_local(recurso_tipo, recurso_id):
                    # Bloquear temporalmente
                    with lock_bloqueos:
                        clave = f"{recurso_tipo}_{recurso_id}"
                        bloqueos_locales[clave] = datetime.now()
                    client_socket.send("BLOQUEO_OK".encode('utf-8'))
                    print(f"📥 Bloqueo aprobado para {recurso_tipo} {recurso_id} desde {client_address}")
                else:
                    client_socket.send("BLOQUEO_RECHAZADO".encode('utf-8'))
                    print(f"❌ Bloqueo rechazado para {recurso_tipo} {recurso_id} desde {client_address}")
                    
            elif comando.get('accion') == 'LIBERAR_BLOQUEO':
                recurso_tipo = comando['recurso_tipo']
                recurso_id = comando['recurso_id']
                # Liberar bloqueo local
                with lock_bloqueos:
                    clave = f"{recurso_tipo}_{recurso_id}"
                    if clave in bloqueos_locales:
                        del bloqueos_locales[clave]
                client_socket.send("BLOQUEO_LIBERADO".encode('utf-8'))
                
            # Transacciones normales
            elif comando.get('accion') in ['INSERTAR_PACIENTE', 'ASIGNAR_RECURSOS', 'CERRAR_VISITA', 'INCREMENTAR_CONSECUTIVO']:
                # Ejecutar localmente como parte del consenso
                resultado = ejecutar_transaccion_local(comando)
                if resultado:
                    client_socket.send("CONSENSO_OK".encode('utf-8'))
                    print(f"📥 Transacción aceptada de {client_address}: {comando['accion']}")
                else:
                    client_socket.send("CONSENSO_RECHAZADO".encode('utf-8'))
                    
    except Exception as e:
        print(f"Error en handle_client: {e}")
        client_socket.send("ERROR".encode('utf-8'))
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
            client_socket, addr = server_socket.accept()
            t = threading.Thread(target=handle_client, args=(client_socket, addr))
            t.daemon = True
            t.start()
        except socket.timeout:
            continue
        except Exception:
            pass
    server_socket.close()

# ==========================================
#      FUNCIONES DEL SISTEMA
# ==========================================

def ver_pacientes_locales():
    print("\n--- 🤕 PACIENTES ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, edad FROM PACIENTES")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print("   (Sin registros)")
    for r in rows:
        print(f"   ID: {r[0]} | {r[1]} ({r[2]}a)")

def ver_doctores_locales():
    print("\n--- 👨‍⚕️ DOCTORES ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, disponible FROM DOCTORES")
    rows = cursor.fetchall()
    conn.close()
    for r in rows:
        estado = "🟢 Disp" if r[2] == 1 else "🔴 Ocup"
        print(f"   ID: {r[0]} | {r[1]} [{estado}]")

def ver_camas_locales():
    print("\n--- 🛏️ CAMAS ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, numero, ocupada FROM CAMAS_ATENCION")
    rows = cursor.fetchall()
    conn.close()
    for r in rows:
        estado = "🔴 Ocupada" if r[2] == 1 else "🟢 Libre"
        print(f"   ID: {r[0]} | Cama {r[1]} - {estado}")

def ver_visitas_activas():
    """Muestra solo visitas activas"""
    print("\n--- 🚨 VISITAS ACTIVAS ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT folio, paciente_id, doctor_id, cama_id, estado 
        FROM VISITAS_EMERGENCIA 
        WHERE estado != 'Cerrada'
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("   (No hay visitas activas)")
        return []
    
    for r in rows:
        print(f"   📄 {r[0]} | Paciente: {r[1]} | Doctor: {r[2]} | Cama: {r[3]} | Estado: {r[4]}")
    
    return [r[0] for r in rows]  # Retornar folios para selección

def registrar_nuevo_paciente():
    print("\n[Nuevo Paciente]")
    try:
        nombre = input("Nombre: ")
        edad = int(input("Edad: "))
        contacto = input("Contacto: ")
        
        comando = {
            "accion": "INSERTAR_PACIENTE",
            "datos": {
                "nombre": nombre, 
                "edad": edad, 
                "contacto": contacto
            }
        }
        
        # Usar consenso para insertar
        paciente_id = ejecutar_transaccion_local(comando)
        if paciente_id:
            print(f"✅ Paciente registrado con ID: {paciente_id}")
            
            # Ofrecer distribución automática
            distribuir = input("¿Distribuir automáticamente? (s/n): ").lower()
            if distribuir == 's':
                folio = distribuir_visita_automaticamente(paciente_id)
                if folio:
                    print(f"✅ Distribución automática exitosa. Folio: {folio}")
                else:
                    print("❌ No se pudo distribuir automáticamente")
            else:
                print("⚠️  Puede asignar recursos manualmente después")
                
            return paciente_id
        else:
            print("❌ No se pudo registrar paciente.")
            return None
            
    except ValueError:
        print("Error: Datos inválidos.")
        return None

def asignar_doctor_y_cama():
    """ASIGNACIÓN CON EXCLUSIÓN MUTUA"""
    print("\n--- ASIGNACIÓN MANUAL CON EXCLUSIÓN MUTUA ---")
    try:
        ver_pacientes_locales()
        pid = input("\nID Paciente: ")
        if not pid: return

        ver_doctores_locales()
        did = input("ID Doctor: ")
        if not did: return

        ver_camas_locales()
        cid = input("ID Cama: ")
        if not cid: return

        # 1. SOLICITAR BLOQUEOS con EXCLUSIÓN MUTUA
        print("\n🔒 ACTIVANDO EXCLUSIÓN MUTUA...")
        
        if not solicitar_bloqueo_distribuido("DOCTOR", did):
            print("❌ No se pudo bloquear el doctor. Puede estar en uso.")
            return
            
        if not solicitar_bloqueo_distribuido("CAMA", cid):
            print("❌ No se pudo bloquear la cama. Puede estar ocupada.")
            liberar_bloqueo_distribuido("DOCTOR", did)
            return

        # 2. VERIFICAR disponibilidad real (doble verificación)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("SELECT disponible, nombre FROM DOCTORES WHERE id=?", (did,))
        doc = cur.fetchone()
        if not doc or doc[0] == 0:
            print(f"❌ Doctor {did} no disponible")
            liberar_bloqueo_distribuido("DOCTOR", did)
            liberar_bloqueo_distribuido("CAMA", cid)
            conn.close()
            return
            
        cur.execute("SELECT ocupada, numero FROM CAMAS_ATENCION WHERE id=?", (cid,))
        cama = cur.fetchone()
        if not cama or cama[0] == 1:
            print(f"❌ Cama {cid} ya ocupada")
            liberar_bloqueo_distribuido("DOCTOR", did)
            liberar_bloqueo_distribuido("CAMA", cid)
            conn.close()
            return

        conn.close()

        # 3. EJECUTAR ASIGNACIÓN con CONSENSO
        folio = generar_folio_exacto(pid, did, SERVER_PORT)
        comando = {
            "accion": "ASIGNAR_RECURSOS",
            "datos": {
                "folio": folio,
                "paciente_id": pid,
                "doctor_id": did,
                "cama_id": cid
            }
        }
        
        if propagar_transaccion_con_consenso(comando):
            print(f"✅ ASIGNACIÓN MANUAL EXITOSA - Folio: {folio}")
            print(f"   👨‍⚕️ Doctor {doc[1]} asignado")
            print(f"   🛏️ Cama {cama[1]} asignada")
        else:
            print("❌ Error en la asignación")

        # 4. LIBERAR BLOQUEOS
        liberar_bloqueo_distribuido("DOCTOR", did)
        liberar_bloqueo_distribuido("CAMA", cid)

    except Exception as e:
        print(f"Error: {e}")
        # Asegurar liberación de bloqueos en caso de error
        try:
            liberar_bloqueo_distribuido("DOCTOR", did)
            liberar_bloqueo_distribuido("CAMA", cid)
        except:
            pass

def cerrar_visita():
    """Cierra una visita y libera los recursos"""
    print("\n--- CERRAR VISITA ---")
    
    # Mostrar visitas activas
    folios = ver_visitas_activas()
    if not folios:
        return
    
    try:
        folio = input("\nFolio de la visita a cerrar: ")
        if not folio:
            return
        
        # Verificar que el folio existe y está activo
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT estado FROM VISITAS_EMERGENCIA WHERE folio = ?", (folio,))
        visita = cursor.fetchone()
        conn.close()
        
        if not visita:
            print("❌ Folio no encontrado")
            return
            
        if visita[0] == 'Cerrada':
            print("❌ Esta visita ya está cerrada")
            return
        
        # Ejecutar cierre con consenso
        comando = {
            "accion": "CERRAR_VISITA",
            "datos": {
                "folio": folio
            }
        }
        
        if propagar_transaccion_con_consenso(comando):
            print("✅ Visita cerrada exitosamente")
            print("🔓 Doctor y cama liberados para nuevas asignaciones")
        else:
            print("❌ Error al cerrar la visita")
            
    except Exception as e:
        print(f"Error: {e}")

# ==========================================
#      SISTEMA DE LOGIN Y MENÚS ACTUALIZADOS
# ==========================================

def login():
    print("\n🔐 INICIO DE SESIÓN")
    print("-----------------------------")

    intentos = 0
    while intentos < 3:
        user = input("Usuario: ")
        pwd = getpass.getpass("Contraseña: ")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT rol, id_personal FROM USUARIOS_SISTEMA WHERE username=? AND password=?", (user, pwd))
        resultado = cursor.fetchone()
        conn.close()

        if resultado:
            rol_encontrado = resultado[0]
            print(f"\n✅ Bienvenido. Accediendo como: {rol_encontrado}")
            return True, rol_encontrado, user
        else:
            print("❌ Credenciales incorrectas. Intente de nuevo.")
            intentos += 1

    print("⛔ Demasiados intentos fallidos. Cerrando sistema.")
    return False, None, None

def menu_trabajador_social(usuario):
    while True:
        print("\n" + "=" * 50)
        print(f"   PANEL TRABAJADOR SOCIAL ({usuario})")
        print("=" * 50)
        print("1. ➕ Registrar Nuevo Paciente")
        print("2. 🤕 Ver Pacientes")
        print("3. 👨‍⚕️ Ver Doctores")
        print("4. 🛏️ Ver Camas")
        print("5. 🚨 Ver Visitas Activas")
        print("6. 🩺 Asignar Manual (EXCLUSIÓN MUTUA)")
        print("7. 🤖 Distribuir Automáticamente")
        print("9. 🚪 Cerrar Sesión")
        print("-" * 50)

        op = input("Opción > ")

        if op == '1': 
            registrar_nuevo_paciente()
        elif op == '2': 
            ver_pacientes_locales()
        elif op == '3': 
            ver_doctores_locales()
        elif op == '4': 
            ver_camas_locales()
        elif op == '5': 
            ver_visitas_activas()
        elif op == '6': 
            asignar_doctor_y_cama()
        elif op == '7':  # NUEVA OPCIÓN
            ver_pacientes_locales()
            pid = input("ID Paciente a distribuir automáticamente: ")
            if pid:
                folio = distribuir_visita_automaticamente(int(pid))
                if folio:
                    print(f"✅ Distribución automática exitosa. Folio: {folio}")
        elif op == '9': 
            print("Cerrando sesión...")
            shutdown_event.set()
            break
        else: print("Opción no válida.")

def menu_doctor(usuario):
    while True:
        print("\n" + "=" * 50)
        print(f"   PANEL MÉDICO ({usuario})")
        print("=" * 50)
        print("1. 🚨 Ver Visitas Asignadas")
        print("2. ✅ Cerrar Visita")
        print("3. 🚪 Cerrar Sesión")
        print("-" * 50)

        op = input("Opción > ")

        if op == '1': 
            ver_visitas_activas()
        elif op == '2': 
            cerrar_visita()
        elif op == '9':
            print("Cerrando sesión...")
            shutdown_event.set()
            break
        else: print("Opción no válida.")

def main():
    init_db()
    
    # Iniciar servidor en segundo plano
    t = threading.Thread(target=server, args=(SERVER_PORT,))
    t.daemon = True
    t.start()
    
    print(f"\n🖥️  SISTEMA DISTRIBUIDO HOSPITALARIO")
    print(f"📡 Nodo activo en puerto {SERVER_PORT}")
    print(f"🔗 Nodos conocidos: {len(NODOS_REMOTOS)}")
    
    autenticado, rol, usuario = login()
    
    if autenticado:
        try:
            if rol == 'SOCIAL':
                menu_trabajador_social(usuario)
            elif rol == 'DOCTOR':
                menu_doctor(usuario)
        except KeyboardInterrupt:
            shutdown_event.set()
    else:
        shutdown_event.set()

    print("Esperando cierre de hilos...")
    try:
        dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dummy.connect(('127.0.0.1', SERVER_PORT))
        dummy.close()
    except: pass

    threading.Event().wait(1)
    print("Sistema apagado.")

if __name__ == "__main__":
    main()
