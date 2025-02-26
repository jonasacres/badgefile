from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from log.logger import log

import time
import os

"""Provides helper methods for dealing with Google API stuff."""

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
      log.info(f"{basename}: Waiting {wait}s to retry")
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
  
def create_sheet_if_not_exists(service, file_name, folder_id, sheet_name):
  files = locate_existing_files(service, file_name, folder_id)
  log.debug(f"Locating file {file_name} in folder {folder_id} with worksheet {sheet_name}")
  
  if not files:
    # Create new spreadsheet
    log.debug(f"Creating file {file_name}")
    file_metadata = {
      'name': file_name,
      'mimeType': 'application/vnd.google-apps.spreadsheet'
    }
    if folder_id:
      file_metadata['parents'] = [folder_id]
      
    file = retry_with_backoff(file_name,
      lambda: service['drive'].files().create(
        body=file_metadata,
        fields='id',
        supportsAllDrives=True
      ).execute()
    )
    
    # Rename first worksheet
    requests = [{
      'updateSheetProperties': {
        'properties': {
          'sheetId': 0,
          'title': sheet_name
        },
        'fields': 'title'
      }
    }]
    
    log.debug(f"Renaming first worksheet of {file_name} to {sheet_name}")
    retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().batchUpdate(
        spreadsheetId=file['id'],
        body={'requests': requests}
      ).execute()
    )
    
    return file['id']
    
  file = files[0]
  
  # Check if worksheet exists
  spreadsheet = retry_with_backoff(file_name,
    lambda: service['sheets'].spreadsheets().get(
      spreadsheetId=file['id']
    ).execute()
  )
  
  log.debug(f"Located file {file_name} with id {file}")
  sheet_exists = any(sheet['properties']['title'] == sheet_name 
                    for sheet in spreadsheet['sheets'])
                    
  if not sheet_exists:
    # Add new worksheet
    log.debug(f"Adding worksheet {sheet_name} to existing file {file_name} with id {file}")
    requests = [{
      'addSheet': {
        'properties': {
          'title': sheet_name
        }
      }
    }]
    
    retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().batchUpdate(
        spreadsheetId=file['id'],
        body={'requests': requests}
      ).execute()
    )
    
  return file['id']

def read_sheet_data(service, file, sheet_name=None):
  # Get spreadsheet metadata
  spreadsheet = retry_with_backoff(file,
    lambda: service['sheets'].spreadsheets().get(
      spreadsheetId=file
    ).execute()
  )

  # If sheet_name not specified, use first sheet
  if sheet_name is None:
    sheet_name = spreadsheet['sheets'][0]['properties']['title']

  log.debug(f"Reading worksheet {sheet_name} of file id {file}")
  # Read values from the sheet
  result = retry_with_backoff(file,
    lambda: service['sheets'].spreadsheets().values().get(
      spreadsheetId=file,
      range=f'{sheet_name}!A1:ZZ'
    ).execute()
  )

  # Return empty list if no data
  if 'values' not in result:
    return []

  return result['values']
  
def sync_sheet_table(service, file_name, sheet_header, sheet_data, key_index, sheet_name=None, folder_id=None, valueInputOption='RAW'):
  file = create_sheet_if_not_exists(service, file_name, folder_id, sheet_name)
  existing_data = read_sheet_data(service, file, sheet_name)

  if len(existing_data) == 0:
    existing_data = [[v for v in sheet_header]]

  mapped_rows = {}
  seen_rows = {}
  new_rows = []

  for i, row in enumerate(existing_data):
    if len(row) > key_index:
      mapped_rows[row[key_index]] = i
      seen_rows[row[key_index]] = False

  updated_data = existing_data.copy()

  for row in sheet_data:
    key = str(row[key_index])
    if key in mapped_rows:
      for i, value in enumerate(row):
        if i >= len(updated_data[mapped_rows[key]]):
            updated_data[mapped_rows[key]].extend([None] * (i - len(updated_data[mapped_rows[key]]) + 1))
        updated_data[mapped_rows[key]][i] = value
    else:
      new_rows.append(row)
    seen_rows[key] = True

  best_row_index = -1
  best_row_count = 0
  for row_index, row in enumerate(existing_data):
    row_match_count = 0
    for col_index, column in enumerate(row):
      if col_index < len(sheet_header) and column in sheet_header:
        row_match_count += 1
    if row_match_count > best_row_count:
      best_row_index = row_index
      best_row_count = row_match_count
  
  if best_row_index < 0:
    unseen = list(range(len(existing_data)+1))
    for mapping in mapped_rows:
      unseen.remove(mapped_rows[mapping])
    best_row_index = unseen[0]

  if best_row_index == len(updated_data):
    updated_data.append(sheet_header)
  else:
    for i, value in enumerate(sheet_header):
      if i >= len(updated_data[best_row_index]):
          updated_data[best_row_index].extend([None] * (i - len(updated_data[best_row_index]) + 1))
      updated_data[best_row_index][i] = value
  seen_rows[sheet_header[key_index]] = True

  updated_data.extend(new_rows)


  for key, seen in seen_rows.items():
    if not seen:
      updated_data[mapped_rows[key]] = None

  # Filter out None rows and prepare data for batch update
  valid_rows = [(i, row) for i, row in enumerate(updated_data) if row is not None]
  if valid_rows:
    log.debug(f"Updating {len(valid_rows)} data rows in file {file_name}, worksheet {sheet_name}")
    batch_data = {
      'valueInputOption': valueInputOption,
      'data': [
        {
          'range': f'{sheet_name}!A{i+1}',
          'values': [row]
        } for i, row in valid_rows
      ]
    }
    
    retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().values().batchUpdate(
        spreadsheetId=file,
        body=batch_data
      ).execute()
    )
  
  # Delete rows that were marked as None
  rows_to_delete = []
  for i, row in enumerate(updated_data):
    if row is None:
      rows_to_delete.append(i + 1) # Add 1 since sheet rows are 1-based
  
  if rows_to_delete:
    log.debug(f"Deleting {len(rows_to_delete)} rows from file {file_name}, worksheet {sheet_name}")
    # Sort in descending order to avoid shifting indices when deleting
    rows_to_delete.sort(reverse=True)
    
    # Create delete request for each row
    requests = [{
      'deleteDimension': {
        'range': {
          'sheetId': 0, # Default first sheet
          'dimension': 'ROWS',
          'startIndex': row - 1, # Convert back to 0-based
          'endIndex': row # Delete 1 row
        }
      }
    } for row in rows_to_delete]

    # Execute all deletes in a single batch update
    retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().batchUpdate(
        spreadsheetId=file,
        body={'requests': requests}
      ).execute()
    )
  
  # After all data updates and row deletions are complete, check and update table range
  spreadsheet = retry_with_backoff(file_name,
      lambda: service['sheets'].spreadsheets().get(
          spreadsheetId=file
      ).execute()
  )

  import json
  log.debug(f"Spreadsheet\n{json.dumps(spreadsheet, indent=2)}")

  for sheet in spreadsheet['sheets']:
    if sheet['properties']['title'] != sheet_name:
      continue
    if not 'bandedRanges' in sheet or len(sheet['bandedRanges']) == 0:
      continue
    for bandedRange in sheet['bandedRanges']:
      if bandedRange['range']['startRowIndex'] != 0:
        continue
        
      # Update the banded range to match the new data length
      bandedRange['range']['endRowIndex'] = len(updated_data)
      
      # Send update request
      retry_with_backoff(file_name,
        lambda: service['sheets'].spreadsheets().batchUpdate(
          spreadsheetId=file,
          body={
            'requests': [{
              'updateBanding': {
                'bandedRange': bandedRange,
                'fields': 'range.endRowIndex'
              }
            }]
          }
        ).execute()
      )

