import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from model.badgefile import Badgefile
from util.secrets import secret
from log.logger import log

class Email:
  def __init__(self, template, attendee, extra={}):
    self.template = template
    self.attendee = attendee
    self.extra = extra

  def apply_template(self):
    info = self.attendee.info() | self.extra
    template_path = os.path.join(os.path.dirname(__file__), f"../static/email_templates/{self.template}.txt")

    with open(template_path, 'r') as f:
      lines = f.readlines()
    
      # First line is subject, then blank line, then body
      subject = lines[0].replace("Subject: ", "").strip()
      body = "".join(lines[2:]).format(**{key: info[key] for key in info.keys()})
      return subject, body

  def send(self, server, force=False):
    sent_time = self.attendee.email_sent_time(self.template)
    if sent_time != None:
      log.info(f"Email {self.template} already sent to {self.attendee.info()['email']} at {sent_time}; not sending again without force flag")
      return False
    
    msg = self.create_html_email()
    log.debug(f"Sending email {self.template} to {self.attendee.info()['email']}")
    server.send_message(msg)
    log.debug(f"Marking email sent.")
    self.attendee.mark_email_sent(self.template)

  def create_html_email(self):
    subject, body = self.apply_template()
    info = self.attendee.info() | self.extra
    to_email = info["email"]

    log.trace(f"To: {to_email}\nSubject: {subject}\n\n{body}")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "US Go Congress <registrar@gocongress.org>"
    msg['To'] = to_email
    
    # Convert plain text to simple HTML
    html_body = f"<html><body>{body}</body></html>"
    
    # Attach both plain text and HTML versions
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    return msg


def connect_smtp():
  # Initialize SMTP connection
  smtp_server = 'mail.smtp2go.com'
  smtp_port = 587
  smtp_user = secret('smtp_username')
  smtp_pass = secret('smtp_password')
  
  # Connect to SMTP server
  log.info(f"Connecting as SMTP user {smtp_user}@{smtp_server}:{smtp_port}")
  server = smtplib.SMTP(smtp_server, smtp_port)

  log.debug("Starting TLS connection to SMTP server")
  server.starttls()

  log.debug("Authenticating with SMTP server")
  server.login(smtp_user, smtp_pass)
  return server

