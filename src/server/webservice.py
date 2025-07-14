import hashlib
import json
import os
import re
import base64
import logging
import time

from flask import Flask, request, redirect, render_template, jsonify, abort, send_file
from flask_sock import Sock
from werkzeug.exceptions import NotFound

from log.logger import log
from util.version import Version
from util.secrets import secret
from model.event import Event, AttendeeNotEligible
from model.local_attendee_overrides import LocalAttendeeOverrides
from server.socketserver import SocketServer
from model.notification_manager import NotificationManager

class HTTPError(Exception):
  def __init__(self, status, message=None, data=None):
    self.status = status
    self.message = message
    self.data = data
    super().__init__(self.message)

class WebService:
  def __init__(self, badgefile, listen_interface='127.0.0.1', port=8080):
    self.badgefile = badgefile
    self.listen_interface = listen_interface
    self.port = port
    template_dir = os.path.abspath('src/static/html_templates')
    self.app = Flask(__name__, template_folder=template_dir)
    # Disable Flask's default logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    self.sock = Sock(self.app)
    self.websocket_clients = set()
    self._setup_routes()
    self.recent_scans = {}

    def received_notification(key, notification):
      if key != "event":
        return
      
      event = notification.get("event")
      attendee = notification.get("attendee")
      data = notification.get("data", {})

      num_scanned = event.num_scanned_attendees()
      num_eligible_attendees = event.num_eligible_attendees()

      response_data = {
        "attendee": attendee.web_info(),
        "event": {
          "name": event.name,
          "is_reset": data.get("is_reset"),
          "num_scans_for_attendee": data.get('num_times_attendee_scanned'),
          "total_attendees_scanned": num_scanned,
          "total_scannable": num_eligible_attendees,
        }
      }

      websocket_message = {
        "type": "scan", 
        "data": response_data,
      }

      self.broadcast_to_websockets(websocket_message)

      if not event.name in self.recent_scans:
        self.recent_scans[event.name] = []
      self.recent_scans[event.name].append(websocket_message)
      while len(self.recent_scans[event.name]) > 20:
        self.recent_scans[event.name] = self.recent_scans[event.name][1:]
    
    NotificationManager.shared().observe(received_notification)

  def ip():    
    client_ip = request.remote_addr
    
    # Check if client_ip is RFC 1918 (private) or localhost
    is_private = (
      client_ip.startswith('10.') or
      client_ip.startswith('172.16.') or
      client_ip.startswith('172.17.') or
      client_ip.startswith('172.18.') or
      client_ip.startswith('172.19.') or
      client_ip.startswith('172.2') or
      client_ip.startswith('172.30.') or
      client_ip.startswith('172.31.') or
      client_ip.startswith('192.168.') or
      client_ip.startswith('127.')
    )
    
    # Check if X-Real-Ip header exists and is valid-ish
    x_real_ip = request.headers.get('X-Real-Ip')
    if is_private and x_real_ip:
      return x_real_ip
    else:
      return client_ip

  def logmsg(self, msg):
    client_ip = WebService.ip()
    method = request.method
    endpoint = request.path
    return f"{client_ip} {method} {endpoint}: {msg}"
  
  def require_authentication(self):
    # Check for HTTP Basic Authentication
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Basic '):
      # Extract and decode credentials
      encoded_credentials = auth_header[6:]  # Remove 'Basic ' prefix
      try:
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        username, password = decoded_credentials.split(':', 1)
        credentials_valid = False # TODO: implement a user list
        if credentials_valid:
          log.debug(self.logmsg("Authenticated"))
          return  # Authentication successful
        else:
          log.info(self.logmsg(f"Invalid credentials for user '{username}'"))
      except Exception:
        log.info(self.logmsg("Invalid credentials"))
        pass  # Continue to authentication failure
    
    # Check for HTTP Bearer Authentication
    elif auth_header and auth_header.startswith('Bearer '):
      token = auth_header[7:]  # Remove 'Bearer ' prefix
      if token == secret("web_apikey"):
        log.debug(self.logmsg("Authenticated"))
        return  # Authentication successful
      else:
        token_preview = f"'{token[0:8]}'..." if len(token) > 8 else f"'{token}'"
        log.info(self.logmsg(f"Invalid bearer token {token_preview}"))
    else:
      log.debug(self.logmsg("No credentials"))
    
    # Authentication failed or no authentication provided
    self.fail_request(401, "Authentication required")
  
  def parse_request(self):
    try:
      # Try to parse JSON regardless of Content-Type header
      data = request.get_json(force=True, silent=True)
      
      # If parsing failed or didn't return a dict, try to read the raw data
      if data is None:
        data = json.loads(request.data.decode('utf-8')) if request.data else {}
      
      if not isinstance(data, dict):
        self.fail_request(400, "Request body must be a JSON object")
    except json.JSONDecodeError:
      self.fail_request(400, "Invalid JSON in request body")
    
    return data
  
  def fail_request(self, status, message=None, data=None):
    response = jsonify({
      "status": status,
      "error": {
        "message": message,
        "data": data,
      }
    })

    response.status_code = status
    raise HTTPError(status, message, data)

  def respond(self, response_obj, status=200):
    wrapped_response = jsonify({
      "status": status,
      "response": response_obj,
    })

    wrapped_response.status_code = status
    wrapped_response.mimetype = 'application/json'
    abort(wrapped_response)
  
  def handler_crashed(self, exc):
    log.error(self.logmsg(f"Handler crashed: {str(exc)}"), exception=exc)
    response = jsonify({
      "status": 500,
      "error": {
        "message": "Internal error"
      }
    })
    response.status_code = 500
    return response

  def broadcast_to_websockets(self, message):
    closed_sockets = set()
    log.debug(f"Broadcasting message of type {message.get('type')} to {len(self.websocket_clients)} websocket clients")
    for ws in self.websocket_clients:
      try:
        ws.send(json.dumps(message))
      except Exception as exc:
        log.warn(f"Failed to send to websocket", exception=exc)
        closed_sockets.add(ws)
    
    # Remove closed websockets
    self.websocket_clients -= closed_sockets

  def _setup_routes(self):
    # Add a decorator to measure request processing time and log metrics
    @self.app.after_request
    def log_request_info(response):
      # Calculate request processing time (need to store start time in g)
      from flask import g
      import time
      from datetime import datetime
      
      # Get request processing time if available
      if hasattr(g, 'start_time'):
        process_time = (time.time() - g.start_time) * 1000  # Convert to ms
      else:
        process_time = 0
        
      # Get request and response sizes
      request_size = request.content_length or 0
      response_size = response.calculate_content_length() or 0
      
      # Log the request metrics
      log.debug(f"webreq {WebService.ip()} \"{request.method} {request.path}\" {response.status_code} {process_time:.1f}ms {request_size} {response_size}")
      
      return response
      
    @self.app.before_request
    def record_request_start_time():
      from flask import g
      import time
      g.start_time = time.time()
    
    @self.app.errorhandler(Exception)
    def handle_exception(exc):
      if isinstance(exc, HTTPError):
        # This is an intentional abort with a specific status code
        response = jsonify({
          "status": exc.status,
          "error": {
            "message": exc.message,
            "data": exc.data,
          }
        })
        response.status_code = exc.status
        return response
      elif isinstance(exc, NotFound):
        # Handle 404 Not Found errors
        response = jsonify({
          "status": 404,
          "error": {
            "message": str(exc) or "Resource not found",
            "data": None,
          }
        })
        response.status_code = 404
        return response
      else:
        # This is an unexpected exception
        return self.handler_crashed(exc)
    
    @self.app.route('/')
    def home():
      return redirect('https://www.gocongress.org/')
    
    @self.app.route('/version')
    def version():
      return jsonify({'version': Version().hash()})
    
    @self.app.route('/reprint', methods=['GET'])
    def reprint_get():
      # Force template reload by clearing the template cache
      self.app.jinja_env.cache.clear()
      return render_template('checkin_page.html')
    
    @self.app.route('/scanner/<event_name>', methods=['GET'])
    def scanner_get(event_name):
      # Force template reload by clearing the template cache
      self.app.jinja_env.cache.clear()
      return render_template('event-scanner.html',
                             event_name=event_name)
    
    @self.app.route('/attendees/<hashid>/confirm_housing', methods=['GET'])
    def confirm_housing_get(hashid):
      self.badgefile.attendees(force_refresh=True)
      if hashid == "None":
        return render_template('confirm_housing_bug_apology.html', 
                            attendee=None,
                            message="Please pardon our mess!")
    
      attendee = self.badgefile.lookup_attendee_by_hash_id(hashid)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      if not attendee.is_primary():
        self.fail_request(400, "Only primary registrants can confirm housing")
      
      if attendee.party_housing():
        return render_template('confirm_housing_already_have.html', 
                              attendee=attendee.info(),
                              message="You have already reserved housing. Thank you for registering for the 2025 US Go Congress.")
      
      return render_template('confirm_housing.html', 
                            attendee=attendee.info(),
                            will_arrange_own_housing=attendee.will_arrange_own_housing())
    
    @self.app.route('/attendees/<hashid>/confirm_housing', methods=['POST'])
    def confirm_housing_post(hashid):
      self.badgefile.attendees(force_refresh=True)
      attendee = self.badgefile.lookup_attendee_by_hash_id(hashid)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      if not attendee.is_primary():
        self.fail_request(400, "Only primary registrants can confirm housing")
      
      will_arrange_own_housing = request.form.get('will_arrange_own_housing')
      if will_arrange_own_housing not in ['true', 'false']:
        self.fail_request(400, "Invalid housing preference")
      
      attendee.set_will_arrange_own_housing(will_arrange_own_housing == 'true')
      return render_template('confirm_housing_thank_you.html', 
                            attendee=attendee.info(),
                            message="Thank you for responding to our housing survey.")
    
    @self.sock.route('/ws')
    def monitor(ws):
      # self.require_authentication()
      self.websocket_clients.add(ws)
      log.info(self.logmsg(f"WebSocket client connected, total clients: {len(self.websocket_clients)}"))
      try:
        # Keep the connection alive until client disconnects
        while True:
          # This will block until a message is received or the connection is closed
          message = ws.receive()
          # We're not expecting any messages from the client, but we could process them here
      except Exception as exc:
        log.info(self.logmsg(f"WebSocket disconnected"), exception=exc)
      finally:
        self.websocket_clients.discard(ws)
        log.info(self.logmsg(f"WebSocket client disconnected, remaining clients: {len(self.websocket_clients)}"))

    @self.app.route('/events/<event_name>/scans', methods=['POST'])
    def event_scans_post(event_name):
      # self.require_authentication()

      if not Event.exists(event_name):
        log.debug(f"request for non-existent event: {event_name}")
        self.fail_request(404, "Event not found")
      
      request = self.parse_request()

      if 'badgefile_id' in request:
        attendee = self.badgefile.lookup_attendee(int(request['badgefile_id']))
      elif 'hash_id' in request:
        attendee = self.badgefile.lookup_attendee_by_hash_id(request['hash_id'])
      else:
        self.fail_request(400, "Missing badgefile_id or hash_id in request")

      is_reset = request.get('reset', False) == True
      
      if attendee is None:
        log.debug(f"scan request for non-existent user: request {request}")
        self.fail_request(404, "Attendee not found")
      
      event = Event(event_name)
      try:
        num_scans = event.scan_in_attendee(attendee, is_reset=is_reset)
      except AttendeeNotEligible:
        self.fail_request(400, "Attendee not eligible", {"attendee": attendee.web_info()})
      
      total_scans_for_event = event.num_scanned_attendees()
      total_eligible = event.num_eligible_attendees()

      response_data = {
        "attendee": attendee.web_info(),
        "event": {
          "name": event_name,
          "is_reset": is_reset,
          "num_scans_for_attendee": num_scans,
          "total_attendees_scanned": total_scans_for_event,
          "total_scannable": total_eligible,
        }
      }

      # Broadcast scan event to all connected websocket clients
      websocket_message = {
        "type": "scan", 
        "data": response_data,
      }
      self.broadcast_to_websockets(websocket_message)
      SocketServer.shared().broadcast(websocket_message)

      self.respond(response_data)

    @self.app.route('/events/<event_name>/scans', methods=['GET'])
    def event_scans_get(event_name):
      self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")
      
      event = Event(event_name)

      self.respond({
        "event": {
          "name": event_name,
          "scans": event.scan_counts(),
        }
      })

    @self.app.route('/events/<event_name>/scans/recent', methods=['GET'])
    def event_scans_recent_get(event_name):
      # self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")
      
      event = Event(event_name)
      self.respond(self.recent_scans.get(event_name, []))
    
    @self.app.route('/events/<event_name>/status', methods=['GET'])
    def event_status_get(event_name):
      # self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")
      
      event = Event(event_name)
      total_scans_for_event = event.num_scanned_attendees()
      total_eligible = event.num_eligible_attendees()

      self.respond({
        "event": {
          "name": event_name,
          "total_attendees_scanned": total_scans_for_event,
          "total_scannable": total_eligible,
        }
      })
    
    @self.app.route('/events/<event_name>/count', methods=['GET'])
    def event_count_get(event_name):
      # self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")

      def make_response():
        event = Event(event_name)
        total_scans_for_event = event.num_scanned_attendees()
        total_eligible = event.num_eligible_attendees()

        event_data = {
          "name": event_name,
          "total_attendees_scanned": total_scans_for_event,
          "total_scannable": total_eligible,
        }

        # Serialize event_data to JSON
        event_data_json = json.dumps(event_data, sort_keys=True)
        event_data_hash = hashlib.sha256(event_data_json.encode()).hexdigest()
        return {
          "event": event_data,
          "hash": event_data_hash,
        }

      # Get the hash query parameter if provided, otherwise set to None
      last_hash = request.args.get('hash', None)

      while True:
        # if 'hash' was provided, then don't return a response until we have an updated object
        rr = make_response()
        if rr["hash"] != last_hash:
          self.respond(rr)
          break # shouldn't be needed, but let's be safe
        
        # Sleep for 100ms before checking again
        time.sleep(0.1)

    @self.app.route('/attendees', methods=['GET'])
    def attendees_get():
      # self.require_authentication()
      
      # Get all attendees from the badgefile
      attendees = self.badgefile.attendees()
      
      # Convert attendee objects to web-friendly format
      attendees_data = []
      for attendee in attendees:
        attendee_info = attendee.web_info()
        attendees_data.append(attendee_info)
      
      # Sort attendees by family name, then given name
      attendees_data.sort(key=lambda x: (x.get('name_family', ''), x.get('name_given', '')))
      
      self.respond(attendees_data)

    @self.app.route('/attendees', methods=['POST'])
    def attendees_post():
      # self.require_authentication()
      
      try:
        data = self.parse_request()
        
        # Validate required fields
        required_fields = ['name_given', 'name_family', 'badge_type']
        for field in required_fields:
          if not data.get(field):
            self.fail_request(400, f"Missing required field: {field}")
        
        # Create manual attendee info
        manual_info = {
          'name_given': data.get('name_given', ''),
          'name_family': data.get('name_family', ''),
          'name_mi': data.get('name_mi', ''),
          'name_nickname': data.get('name_nickname', ''),
          'email': data.get('email', ''),
          'phone_a': data.get('phone', ''),
          'addr1': data.get('addr1', ''),
          'addr2': data.get('addr2', ''),
          'city': data.get('city', ''),
          'state': data.get('state', ''),
          'postcode': data.get('postcode', ''),
          'country': data.get('country', ''),
          'company': data.get('company', ''),
          'phone_cell': data.get('phone', ''),
          'job_title': data.get('title', ''),
          'is_primary': 'Yes',
          'is_member': 'Yes',
          'aga_id': None,
          'regtype': 'manual',
          'primary_registrant_name': f"{data.get('name_given')} {data.get('name_family')}".strip(),
          'seqno': '',
          'signed_datetime': time.strftime("%m/%d/%Y %H:%M:%S"),
          'state_comments': '',
          'country_comments': '',
          'date_of_birth': '',
          'date_of_birth_comments': '',
          'tshirt': '',
          'tshirt_comments': '',
          'rank_playing': data.get('badge_rating', ''),
          'rank_comments': '',
          'tournaments': ','.join(data.get('tournaments', [])),
          'tournaments_comments': '',
          'phone_mobile': data.get('phone', ''),
          'phone_mobile_comments': '',
          'emergency_contact_name': '',
          'emergency_contact_comments': '',
          'emergency_contact_phone': '',
          'emergency_contact_phone_comments': '',
          'emergency_contact_email': '',
          'emergency_contact_email_comments': '',
          'emergency_contact_': '',
          'youth_adult_at_congress': '',
          'youth_adult_type': '',
          'youth_adult_type_comments': '',
          'languages': ','.join(data.get('languages', [])),
          'languages_comments': '',
          'translator': '',
          'translator_comments': '',
          'admin1': '',
          'admin1_comments': '',
          'title': data.get('title', ''),
          'badge_type': data.get('badge_type', 'player'),
          'is_attending_banquet': data.get('is_attending_banquet', False),
          'is_checked_in': data.get('is_checked_in', False),
          'aga_chapter': data.get('aga_chapter', ''),
        }
        
        # Create the manual attendee
        attendee = self.badgefile.issue_manual_attendee(manual_info)
        LocalAttendeeOverrides.shared().set_override(attendee, data)
        Event("congress").mark_attendee_eligible(attendee, is_eligible=True)
        if(data.get('is_checked_in', False)):
          Event("congress").scan_in_attendee(attendee, is_reset=False)
        
        # Update the badgefile to include the new attendee
        # self.badgefile.update_attendees()
        
        # Return the created attendee info
        return jsonify({
          'status': 200,
          'response': attendee.web_info()
        })
        
      except HTTPError:
        raise
      except Exception as exc:
        log.error(f"Error creating manual attendee: {str(exc)}", exception=exc)
        self.fail_request(500, "Internal error creating manual attendee")

    @self.app.route('/attendees/<badgefile_id>', methods=['POST'])
    def attendee_override_post(badgefile_id):
      # self.require_authentication()
      
      data = self.parse_request()

      try:
        badgefile_id = int(badgefile_id)
      except ValueError:
        self.fail_request(400, "Invalid badgefile_id - must be an integer")
      
      attendee = self.badgefile.lookup_attendee(badgefile_id)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      if 'is_checked_in' in data:
        event = Event("congress")
        checked_in = data['is_checked_in']
        del data['is_checked_in']

        was_checked_in = event.num_times_attendee_scanned(attendee) != 0
        if was_checked_in != checked_in:
          event.scan_in_attendee(attendee, is_reset=not checked_in)
      
      override_result = LocalAttendeeOverrides.shared().set_override(attendee, data)
      log.debug(f"Attendee {attendee.full_name()} {attendee.id()} override result: {override_result}")
      attendee.badge().generate()
      attendee.checksheet().generate()

      attendee_info = attendee.web_info()

      websocket_message = {
        "type": "attendee_update", 
        "data": attendee_info,
      }

      self.broadcast_to_websockets(websocket_message)
      NotificationManager.shared().notify("attendee_update", {"attendee": attendee})

      self.respond(override_result)

    @self.app.route('/attendees/<badgefile_id>/badge', methods=['GET'])
    def attendee_badge_get(badgefile_id):
      # self.require_authentication()
      
      try:
        badgefile_id = int(badgefile_id)
      except ValueError:
        self.fail_request(400, "Invalid badgefile_id - must be an integer")
      
      attendee = self.badgefile.lookup_attendee(badgefile_id)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      badge = attendee.badge()
      if not badge.already_exists():
        badge.generate()
      
      return send_file(os.path.abspath(badge.path()), mimetype='application/pdf')

    @self.app.route('/attendees/<badgefile_id>/checksheet', methods=['GET'])
    def attendee_checksheet_get(badgefile_id):
      # self.require_authentication()
      
      try:
        badgefile_id = int(badgefile_id)
      except ValueError:
        self.fail_request(400, "Invalid badgefile_id - must be an integer")
      
      attendee = self.badgefile.lookup_attendee(badgefile_id)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      checksheet = attendee.checksheet()
      if not checksheet.already_exists():
        checksheet.generate()
      
      return send_file(os.path.abspath(checksheet.path()), mimetype='application/pdf')
    
    @self.app.route('/media/<filename>', methods=['GET'])
    def send_media(filename):
      path = os.path.abspath("src/static/media/" + filename)
      if not os.path.exists(path):
        abort(404, description="Media file not found")

      ext = os.path.splitext(filename)[1].lower()
      if ext == ".png":
        mimetype = "image/png"
      elif ext in [".jpg", ".jpeg"]:
        mimetype = "image/jpeg"
      elif ext == ".gif":
        mimetype = "image/gif"
      elif ext == ".wav":
        mimetype = "audio/wav"
      elif ext == ".mp3":
        mimetype = "audio/mpeg"
      elif ext == ".pdf":
        mimetype = "application/pdf"
      else:
        # Default to octet-stream for unknown types
        mimetype = "application/octet-stream"

      return send_file(path, mimetype=mimetype)

  def run(self):
    self.app.run(host=self.listen_interface, port=self.port)
