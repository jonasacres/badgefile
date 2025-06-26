#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from integrations.leago import Leago

def debug_current_token():
    """Debug the current token"""
    
    # Initialize Leago (you'll need to set the correct URLs and event key)
    leago = Leago(
        url="https://leago.gg",  # Replace with actual URL
        id_url="https://id.leago.gg",  # Replace with actual ID URL
        event_key="your-event-key"  # Replace with actual event key
    )
    
    # Debug the token
    leago.debug_token()

if __name__ == "__main__":
    debug_current_token() 