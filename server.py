import asyncio
import websockets
import json
import uuid
import pymysql
from datetime import datetime

# Подключение к БД
def get_db():
    return pymysql.connect(
        host='localhost',
        user='root',  # заменить на свой логин
        password='1234',  # заменить на свой пароль
        database='chat_db',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# Сохранение нового сообщения
def save_message(room, sender, text):
    db = get_db()
    with db.cursor() as cursor:
        message_id = str(uuid.uuid4())
        now = datetime.now().strftime("%H:%M:%S")
        sql = "INSERT INTO messages (id, room, sender, text, time, edited) VALUES (%s, %s, %s, %s, %s, %s)"
        cursor.execute(sql, (message_id, room, sender, text, now, False))
        db.commit()
    return message_id

# Получение истории сообщений
def get_history(room):
    db = get_db()
    with db.cursor() as cursor:
        sql = "SELECT * FROM messages WHERE room = %s ORDER BY time ASC"
        cursor.execute(sql, (room,))
        return cursor.fetchall()

# Редактирование сообщения и установка edited=True
def edit_message(message_id, new_text):
    db = get_db()
    with db.cursor() as cursor:
        sql = "UPDATE messages SET text = %s, edited = %s WHERE id = %s"
        cursor.execute(sql, (new_text, True, message_id))
        db.commit()

# Удаление сообщения по ID
def delete_message(message_id):
    db = get_db()
    with db.cursor() as cursor:
        sql = "DELETE FROM messages WHERE id = %s"
        cursor.execute(sql, (message_id,))
        db.commit()

# Обработка WebSocket-соединений
async def handle_client(websocket, path):
    print("Клиент подключился.")
    username = "Гость"
    room = None

    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "init":
                username = data.get("username", "Гость")
                room = data.get("room", "default")

                # Добавляем клиента в комнату
                if room not in clients:
                    clients[room] = set()
                clients[room].add(websocket)

                # Отправляем историю
                history = get_history(room)
                await websocket.send(json.dumps({
                    "type": "history",
                    "messages": history
                }))

            elif data.get("type") == "new_message":
                msg_text = data.get("text", "").strip()
                if not msg_text:
                    continue

                message_id = save_message(room, username, msg_text)
                now = datetime.now().strftime("%H:%M:%S")

                response = {
                    "type": "new_message",
                    "message": {
                        "id": message_id,
                        "room": room,
                        "sender": username,
                        "text": msg_text,
                        "time": now,
                        "edited": False
                    }
                }

                # Рассылаем всем в комнате
                if room in clients:
                    for ws in clients[room]:
                        if ws.open:
                            await ws.send(json.dumps(response))

            elif data.get("type") == "edit_message":
                message_id = data.get("message_id")
                new_text = data.get("new_text", "").strip()
                if not new_text:
                    continue

                edit_message(message_id, new_text)
                response = {
                    "type": "message_edited",
                    "message_id": message_id,
                    "new_text": new_text
                }

                if room in clients:
                    for ws in clients[room]:
                        if ws.open:
                            await ws.send(json.dumps(response))

            elif data.get("type") == "delete_message":
                message_id = data.get("message_id")
                delete_message(message_id)

                response = {
                    "type": "message_deleted",
                    "message_id": message_id
                }

                if room in clients:
                    for ws in clients[room]:
                        if ws.open:
                            await ws.send(json.dumps(response))

    except Exception as e:
        print(f"Ошибка: {e}")

    finally:
        print("Клиент отключился.")
        if room and websocket in clients.get(room, set()):
            clients[room].remove(websocket)
            if not clients[room]:  # Очистка пустых комнат
                del clients[room]


# Храним соединения по комнатам
clients = {}

# Запуск сервера
start_server = websockets.serve(
    handle_client,
    "localhost",
    8765
)

print("Сервер запущен на ws://localhost:8765")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()