#!/usr/bin/env python3
"""
Example script demonstrating OAuth2 authentication with Leago API.

Usage:
    python leago_oauth_example.py          # Authenticate and test API
    python leago_oauth_example.py --logout # Remove stored tokens
"""

import sys
import pathlib
import argparse

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from integrations.leago import Leago
from util.secrets import secret

def main():
    parser = argparse.ArgumentParser(description='Leago OAuth2 Authentication Example')
    parser.add_argument('--logout', action='store_true', help='Remove stored tokens')
    args = parser.parse_args()
    
    # Initialize Leago client
    leago_url = "https://api.leago.gg"  # Replace with actual Leago API URL
    leago_id_url = "https://id.leago.gg"
    event_key = secret('leago_event_key')
    
    leago = Leago(leago_url, leago_id_url, event_key)
    
    if args.logout:
        print("Removing stored tokens...")
        leago.deauthenticate()
        print("Tokens removed successfully!")
        return
    
    # Check if already authenticated
    token = leago.get_access_token()
    if token:
        print("Already authenticated!")
    else:
        print("Starting OAuth2 authentication flow...")
        
        # Get authorization URL
        auth_url = leago.authenticate()
        print(f"\nPlease visit this URL to authenticate:")
        print(f"{auth_url}")
        print("\nAfter authorizing, you'll be redirected to a URL.")
        print("Copy and paste that redirect URL here:")
        
        redirect_url = input("Redirect URL: ").strip()
        
        try:
            # Complete authentication
            token = leago.complete_authentication(redirect_url)
            print("Authentication completed successfully!")
        except Exception as e:
            print(f"Authentication failed: {e}")
            return
    
    # Test API calls
    try:
        print("\nTesting API calls...")
        
        # Get tournaments
        tournaments = leago.get_tournaments()
        print(f"Found {len(tournaments)} tournaments:")
        for name, tournament in tournaments.items():
            print(f"  - {tournament.get('title', 'Unknown')}")
        
        # Get registrations
        registrations = leago.get_registrations()
        print(f"Found {len(registrations)} registrations")
        
        print("\nAPI test completed successfully!")
        
    except Exception as e:
        print(f"API test failed: {e}")

if __name__ == "__main__":
    main() 