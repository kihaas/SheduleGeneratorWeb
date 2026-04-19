/**
 * login.js — логика формы входа
 */

document.addEventListener('DOMContentLoaded', () => {

    // ===== ГЛАЗИК — вешаем на каждую кнопку .toggle-password =====
    document.querySelectorAll('.toggle-password').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var targetId = btn.getAttribute('data-target');
            var input = document.getElementById(targetId);
            var icon = btn.querySelector('i');
            if (!input || !icon) return;

            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fas fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fas fa-eye';
            }
        });
    });

    // ===== ФОРМА =====
    var form       = document.getElementById('login-form');
    var submitBtn  = document.getElementById('submit-btn');
    var errorAlert = document.getElementById('error-alert');
    var errorText  = document.getElementById('error-text');

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
        submitBtn.classList.toggle('loading', loading);
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        hideError();

        var username = document.getElementById('username').value.trim();
        var password = document.getElementById('password').value;

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

        // OAuth2PasswordRequestForm требует x-www-form-urlencoded
        var formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        setLoading(true);

        try {
            var res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
                credentials: 'include'
            });

            var data = {};
            try { data = await res.json(); } catch(e) {}

            if (res.ok) {
                // Cookie установлена сервером — идём на главную
                window.location.href = data.redirect || '/';
            } else {
                showError(data.detail || 'Неверный логин или пароль');
                setLoading(false);
            }
        } catch(err) {
            showError('Ошибка соединения с сервером. Попробуйте ещё раз.');
            setLoading(false);
        }
    });

    // Сбрасываем ошибку при вводе
    ['username', 'password'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('input', hideError);
    });
});