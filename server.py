import asyncio
import websockets
import json
import uuid
import pymysql
from datetime import datetime

# Имя бота — должно совпадать с BOT_NAME из JS
BOT_NAME = "Магический Бот"

# Подключение к БД
def get_db():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='1234',
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
    db.close()
    return message_id

# Получение истории сообщений
def get_history(room):
    db = get_db()
    with db.cursor() as cursor:
        sql = "SELECT * FROM messages WHERE room = %s ORDER BY time ASC"
        cursor.execute(sql, (room,))
        result = cursor.fetchall()
    db.close()
    return result

# Редактирование сообщения
def edit_message(message_id, new_text):
    db = get_db()
    with db.cursor() as cursor:
        sql = "UPDATE messages SET text = %s, edited = %s WHERE id = %s"
        cursor.execute(sql, (new_text, True, message_id))
        db.commit()
    db.close()

# Удаление сообщения по ID
def delete_message(message_id):
    db = get_db()
    with db.cursor() as cursor:
        sql = "DELETE FROM messages WHERE id = %s"
        cursor.execute(sql, (message_id,))
        db.commit()
    db.close()

# Храним соединения по комнатам
clients = {}

async def handle_client(websocket, path):
    print("Клиент подключился.")
    username = "Гость"
    room = "default"

    async def safe_send(ws, msg):
        try:
            if ws.state == websockets.protocol.State.OPEN:
                await ws.send(msg)
        except Exception as e:
            print(f"[ERROR] Ошибка отправки: {e}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                print(f"Получено: {data}")

                if data.get("type") == "init":
                    username = data.get("username", "Гость")
                    room = data.get("room", "default")

                    if room not in clients:
                        clients[room] = set()
                    clients[room].add(websocket)

                    history = get_history(room)
                    await safe_send(websocket, json.dumps({
                        "type": "history",
                        "messages": history
                    }))

                elif data.get("type") == "new_message":
                    msg_text = data.get("text", "").strip()
                    target_room = data.get("room", room)
                    sender = data.get("sender", username)

                    # ❌ Запрет на имя бота от клиента
                    if sender == BOT_NAME:
                        await safe_send(websocket, json.dumps({
                            "type": "error",
                            "message": f"Нельзя отправлять сообщения от имени '{BOT_NAME}'"
                        }))
                        continue

                    if not msg_text or target_room not in clients:
                        continue

                    message_id = save_message(target_room, sender, msg_text)
                    now = datetime.now().strftime("%H:%M:%S")

                    response = {
                        "type": "new_message",
                        "message": {
                            "id": message_id,
                            "room": target_room,
                            "sender": sender,
                            "text": msg_text,
                            "time": now,
                            "edited": False
                        }
                    }

                    tasks = [safe_send(ws, json.dumps(response)) for ws in clients[target_room]]
                    await asyncio.gather(*tasks)

                elif data.get("type") == "edit_message":
                    message_id = data.get("message_id")
                    new_text = data.get("new_text", "").strip()
                    target_room = data.get("room", room)

                    if not new_text or not message_id or target_room not in clients:
                        continue

                    edit_message(message_id, new_text)

                    response = {
                        "type": "message_edited",
                        "message_id": message_id,
                        "new_text": new_text,
                        "room": target_room
                    }

                    tasks = [safe_send(ws, json.dumps(response)) for ws in clients[target_room]]
                    await asyncio.gather(*tasks)

                elif data.get("type") == "delete_message":
                    message_id = data.get("message_id")
                    target_room = data.get("room", room)

                    if not message_id or target_room not in clients:
                        continue

                    delete_message(message_id)

                    response = {
                        "type": "message_deleted",
                        "message_id": message_id,
                        "room": target_room
                    }

                    tasks = [safe_send(ws, json.dumps(response)) for ws in clients[target_room]]
                    await asyncio.gather(*tasks)

            except json.JSONDecodeError:
                await safe_send(websocket, json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                print(f"Ошибка обработки сообщения: {e}")
                await safe_send(websocket, json.dumps({
                    "type": "error",
                    "message": str(e)
                }))

    except websockets.exceptions.ConnectionClosed:
        print("Клиент закрыл соединение.")
    except Exception as e:
        print(f"Ошибка соединения: {e}")
    finally:
        # Удаляем соединение из всех комнат
        for room_name in list(clients.keys()):
            if websocket in clients[room_name]:
                clients[room_name].discard(websocket)
                if not clients[room_name]:  # Очистка пустых комнат
                    del clients[room_name]
        print(f"Клиент отключился: {username}")


async def main():
    # Проверка подключения к БД
    try:
        db = get_db()
        db.close()
        print("✔ Успешное подключение к БД")
    except Exception as e:
        print(f"✖ Ошибка подключения к БД: {e}")
        return

    start_server = await websockets.serve(
        handle_client,
        "localhost",
        8765,
        ping_interval=20,
        ping_timeout=30
    )

    print(f"Сервер запущен на ws://localhost:8765")
    await start_server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Сервер остановлен")
    except Exception as e:
        print(f"Критическая ошибка: {e}")