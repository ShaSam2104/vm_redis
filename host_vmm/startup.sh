#!/bin/bash

source venv/bin/activate

ip_address="10.20.24.134"	# dummy address, replace with the command to fetch ip in production

uvicorn gateway:app --reload --host $ip_address --port 8000 && \
uvicorn app:app --reload --port 8080
