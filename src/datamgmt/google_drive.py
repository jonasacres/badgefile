from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import os

# Authenticate with the service account
def authenticate_service_account(service_account_file):
  SCOPES = ['https://www.googleapis.com/auth/drive']
  creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
  return build('drive', 'v3', credentials=creds)

# # Upload CSV to Google Drive
# def upload_csv_to_drive(service, path, filename, folder_id=None):
#   # Save the CSV content to a temporary file
#   # Define file metadata
#   file_metadata = {'name': filename}
#   if folder_id:
#       file_metadata['parents'] = [folder_id]

#   # Define media for upload
#   media = MediaFileUpload(path, mimetype='text/csv')

#   # Upload the file
#   uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
#   print(f"File uploaded successfully. File ID: {uploaded_file.get('id')}")

def upload_csv_to_drive(service, file_path, file_name, folder_id=None):
    # Search for existing file with the same name in the specified folder

    if not os.path.exists(file_path):
      raise FileNotFoundError(f"File not found: {file_path}")

    import time
    from googleapiclient.errors import HttpError

    basename = file_name.removesuffix(".csv")
    print(f"Upload {basename} from {file_name}")
    query = f"name='{basename}'"
    if folder_id:
      query += f" and '{folder_id}' in parents"

    print(f"query: {query}")
    
    def retry_with_backoff(func, max_wait=30):
        start_wait = 0.5
        wait = start_wait
        while True:
          try:
            if wait != start_wait:
              print(f"Making Google API request after delay of {wait}")
            return func()
          except (HttpError, TimeoutError) as e:
            if isinstance(e, HttpError):
              print(f"Caught HttpError waiting for Google Drive: {e}")
              if e.resp.status < 500:
                print(f"Raising exception")
                raise
            else:
              print(f"Caught TimeoutError waiting for Google Drive: {e}")
            print(f"Waiting {wait}s to retry")
            time.sleep(wait)
            wait = min(wait * 2, max_wait)
  
    results = retry_with_backoff(
        lambda: service.files().list(q=query, spaces='drive', fields="files(id, name)", 
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    )
    print(f"results: {results}")
    files = results.get('files', [])
    media = MediaFileUpload(file_path, mimetype='text/csv')
    file_metadata = {'name': basename, 'mimeType': "application/vnd.google-apps.spreadsheet"}
    if folder_id:
      file_metadata['parents'] = [folder_id]
    
    # If the file exists, overwrite it so we keep the same file ID
    if files:
      # if more than one existing copy is present, delete all but one
      for file in files[1:]:
        print(f"Deleting existing file {file['id']} {file['name']}")
        retry_with_backoff(
            lambda: service.files().delete(fileId=file['id'], supportsAllDrives=True).execute()
        )
        print(f"Deleted existing file {file['id']} {file['name']}")
      print(f"Updating existing file {files[0]['name']} at ID {files[0]['id']}")
      retry_with_backoff(
          lambda: service.files().update(fileId=files[0]['id'], media_body=media, supportsAllDrives=True).execute()
      )
      print(f"Updated file {files[0]['name']} successfully")
    else:
      # Upload the new file
      print(f"Uploading {basename} to new location")
      uploaded_file = retry_with_backoff(
          lambda: service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
      )
      print(f"Uploaded file {basename} successfully. File ID: {uploaded_file.get('id')}")
