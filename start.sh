#!/bin/bash
echo "Starting PhoneInsight API Server..."
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
