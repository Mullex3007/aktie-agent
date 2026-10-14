import yagmail
import os
from dotenv import load_dotenv

load_dotenv()

def send_email(emne, besked):
    try:
        yag = yagmail.SMTP(
            user=os.getenv("YAHOO_EMAIL"),
            password=os.getenv("YAHOO_APP_PASSWORD"),
            host='smtp.mail.yahoo.com',
            port=465,
            smtp_ssl=True
        )
        yag.send(
            to=os.getenv("YAHOO_EMAIL"),
            subject=emne,
            contents=besked
        )
        print(f"📧 Email sendt: {emne}")
    except Exception as e:
        print(f"❌ Email fejl: {e}")
