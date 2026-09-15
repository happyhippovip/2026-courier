#!/bin/bash
source deploy/.env
curl -s -H "Authorization: Bearer $COURIER_API_KEY" http://127.0.0.1:8080/status
