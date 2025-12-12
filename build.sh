#!/usr/bin/env bash
# Build script for Render deployment
set -o errexit

echo "Python version:"
python --version

echo "Pip version:"
pip --version

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Verifying gunicorn installation..."
python -m pip show gunicorn || python -m pip install gunicorn
which gunicorn || echo "Gunicorn not in PATH, but should be installed"

echo "Checking database configuration..."
python manage.py check --database default

echo "Running database migrations..."
python manage.py migrate --noinput || {
    echo "WARNING: Migrations failed, but continuing build..."
    echo "This might be normal if the database is not yet configured."
}

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build complete!"
