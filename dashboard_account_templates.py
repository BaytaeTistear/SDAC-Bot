"""Account and admin login templates for the SDAC dashboard."""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Admin Login</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 12px;
            margin: 10vh auto 0;
            max-width: 420px;
            padding: 24px;
        }
        h1 { margin-top: 0; text-align: center; }
        label { display: block; margin-bottom: 8px; }
        input, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 16px;
            padding: 10px 12px;
            width: 100%;
        }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
            margin-top: 14px;
        }
        .error {
            border: 1px solid #e45d68;
            border-radius: 8px;
            margin-bottom: 16px;
            padding: 10px;
            text-align: center;
        }
        .oauth {
            display: block;
            background: #5865f2;
            border-radius: 8px;
            color: white;
            margin: 0 0 18px;
            padding: 11px;
            text-align: center;
            text-decoration: none;
        }
    </style>
</head>
<body>
<main>
    <h1>Admin Login</h1>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    {% if oauth_enabled %}
        <a class="oauth" href="{{ url_for('admin_oauth_start', key=admin_key, next=next_url) }}">Log in with Discord</a>
    {% endif %}
    <form method="post">
        <input type="hidden" name="key" value="{{ admin_key }}">
        <input type="hidden" name="next" value="{{ next_url }}">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <label for="username">Admin username or email</label>
        <input id="username" name="username" value="{{ username }}" placeholder="admin@example.com" autofocus required>
        <label for="password">Admin password</label>
        <input id="password" name="password" type="password" required>
        <button type="submit">Log In</button>
    </form>
    <p class="note">
        Need a normal account?
        <a href="{{ url_for('account_register') }}">Create one here</a>.
        Admin access must be granted by an existing admin or the server CLI.
    </p>
</main>
</body>
</html>
"""


ACCOUNT_REGISTER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Create SDAC Account</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 60px auto; padding: 24px; width: min(100%, 440px); }
        h1 { text-align: center; }
        a { color: #7c9cff; }
        label { display: block; font-weight: bold; margin: 14px 0 6px; }
        input, button { border: 1px solid #30333b; border-radius: 7px; box-sizing: border-box; font-size: 16px; padding: 10px 12px; width: 100%; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; margin-top: 18px; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin-bottom: 16px; padding: 10px; text-align: center; }
        .error { border-color: #e45d68; }
        .muted { color: #a8adb8; }
    </style>
</head>
<body>
<main>
    <h1>Create Account</h1>
    {% if notice %}<div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>{% endif %}
    <form method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" value="{{ email }}" maxlength="254" required>
        <label for="username">Username <span class="muted">(optional)</span></label>
        <input id="username" name="username" value="{{ username }}" maxlength="40" placeholder="Leave blank to derive from email">
        <label for="discord_user_id">Discord User ID <span class="muted">(optional)</span></label>
        <input id="discord_user_id" name="discord_user_id" value="{{ discord_user_id }}" inputmode="numeric" placeholder="Needed for My Submissions">
        <label for="password">Password</label>
        <input id="password" name="password" type="password" minlength="10" required>
        <label for="confirm_password">Confirm Password</label>
        <input id="confirm_password" name="confirm_password" type="password" minlength="10" required>
        <button type="submit">Create Account</button>
    </form>
    <p class="muted">
        New accounts start as regular users. Admins can promote accounts to
        trusted user, moderator, admin, Server Owner, or Bot Owner from the admin Settings page.
    </p>
    <p><a href="{{ url_for('account_login') }}">Already have an account?</a></p>
    <p><a href="{{ url_for('index') }}">Back to submissions</a></p>
</main>
</body>
</html>
"""


ACCOUNT_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Account Login</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 60px auto; padding: 24px; width: min(100%, 440px); }
        h1 { text-align: center; }
        a { color: #7c9cff; }
        label { display: block; font-weight: bold; margin: 14px 0 6px; }
        input, button { border: 1px solid #30333b; border-radius: 7px; box-sizing: border-box; font-size: 16px; padding: 10px 12px; width: 100%; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; margin-top: 18px; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin-bottom: 16px; padding: 10px; text-align: center; }
        .error { border-color: #e45d68; }
        .muted { color: #a8adb8; }
        .oauth { background: #5865f2; border-radius: 8px; color: white; display: block; font-weight: bold; margin-bottom: 16px; padding: 11px; text-align: center; text-decoration: none; }
    </style>
</head>
<body>
<main>
    <h1>Account Login</h1>
    {% if notice %}<div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>{% endif %}
    <a class="oauth" href="{{ url_for('account_oauth_start', next=next_url) }}">Continue with Discord</a>
    <form method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <input type="hidden" name="next" value="{{ next_url }}">
        <label for="identifier">Username or email</label>
        <input id="identifier" name="identifier" value="{{ identifier }}" required>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" required>
        <button type="submit">Log In</button>
    </form>
    <p><a href="{{ url_for('account_register') }}">Create an account</a></p>
    <p><a href="{{ url_for('admin_login', key=admin_key) }}">Admin login</a></p>
</main>
</body>
</html>
"""
