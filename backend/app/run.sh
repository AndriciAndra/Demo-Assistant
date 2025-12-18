#!/bin/bash

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run FastAPI server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
