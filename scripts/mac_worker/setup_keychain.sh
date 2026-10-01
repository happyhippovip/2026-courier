#!/bin/bash

echo "Configuring Courier Mac Worker securely in macOS Keychain."

read -p "Enter Courier Server URL (e.g., http://127.0.0.1:8080): " server_url
read -rsp "Enter Courier API Key (input hidden): " api_key; echo

# Delete existing if any to avoid prompt issues
security delete-generic-password -a "courier_worker" -s "courier_server_url" 2>/dev/null
security delete-generic-password -a "courier_worker" -s "courier_api_key" 2>/dev/null

security add-generic-password -a "courier_worker" -s "courier_server_url" -w "$server_url" -U
security add-generic-password -a "courier_worker" -s "courier_api_key" -w "$api_key" -U

echo "Stored securely in Keychain."
