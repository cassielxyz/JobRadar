import os, smtplib
from email.message import EmailMessage

def send(subject, text):
    host=os.getenv('SMTP_HOST','smtp.gmail.com'); port=int(os.getenv('SMTP_PORT','587'))
    user=os.getenv('SMTP_USERNAME'); password=os.getenv('SMTP_PASSWORD'); to=os.getenv('ALERT_EMAIL_TO')
    if not user or not password or not to: return False
    msg=EmailMessage(); msg['Subject']=subject; msg['From']=os.getenv('ALERT_EMAIL_FROM',user); msg['To']=to
    msg.set_content(text)
    try:
        with smtplib.SMTP(host,port,timeout=20) as s:
            s.starttls(); s.login(user,password); s.send_message(msg)
        return True
    except Exception:
        return False
