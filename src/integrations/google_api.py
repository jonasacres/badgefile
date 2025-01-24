from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from log.logger import log

import time
import os

# Authenticate with the service account
def authenticate_service_account(service_account_file=None):
  if service_account_file is None:
    service_account_file = "google_service_account.json"
  SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
  ]
  creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
  return {
    'drive': build('drive', 'v3', credentials=creds),
    'sheets': build('sheets', 'v4', credentials=creds)
  }

def retry_with_backoff(basename, func, max_wait=30):
  start_wait = 0.5
  wait = start_wait
  while True:
    try:
      if wait != start_wait:
        log.info(f"{basename}: Making Google API request after delay of {wait}")
      return func()
    except (HttpError, TimeoutError) as e:
      if isinstance(e, HttpError):
        log.notice(f"{basename}: Caught HttpError waiting for Google Drive: {e}")
        if e.resp.status < 500:
          log.warn(f"{basename}: Raising exception")
          raise
      else:
        log.notice(f"{basename}: Caught TimeoutError waiting for Google Drive: {e}")
      log.info(f"{file_name}: Waiting {wait}s to retry")
      time.sleep(wait)
      wait = min(wait * 2, max_wait)

def locate_existing_files(service, basename, folder_id=None):
    query = f"name='{basename}'"
    if folder_id:
      query += f" and '{folder_id}' in parents"

    log.trace(f"{basename}: Google drive API query -- \"{query}\"")
  
    results = retry_with_backoff(basename,
        lambda: service['drive'].files().list(q=query, spaces='drive', fields="files(id, name)", 
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    )
    log.trace(f"{basename}: query results {results}")
    files = results.get('files', [])
    return files

def upload_file_to_drive(service, file_path, file_name, folder_id=None, mimetype=None, google_mimetype=None):
    # Search for existing file with the same name in the specified folder

    if not os.path.exists(file_path):
      raise FileNotFoundError(f"File not found: {file_path}")

    basename = file_name.removesuffix(".csv")
    log.info(f"{basename}: Uploading from {file_path}, mimetype '{mimetype}', google mimetype '{google_mimetype}'")
    media = MediaFileUpload(file_path, mimetype=mimetype)
    file_metadata = {'name': basename, 'mimeType': google_mimetype}
    if folder_id:
      file_metadata['parents'] = [folder_id]
    
    files = locate_existing_files(service, basename, folder_id)
    # If the file exists, overwrite it so we keep the same file ID
    if files:
      # if more than one existing copy is present, delete all but one
      for file in files[1:]:
        log.info(f"{basename} Deleting existing file {file['id']} {file['name']}")
        retry_with_backoff(basename,
            lambda: service['drive'].files().delete(fileId=file['id'], supportsAllDrives=True).execute()
        )
        log.debug(f"{basename}: Deleted existing file {file['id']} {file['name']}")
      log.debug(f"{basename}: Updating existing file {files[0]['name']} at ID {files[0]['id']}")
      retry_with_backoff(basename,
          lambda: service['drive'].files().update(fileId=files[0]['id'], media_body=media, supportsAllDrives=True).execute()
      )
      log.debug(f"{basename}: Updated file {files[0]['name']} successfully")
    else:
      # Upload the new file
      log.debug(f"{basename}: Uploading to new location")
      uploaded_file = retry_with_backoff(basename,
          lambda: service['drive'].files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
      )
      log.debug(f"{basename}: Uploaded file successfully. File ID: {uploaded_file.get('id')}")

def upload_csv_to_drive(service, file_path, file_name, folder_id=None):
  return upload_file_to_drive(service, file_path, file_name, folder_id, "text/csv", "application/vnd.google-apps.spreadsheet")


def upload_json_to_drive(service, file_path, file_name, folder_id=None):
  return upload_file_to_drive(service, file_path, file_name, folder_id, "application/json", "application/json")

def update_sheets_worksheet(service, file_name, sheet_data, folder_id=None):
  files = locate_existing_files(service, file_name, folder_id)
  if files is None or len(files) == 0:
    log.critical(f"{file_name}: Unable to locate existing Google Sheets sheet matching name in folder {folder_id}")
    return False
  
  file = files[0]
  
  # Convert data to Google Sheets format
  body = {
    'values': sheet_data
  }

  try:
    # Clear existing data first
    retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().values().clear(
        spreadsheetId=file['id'],
        range='Data!A1:ZZ',
        body={}
      ).execute()
    )

    # Update with new data
    retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().values().update(
        spreadsheetId=file['id'],
        range='Data!A1',
        valueInputOption='RAW',
        body=body
      ).execute()
    )
    
    log.debug(f"{file_name}: Successfully updated worksheet")
    return True

  except Exception as e:
    log.critical(f"{file_name}: Encountered exception updating worksheet", exception=e)
    return False