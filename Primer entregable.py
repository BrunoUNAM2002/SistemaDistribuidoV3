import socket
import threading
from datetime import datetime

# Función para manejar la recepción de mensajes
def handle_client(client_socket, client_address, messages):
    try:
        while True:
            # Recibir mensaje del cliente
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break  # Si no hay mensaje, cerrar la conexión

            print(f"Mensaje recibido de {client_address}: {message}")

            # Añadir el mensaje recibido a la lista de mensajes
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            message_with_timestamp = f"De {client_address}: {message} - Recibido a {timestamp}"
            messages.append(message_with_timestamp)
            
            # Almacenar el mensaje en un archivo
            save_message_to_file(message_with_timestamp)

            # Enviar una respuesta con el timestamp de recepción
            response = f"Mensaje recibido a las {timestamp}"
            client_socket.send(response.encode('utf-8'))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cerrar la conexión con el cliente
        print(f"Conexión cerrada con {client_address}")
        client_socket.close()

# Función para guardar los mensajes en un archivo
def save_message_to_file(message, filename="messages.txt"):
    with open(filename, 'a') as file:
        file.write(message + "\n")

# Función para enviar un mensaje a otro nodo
def send_message(message, server_ip, server_port):
    # Crear un socket para el cliente
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((server_ip, server_port))  # Conectar al servidor

        # Agregar el timestamp al mensaje
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_message = f"{timestamp}: {message}"

        # Enviar el mensaje al servidor
        client_socket.send(full_message.encode('utf-8'))

        # Guardar el mensaje enviado en el nodo emisor
        sent_message = f"Enviado a {server_ip}: {full_message}"
        save_message_to_file(sent_message)

        # Esperar la respuesta del servidor
        response = client_socket.recv(1024).decode('utf-8')
        print(f"Respuesta del servidor: {response}")

    except Exception as e:
        print(f"Error al enviar mensaje: {e}")
    finally:
        client_socket.close()  # Cerrar la conexión

# Función para configurar y ejecutar el servidor
def server(server_port, messages):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', server_port))  # Escuchar en el puerto
    server_socket.listen(5)
    print(f"Servidor esperando conexiones en el puerto {server_port}...")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Conexión establecida con {client_address}")

        # Crear un hilo para manejar cada cliente
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address, messages))
        thread.start()

# Función principal que maneja tanto cliente como servidor
def main():
    server_port = 5555  # Puerto en el que el servidor escuchará
    messages = []  # Lista para almacenar los mensajes recibidos

    # Ejecutar el servidor en un hilo
    server_thread = threading.Thread(target=server, args=(server_port, messages))
    server_thread.start()

    while True:
        # Pedir al usuario un mensaje para enviar
        message = input("Escribe el mensaje que deseas enviar: ")

        # Configurar la dirección IP de otro nodo a conectar (esto puede ser dinámico)
        server_ip = input("Introduce la IP del servidor al que deseas conectar (puede ser 'localhost' o IP remota): ")

        # Enviar el mensaje al servidor de otro nodo
        send_message(message, server_ip, server_port)

if __name__ == "__main__":
    main()
