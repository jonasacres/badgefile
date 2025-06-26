#!/usr/bin/env python3

import sys
import pathlib
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))


from integrations.leago import Leago
from log.logger import log
from util.secrets import secret

def test_leago_refresh():
    """Test the Leago token refresh functionality"""
    
    # Initialize Leago with your configuration
    # You'll need to set these values based on your environment
    leago = Leago(
        url="https://leago.gg",  # Replace with actual URL
        id_url="https://id.leago.gg",  # Replace with actual ID URL
        event_key = secret("leago_event_key")  # Replace with actual event key
    )
    
    # Try to get an access token
    token = leago.get_access_token()
    
    if token:
        print(f"✅ Successfully got access token: {token[:50]}...")
        
        # Test the refresh mechanism
        print("🔄 Testing token refresh...")
        refreshed_data = leago._refresh_token()
        
        if refreshed_data:
            print("✅ Token refresh successful!")
            new_token = refreshed_data['token']['access_token']
            print(f"New token: {new_token[:50]}...")
        else:
            print("❌ Token refresh failed")
    else:
        print("❌ No access token available. You may need to authenticate first.")
        print("Run leago.authenticate() to start the authentication flow.")

if __name__ == "__main__":
    test_leago_refresh() 