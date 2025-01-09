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
    query = f"name='{file_name}'"
    if folder_id:
      query += f" and '{folder_id}' in parents"

    print(f"query: {query}")
    
    results = service.files().list(q=query, spaces='drive', fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    print(f"results: {results}")
    files = results.get('files', [])
    media = MediaFileUpload(file_path, mimetype='text/csv')
    file_metadata = {'name': file_name}
    if folder_id:
      file_metadata['parents'] = [folder_id]
    
    # If the file exists, overwrite it so we keep the same file ID
    if files:
      # if more than one existing copy is present, delete all but one
      for file in files[1:]:
        print(f"Deleting existing file {file['id']} {file['name']}")
        service.files().delete(fileId=file['id'], supportsAllDrives=True).execute()
        print(f"Deleted existing file {file['id']} {file['name']}")
      service.files().update(fileId=files[0]['id'], media_body=media, supportsAllDrives=True).execute()
      print(f"Updating existing file {files[0]['id']}")
    else:
      # Upload the new file
      uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
      print(f"Uploaded file successfully. File ID: {uploaded_file.get('id')}")
