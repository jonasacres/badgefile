from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from log.logger import *

import time
import os

# Authenticate with the service account
def authenticate_service_account(service_account_file=None):
  if service_account_file is None:
    service_account_file = "google_service_account.json"
  SCOPES = ['https://www.googleapis.com/auth/drive']
  creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
  return build('drive', 'v3', credentials=creds)

def upload_csv_to_drive(service, file_path, file_name, folder_id=None):
    # Search for existing file with the same name in the specified folder

    if not os.path.exists(file_path):
      raise FileNotFoundError(f"File not found: {file_path}")

    basename = file_name.removesuffix(".csv")
    log_info(f"{basename}: Uploading from {file_path}")
    query = f"name='{basename}'"
    if folder_id:
      query += f" and '{folder_id}' in parents"

    log_trace(f"{basename}: Google drive API query -- \"{query}\"")
    
    def retry_with_backoff(func, max_wait=30):
        start_wait = 0.5
        wait = start_wait
        while True:
          try:
            if wait != start_wait:
              log_info(f"{basename}: Making Google API request after delay of {wait}")
            return func()
          except (HttpError, TimeoutError) as e:
            if isinstance(e, HttpError):
              log_notice(f"{basename}: Caught HttpError waiting for Google Drive: {e}")
              if e.resp.status < 500:
                log_warn(f"{basename}: Raising exception")
                raise
            else:
              log_notice(f"{basename}: Caught TimeoutError waiting for Google Drive: {e}")
            log_info(f"{file_name}: Waiting {wait}s to retry")
            time.sleep(wait)
            wait = min(wait * 2, max_wait)
  
    results = retry_with_backoff(
        lambda: service.files().list(q=query, spaces='drive', fields="files(id, name)", 
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    )
    log_trace(f"{basename}: query results {results}")
    files = results.get('files', [])
    media = MediaFileUpload(file_path, mimetype='text/csv')
    file_metadata = {'name': basename, 'mimeType': "application/vnd.google-apps.spreadsheet"}
    if folder_id:
      file_metadata['parents'] = [folder_id]
    
    # If the file exists, overwrite it so we keep the same file ID
    if files:
      # if more than one existing copy is present, delete all but one
      for file in files[1:]:
        log_info(f"{basename} Deleting existing file {file['id']} {file['name']}")
        retry_with_backoff(
            lambda: service.files().delete(fileId=file['id'], supportsAllDrives=True).execute()
        )
        log_debug(f"{basename}: Deleted existing file {file['id']} {file['name']}")
      log_debug(f"{basename}: Updating existing file {files[0]['name']} at ID {files[0]['id']}")
      retry_with_backoff(
          lambda: service.files().update(fileId=files[0]['id'], media_body=media, supportsAllDrives=True).execute()
      )
      log_debug(f"{basename}: Updated file {files[0]['name']} successfully")
    else:
      # Upload the new file
      log_debug(f"{basename}: Uploading to new location")
      uploaded_file = retry_with_backoff(
          lambda: service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
      )
      log_debug(f"{basename}: Uploaded file successfully. File ID: {uploaded_file.get('id')}")
