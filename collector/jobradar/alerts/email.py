import os
import smtplib
from email.message import EmailMessage


def send_result(subject, text):
    host=os.getenv('SMTP_HOST','smtp.gmail.com');port=int(os.getenv('SMTP_PORT','587'));user=os.getenv('SMTP_USERNAME');password=os.getenv('SMTP_PASSWORD');to=os.getenv('ALERT_EMAIL_TO')
    if not user or not password or not to:return {'channel':'email','configured':False,'ok':False,'error':'not configured'}
    msg=EmailMessage();msg['Subject']=subject;msg['From']=os.getenv('ALERT_EMAIL_FROM',user);msg['To']=to;msg.set_content(text)
    try:
        with smtplib.SMTP(host,port,timeout=20) as s:s.starttls();s.login(user,password);s.send_message(msg)
        return {'channel':'email','configured':True,'ok':True}
    except Exception as e:return {'channel':'email','configured':True,'ok':False,'error':str(e)[:180]}

def send(subject,text):return bool(send_result(subject,text).get('ok'))
