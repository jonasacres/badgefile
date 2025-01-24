import os
import csv
from datetime import datetime
from integrations.google_api import update_sheets_worksheet, authenticate_service_account
from util.secrets import secret

from log.logger import *

class RegHistoryReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def generate(self, path):
    log_debug("reg_history_report: Generating report")
    self.history = self.load_history()
    self.save(path)
    self.upload()

  def save(self, path):
    log_debug(f"reg_history_report: Saving to {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode='w', newline='', encoding='utf-8') as file:
      writer = csv.writer(file)
      writer.writerow(["Year"] + self.history["date_labels"])
      for year, counts in self.history.items():
        if year == "date_labels":
          continue
        writer.writerow([year] + counts)

  def load_history(self):
    raw_history = {}
    with open(self.history_path(), 'r') as file:
      reader = csv.reader(file)
      raw_history["date_labels"] = next(reader)[1:]
      for row in reader:
        if len(row) > 0 and row[0]: # Check for non-empty year
          year = row[0]
          raw_history[year] = row[1:] # Store all columns after year
    if not self.validate_history(raw_history):
      raise Exception("Invalid history file")
    
    normalized = self.normalize_history(raw_history)
    log_debug(f"reg_history_report: Loaded history file")
    return normalized
  
  def validate_history(self, raw_history):
    first_year = list(raw_history.keys())[0]
    expected_cols = len(raw_history[first_year])

    for year, counts in raw_history.items():
      if year == "date_labels":
        # we have a header row with date labels, it validates differently from the data rows
        if len(counts) != expected_cols:
          log_warn(f"congress_history.csv: Row for date labels has {len(counts)} columns, expected {expected_cols}")
          return False
        
        # Validate date label format (e.g. "1-Jan")
        for date_label in counts:
          try:
            datetime.strptime(date_label, "%d-%b")
          except ValueError:
            log_warn(f"congress_history.csv: Invalid date label format: {date_label}")
            return False

        continue
      
      # OK, not the date label row, so this must be data for a year
      # Validate year is integer
      if not year.isdigit():
        log_warn(f"congress_history.csv: Invalid year format: {year}")
        return False

      # Validate all rows have same number of columns
      if len(counts) != expected_cols:
        log_warn(f"congress_history.csv: Row for year {year} has {len(counts)} columns, expected {expected_cols}")
        return False

      # Validate all counts are integers or empty strings
      for count in counts:
        if count and not count.strip().replace('-','').isdigit():
          log_warn(f"congress_history.csv: Invalid count format in year {year}: {count}")
          return False

    return True
  
  def normalize_history(self, raw_history):
    normalized = { "date_labels": raw_history["date_labels"] }
    for year, counts in raw_history.items():
      if year == "date_labels":
        continue

      # Convert empty strings to 0, otherwise convert string to int
      normalized_counts = [0 if count.strip() == '' else int(count) for count in counts]
      normalized[int(year)] = normalized_counts

    return normalized

  def history_path(self):
    # return a path to "../static/congress_data.csv", relative to this source file
    return os.path.join(os.path.dirname(__file__), "../static/congress_history.csv")
  
  def current_year_data(self, date_labels):
    # Convert date labels to datetime objects for comparison
    current_year = datetime.now().year
    dates = []
    for label in date_labels:
      dt = datetime.strptime(f"{label}-{current_year}", "%d-%b-%Y")
      dates.append(dt)
    
    # Add Dec 31 as final date for last interval
    dates.append(datetime(current_year, 12, 31))

    # Initialize counts array
    counts = [0] * len(date_labels)
    
    # Count registrants in each interval
    for attendee in self.badgefile.attendees():
      if attendee.is_cancelled():
        continue
        
      reg_date = attendee.regtime()
      
      # Find which interval this registration falls into
      for i in range(len(dates)-1):
        if i == 0:
          continue
        if reg_date >= dates[i-1] and reg_date < dates[i]:
          counts[i] += 1
          break
    
    return {current_year: counts}

  def upload(self):
    log_debug("reg_history_report: Uploading to Google Sheets")
    all_data = self.history | self.current_year_data(self.history["date_labels"])
    sheet_data = [["Year"] + all_data["date_labels"]]
    for year in sorted(all_data.keys(), key=lambda x: str(x)):
      if year == "date_labels":
        continue
      sheet_data.append([year] + all_data[year])
    
    service = authenticate_service_account()
    update_sheets_worksheet(service, "reg_history_report", sheet_data, secret("folder_id"))
