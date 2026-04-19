/**
 * login.js — логика формы входа
 */

document.addEventListener('DOMContentLoaded', () => {
    // ===== Глазик =====
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
    const form       = document.getElementById('login-form');
    const submitBtn  = document.getElementById('submit-btn');
    const errorAlert = document.getElementById('error-alert');
    const errorText  = document.getElementById('error-text');

    if (!form) return;

    function showError(msg) {
        errorText.textContent = msg;
        errorAlert.classList.remove('hidden');
    }

    function hideError() {
        errorAlert.classList.add('hidden');
    }

    function setLoading(loading) {
        submitBtn.disabled = loading;
        if (loading) {
            submitBtn.classList.add('loading');
        } else {
            submitBtn.classList.remove('loading');
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        // Клиентская валидация
        if (!username) {
            showError('Введите логин');
            document.getElementById('username').focus();
            return;
        }
        if (!password) {
            showError('Введите пароль');
            document.getElementById('password').focus();
            return;
        }

        // OAuth2PasswordRequestForm ожидает application/x-www-form-urlencoded
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        setLoading(true);

        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
                credentials: 'include'   // ← важно: cookie должна сохраниться
            });

            const data = await res.json().catch(() => ({}));

            if (res.ok) {
                // Cookie уже установлена сервером — переходим на главную
                window.location.href = data.redirect || '/';
            } else {
                showError(data.detail || 'Неверный логин или пароль');
                setLoading(false);
            }
        } catch {
            showError('Ошибка соединения с сервером. Попробуйте ещё раз.');
            setLoading(false);
        }
    });

    // Скрываем ошибку при вводе
    ['username', 'password'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', hideError);
    });
});