// Основные функции для работы с UI

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всех компонентов
    initTabs();
    initPopups();
    initForms();
});

// Работа с табами
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
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
        trigger.addEventListener('click', function() {
            const popupId = this.getAttribute('data-popup');
            const popup = document.getElementById(popupId);
            if (popup) {
                popup.classList.add('active');
            }
        });
    });
    
    popupCloses.forEach(close => {
        close.addEventListener('click', function() {
            const popup = this.closest('.popup');
            if (popup) {
                popup.classList.remove('active');
            }
        });
    });
    
    // Закрытие по клику вне попапа
    document.querySelectorAll('.popup').forEach(popup => {
        popup.addEventListener('click', function(e) {
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
        form.addEventListener('submit', function(e) {
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
        const response = await fetch(action, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
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

// API функции
const api = {
    async get(url) {
        const response = await fetch(url);
        return await response.json();
    },
    
    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    },
    
    async put(url, data) {
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    },
    
    async delete(url) {
        const response = await fetch(url, {
            method: 'DELETE'
        });
        return await response.json();
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

