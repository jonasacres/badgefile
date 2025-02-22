#!/usr/bin/env python3

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from model.badgefile import Badgefile
from util.secrets import secret
from log.logger import log

def load_template():
    template_path = os.path.join(os.path.dirname(__file__), "static/email_templates/housing_open.txt")
    with open(template_path, 'r') as f:
        lines = f.readlines()
    
    # First line is subject, then blank line, then body
    subject = lines[0].replace("Subject: ", "").strip()
    body = "".join(lines[2:])
    return subject, body

def create_html_email(to_email, subject, body):
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

def send_emails():
    # Load email template
    subject_template, body_template = load_template()
    
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

    # log.debug("Authenticating with SMTP server")
    # server.login(smtp_user, smtp_pass)
    
    try:
        # Load badgefile
        log.debug("Loading badgefile")
        bf = Badgefile()
        
        # Get all primary registrants
        primary_registrants = [att for att in bf.attendees() if att.is_primary() and not att.is_cancelled()]
        
        log.info(f"Sending housing emails to {len(primary_registrants)} primary registrants")
        
        # Send email to each primary registrant
        for attendee in primary_registrants:
            info = attendee.info()
            
            # Skip if no email address
            if not info.get('email'):
                log.warn(f"No email address for attendee {info.get('name_given')} {info.get('name_family')} ({info.get('badgefile_id')})")
                continue
            
            # Personalize email
            personalized_body = body_template.format(
                name_given=info['name_given']
            )
            
            # Create email message
            msg = create_html_email(
                info['email'],
                subject_template,
                personalized_body
            )
            
            # Send email
            # server.send_message(msg)
            log.info(f"Sent housing email to {info['email']} ({info['name_given']} {info['name_family']})")
            
    finally:
        log.info("Done sending e-mails")
        server.quit()
        pass

if __name__ == "__main__":
    # I don't want to accidentally run this again and spam all our attendees, so I commented out the line to run the mailer...
    # send_emails()
    pass
