#!/usr/bin/env python3
"""
Add API key directly to Supabase database
"""

import os
import secrets
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env.supabase")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Missing Supabase credentials")
    sys.exit(1)

# Create Supabase client
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Generate a unique API key on each run.
api_key = f"mtv_{secrets.token_hex(5)}_{secrets.token_urlsafe(32)}"
key_prefix = api_key[:10] + "..."

try:
    # Insert API key (matching actual table structure)
    result = (
        client.table("api_keys")
        .insert(
            {
                "key": api_key,
                "user_email": "user@metivta.com",
                "user_name": "Production User",
                "is_active": True,
            }
        )
        .execute()
    )

    print("✅ API key added successfully!")
    print(f"Key: {api_key}")

except Exception as e:
    if "duplicate" in str(e).lower():
        print("⚠️ API key already exists")
    else:
        print(f"❌ Error: {e}")
