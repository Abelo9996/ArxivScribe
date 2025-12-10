#!/bin/bash
# Quick start script for ArxivScribe

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if required environment variables are set
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "❌ Error: DISCORD_BOT_TOKEN not set in .env file"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ] && [ -z "$HUGGINGFACE_API_KEY" ]; then
    echo "❌ Error: Neither OPENAI_API_KEY nor HUGGINGFACE_API_KEY is set in .env file"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the bot
echo "🚀 Starting ArxivScribe..."
python main.py
