import os
import sys
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from util.secrets import secret, override_secret
from log.logger import log
from model.email_history import EmailHistory
from smtplib import SMTPRecipientsRefused

class Email:
  _default_server = None

  @classmethod
  def email_whitelist_path(cls):
    os.path.join(os.path.dirname(__file__), "../../email-whitelist.txt")

  @classmethod
  def email_whitelist(cls):
    whitelist_path = os.path.join(os.path.dirname(__file__), "../../email-whitelist.txt")
    if not os.path.exists(whitelist_path):
      return None
    
    try:
      with open(whitelist_path, 'r') as f:
        # Read all lines, strip comments and whitespace, and filter out empty lines
        emails = [line.split('#')[0].strip() for line in f.readlines() if line.split('#')[0].strip()]
        return emails
    except Exception as e:
      log.error(f"Failed to read email whitelist: {e}")
      return None

  @classmethod
  def override_enable(cls):
    if not secret("email_enable"):
      delay = 3
      print("WARNING: This environment has email_enable configured to be false, which means emails do not get sent.")
      print("This is obviously counterproductive for this script.")
      print("Therefore, this script will OVERRIDE this safety setting and send e-mails anyway, but only to those designated in email-whitelist.txt.")

      # if email-whitelist.txt does not exist, warn the user and exit with status 1.
      whitelist = cls.email_whitelist()
      if whitelist is None:
        print("ERROR: email-whitelist.txt does not exist. This file is required for safety when overriding email settings.")
        print("Please create this file with a list of email addresses that are allowed to receive test emails.")
        sys.exit(1)
      
      print(f"\n{len(whitelist)} whitelisted email addresses:")
      for email in whitelist:
        print(email)
      print()
      
      print("Hit CTRL+C to abort.")
      print(f"Waiting {delay} seconds...")
      for i in range(delay, 0, -1):
        print(f"{i}...")
        time.sleep(1)

      # Override the email_enable setting to force sending emails
      override_secret("email_enable", True)
      override_secret("email_safety", True)
      print("Override in place. This session WILL send live e-mails.")
      return True
    return False


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
    
  def email_address_allowed(self, email_address):
    whitelist = self.__class__.email_whitelist()

    if whitelist is None:
      if secret("email_safety", False):
        # we set this when we override e-mail to be deliverable from test scripts in environments that otherwise disable it.
        log.error(f"Refusing to send e-mail to {email_address} without existence of email-whitelist.txt, due to email_safety flag")
        sys.exit(1)
      else:
        return True
    
    return email_address.strip().lower() in [email.strip().lower() for email in whitelist if email.strip()]

  def send(self, server=None, force=False):
    server = server or Email.default_server()
    sent_emails = EmailHistory.shared().latest_emails_for_user(self.attendee.id())
    prior_email = sent_emails.get(self.template)
    email_to = self.attendee.info()['email']

    if prior_email != None and not force:
      log.debug(f"Email {self.template} already sent to {email_to} at {prior_email['timestamp']}; not sending again without force flag")
      return False
    
    msg, html_body, plaintext_body = self.create_html_email()
    if email_to is None:
      log.notice(f"Member {self.attendee.full_name()} (#{self.attendee.id()}) does not have an e-mail address; not sending e-mail")
      return False
    if secret("email_enable") is True:
      log.debug(f"from: {msg['From']}, to: {msg['To']}, subject: {msg['Subject']}\n\n{html_body}")
      
      if self.email_address_allowed(email_to):
        log.info(f"ACTUAL EMAIL: Sending email {self.template} to {email_to}")
        retry_count = 0
        retry_max = 3
        while retry_count < retry_max:
          try:
            server.send_message(msg)
            break
          except SMTPRecipientsRefused:
            log.notice(f"Member {self.attendee.full_name()} (#{self.attendee.id()}) has invalid e-mail address {email_to}; not sending e-mail")
            return False
          except smtplib.SMTPServerDisconnected:
            retry_count += 1
            if retry_count >= retry_max:
              log.warn(f"Got SMTPServerDisconnected; giving up after {retry_count} attempts")
              break
            log.notice(f"Got SMTPServerDisconnected; retrying (attempt {retry_count+1})")
            Email._default_server = None
            server = Email.default_server()
      else:
        log.debug(f"Skipping email {self.template} to {email_to}; address not in whitelist")
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

