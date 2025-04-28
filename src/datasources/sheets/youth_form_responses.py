from datetime import datetime
from util.secrets import secret
from integrations.google_api import read_sheet_data, authenticate_service_account
from log.logger import log

class YouthFormResponses:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    self.read_sheet()

  def youth_form(self, attendee):
    return self.responses.get(attendee.id(), None)

  def read_sheet(self):
    log.info(f"Reading youth form sheet...")
    self.responses = {}
    service = authenticate_service_account()
    file_id = secret("youth_form_response_file_id")
    data = read_sheet_data(service, file_id)
    map = self.column_map()
    responses = [self.transform_row({map[i]: val for i, val in enumerate(row)}) for row in data if self.row_looks_legit(row)]

    log.debug(f"{len(responses)} youth forms received so far.")

    for response in responses:
      attendee = self.locate_attendee_for_response(response)
      if attendee is not None:
        self.responses[attendee.id()] = response

    for attendee in self.badgefile.attendees():
      attendee.set_youth_info(self.responses.get(attendee.id(), None))
    
    log.debug("Finished reading youth forms")
  
  def row_looks_legit(self, row):
    try:
      datetime.strptime(row[0], '%m/%d/%Y %H:%M:%S')
      datetime.strptime(row[2], '%m/%d/%Y')
      return row[1] != None and len(row[1]) > 0
    except (ValueError, IndexError):
      return False
  
  def locate_attendee_for_response(self, response):
    name_comps = [s.lower() for s in response['name_full'].split()]

    for attendee in self.badgefile.attendees():
      attendee_name_comps = [s.lower() for s in [attendee.info()['name_given'], attendee.info()['name_family']]]
      match_names = all(name_comp in name_comps for name_comp in attendee_name_comps)
      match_dob = attendee.date_of_birth() == response['date_of_birth']
      if match_dob:
        log.debug(f"Possible match for {response['name_full']} -> {attendee.id()} {attendee.info()['name_given']} {attendee.info()['name_family']}. name match: {match_names}")

      if match_dob and match_names:
        return attendee
    
    log.notice(f"Cannot find matching registration for youth form with name '{response['name_full']}', dob {response['date_of_birth']}, form entered '{response['timestamp']}'")
    return None
  
  def transform_row(self, row):
    transformed = row.copy()
    transformed['timestamp'] = datetime.strptime(row['timestamp'], '%m/%d/%Y %H:%M:%S')
    transformed['date_of_birth'] = datetime.strptime(row['date_of_birth'], '%m/%d/%Y')
    transformed['signer_is_attending_raw'] = row['signer_is_attending']
    transformed['signer_is_attending'] = row['signer_is_attending'].lower() == 'Myself (Parent/Legal Guardian)'.lower()
    return transformed
    
  def column_map(self):
    return [
      'timestamp',
      'name_full',
      'date_of_birth',
      'age_at_congress',
      'email',
      'phone',
      'addr1',
      'addr2',
      'insurance_company',
      'insurance_policy_num',
      'group_plan',
      'medical_info',
      'signing_guardian_name',
      'signing_guardian_relationship',
      'signing_guardian_contact_email',
      'signing_guardian_contact_phone',
      'signing_guardian_addr1',
      'signing_guardian_addr2',
      'signer_is_attending',
      'attending_guardian_name',
      'attending_guardian_relation',
      'attending_guardian_email',
      'attending_guardian_phone',
      'attending_guardian_addr1',
      'attending_guardian_addr2',
      'attending_guardian_signature',
      'attending_guardian_signature_date',
      'emergency_contact_name',
      'emergency_contact_relation',
      'emergency_contact_email',
      'emergency_contact_phone',
      'signing_guardian_signature',
      'signing_guardian_signature_date',
    ]