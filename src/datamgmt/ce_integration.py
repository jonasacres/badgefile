import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import hashlib
import os
import base64

# Pulls reports from ClubExpress.
class CEIntegration:
  _shared = None

  @classmethod
  def shared(cls):
    if cls._shared != None:
       return cls._shared
    
    credentials_path = os.path.expanduser("~/.badgefile_credentials")
    with open(credentials_path, "r") as file:
      lines = file.read().splitlines()  # Split on newline
      if len(lines) >= 2:
          username, password = lines[0], lines[1]
      else:
          raise ValueError("File does not contain enough lines to assign username and password.")
    
    cls._shared = CEIntegration(username, password)
    # TODO: add in report definitions
    # registrant_data
    return cls._shared
     
  # username and password are actual login credentials for admin account on usgo.org.
  def __init__(self, username, password):
    self.username = username
    self.password = password
    self.reports = {}
    self.session = None
    self.headers = {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
      'Accept': '*/*',
      'Accept-Language': 'en-US,en;q=0.5',
      'Accept-Encoding': 'gzip, deflate, br',
      'Referer': 'https://usgo.org/',
      'X-Requested-With': 'XMLHttpRequest',
      'X-Microsoftajax': 'Delta=true',
      'Cache-Control': 'no-cache',
      'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
      'Origin': 'https://usgo.org',
      'Dnt': '1',
      'Sec-Fetch-Dest': 'empty',
      'Sec-Fetch-Mode': 'cors',
      'Sec-Fetch-Site': 'same-origin',
      'Priority': 'u=0',
      'Te': 'trailers',
    }

  def login(self):
    landing_uri = "https://usgo.org/"
    login_uri = "https://usgo.org/content.aspx?club_id=454497&page_id=31&action=login"

    self.session = requests.Session()

    # hit the UGA landing page first, so this looks more natural
    self.session.get(landing_uri, headers=self.headers)

    # Dictionary to hold the extracted form data
    login_form_data = {
      "script_manager": "ctl00$ctl00$ctl00$ctl00$login_wrapperPanel|ctl00$ctl00$login_button",
      "__EVENTTARGET": "ctl00$ctl00$login_button",
      "ctl00$ctl00$dummy": "",
      "ctl00$ctl00$uuid_value": "",
      "ctl00$ctl00$login_name": self.username,
      "ctl00$ctl00$password": self.password,
      "ctl00$ctl00$hiddenPassword": base64.b64encode(self.password.encode('utf-8')).decode('utf-8'),
      "__ASYNCPOST": "true",
      "RadAJAXControlID": "ctl00_ctl00_ajax_manager"
    }
    
    login_response = self.make_form_query(login_uri, login_form_data)
    print(login_response.status_code)
    print(login_response.text)


  def make_form_query(self, uri, data):
    # ASP.net expects to see a bunch of hidden form parameters to fulfill our request, like VIEWSTATE.
    # We can get these by doing a GET request for the page which has the form we want to submit.
    if(self.session is None):
       self.login()
    get_resp = self.session.get(uri, headers=self.headers)
    soup = BeautifulSoup(get_resp.text, 'html.parser')
    field_names = [
        'style_sheet_manager_TSSM',
        '__EVENTARGUMENT',
        'DES_Group',
        '__VIEWSTATE',
        '__VIEWSTATEGENERATOR',
    ]

    # We have to inject in certain constants as well -- these are buried elsewhere in the static site content, but aren't as easy to extract.
    # So they just have hardcoded values here.
    form_data = {
        "script_manager_TSM": ";;System.Web.Extensions, Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35:en-US:e441b334-44bb-41f8-b8ef-43fec6e58811:ea597d4b:b25378d2;Telerik.Web.UI:en-US:8b7d6a7a-6133-413b-b622-bbc1f3ee15e4:16e4e7cd:365331c3:24ee1bba:ed16cbdc",
        "DES_JSE": 1,
        "changes_pending": "",
    }

    # Some forms have a VIEWSTATEFIELDCOUNT variable indicating that there is more than 1
    # VIEWSTATE field. Subsequent VIEWSTATEs are named VIEWSTATE1, VIEWSTATE2, ...
    # Including the original VIEWSTATE, there are a total of VIEWSTATEFIELDCOUNT variables.
    # If VIEWSTATEFILEDCOUNT is omitted, then VIEWSTATE is the only VIEWSTATE field.
    
    # we see VIEWSTATEFIELDCOUNT, so we should add the subsequent VIEWSTATEx fields to
    # the list of fields to extract from the form data returned in the GET request.
    field_count = soup.find('input', {'name': "__VIEWSTATEFIELDCOUNT"})
    if field_count:
        field_count_value = field_count.get('value', '')
        form_data["__VIEWSTATEFIELDCOUNT"] = field_count_value
        num_fields = int(field_count_value)
        for i in range(1, num_fields):
            field_names.append("__VIEWSTATE" + str(i))

    # now go get the fields from the form data.
    for name in field_names:
        input_tag = soup.find('input', {'name': name})
        if input_tag:
            form_data[name] = input_tag.get('value', '')
        else:
            form_data[name] = ''
    
    # inject in any additional data from our requestor
    form_data = form_data | data
    
    # URL encode the form data as a single string, and set the Referer field so it looks
    # like we're coming from the page with the form
    data = urllib.parse.urlencode(form_data)
    my_headers = self.headers.copy()
    my_headers["Referer"] = uri

    # issue the request and return the response
    return self.session.post(uri, headers=self.headers, data=data)

  def pull_all_reports(self):
    for report_name, defn in self.reports.items():
      # Pull the report
      csv = self.pull_report(defn["uri"], defn["data"])
      sha256_hash = hashlib.sha256(csv.encode()).hexdigest()
      filename = f"{report_name}-{sha256_hash}.csv"

      # Skip if the file exists and matches the hash
      if os.path.exists(filename):
        with open(filename, "r") as existing_file:
          existing_content = existing_file.read()
          existing_hash = hashlib.sha256(existing_content.encode()).hexdigest()
          if existing_hash == sha256_hash:
              continue

      # Write the file if it doesn't exist or hash doesn't match
      with open(filename, "w") as file:
        file.write(csv)

  
  def pull_report(self, uri, data):
    response = self.make_form_query(uri, data)
    csv = response.text
    return csv.encode("utf-8")
  
  def add_report(self, report_name, uri, data):
     self.reports[report_name] = { "uri": uri, "data": data}


# TODO: this is just here for future reference
# each key in 'exports' is a report name.
# each value is a dict with a uri and data that can be provided to add_report or pull_report.

exports = {
  "youth_form_legal_guardian": {
      "uri": "https://usgo.org/content.aspx?page_id=1479&club_id=454497&item_id=9632&actr=3",
      "data": {
          "__EVENTTARGET": "ctl00$ctl00$export_button",
          "ctl00$ctl00$status_dropdown": "-1",
          "ctl00$ctl00$start_date$date_text_box": "",
          "ctl00$ctl00$end_date$date_text_box": "",
      }
  },

  "youth_form_attending_guardian": {
      "uri": "https://usgo.org/content.aspx?page_id=1479&club_id=454497&item_id=9631&actr=3",
      "data": {
          "__EVENTTARGET": "ctl00$ctl00$export_button",
          "ctl00$ctl00$status_dropdown": "-1",
          "ctl00$ctl00$start_date$date_text_box": "",
          "ctl00$ctl00$end_date$date_text_box": "",
      }
  },

  "registrant_data": {
      "uri": "https://usgo.org/popup.aspx?page_id=4036&club_id=454497&item_id=2197916",
      "data": {
          "__EVENTTARGET": "ctl00$save_button",
          "ctl00$export_radiobuttonlist": "2",
          "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
          "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
      }
  },

  "registration_fees_and_charges": {
      "uri": "https://usgo.org/popup.aspx?page_id=4036&club_id=454497&item_id=2197916",
      "data": {
          "__EVENTTARGET": "ctl00$save_button",
          "ctl00$export_radiobuttonlist": "4",
          "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
          "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
      }
  },

  "2023_housing_meals_registrant_data": {
      "uri": "https://usgo.org/popup.aspx?page_id=4036&club_id=454497&item_id=1938036",
      "data": {
          "__EVENTTARGET": "ctl00$save_button",
          "ctl00$export_radiobuttonlist": "2",
          "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
          "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
      }
  }
}
