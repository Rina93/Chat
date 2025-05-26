document.addEventListener("DOMContentLoaded", function () {
    const contacts = document.querySelectorAll(".contact");
    const currentChatTitle = document.getElementById("current-chat");
    const messagesContainer = document.getElementById("messages");
    const messageInput = document.getElementById("message-input");
    const sendButton = document.getElementById("send-button");

    let activeContact = null;
    let ws = null;
    let username = "";

    // Получаем имя пользователя
    function setUsername() {
        const input = prompt("Введите ваше имя:");
        if (input && input.trim()) {
            username = input.trim();
            connectWebSocket();
        } else {
            setUsername(); // Повторяем, если имя не введено
        }
    }

    // Подключение к WebSocket
    function connectWebSocket() {
        ws = new WebSocket("ws://localhost:8765");

        ws.onopen = () => {
            console.log("✅ Подключено к серверу");
            ws.send(JSON.stringify({ username }));
        };

        ws.onmessage = function (event) {
            try {
                const message = JSON.parse(event.data);
                addMessageToChat(message);
            } catch (e) {
                console.error("❌ Ошибка парсинга сообщения:", e);
            }
        };

        ws.onerror = function (error) {
            console.error("❌ WebSocket Error:", error);
        };

        ws.onclose = function (event) {
            console.log("⚠️ Соединение закрыто. Переподключение...");
            setTimeout(connectWebSocket, 3000); // Автоматическое переподключение
        };
    }

    // Добавление сообщения в интерфейс
    function addMessageToChat(message) {
        const isSent = message.sender === username;
        const messageElement = document.createElement("div");
        messageElement.className = `message ${isSent ? "sent" : "received"}`;

        if (isSent) {
            messageElement.innerHTML = `
                <div class="message-content">
                    <div class="message-text">${message.text}</div>
                    <div class="message-time">${message.time}</div>
                </div>
            `;
        } else {
            messageElement.innerHTML = `
                <img src="/static/images/user_icons/${message.sender.toLowerCase()}.png" alt="User">
                <div class="message-content">
                    <div class="message-text">${message.text}</div>
                    <div class="message-time">${message.time}</div>
                </div>
            `;
        }

        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Отправка сообщения
    function sendMessage() {
        const text = messageInput.value.trim();
        if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

        ws.send(JSON.stringify({ text }));
        messageInput.value = "";
    }

    // Обработчики событий
    sendButton.addEventListener("click", sendMessage);
    messageInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") sendMessage();
    });

    // Переключение контактов
    contacts.forEach(contact => {
        contact.addEventListener("click", function () {
            contacts.forEach(c => c.classList.remove("active"));
            this.classList.add("active");
            const contactName = this.querySelector(".name").textContent;
            currentChatTitle.textContent = contactName;
            activeContact = this.dataset.contactId;
        });
    });

    // Запуск
    setUsername();
});