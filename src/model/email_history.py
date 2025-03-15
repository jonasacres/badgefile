from datetime import datetime
from integrations.database import Database
from util.secrets import secret
from log.logger import log
import hashlib

class EmailHistory:
  @classmethod
  def shared(cls):
    if not hasattr(cls, '_shared'):
      cls._shared = EmailHistory(Database.shared())
    return cls._shared

  def __init__(self, database):
    self.database = database
    self.create_table_if_not_exists()

  def create_table_if_not_exists(self):
    self.database.execute("""
      CREATE TABLE IF NOT EXISTS email_history (
        email_id INTEGER PRIMARY KEY AUTOINCREMENT,
        badgefile_id TEXT,
        email_type TEXT,
        timestamp DATETIME,
        email_from TEXT,
        email_to TEXT,
        email_subject TEXT,
        email_body TEXT,
        email_copy_url TEXT
      )
    """)

  def email_types(self):
    results = self.database.query("""
      SELECT DISTINCT email_type 
      FROM email_history
      GROUP BY email_type
      ORDER BY MIN(timestamp)
    """)
    return [row['email_type'] for row in results]

  def latest_emails_for_user(self, badgefile_id):
    results = self.database.query("""
      SELECT e1.* 
      FROM email_history e1
      LEFT OUTER JOIN email_history e2 
        ON e1.email_type = e2.email_type
        AND e1.badgefile_id = e2.badgefile_id 
        AND e1.timestamp < e2.timestamp
      WHERE e1.badgefile_id = ?
        AND e2.email_id IS NULL
    """, [badgefile_id])

    email_dict = {}
    for row in results:
      email_dict[row['email_type']] = row
    return email_dict

  def sent_email_for_user(self, badgefile_id, email_type, email_from, email_to, email_subject, email_body, time_sent=None):
    if time_sent is None:
      time_sent = datetime.now()
      
    self.database.execute("""
      INSERT INTO email_history 
      (badgefile_id, email_type, timestamp, email_from, email_to, email_subject, email_body)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [badgefile_id, email_type, time_sent, email_from, email_to, email_subject, email_body])
  
  def recipients_for_email(self, email_type):
    # return a list of badgefile_ids that received a given email_type
    results = self.database.query("""
      SELECT DISTINCT badgefile_id
      FROM email_history
      WHERE email_type = ?
      ORDER BY badgefile_id
    """, [email_type])
    return [row['badgefile_id'] for row in results]

  def sync_emails(self):
    import os

    log.debug(f"Syncing emails to storage")

    # Create artifacts/emails directory if it doesn't exist
    email_dir = os.path.join("artifacts", "emails")
    os.makedirs(email_dir, exist_ok=True)

    # Get all emails from database
    results = self.database.query("SELECT * FROM email_history")
    url_base = secret("email_url_base")
    
    for email_data in results:
      # Format email content
      fmt_email = self.format_email(email_data)
      
      # Create hash input string
      email_type = email_data['email_type']
      salt = secret("email_filename_salt")
      hash_input = f"{salt}|{len(email_type)}|{email_type}|{len(fmt_email)}|{fmt_email}"
      
      # Generate hash
      sha256 = hashlib.sha256(hash_input.encode()).hexdigest()[0:15]
      
      # Format timestamp
      timestamp = datetime.strptime(email_data['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S')
      timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
      
      # Create filename
      filename = f"{email_type}_{email_data['email_to']}_{timestamp_str}_{sha256}.txt"
      filepath = os.path.join(email_dir, filename)
      
      # Write file if it doesn't exist
      if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
          f.write(fmt_email)

        # Update the URL in the DB to point to local file
        self.database.execute(
          "UPDATE email_history SET email_copy_url = ? WHERE email_id = ?",
          [
            f"{url_base}/{filename}",
            email_data['email_id']
          ]
        )

  def format_email(self, row):
    return f"From: {row['email_from']}\nTo: {row['email_to']}\nDate: {row['timestamp']}\nSubject: {row['email_subject']}\n\n{row['email_body']}"
