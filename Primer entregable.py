import socket
import threading
from datetime import datetime
import sqlite3  # <-- Asegúrate que esté
import json     # <-- Lo necesitarás pronto
import os       # <-- Asegúrate que esté


# --- Configuración de Rutas ---

# 1. Esto encuentra la ruta de la carpeta donde está tu script
#    En tu caso: /opt/emergencias/SistemaDistribuido/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Ruta a tus "planos" (el archivo .sql)
#    Usa os.path.join para unir la base con la subcarpeta
SQL_SCHEMA_PATH = os.path.join(BASE_DIR,'schema2.sql')

# 3. Ruta a tu "edificio" (la base de datos real .db)
#    Vamos a crearla dentro de tu carpeta 'data'
DB_PATH = os.path.join(BASE_DIR,'emergencias.db') # <--- ¡Crearemos este!

def init_db():
    """
    Usa los 'planos' (schema2.sql) para construir
    el 'edificio' (emergencias.db).
    """
    print(f"Inicializando la base de datos en: {DB_PATH}")
    conn = None
    try:
        # 1. Conecta (y crea) el archivo .db (el edificio)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Habilitar claves foráneas
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 2. Abre y lee el archivo .sql (los planos)
        print(f"Leyendo 'planos' desde: {SQL_SCHEMA_PATH}")
        with open(SQL_SCHEMA_PATH, 'r') as f:
            sql_script = f.read()  # Lee todo el contenido del archivo

        # 3. Ejecuta los "planos" en el "edificio"
        #    Usamos 'executescript' porque tu archivo .sql
        #    probablemente tiene múltiples comandos.
        cursor.executescript(sql_script)
        conn.commit()
        print(f"¡Éxito! Base de datos y tablas creadas en {DB_PATH}")

    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo de schema en: {SQL_SCHEMA_PATH}")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
    finally:
        if conn:
            conn.close()

# Flag para controlar el cierre del programa
shutdown_event = threading.Event()

# Función para manejar la recepción de mensajes
def handle_client(client_socket, client_address, messages):
    try:
        while not shutdown_event.is_set():
            # Configurar timeout para poder verificar el shutdown_event
            client_socket.settimeout(1.0)
            try:
                message = client_socket.recv(1024).decode('utf-8')
                if not message:
                    break
                print(f"\nMensaje recibido de {client_address}: {message}")
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_with_timestamp = f"De {client_address}: {message} - Recibido a {timestamp}"
                messages.append(message_with_timestamp)
                
                save_message_to_file(message_with_timestamp)
                
                response = f"Mensaje recibido a las {timestamp}"
                client_socket.send(response.encode('utf-8'))
                print("Escribe el mensaje que deseas enviar (o '/salir' para cerrar): ", end='', flush=True)
            except socket.timeout:
                continue
            except Exception as e:
                if not shutdown_event.is_set():
                    print(f"Error en recepción: {e}")
                break
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print(f"Conexión cerrada con {client_address}")
        client_socket.close()

# Función para guardar los mensajes en un archivo
def save_message_to_file(message, filename="messages.txt"):
    with open(filename, 'a') as file:
        file.write(message + "\n")

# Función para enviar un mensaje a otro nodo
def send_message(message, server_ip, server_port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.settimeout(5.0)  # Timeout de 5 segundos
        client_socket.connect((server_ip, server_port))
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_message = f"{timestamp}: {message}"
        
        client_socket.send(full_message.encode('utf-8'))
        
        sent_message = f"Enviado a {server_ip}: {full_message}"
        save_message_to_file(sent_message)
        
        response = client_socket.recv(1024).decode('utf-8')
        print(f"Respuesta del servidor: {response}")
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")
    finally:
        client_socket.close()

# Función para configurar y ejecutar el servidor
def server(server_port, messages):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', server_port))
    server_socket.listen(5)
    server_socket.settimeout(1.0)  # Timeout para poder verificar el shutdown_event
    print(f"Servidor esperando conexiones en el puerto {server_port}...")
    
    while not shutdown_event.is_set():
        try:
            client_socket, client_address = server_socket.accept()
            print(f"\nConexión establecida con {client_address}")
            
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address, messages))
            thread.daemon = True  # Thread daemon se cierra automáticamente
            thread.start()
            print("Escribe el mensaje que deseas enviar (o 'salir' para cerrar): ", end='', flush=True)
        except socket.timeout:
            continue
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"Error en servidor: {e}")
    
    server_socket.close()
    print("Servidor cerrado correctamente")

# Función principal que maneja tanto cliente como servidor
def main():

    server_port = 5555
    messages = []
    init_db = []
    
    # Ejecutar el servidor en un hilo daemon
    server_thread = threading.Thread(target=server, args=(server_port, messages))
    server_thread.daemon = True
    server_thread.start()
    
    print("\n" + "="*50)
    print("Sistema de mensajería P2P iniciado")
    print("Escribe '/salir' para cerrar el programa")
    print("="*50 + "\n")
    
    try:
        while True:
            message = input("Escribe el mensaje que deseas enviar (o '/salir' para cerrar): ")

            # Verificar si el usuario quiere salir (solo con /)
            if message.strip() in ['/salir', '/exit', '/quit', '/q']:
                print("\nCerrando el programa...")
                shutdown_event.set()
                break
            
            if message.strip():  # Solo enviar si hay contenido
                server_ip = input("Introduce la IP del servidor (o presiona Enter para cancelar): ")
                
                if server_ip.strip():
                    send_message(message, server_ip, server_port)
                else:
                    print("Envío cancelado")
    except KeyboardInterrupt:
        print("\n\nCerrando el programa con Ctrl+C...")
        shutdown_event.set()
    
    # Esperar un momento para que los threads terminen
    print("Esperando a que los threads terminen...")
    threading.Event().wait(2)
    print("Programa cerrado correctamente. ¡Hasta luego!")

if __name__ == "__main__":
    main()