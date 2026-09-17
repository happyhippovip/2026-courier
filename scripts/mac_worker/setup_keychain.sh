#!/bin/bash

echo "Configuring Courier Mac Worker securely in macOS Keychain."

read -r -p "Enter Courier Server URL (e.g., http://127.0.0.1:8080): " server_url
read -r -s -p "Enter Courier API Key: " api_key
echo

if [ -z "$server_url" ] || [ -z "$api_key" ]; then
    echo "Server URL and API key are required." >&2
    exit 1
fi

# -U updates an existing item in place or creates it when absent.  Do not
# delete a working credential before its replacement has been stored.
security add-generic-password -a "courier_worker" -s "courier_server_url" -w "$server_url" -U
security add-generic-password -a "courier_worker" -s "courier_api_key" -w "$api_key" -U

unset api_key

echo "Stored securely in Keychain."
