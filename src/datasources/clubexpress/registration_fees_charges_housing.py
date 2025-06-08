from .registration_fees_charges_congress import RegistrationFeesChargesCongress
from util.secrets import secret


class RegistrationFeesChargesHousing(RegistrationFeesChargesCongress):
  @classmethod
  def report_key(cls):
    return "reg_fees_charges_housing"

  @classmethod
  def report_uri(cls):
    return secret('housing_event_url')

  @classmethod
  def google_drive_name(cls):
    return "reg_fees_charges_housing.csv"
  