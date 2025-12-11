// Основные функции для работы с UI

document.addEventListener('DOMContentLoaded', function () {
    // Инициализация всех компонентов
    initTabs();
    initPopups();
    initForms();
});

// Работа с табами
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function () {
            const tabGroup = this.closest('.tabs');
            const allTabs = tabGroup.querySelectorAll('.tab');
            allTabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

// Работа с попапами
function initPopups() {
    const popupTriggers = document.querySelectorAll('[data-popup]');
    const popupCloses = document.querySelectorAll('.popup-close');

    popupTriggers.forEach(trigger => {
        trigger.addEventListener('click', function () {
            const popupId = this.getAttribute('data-popup');
            const popup = document.getElementById(popupId);
            if (popup) {
                popup.classList.add('active');
            }
        });
    });

    popupCloses.forEach(close => {
        close.addEventListener('click', function () {
            const popup = this.closest('.popup');
            if (popup) {
                popup.classList.remove('active');
            }
        });
    });

    // Закрытие по клику вне попапа
    document.querySelectorAll('.popup').forEach(popup => {
        popup.addEventListener('click', function (e) {
            if (e.target === this) {
                this.classList.remove('active');
            }
        });
    });
}

// Работа с формами
function initForms() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        if (form.hasAttribute('data-custom-submit')) return;

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            handleFormSubmit(this);
        });
    });
}

// Обработка отправки формы
async function handleFormSubmit(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    const action = form.getAttribute('action') || form.getAttribute('data-action');
    const method = form.getAttribute('data-method') || form.getAttribute('method') || 'POST';

    if (!action) {
        console.error('No action specified for form');
        return;
    }

    try {
        // Используем api.request для включения JWT токена
        const result = await api.request(action, {
            method: method,
            body: JSON.stringify(data)
        });

        if (result.success) {
            showNotification('Успешно сохранено', 'success');
            if (form.dataset.redirect) {
                setTimeout(() => {
                    window.location.href = form.dataset.redirect;
                }, 1000);
            }
        } else {
            showNotification(result.message || 'Ошибка при сохранении', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Ошибка соединения с сервером', 'error');
    }
}

// Показ уведомлений с красивой анимацией
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    const colors = {
        success: '#10b981',
        error: '#ef4444',
        info: '#2563eb'
    };

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${colors[type] || colors.info};
        color: white;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        font-weight: 500;
        font-size: 14px;
        max-width: 400px;
        word-wrap: break-word;
        animation: slideInNotification 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        transform-origin: top right;
        backdrop-filter: blur(10px);
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOutNotification 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        setTimeout(() => {
            if (notification.parentNode) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Функция применения темы (глобальная)
function applyTheme(theme) {
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(`theme-${theme}`);
    localStorage.setItem('theme', theme);
}

// API функции с поддержкой JWT токенов
const api = {
    // Получение токена из localStorage
    getToken() {
        return localStorage.getItem('auth_token');
    },

    // Сохранение токена в localStorage
    setToken(token) {
        localStorage.setItem('auth_token', token);
    },

    // Удаление токена из localStorage
    clearToken() {
        localStorage.removeItem('auth_token');
    },

    // Базовый метод для всех запросов
    async request(url, options = {}) {
        const token = this.getToken();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Добавляем токен если есть
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, { ...options, headers });

            // Авто-редирект на логин при 401
            if (response.status === 401) {
                this.clearToken();
                // Не редиректим если уже на странице логина или регистрации
                if (!window.location.pathname.includes('/login') &&
                    !window.location.pathname.includes('/registration')) {
                    window.location.href = '/login';
                }
                return { success: false, message: 'Требуется авторизация' };
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            return { success: false, message: 'Ошибка соединения с сервером' };
        }
    },

    async get(url) {
        return this.request(url, { method: 'GET' });
    },

    async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async put(url, data) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
};

// Добавление анимаций для уведомлений
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInNotification {
        from {
            transform: translateX(120%) scale(0.8);
            opacity: 0;
        }
        to {
            transform: translateX(0) scale(1);
            opacity: 1;
        }
    }
    
    @keyframes slideOutNotification {
        from {
            transform: translateX(0) scale(1);
            opacity: 1;
        }
        to {
            transform: translateX(120%) scale(0.8);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

