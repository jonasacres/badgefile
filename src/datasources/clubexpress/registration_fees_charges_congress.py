import csv
from datetime import datetime
from io import StringIO

from .ce_report_base import CEReportBase
from util.secrets import secret

class RegistrationFeesChargesCongress(CEReportBase):
  @classmethod
  def report_key(cls):
    return "reg_fees_charges_congress"

  @classmethod
  def report_uri(cls):
    return secret('congress_event_url')
  
  @classmethod
  def report_data(cls):
    return {
      "__EVENTTARGET": "ctl00$save_button",
      "ctl00$export_radiobuttonlist": "4",
      "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
      "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
    }

  @classmethod
  def google_drive_name(cls):
    return "reg_fees_charges_congress.csv"
  
  def __init__(self, csv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv
    self.header_row = None
    self._path = None
    self._hash = None
    self._last_anchor_row = None
    self._by_transrefnum = None

  def translate_row(self, csvrow):
    map = self.column_map()
    result = {}

    # this report has a very irritating construction that i'm sure someone thought looked super clean or something
    # rows are not independent. they are grouped together by transaction, each with a unique transrefnum.
    # only the first row of a transaction has all the data, including the transrefnum.
    # so we have to pay attention to which rows have that, and when we notice one, hold onto it.
    # then for the missing fields, we can copy the data from that row into each subsequent row of the transaction.

    transrefnum_index = map.index("transrefnum")
    if csvrow[transrefnum_index].strip() != "":
      for i, key in enumerate(map):
        if i >= len(csvrow):
          result[key] = None
        else:
          result[key] = self.translate_value(key, csvrow[i])
      self._last_anchor_row = result
    else:
      for i, key in enumerate(map):
        if i >= len(csvrow):
          result[key] = None
        elif csvrow[i].strip() == "" and self._last_anchor_row is not None:
          result[key] = self._last_anchor_row[key]
        else:
          result[key] = self.translate_value(key, csvrow[i])

    
    self._last_anchor_row = result
    return result

  def translate_value(self, key, value):
    if value is None:
      return None
      
    value = str(value).strip()
    if value == "" and key == "balance_due":
      return 0
    
    # I will be the first to tell you that handling currency in floats is inviting danger, due to round-off error.
    # By rights, we ought to cast to pennies and then only convert back to dollars when we have to for presentation purposes.
    # However, this is tedious, and we do almost no arithmetic on these values, which mitigates our exposure... and we're not
    # really accounting software.

    # Remove $ and , from the value
    clean_value = value.lstrip('$').replace(',', '')
    
    # Try parsing as float first (handles both decimal and non-decimal numbers)
    try:
        num = float(clean_value)
        # If it's a whole number, return as int
        return int(num) if num.is_integer() else num
    except ValueError:
        # If not numeric, return original value
        return value

  def rows(self):
    return [self.translate_row(row) for row in csv.reader(StringIO(self.csv.decode("utf-8")))][1:]
  
  def by_transrefnum(self):
    if self._by_transrefnum is not None:
      return self._by_transrefnum
    
    by_transrefnum = {}

    for row in self.rows():
      # if "housing" in self.__class__.google_drive_name():
      #   print(row)
      trn = row['transrefnum']
      if not trn in by_transrefnum:
        by_transrefnum[trn] = []
      by_transrefnum[trn].append(row)
    
    self._by_transrefnum = by_transrefnum
    return self._by_transrefnum
    

  def column_map(self):
    return [
      "event_title",                    # "Event Title",
      "event_date",                     # "Event Date",
      "registrant",                     # "Registrant", # 'name_given name_family'
      "email",                          # "Email",
      "phone_cell",                     # "Cell Phone",
      "transaction_date",               # "Transaction Date",
      "total_fees",                     # "Total Fees",
      "transrefnum",                    # "Refernce Number",
      "payment_status",                 # "Status",
      "balance_due",                    # "Balance Due",
      "is_primary",                     # "Primary?",
      "item_description",               # "Activity/Item Fee",
      "item_fee",                       # "Activity/Item Fee", # yes, they have two columns with the same name containing different data
      "payment_date",                   # "Payment Date",
      "payment_amount",                 # "Pmt Amt",
      "payment_type",                   # "Payment Type",
      "check_number",                   # "Check Number",
      "cc_last_four",                   # "CC Last 4 Digits",
      "payment_distribution_amount",    # "Payment Distribution Amount",
      "payment_processor_fee",          # "Payment Processor Fee",
      "remit_status",                   # "Remit Status",
    ]

  