{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python311; # You can change this to the desired Python version, e.g., python310 for Python 3.10
in
pkgs.mkShell {
  name = "python-env";

  buildInputs = [
    pkgs.sqlite
    python
    python.pkgs.pip
    python.pkgs.setuptools
    python.pkgs.wheel
    python.pkgs.virtualenv
    python.pkgs.reportlab
    python.pkgs.pillow
    python.pkgs.inotify-simple
    python.pkgs.pycups
    python.pkgs.pypdf2
    python.pkgs.requests
    python.pkgs.beautifulsoup4
    python.pkgs.flask
    python.pkgs.flask-sock
    python.pkgs.pytz
    python.pkgs.google-auth-oauthlib
    python.pkgs.google-auth
    python.pkgs.google-auth-httplib2
    python.pkgs.google-api-python-client
    python.pkgs.python-dateutil
    python.pkgs.pyyaml
    python.pkgs.boto3
    python.pkgs.pylibdmtx
  ];

  shellHook = ''
    # Optionally, you can set up a virtual environment here
    # virtualenv venv
    # source venv/bin/activate
    echo "Ready to run!"
  '';
}
