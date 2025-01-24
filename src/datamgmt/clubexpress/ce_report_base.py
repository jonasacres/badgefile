from datetime import datetime
import os
import hashlib
import csv
from io import StringIO
from ..report_manager import ReportManager
from integrations.google_drive import authenticate_service_account, upload_csv_to_drive
from log.logger import *
from util.secrets import secret

class CEReportBase:
  """Base class for ClubExpress reports like ActivityList and RegList."""

  # Subclasses should override these to provide the correct report key,
  # directory path, and any downloading details (URI & form data).
  @classmethod
  def report_key(cls):
    """Internal name of report (no spaces or special characters). eg. reglist, activity_list"""
    raise NotImplementedError("Subclass must define a 'report_key' classmethod.")

  @classmethod
  def directory(cls):
    return f"reports/{cls.report_key()}"

  @classmethod
  def report_uri(cls):
    """URI for pulling the specific report from ClubExpress. You can get this by going to the page in CE where we run Exports for the relevant event,
    and copying the URI."""
    raise NotImplementedError("Subclass must define a 'report_uri' classmethod.")
  
  @classmethod
  def google_drive_name(cls):
    return f"{cls.report_key()}.csv"

  @classmethod
  def report_data(cls):
    """POST form data for pulling the specific report from ClubExpress."""
    # Get this by recording the HTTP POST for the desired Export (e.g. using Developer Tools in the browser)
    # Look at the request data for the form submission (this will also give you report_uri)
    # Return a hash defining the following 4 keys. ce_integration.py will fill in the other keys for you, so you should
    # ONLY need to supply these 4 keys! Copy-paste the values for each key from the form submission you captured.
    # DO NOT URL-ENCODE THESE VALUES. Decode them from what is presented in your tooling if needed!
    # 
    # eg. return {
    #   "__EVENTTARGET" : "...copypasted value goes here...",
    #   "ctl00$export_radiobuttonlist": "...copypasted value goes here...",
    #   "ctl00$registration_status_dropdown": "...copypasted value goes here...",
    #   "ctl00_registration_status_dropdown_ClientState": "...copypasted value goes here...",
    # }
    raise NotImplementedError("Subclass must define a 'report_data' classmethod.")

  def __init__(self, csv_bytes, timestamp=None):
    if timestamp is None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv_bytes
    self._path = None
    self._hash = None

  @classmethod
  def latest(cls):
    """
    Return the latest copy of this report from disk, according to the database.
    If no existing copy or it's missing on disk, returns None.
    """
    latest_info = ReportManager.shared().last_report_info(cls.report_key())
    if latest_info is None:
      return None

    path = latest_info["path"]
    timestamp = "_".join(path.split("_")[-3:-1])

    try:
      with open(path, "rb") as file:
        recorded_csv = file.read()
        return cls(recorded_csv, timestamp)
    except FileNotFoundError:
      return None

  @classmethod
  def download(cls):
    """
    Pull a new copy of this report from ClubExpress, save to disk, upload 
    to drive, and register it in the ReportManager. Use an existing copy if unchanged.
    """
    # Subclasses might override these classmethods if they have special URIs or data
    uri = cls.report_uri()
    data = cls.report_data()

    from integrations.ce_integration import CEIntegration
    log_debug(f"{cls.report_key()}: Downloading from {uri}")
    csv_bytes = CEIntegration.shared().pull_report(uri, data)
    new_report = cls(csv_bytes)

    # Compare hash with the latest
    new_hash = new_report.hash()
    log_debug(f"{cls.report_key()} sha256 {new_hash}")

    latest_report = cls.latest()
    if latest_report is not None:
      if latest_report.hash() == new_hash:
        # Reuse existing copy, just update the DB so the last pulled time is recorded
        ReportManager.shared().pulled_report(cls.report_key(), new_hash, latest_report.path())
        log_debug(f"{cls.report_key()}: Matches existing copy (sha256 {new_hash}); reusing existing copy at {latest_report.path()}")
        latest_report.timestamp = new_report.timestamp  # refresh timestamp if needed
        return latest_report

    # Otherwise, save, upload, and record
    log_info(f"{cls.report_key()}: New version (sha256 {new_hash}); saving to {new_report.path()}")
    new_report.save()
    new_report.upload()
    ReportManager.shared().pulled_report(cls.report_key(), new_hash, new_report.path())

    return new_report

  def save(self):
    """Save the CSV bytes to disk."""
    os.makedirs(self.directory(), exist_ok=True)
    with open(self.path(), "w", encoding="utf-8") as file:
      file.write(self.csv.decode("utf-8"))

  def hash(self):
    """Compute or retrieve the SHA-256 hash of the CSV content."""
    if self._hash is None:
      self._hash = hashlib.sha256(self.csv).hexdigest()
    return self._hash

  def path(self):
    """Generate or return the path where this file is stored (or will be stored)."""
    if self._path is None:
      short_hash = self.hash()[:8]
      self._path = f"{self.directory()}/{self.__class__.__name__}_{self.timestamp}_{short_hash}.csv"
    return self._path

  def is_latest(self):
    """Check (via report manager) if this copy's hash is the latest in the DB."""
    return ReportManager.shared().last_report_info(self.report_key())["hash"] == self.hash()

  def upload(self):
    """Uploads the CSV to Google Drive using the shared credentials."""
    service = authenticate_service_account()
    upload_csv_to_drive(service, self.path(), self.__class__.google_drive_name(), secret("folder_id")) 

  def header(self):
    if self.header_row == None:
      self.header_row = next(csv.reader(StringIO(self.csv.decode("utf-8")), None))
    return self.header_row
  
  def index_for_field(self, field_name):
    map = self.heading_map()
    heading = map[field_name].lower()
    for i, string in enumerate(self.header()):
      if string.lower() == heading:
        return i
    return None
  