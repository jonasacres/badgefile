import json
from flask import Flask, request, redirect, render_template, jsonify
from util.version import Version
import os

class WebService:
  def __init__(self, badgefile, listen_interface='127.0.0.1', port=8080):
    self.badgefile = badgefile
    self.listen_interface = listen_interface
    self.port = port
    template_dir = os.path.abspath('src/static/html_templates')
    self.app = Flask(__name__, template_folder=template_dir)
    self._setup_routes()
  
  def _setup_routes(self):
    @self.app.route('/')
    def home():
      return redirect('https://www.gocongress.org/')
    
    @self.app.route('/version')
    def version():
      return jsonify({'version': Version().hash()})
    
    @self.app.route('/attendees/<hashid>/confirm_housing', methods=['GET'])
    def confirm_housing_get(hashid):
      attendee = self.badgefile.lookup_attendee_by_hash_id(hashid)
      if attendee is None:
        return "Attendee not found", 404
      
      if not attendee.is_primary():
        return "Only primary registrants can confirm housing", 400
      
      # if attendee.party_housing():
      #   return render_template('confirm_housing_already_have.html', 
      #                         attendee=attendee.info(),
      #                         message="You have already reserved housing. Thank you for registering for the 2025 US Go Congress.")
      
      return render_template('confirm_housing.html', 
                            attendee=attendee.info(),
                            will_arrange_own_housing=attendee.will_arrange_own_housing())
    
    @self.app.route('/attendees/<hashid>/confirm_housing', methods=['POST'])
    def confirm_housing_post(hashid):
      attendee = self.badgefile.lookup_attendee_by_hash_id(hashid)
      if attendee is None:
        return "Attendee not found", 404
      
      if not attendee.is_primary():
        return "Only primary registrants can confirm housing", 400
      
      will_arrange_own_housing = request.form.get('will_arrange_own_housing')
      if will_arrange_own_housing not in ['true', 'false']:
        return "Invalid housing preference", 400
      
      attendee.set_will_arrange_own_housing(will_arrange_own_housing == 'true')
      return render_template('confirm_housing_thank_you.html', 
                            attendee=attendee.info(),
                            message="Thank you for responding to our housing survey.")
  
  def run(self):
    self.app.run(host=self.listen_interface, port=self.port)
