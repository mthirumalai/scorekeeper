#!/usr/bin/env python3
"""
One-time OAuth setup. Run this once to create token.json.
Requires credentials.json in the project root (downloaded from Google Cloud Console).
"""
import os
import sys

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(__file__))

from scorekeeper.sheets_writer import get_service

if __name__ == '__main__':
    print("Opening browser for Google OAuth flow...")
    service = get_service()
    print("Authentication successful! token.json has been created.")
    print("You can now run: python -m scorekeeper.main")
