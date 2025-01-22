# wraps up a single row from the Registration Fees and Charges report from CE (as described by Regfees)

class RegfeesRow:
  #### DATA ACCESSORS
  #  0 event_title
  #  1 event_date (formatted mm/dd/yy)
  #  2 registrant_name (formatted as first + " " + last)
  #  3 email
  #  4 cell phone
  #  5 transaction_date (mm/dd/yy)
  #  6 total_fees (has leading $)
  #  7 reference_num (should match transaction ref num in reglist)
  #  8 status ("Paid in Full" / "Not Paid"/ "Canceled" / "Partial Payment")
  #  9 balance_due (leading $, blank for no balance due)
  # 10 primary? ("Yes" / "No")
  # 11 item_name (string describing name of registrant AND name of thing paid for)
  # 12 item_fee (leading $)
  # 13 payment_date (mm/dd/yy)
  # 14 payment_amount (leading $)
  # 15 payment_type ("Discount Coupon", "PayPal", "Credit Card", "Comp", "Use Credit Balance", "Separate System", "Cash (to club)")
  # 16 check_number (always blank?)
  # 17 cc_last_4 (e.g. "Visa - 1234" -- probably best we don't even keep this)
  # 18 payment_distribution_amount (leading $)
  # 19 payment_processor_fee (leading $)
  # 20 remit_status ("Received By Club" / "Remitted To Club" / "Not Processed")
  pass
