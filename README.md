# Sistema de Mensajería Distribuida P2P

Sistema de mensajería peer-to-peer implementado en Python utilizando sockets TCP y programación paralela con threads.

## Características

- **Envío de mensajes** desde cualquier nodo a cualquier otro nodo
- **Respuesta automática** de confirmación cuando se recibe un mensaje
- **Almacenamiento dual**: Los mensajes se guardan tanto en el nodo emisor como en el receptor
- **Timestamps**: Cada mensaje incluye la hora del reloj del nodo que lo envía
- **Programación paralela**: Usa threading para manejar múltiples conexiones simultáneas

## Requisitos

- Python 3.x

## Ejecución

```bash
python3 "Primer entregable.py"
```

El programa:
1. Inicia un servidor en el puerto 5555
2. Te solicita un mensaje para enviar
3. Te pide la IP del nodo destino

## Prueba con Múltiples Nodos

### Opción 1: Misma máquina (localhost)

**Terminal 1 (Nodo 1):**
```bash
python3 "Primer entregable.py"
```
- Mensaje: "Hola desde Nodo 1"
- IP destino: `localhost` o `127.0.0.1`

**Terminal 2 (Nodo 2):**
```bash
python3 "Primer entregable.py"
```
- Mensaje: "Hola desde Nodo 2"
- IP destino: `localhost` o `127.0.0.1`

### Opción 2: Diferentes máquinas (red local)

**Máquina A:**
```bash
# Primero obtén tu IP local
hostname -I  # Linux/Mac
ipconfig     # Windows

python3 "Primer entregable.py"
```

**Máquina B:**
```bash
python3 "Primer entregable.py"
```
- IP destino: IP de la Máquina A (ejemplo: `192.168.1.10`)

## Arquitectura

### Componentes Principales

1. **Servidor Thread**: Escucha conexiones entrantes en el puerto 5555
2. **Handler Threads**: Un thread por cada cliente conectado para procesar mensajes
3. **Cliente**: Envía mensajes a otros nodos y espera confirmación
4. **Almacenamiento**: Archivo `messages.txt` con todos los mensajes enviados/recibidos

### Flujo de Mensajes

```
Nodo A                                    Nodo B
  |                                         |
  | 1. Usuario escribe mensaje              |
  | 2. Se agrega timestamp                  |
  | 3. Se guarda en messages.txt (ENVÍO)    |
  | 4. Envía mensaje ---------------------->|
  |                                         | 5. Recibe mensaje
  |                                         | 6. Guarda en messages.txt (RECIBIDO)
  | 7. Recibe confirmación <----------------| 6. Envía confirmación
  |                                         |
```

## Formato de Almacenamiento

### En el nodo emisor:
```
Enviado a 127.0.0.1: 2025-10-20 16:30:45: Hola mundo
```

### En el nodo receptor:
```
De ('127.0.0.1', 54321): 2025-10-20 16:30:45: Hola mundo - Recibido a 2025-10-20 16:30:46
```

## Protocolo de Comunicación

- **Puerto**: 5555 (TCP)
- **Encoding**: UTF-8
- **Buffer**: 1024 bytes
- **Formato mensaje**: `YYYY-MM-DD HH:MM:SS: <contenido>`
- **Formato respuesta**: `Mensaje recibido a las YYYY-MM-DD HH:MM:SS`

## Solución de Problemas

### Error: "Address already in use"
```bash
# Matar proceso usando el puerto 5555
lsof -ti:5555 | xargs kill -9
```

### No se puede conectar entre máquinas
- Verifica que ambas máquinas estén en la misma red
- Desactiva firewalls o permite el puerto 5555
- Confirma la IP correcta con `hostname -I` o `ipconfig`
