#!/usr/bin/env python3
"""
Script to create a Supabase project via API
Requires SUPABASE_ACCESS_TOKEN environment variable
"""

import os
import secrets
import time
from datetime import UTC, datetime

import requests


def create_supabase_project():
    """Create a new Supabase project via API."""

    # Get access token from environment or prompt
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
    if not access_token:
        print("Please set SUPABASE_ACCESS_TOKEN environment variable")
        print("Get it from: https://app.supabase.com/account/tokens")
        access_token = input("Or paste it here: ").strip()

    if not access_token:
        print("No access token provided")
        return None

    # Project configuration
    project_data = {
        "name": "metivta-eval",
        "organization_id": "odphaoolwbxbtddbtvyu",
        "region": "us-east-1",
        "plan": "free",
        "db_pass": secrets.token_urlsafe(24),
    }

    # Create project
    print(f"Creating project: {project_data['name']}")
    response = requests.post(
        "https://api.supabase.com/v1/projects",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=project_data,
    )

    if response.status_code == 201:
        project = response.json()
        print("✅ Project created successfully!")
        print(f"Project ID: {project['id']}")
        print(f"Project URL: https://app.supabase.com/project/{project['id']}")

        # Wait for project to be ready
        print("\nWaiting for project to initialize...")
        for _i in range(30):  # Wait up to 5 minutes
            time.sleep(10)
            status_response = requests.get(
                f"https://api.supabase.com/v1/projects/{project['id']}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if status_response.status_code == 200:
                status = status_response.json()
                if status.get("status") == "ACTIVE":
                    print("✅ Project is ready!")

                    # Get project details
                    print("\n=== PROJECT DETAILS ===")
                    print(f"Project URL: https://{project['id']}.supabase.co")
                    print(f"Database Host: db.{project['id']}.supabase.co")

                    # Get API keys
                    keys_response = requests.get(
                        f"https://api.supabase.com/v1/projects/{project['id']}/api-keys",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if keys_response.status_code == 200:
                        keys = keys_response.json()
                        anon_key = next((k["api_key"] for k in keys if k["name"] == "anon"), None)
                        service_key = next(
                            (k["api_key"] for k in keys if k["name"] == "service_role"), None
                        )

                        print("\n=== API KEYS ===")
                        print(f"SUPABASE_URL=https://{project['id']}.supabase.co")
                        print(f"SUPABASE_ANON_KEY={anon_key}")
                        print(f"SUPABASE_SERVICE_KEY={service_key}")

                        # Save to .env file
                        with open(".env.supabase", "w") as f:
                            f.write("# Supabase Configuration\n")
                            f.write(f"# Created: {datetime.now(UTC).isoformat()}\n")
                            f.write(f"SUPABASE_URL=https://{project['id']}.supabase.co\n")
                            f.write(f"SUPABASE_ANON_KEY={anon_key}\n")
                            f.write(f"SUPABASE_SERVICE_KEY={service_key}\n")
                            f.write(f"SUPABASE_PROJECT_ID={project['id']}\n")

                        print("\n✅ Credentials saved to .env.supabase")
                        print("Add these to your .env file and Render environment variables")

                    return project
                print(f"Status: {status.get('status', 'UNKNOWN')}")

        print("⚠️ Project creation timed out. Check Supabase dashboard.")
        return project

    print(f"❌ Failed to create project: {response.status_code}")
    print(response.text)
    return None


if __name__ == "__main__":
    create_supabase_project()
