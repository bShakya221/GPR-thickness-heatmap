#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Building Frontend..."
cd frontend
npm install
npm run build

echo "Setting up Backend..."
cd ../backend
pip install -r requirements.txt

echo "Build process complete!"
