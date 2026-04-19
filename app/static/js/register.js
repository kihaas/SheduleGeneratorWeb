/**
 * register.js — логика формы регистрации
 */

document.addEventListener('DOMContentLoaded', () => {
    // ===== Глазики =====
    document.querySelectorAll('.toggle-password').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const input = document.getElementById(targetId);
            const icon  = btn.querySelector('i');
            if (!input) return;

            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fas fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fas fa-eye';
            }
        });
    });

    // ===== Форма =====
    const form         = document.getElementById('register-form');
    const submitBtn    = document.getElementById('submit-btn');
    const errorAlert   = document.getElementById('error-alert');
    const errorText    = document.getElementById('error-text');
    const successAlert = document.getElementById('success-alert');
    const successText  = document.getElementById('success-text');

    if (!form) return;

    function showError(msg) {
        errorText.textContent = msg;
        errorAlert.classList.remove('hidden');
        successAlert.classList.add('hidden');
    }

    function showSuccess(msg) {
        successText.textContent = msg;
        successAlert.classList.remove('hidden');
        errorAlert.classList.add('hidden');
    }

    function hideAlerts() {
        errorAlert.classList.add('hidden');
        successAlert.classList.add('hidden');
    }

    function setLoading(loading) {
        submitBtn.disabled = loading;
        if (loading) {
            submitBtn.classList.add('loading');
        } else {
            submitBtn.classList.remove('loading');
        }
    }

    function markFieldError(fieldId) {
        const el = document.getElementById(fieldId);
        if (el) el.classList.add('error');
    }

    function clearFieldErrors() {
        document.querySelectorAll('.form-control.error').forEach(el => {
            el.classList.remove('error');
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlerts();
        clearFieldErrors();

        const username  = document.getElementById('username').value.trim();
        const password  = document.getElementById('password').value;
        const password2 = document.getElementById('password2').value;

        // ===== Клиентская валидация =====
        if (!username) {
            showError('Введите логин');
            markFieldError('username');
            document.getElementById('username').focus();
            return;
        }
        if (username.length < 3) {
            showError('Логин должен быть минимум 3 символа');
            markFieldError('username');
            document.getElementById('username').focus();
            return;
        }
        if (!password) {
            showError('Введите пароль');
            markFieldError('password');
            document.getElementById('password').focus();
            return;
        }
        if (password.length < 6) {
            showError('Пароль должен быть минимум 6 символов');
            markFieldError('password');
            document.getElementById('password').focus();
            return;
        }
        if (!password2) {
            showError('Повторите пароль');
            markFieldError('password2');
            document.getElementById('password2').focus();
            return;
        }
        if (password !== password2) {
            showError('Пароли не совпадают');
            markFieldError('password');
            markFieldError('password2');
            document.getElementById('password2').focus();
            return;
        }

        setLoading(true);

        try {
            const res = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            });

            const data = await res.json().catch(() => ({}));

            if (res.ok) {
                showSuccess('Аккаунт создан! Перенаправляем на страницу входа...');
                submitBtn.disabled = true;
                setTimeout(() => {
                    window.location.href = '/login';
                }, 1500);
            } else {
                showError(data.detail || 'Ошибка регистрации');
                setLoading(false);
            }
        } catch {
            showError('Ошибка соединения с сервером. Попробуйте ещё раз.');
            setLoading(false);
        }
    });

    // Сбрасываем ошибки при вводе
    ['username', 'password', 'password2'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                el.classList.remove('error');
                hideAlerts();
            });
        }
    });
});