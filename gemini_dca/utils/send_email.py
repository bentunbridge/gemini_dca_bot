from typing import List, Any
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders


def email_config(config: Any) -> Any:
    return config["email"]


def send_email_gmail(config_file: str,
                     subject: str,
                     message: str,
                     destination: str):
    config = email_config(config_file)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    # This is where you would replace your password with the app password
    server.login(config["SOURCE"], config["PASS"])

    msg = EmailMessage()

    message = f'Message:\n{message}\n'
    msg.set_content(message)
    msg['Subject'] = subject
    msg['From'] = config["SOURCE"]
    msg['To'] = destination
    server.send_message(msg)


def send_email_gmail_with_images(config_file: str,
                                 subject: str,
                                 message: str,
                                 destination: str,
                                 attactments: List[str] = [],
                                 embedded: List[str] = []):
    config = email_config(config_file)
    message_html = message.replace("\n", "<br>")

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    # This is where you would replace your password with the app password
    server.login(config["SOURCE"], config["PASS"])

    # Create the root message and fill in the from, to, and subject headers
    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = subject
    msgRoot['From'] = config["SOURCE"]
    msgRoot['To'] = destination
    msgRoot.preamble = 'Root Example Text.'

    # Encapsulate the plain and HTML versions of the message body in an
    # 'alternative' part, so message agents can decide which they want to display.
    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    msgText = MIMEText(message_html)
    msgAlternative.attach(msgText)

    # We reference the image in the IMG SRC attribute by the ID we give it below
    email_body = f'{message_html}<br>'
    for i in range(len(embedded)):
        email_body = f'{email_body}<br><img src="cid:image{i}"><br>'

    msgText = MIMEText(email_body, 'html')
    msgAlternative.attach(msgText)

    # add embedded plots
    for i, emb in enumerate(embedded):
        fp = open(emb, 'rb')
        msgImage = MIMEImage(fp.read())
        fp.close()

        # Define the image's ID as referenced above
        msgImage.add_header('Content-ID', f'<image{i}>')
        msgRoot.attach(msgImage)

    # Add Attachments
    for att in attactments:
        # open the file to be sent
        attachment = open(att, "rb")
        # instance of MIMEBase and named as p
        p = MIMEBase('application', 'octet-stream')
        # To change the payload into encoded form
        p.set_payload((attachment).read())
        # encode into base64
        encoders.encode_base64(p)
        p.add_header('Content-Disposition', "attachment; filename= %s" % filename)
        # attach the instance 'p' to instance 'msg'
        msgRoot.attach(p)

        # server.send_message(msg)
    server.sendmail(config["SOURCE"], destination, msgRoot.as_string())
    server.quit()
