#!/usr/bin/env bash
set -e

# Change to the project root directory
cd "$(dirname "$0")/.."

echo "🚀 Setting up the OA System..."

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
echo "🗄️ Running database migrations..."
export DJANGO_DEBUG=1
python manage.py migrate

echo "✅ Setup complete!"
echo "🌐 Starting the Django development server on http://localhost:8000..."
python manage.py runserver 0.0.0.0:8000
