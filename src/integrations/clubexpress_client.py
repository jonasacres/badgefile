import requests
from bs4 import BeautifulSoup
import urllib.parse
import hashlib
import os
import base64
import time
import csv
import traceback
import json
from io import StringIO
from log.logger import log
from util.secrets import secret

class ClubExpressClient:
  """Provides an interface to authenticate with ClubExpress, download reports and submit forms."""

  _shared = None

  @classmethod
  def shared(cls):
    if cls._shared != None:
       return cls._shared
    
    username = secret("aga_username")
    password = secret("aga_password")

    cls._shared = ClubExpressClient(username, password)
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
    log.debug(f"CE login response: HTTP {login_response.status_code}", login_response.text)

  def make_form_query(self, uri, data, allow_non2xx=False):
    attempts = 0
    max_attempts = 5
    delay = 10

    while attempts < max_attempts:
      try:
        response = self._make_form_query(uri, data)
        log.trace(f"Received HTTP {response.status_code}, {len(response.text)} bytes")

        bad_session_str = "alert('Sorry - your session expired and we could not process your request');window.top.closeModalPopup();"
        if len(response.text) < 500 and bad_session_str in response.text:
          log.info("Got session expired notice; logging in again")
          self.login()
          continue

        if allow_non2xx or response.status_code // 100 == 2:
          # successful http response AND it looks like a CSV file; return it
          return response
      except Exception as e:
        attempts += 1
        if attempts == max_attempts:
          raise e
        log.info(f"Request for {uri} failed ({str(e)}), retrying in {delay}s (attempt {attempts}/{max_attempts})", exception=e)
      time.sleep(delay)
    
    log.warn(f"Request for {uri} failed after {attempts} retries")

  def _make_form_query(self, uri, data):
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

    # We have to inject in certain constants as well. They get injected via Javascript. Thankfully, they either
    # have easy constant values, or are parseable from elsewhere in the HTML.
    
    # script_manager_TSM is an interesting one. The HTML form has a hidden element with an empty value, which gets populated from Javascript.
    # The script inclusion for that looks like this:
    # <script src="/Telerik.Web.UI.WebResource.axd?_TSM_HiddenField_=script_manager_TSM&amp;compress=1&amp;_TSM_CombinedScripts_=SCRIPT_MANAGER_TSM_GOES_HERE" type="text/javascript"></script>
    # so we can check the HTML for the script with src starting with "/Telerik.Web.UI.WebResource.axd", 
    # then split on ? to extract the query string
    # then URL-decode the result (eg. "%20" and "+" both become " "), translate html entties (eg. &amp; becomes &)
    # extract the _TSM_CombinedScripts_ field of the query
    # use the resulting value as the value of the 'script_manager_TSM' field in our form submission

    script_tag = soup.find('script', {'src': lambda x: x and x.startswith('/Telerik.Web.UI.WebResource.axd')})
    parsed_script_manager_tsm = None
    if script_tag:
        src = script_tag['src']
        query_string = src.split('?')[1]
        query_params = urllib.parse.parse_qs(urllib.parse.unquote(query_string))
        if '_TSM_CombinedScripts_' in query_params:
            parsed_script_manager_tsm = query_params['_TSM_CombinedScripts_'][0]

    form_data = {
        "script_manager_TSM": parsed_script_manager_tsm,
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
    request_body = urllib.parse.urlencode(form_data)
    my_headers = self.headers.copy()
    my_headers["Referer"] = uri

    # issue the request and return the response
    return self.session.post(uri, headers=self.headers, data=request_body)
  
  def iterated_form_query(self, uri, watch_fields=[], data_tiers={}):
    log.info(f"Performing iterated request for {uri} (initial GET)")
    data = self._do_iterated_form_query(uri, watch_fields)

    for i, tier in enumerate(data_tiers):
      log.info(f"Performing iterated request for {uri} (POST {i})")
      data = data | tier
      data = data | self._do_iterated_form_query(uri, watch_fields, data)
      log.trace(f"Data: {json.dumps(data)}")
    
    return data

  def _do_iterated_form_query(self, uri, watch_fields=[], data=None):
    if(self.session is None):
      self.login()
    
    if data is None:
      http_resp = self.session.get(uri, headers=self.headers)
    else:
      request_body = urllib.parse.urlencode(data)
      my_headers = {
        "User-Agent": 'Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0',
        "Accept": 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': str(len(request_body)),
        'Origin': 'null',
        'Dnt': '1',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'iframe',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=4',
        'Te': 'trailers',
      }
      
      log.trace(f"Request body: {request_body}")
      http_resp = self.session.post(uri, headers=my_headers, data=request_body)
    
    soup = BeautifulSoup(http_resp.text, 'html.parser')
    default_field_names = [
        'style_sheet_manager_TSSM',
        '__EVENTARGUMENT',
        '__VIEWSTATE',
        '__VIEWSTATEGENERATOR',
    ]
    
    field_names = default_field_names + list(set(watch_fields) - set(default_field_names))

    script_tag = soup.find('script', {'src': lambda x: x and x.startswith('/Telerik.Web.UI.WebResource.axd')})
    parsed_script_manager_tsm = data.get("script_manager_TSM", None) if data else None
    if script_tag:
        src = script_tag['src']
        query_string = src.split('?')[1]
        query_params = urllib.parse.parse_qs(urllib.parse.unquote(query_string))
        if '_TSM_CombinedScripts_' in query_params:
          parsed_script_manager_tsm = query_params['_TSM_CombinedScripts_'][0]

    form_data = {
      "script_manager_TSM": parsed_script_manager_tsm,
    }

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
      elif name in default_field_names:
        form_data[name] = ''
  
    # inject in any additional data specified by our requestor, unless overridden by response
    if data is not None:
      form_data = data | form_data
    return form_data

  def validate(self, potential_csv):
    # return True if this looks like a valid CSV file; false otherwise
    # this does require us to have at least one data row, so it'll fail if we pull an empty report!

    try:
      # Try to parse the CSV using StringIO to create a file-like object
      csv_file = StringIO(potential_csv)
      csv_reader = csv.reader(csv_file)
      
      # Read first row to verify we can parse it
      header = next(csv_reader)
      
      # Check that we have at least two header columns (mostly arbitrary choice)
      if len(header) <= 1:
        return False
        
      # Try reading one data row
      first_row = next(csv_reader)
      if len(first_row) != len(header):
        return False
        
      return True
      
    except (csv.Error, UnicodeDecodeError, StopIteration):
      # Return False if we hit any parsing errors
      return False

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
    attempts = 0
    max_attempts = 5
    delay = 10

    while attempts < max_attempts:
      response = self.make_form_query(uri, data)
      possible_csv = response.text

      if self.validate(possible_csv):
        return possible_csv.encode("utf-8")
      
      # but if the response looks bad, then retry a few times
      attempts += 1
      log.info(f"Request failed, got non-csv file for {uri} (attempt {attempts}/{max_attempts})", data=possible_csv)
      log.debug(f"Waiting {delay}s before retrying...")
      time.sleep(delay)
    
    # we had problems and they didn't resolve themselves on retry, so throw an exception.
    log.warn(f"Failed to get CSV file from {uri} after {attempts} attempts")
    raise Exception("Failed to get CSV")
  
  def add_report(self, report_name, uri, data):
     self.reports[report_name] = { "uri": uri, "data": data}
