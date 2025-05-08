import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from util.secrets import secret
from log.logger import log
from model.email_history import EmailHistory

class Email:
  _default_server = None

  @classmethod
  def default_server(cls):
    if cls._default_server is None:
      if not secret("email_enable"):
        log.notice("returning dummy for email server since e-mail is disabled")
        return "e-mail disabled"
      
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
      cls._default_server = server

    return cls._default_server

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

  def send(self, server=None, force=False):
    server = server or Email.default_server()
    sent_emails = EmailHistory.shared().latest_emails_for_user(self.attendee.id())
    prior_email = sent_emails.get(self.template)
    email_to = self.attendee.info()['email']

    if prior_email != None and not force:
      log.debug(f"Email {self.template} already sent to {email_to} at {prior_email['timestamp']}; not sending again without force flag")
      return False
    
    msg, html_body, plaintext_body = self.create_html_email()
    if secret("email_enable") is True:
      log.debug(f"Sending email {self.template} to {email_to}")
      server.send_message(msg)
    else:
      log.debug(f"Not sending email {self.template} to {email_to} -- email disabled in configuration")
    
    log.debug(f"Marking email sent.")
    EmailHistory.shared().sent_email_for_user(self.attendee.id(),
                                              self.template,
                                              msg['From'],
                                              msg['To'],
                                              msg['Subject'],
                                              plaintext_body)

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
    
    return [msg, html_body, body]


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

