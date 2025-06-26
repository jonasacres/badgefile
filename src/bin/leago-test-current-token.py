#!/usr/bin/env python3

import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from integrations.leago import Leago

def test_current_token():
    """Test the current token and refresh mechanism"""
    
    # First, let's look at the current token structure
    try:
        with open('leago_token.json', 'r') as f:
            token_data = json.load(f)
        print("Current token structure:")
        print(json.dumps(token_data, indent=2))
        
        # Check if we have an id_token
        id_token = token_data.get('id_token')
        if not id_token and 'token' in token_data:
            id_token = token_data['token'].get('id_token')
        
        if id_token:
            print(f"\n✅ Found id_token: {id_token[:50]}...")
        else:
            print("\n❌ No id_token found in current token file")
            return
            
    except FileNotFoundError:
        print("❌ No leago_token.json file found")
        return
    except Exception as e:
        print(f"❌ Error reading token file: {e}")
        return
    
    # Now test the refresh mechanism
    print("\n🔄 Testing refresh mechanism...")
    
    # Initialize Leago (you'll need to set the correct URLs and event key)
    leago = Leago(
        url="https://leago.gg",  # Replace with actual URL
        id_url="https://id.leago.gg",  # Replace with actual ID URL
        event_key="your-event-key"  # Replace with actual event key
    )
    
    # Test the refresh
    try:
        refreshed_data = leago._refresh_token()
        if refreshed_data:
            print("✅ Refresh successful!")
            print(f"New access token: {refreshed_data['token']['access_token'][:50]}...")
            if 'id_token' in refreshed_data:
                print(f"New id_token: {refreshed_data['id_token'][:50]}...")
        else:
            print("❌ Refresh failed")
    except Exception as e:
        print(f"❌ Error during refresh: {e}")

if __name__ == "__main__":
    test_current_token() 