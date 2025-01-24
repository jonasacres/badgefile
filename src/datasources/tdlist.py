import csv
import requests
import hashlib
import os
from io import StringIO
from datetime import datetime

from log.logger import log
from util.secrets import secret

from datasources.data_source_manager import DataSourceManager
from integrations.google_api import authenticate_service_account, upload_csv_to_drive

# TODO: consolidate this with other report classes into a common subclass that does common parts of latest/download and other operations

class TDList:
  """Tournament Director's list. Shows everyone's AGA membership status (name, rating, sigma, club, last renewal date, expiration date)."""

  @classmethod
  def directory(cls):
    return "reports/TDList"
  
  @classmethod
  # latest copy we pulled according to database
  def latest(cls):
    latest_info = DataSourceManager.shared().last_datasource_info("td_list")
    if latest_info == None:
      return None
    
    path = latest_info["path"]
    timestamp = "_".join(path.split("_")[-3:-1])
    
    try:
      with open(path, "rb") as file:
        tsv = file.read()
        return cls(tsv, timestamp)
    except FileNotFoundError:
      return None

  @classmethod
  # download a copy from CE, then save it to disk and return a copy
  def download(cls):
    uri = "https://aga-functions.azurewebsites.net/api/GenerateTDListB"
    log.debug(f"td_list: Downloading from {uri}")

    tsv = requests.get(uri).text.encode("utf-8")
    td_list = TDList(tsv)

    log.debug(f"td_list: sha256 {td_list.hash()}")
    hash = td_list.hash()

    latest = TDList.latest()
    if latest is not None:
      if latest.hash() == hash:
        log.debug(f"td_list: Matches existing copy (sha256 {hash}); reusing existing copy at {latest.path()}")
        DataSourceManager.shared().pulled_datasource("td_list", hash, latest.path())
        existing = cls(csv)
        existing.path = latest.path()
        return existing

    log.info(f"td_list: New version (sha256 {hash}); saving to {td_list.path()}")
    td_list.save()
    td_list.upload()
    DataSourceManager.shared().pulled_datasource("td_list", hash, td_list.path())

    return cls(tsv)


  def __init__(self, tsv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.tsv = tsv
    self._path = None
    self._hash = None

  
  def hash(self):
    if self._hash is None:
      self._hash = hashlib.sha256(self.tsv).hexdigest()
      log.trace(f"td_list: Calculated hash (sha256 {self._hash}); caching for future use")
    return self._hash

  def rows(self):
    reader = csv.reader(StringIO(self.tsv.decode("utf-8")), dialect="excel-tab")
    next(reader) # skip header row

    columns = [
      'tdlist_name',         # Full name (Last, First)
      'aga_id',              # AGA number
      'member_type',         # Full/Life/Youth/Comp/Non
      'aga_rating',          # negative is kyu, positive is dan
      'aga_expiration_date', # m/d/Y
      'aga_chapter',         # Full chapter name
      'aga_state',           # Two-letter state abbreviation
      'aga_rating_sigma',    # float
      'aga_last_renew_date', # Column heading says "Join date," but this seems to be the date of their last renewal
    ]

    return [{key: self.translate_value(key, value) for key, value in zip(columns, line)} for line in reader]
      
  def apply(self, badgefile):
    log.debug(f"td_list: Merging data from TD list into attendees")
    for tdlist_info in self.rows():
      attendee = badgefile.lookup_attendee(tdlist_info['aga_id'])
      if attendee is not None:
        attendee.merge_tdlist_info(tdlist_info)
  
  # TODO: this appears in 3 places without alteration. REALLY should have a common util class in this project!
  def translate_value(self, field, raw_value):
    """Ensure each field gets translated to an appropriate datatype (eg. ints and floats for numbers, where appropriate)."""

    if "phone" in field or field == "postcode":
      return raw_value  # Ensure these remain as strings, even if numeric
    elif raw_value == "":
      return None  # Blank string becomes None
    elif raw_value.replace("-", "", 1).replace(".", "", 1).isdigit() and (raw_value.count("-") <= 1 and raw_value.find("-") in {-1, 0}):
      # Check if it's a float or int
      return float(raw_value) if "." in raw_value else int(raw_value)
    else:
      return raw_value  # Use the original string if it's not numeric

    
  def path(self):
    if self._path is None:
      shorthash = self.hash()[:8]
      self._path = f"{TDList.directory()}/TDList_{self.timestamp}_{shorthash}.csv"
      log.trace(f"td_list: path calculated as {self._path}; caching for future use")
    return self._path
  
  def is_latest(self):
    return DataSourceManager.shared().last_datasource_info("td_list")["hash"] == self.hash()
  
  def save(self):
    """Save CSV to the filesystem."""

    log.debug(f"td_list: Saving to {self.path()}")
    os.makedirs(TDList.directory(), exist_ok=True)
    with open(self.path(), "w") as file:
      file.write(self.tsv.decode("utf-8"))

  def upload(self):
    """Upload to Google Drive."""

    log.debug(f"td_list: Uploading to Google Drive")
    service = authenticate_service_account()
    upload_csv_to_drive(service, self.path(), "td_list.csv", secret("folder_id"))
