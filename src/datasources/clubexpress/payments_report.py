import csv
import requests
import urllib.parse
from datetime import datetime
from io import StringIO

from .ce_report_base import CEReportBase
from .reglist_row import ReglistRow
from util.secrets import secret
from log.logger import log

class PaymentsReport(CEReportBase):
  """Pulls the 'Payments With Transactions by Date' report from the Money -> Reports page for the interval between the end of the 2024
  Go Congress and the start of the 2025 Go Congress."""

  @classmethod
  def report_key(cls):
    return "payments_report"

  @classmethod
  def report_uri(cls):
    return secret('payments_report_url')

  @classmethod
  def report_watch_fields(self):
    return [
      "__EVENTARGUMENT",
      "club_id",
      "member_id",
      "report_member_id",
      "member_status",
      "submit_step",
      "next_step",
      "start_date",
      "end_date",
      "mailing_list_category_id",
      "committee_id",
      "member_type_id",
      "member_level",
      "sp1",
      "sp2",
      "sp3",
      "sp4",
      "user_payment_type",
      "master_account_id",
      "transaction_type_id",
      "payment_status_id",
      "missing_email",
      "show_level2",
      "show_level3",
      "show_level4",
      "order_status",
      "product_category_id",
      "sort_field",
      "service_category_id",
      "service_request_type",
      "service_request_status",
      "service_provider_type",
      "service_provider_status",
      "event_category_id",
      "resource_id",
      "resource_category_id",
      "metro_area_id",
      "channel_id",
      "document_folder_id",
      "document_folder_name",
      "ushering_coordinator_type",
      "sponsorship_type_id",
      "crse_course_id",
      "title_id",
      "registrant_type_ids",
      'report_title',
      "ctl00$subgroup$subgroup_id",

      "__EVENTTARGET", # POST 0 and beyond: "ctl00$run_button" (do NOT allow override from form data!)
      "report_group_id", # POST 0: '20',
      "report_queue_id", # POST 0: '0', then read from responses
      "report_id", # POST 0: 406
      "ctl00$report_list", # POST 0: '406'
      "ctl00$subgroup$subgroup_name", # POST 1: 'All Members'
      "ctl00_subgroup_dropdown_tree_ClientState", # POST 1: '{"fireServerEvents":false,"enabled":true,"logEntries":[]}',
      'date_option', # POST 2: '3'
      'start_date_entry', # POST 2: '07/21/2024'
      'end_date_entry', # POST 2: '7/20/2025'
      'output_format', # POST 3: '19'
    ]
  
  @classmethod
  def report_csv_query_fields(cls):
    return [
      'report_queue_id',
      'club_id',
      'member_id',
      'report_member_id',
      'member_status',
      'start_date',
      'end_date',
      'mailing_list_category_id',
      'committee_id',
      'member_type_id',
      'member_level',
      'sp1',
      'sp2',
      'sp3',
      'sp4',
      'user_payment_type',
      'master_account_id',
      'transaction_type_id',
      'payment_status_id',
      'missing_email',
      'show_level2',
      'show_level3',
      'show_level4',
      'order_status',
      'product_category_id',
      'sort_field',
      'service_category_id',
      'service_request_type',
      'service_request_status',
      'service_provider_type',
      'service_provider_status',
      'event_category_id',
      'resource_id',
      'resource_category_id',
      'metro_area_id',
      'channel_id',
      'document_folder_id',
      'document_folder_name',
      'ushering_coordinator_type',
      'sponsorship_type_id',
      'crse_course_id',
      'title_id',
      'registrant_type_ids',
      'report_title',
      'output_format',
      'ctl00$subgroup$subgroup_id',
      'ctl00$subgroup$subgroup_name',
    ]
  
  @classmethod
  def get_csv(cls):
    # Subclasses might override these classmethods if they have special URIs or data
    uri = cls.report_uri()

    from integrations.clubexpress_client import ClubExpressClient
    log.debug(f"{cls.report_key()}: Downloading from {uri}")
    data_tiers = [
      {
        "__EVENTTARGET": "ctl00$run_button",
        "report_queue_id": "0",
        "report_id": "406",
        "ctl00$report_list": "406",
      }, {
        "__EVENTTARGET": "ctl00$run_button",
        "ctl00_subgroup_dropdown_tree_EmbeddedTree_ClientState": '{"expandedNodes":[],"collapsedNodes":[],"logEntries":[],"selectedNodes":["0"],"checkedNodes":[],"scrollPosition":0}',
        "ctl00$subgroup$subgroup_name": "All Members",
        "ctl00_subgroup_dropdown_tree_ClientState": '{"fireServerEvents":false,"enabled":true,"logEntries":[]}',
      }, {
        "__EVENTTARGET": "ctl00$run_button",
        "ctl00_subgroup_dropdown_tree_EmbeddedTree_ClientState": '{"expandedNodes":[],"collapsedNodes":[],"logEntries":[],"selectedNodes":["0"],"checkedNodes":[],"scrollPosition":0}',
        'date_option': '3',
        'start_date_entry': '07/21/2024',
        'end_date_entry': '7/20/2025',
      }
    ]

    data = ClubExpressClient.shared().iterated_form_query(uri, cls.report_watch_fields(), data_tiers)
    csv_data = {key: data[key] for key in cls.report_csv_query_fields()}
    csv_data['output_format'] = '19'
    csv_query_str = urllib.parse.urlencode(csv_data)

    report_uri = "https://reports.clubexpress.com/create_report.ashx?" + csv_query_str

    session = requests.Session()
    csv_resp = session.get(report_uri, headers={
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.5',
      'Accept-Encoding': 'gzip, deflate, br',
      'Dnt': '1',
      'Upgrade-Insecure-Requests': '1',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'cross-origin',
      'Sec-Fetch-User': '?1',
      'Priority': 'u=0, i',
      'Te': 'trailers',
    })

    if csv_resp.status_code != 200:
      log.warn(f"Got HTTP {csv_resp.status_code} on request for payments CSV ({report_uri}).\n\nHTTP response body: {csv_resp.text}")
      return None
    
    new_report = cls(csv_resp.text.encode("utf-8"))
    return new_report

  @classmethod
  def google_drive_name(cls):
    return "payments_report.csv"
  
  def __init__(self, csv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv
    self._path = None
    self._hash = None

  def transactions(self):
    mapped_rows = self.rows()
    rows_by_transaction = {}

    for row in mapped_rows:
      if row['ref_num'] not in rows_by_transaction:
        rows_by_transaction[row['ref_num']] = []
      rows_by_transaction[row['ref_num']].append(row)
    
    transactions_list = []
    for ref_num, transaction_rows in rows_by_transaction.items():
      payment_description_str = transaction_rows[0].get('payment_description', None)
      if payment_description_str is None:
        continue

      # payment_description_str format: 'Payment from LastName, FirstName on m/d/yyyy by PaymentMethod'
      # parse out FirstName and LastName
      name_part = payment_description_str.split('Payment from ')[1].split(' on ')[0]
      last_name, first_name = name_part.split(', ', 1) if ', ' in name_part else (name_part, '')

      transaction = {
        'ref_num': ref_num,
        'rows': transaction_rows,
        'total_amount': sum(row['amount'] for row in transaction_rows),
        'name': [first_name, last_name],
        'date': transaction_rows[0]['charge_date'],
      }

      transactions_list.append(transaction)
    
    return transactions_list

  def rows(self):
    return [self.map_row(row) for row in csv.reader(StringIO(self.csv.decode("utf-8"))) if self.is_real_row(row)]
  
  def is_real_row(self, row):
    if len(row) > 0:
      return row[0].startswith("Payment from")
    return False
  
  def map_row(self, row):
    col_names = [
        "payment_description",
        "_literally_just_says_amount",
        "amount",
        "_literally_just_says_status",
        "status",
        "_literally_just_says_applied_to",
        "_literally_just_says_charge_date",
        "_literally_just_says_ref_#",
        "_literally_just_says_description",
        "_literally_just_says_amount_charged",
        "_literally_just_says_amount_paid",
        "charge_date",
        "ref_num",
        "description",
        "amount_charged",
        "amount_paid"
      ]
    
    mapped_row = {}
    for idx, col_name in enumerate(col_names):
      if col_name[0] == "_":
        continue
      mapped_row[col_name] = row[idx]

    # handling currency as floats is always risky business, but we'll run with it for now...
    # if roundoff error on pennies becomes an issue, switch to integer cents (amount * 100)
    mapped_row["amount"] = float(mapped_row["amount"].replace(',', ''))
    mapped_row["charge_date"] = datetime.strptime(mapped_row["charge_date"], '%m/%d/%Y')
    mapped_row["ref_num"] = int(mapped_row["ref_num"].replace(',', ''))
    mapped_row["amount_charged"] = float(mapped_row["amount_charged"].replace(',', ''))
    mapped_row["amount_paid"] = float(mapped_row["amount_paid"].replace(',', ''))
    
    return mapped_row
  
