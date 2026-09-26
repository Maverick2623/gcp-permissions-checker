#!/usr/bin/env python3

import os
import sys
import argparse
from google.oauth2 import service_account, credentials
from googleapiclient import discovery
from tqdm import tqdm


def get_caller_identity(credentials, project_id):
    try:
        service = discovery.build(
            'cloudresourcemanager',
            'v3',
            credentials=credentials
        )

        resource = project_id

        if not resource.startswith('projects/'):
            resource = f'projects/{resource}'

        permissions_test = service.projects().testIamPermissions(
            resource=resource,
            body={
                "permissions": [
                    "resourcemanager.projects.get"
                ]
            }
        ).execute()

        print("Authenticated successfully.")
        print(
            "Accessible permissions:",
            permissions_test.get("permissions", [])
        )

    except Exception as e:
        print(f"Failed to verify caller identity: {e}")
        exit(1)


def test_permissions(service, project_id, permissions_list):
    try:
        resource = project_id

        if not resource.startswith('projects/'):
            resource = f'projects/{resource}'

        request = service.projects().testIamPermissions(
            resource=resource,
            body={
                "permissions": permissions_list
            }
        )

        returned_permissions = request.execute()

        return returned_permissions.get(
            'permissions',
            []
        )

    except Exception:
        return []


def read_permissions(file_path):
    with open(file_path, "r") as file:
        return [
            line.strip()
            for line in file
            if line.strip()
        ]


def batch_permissions(permissions_list, batch_size=100):
    for i in range(
        0,
        len(permissions_list),
        batch_size
    ):
        yield permissions_list[
            i:i + batch_size
        ]


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="GCP Permissions Checker"
    )

    parser.add_argument(
        "key_path",
        nargs='?',
        default=None,
        help="Path to service account key file (ignored if -Token is used)"
    )

    parser.add_argument(
        "-Token",
        dest="access_token",
        help="Access token for authentication"
    )

    parser.add_argument(
        "-ProjectID",
        dest="project_id",
        help="Project ID (required when using -Token)"
    )

    args = parser.parse_args()


    # --------------------------------------------------
    # Authentication - UNCHANGED
    # --------------------------------------------------

    if args.access_token:

        if not args.project_id:
            print(
                "Error: -ProjectID is required when using -Token"
            )
            exit(1)

        credentials = credentials.Credentials(
            token=args.access_token
        )

        project_id = args.project_id

        print(
            "Using provided access token for authentication."
        )

        identity = "Unknown (Token/User)"

    elif args.key_path:

        try:

            print(
                f"[*] Loading credentials from "
                f"{args.key_path}"
            )

            credentials = (
                service_account
                .Credentials
                .from_service_account_file(
                    filename=args.key_path,
                    scopes=[
                        "https://www.googleapis.com/auth/cloud-platform"
                    ],
                )
            )

            project_id = credentials.project_id

            identity = credentials.service_account_email

        except Exception as e:

            print(
                f"Failed to load service account "
                f"credentials: {e}"
            )

            exit(1)

    else:

        print(
            "Usage: ./gcp_perm_checker.py "
            "path/to/key.json "
            "or ./gcp_perm_checker.py "
            "-Token ACCESS_TOKEN "
            "-ProjectID PROJECT_ID"
        )

        exit(1)


    # --------------------------------------------------
    # Configuration
    # --------------------------------------------------

    print("[*] --- Configuration ---")
    print(f"[*] Target Project : {project_id}")
    print(f"[*] Identity       : {identity}")
    print("[*] ---------------------")


    # --------------------------------------------------
    # Authentication verification
    # --------------------------------------------------

    get_caller_identity(
        credentials,
        project_id
    )


    try:

        consolidated_file = "permissions.txt"

        permissions_list = read_permissions(
            consolidated_file
        )

        print(
            f"[*] Loaded {len(permissions_list)} "
            f"permissions from {consolidated_file}"
        )

        print("[*] Starting permission check...")

        print(
            f"[*] Checking permissions against project: "
            f"{project_id}"
        )


        # --------------------------------------------------
        # Build API client ONCE
        # --------------------------------------------------

        service = discovery.build(
            "cloudresourcemanager",
            "v3",
            credentials=credentials
        )


        # --------------------------------------------------
        # Use batches of 100
        # --------------------------------------------------

        batch_size = 100

        total_batches = (
            len(permissions_list)
            // batch_size
            + (
                1
                if len(permissions_list) % batch_size
                else 0
            )
        )


        progress_bar_format = (
            "{desc}: {percentage:3.0f}%|{bar}| "
            "Elapsed Time: {elapsed}"
        )


        # Counter for valid permissions
        valid_permissions_count = 0


        for permissions_batch in tqdm(
            batch_permissions(
                permissions_list,
                batch_size
            ),
            total=total_batches,
            desc="Scanning",
            bar_format=progress_bar_format,
            ncols=80
        ):

            found_permissions = test_permissions(
                service,
                project_id,
                permissions_batch
            )


            # --------------------------------------------------
            # Print allowed permissions in green
            # --------------------------------------------------

            if found_permissions:

                valid_permissions_count += len(
                    found_permissions
                )

                for permission in found_permissions:

                    tqdm.write(
                        f"\033[92m[+] "
                        f"{permission}"
                        f"\033[0m"
                    )


        # --------------------------------------------------
        # Completion message
        # --------------------------------------------------

        print(
            f"[*] Check complete. Found "
            f"{valid_permissions_count} valid permissions."
        )


    except KeyboardInterrupt:

        print(
            "\nOperation cancelled by user. "
            "Exiting gracefully."
        )

        exit(0)
