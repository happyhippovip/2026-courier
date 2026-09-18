#!/bin/bash
set -e

# Configurable Contact Mechanism
# Allows deployment without baking a placeholder into the final HTML

# If NO email is provided, fail the build to satisfy HUMAN_REQUIRED_CONTACT_DESTINATION.
if [ -z "$COURIER_CONTACT_EMAIL" ]; then
    echo "ERROR: COURIER_CONTACT_EMAIL environment variable is required to build the site."
    echo "Please provide an approved public contact address."
    exit 1
fi

mkdir -p public
echo "Building Courier website..."
sed "s/{{SUPPORT_EMAIL_PLACEHOLDER}}/$COURIER_CONTACT_EMAIL/g" src/index.html > public/index.html
echo "Successfully built website to public/index.html"
