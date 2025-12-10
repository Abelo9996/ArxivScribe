#!/bin/bash
# Quick setup script for ArxivScribe

set -e

echo "🚀 ArxivScribe Setup"
echo "===================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $python_version"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
echo "✓ Virtual environment created"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Copy environment file
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys!"
    echo "   - DISCORD_BOT_TOKEN"
    echo "   - OPENAI_API_KEY (or HUGGINGFACE_API_KEY)"
else
    echo "✓ .env file already exists"
fi
echo ""

# Create data directory
mkdir -p data
echo "✓ Data directory created"
echo ""

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys"
echo "2. (Optional) Customize config.yaml"
echo "3. Run: python main.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose up -d"
