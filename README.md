## Setting up

This is a Python3-based project that relies on sqlite3.
I've only really run it on Linux, but I'm sure it either works on Windows/Mac/BSD, or can easily be fixed to work.

The basic function here is:
 - This program logs into usgo.org to pull reports from ClubExpress for the Go Congress. (You need a username and password for this.)
 - It also grabs the TDListB off usgo.org.
 - All the different reports are merged together to make the "badgefile," which is basically a database showing everyone who is at Congress, what they've signed up for, what they've paid, what their rating is, etc.
 - It does some checks to look for common registration mistakes, eg. buying youth admission for adults.
 - Reports are generated and uploaded to Google Drive. (You need a folder ID, and a service account key with write permission for that folder.)

### Installing on Ubuntu
Ensure you have the appropriate packages installed:

TODO: list apt commands
TODO: set up anaconda and `badgefile` environment

### Obtaining the source
Check out a copy of this repository from Github:

```
git clone https://github.com/jonasacres/badgefile
cd badgefile
```

Now install dependencies.

```
conda activate badgefile
pip install -r requirements.txt
```

### Writing secrets.yaml
Inside the badgefile directory, copy the file called `secrets.yaml.example` to `secrets.yaml`. Open `secrets.yaml` in a text editor.

This file will contain pieces of confidential information that are necessary for the Badgefile to operate. You will need to know:

- `aga_username` and `aga_password`: Login credentials for usgo.org for a user with permission to pull reports from the Congress Registration and Housing events.
- `congress_event_url`: URL for the Congress Registration event. Get this by navigating to the event in ClubExpress, and going to the "Edit" page where you can find the "Exports" button. Copy-paste the URL.
- `congress_housing_url`: URL for the Congress Housing event.
- `folder_id`: Google Drive Folder ID for the folder where uploaded spreadsheets and data should be placed. You can get this by going to the Drive in your browser. Copy-paste the URL, and delete everything before the last '/'. So if the URL looks like "https://drive.google.com/drive/u/0/folders/1JoQc6gCZkGX-tOqfesD1d_TuNLCmoP-F", then the ID is "1JoQc6gCZkGX-tOqfesD1d_TuNLCmoP-F".
- `discord_log_webhook`: (Optional) A discord webhook for a channel. If supplied, Badgefile will post error messages to this channel. This is useful if Badgefile is running automatically as a scheduled task, since it provides a convenient way to learn about errors.

### Obtaining google_service_account.json
Go to https://console.cloud.google.com/apis/credentials

Ensure you are signed in as the appropriate Google user (should be part of gocongress.org or usgo.org).

TODO: There needs to be a Google Cloud project for the Go Congress that the user has access to. I have not yet written instructions on how to set one up. You will also need to enable the following APIs:
  - Google Drive API 
  - Google Sheets API

If you don't have a project set up with these API services enabled on your account, you'll need to puzzle this piece out yourself. Sorry! (The good news is, it is free and doesn't require a credit card number.)

Go to https://console.cloud.google.com/apis/credentials
Click "Manage service accounts"

Navigate Google's painfully bad UI to create a Service Account. Presently, this is done by clicking the 3 non-descript dots located by the blue college graduate hat in the header that says "Service accounts". This should open a drop-down with an option that reads "CREATE SERVICE ACCOUNT". Click that.
Fill out an appropriate service account name and account ID.
For account description, enter "Badgefile".
Click "CREATE AND CONTINUE."

Do not add any roles to the account; just hit CONTINUE.
Do not grant any users access to the service account; just hit DONE.

You should now see a list of service accounts, including your newly-created account.
Click the three dots next to the new account and click "Manage Keys".
Click "ADD KEY", and "Create New Key".
Select "JSON" from the popup menu and hit "CREATE".
You should receive a popup saying "Private key saved to your computer", and a very small file download will begin.
The file will be named something like projectname-f054316ce9ab.json.
Rename this file to google_service_account.json and place it in the `badgefile` directory that you cloned from Github.

