#!/bin/bash

# AI Secretary Runner Script
# This script runs the AI Secretary application with proper error handling

# Set up colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}       AI Secretary Runner Script        ${NC}"
echo -e "${BLUE}=========================================${NC}"

# Check for required environment variables
echo -e "${YELLOW}Checking environment variables...${NC}"
missing_vars=0

if [ -z "$SLACK_BOT_TOKEN" ]; then
  echo -e "${RED}ERROR: SLACK_BOT_TOKEN is not set${NC}"
  missing_vars=1
fi

if [ -z "$SLACK_APP_TOKEN" ]; then
  echo -e "${RED}ERROR: SLACK_APP_TOKEN is not set${NC}"
  missing_vars=1
fi

if [ -z "$OPENAI_API_KEY" ]; then
  echo -e "${RED}ERROR: OPENAI_API_KEY is not set${NC}"
  missing_vars=1
fi

if [ -z "$GOOGLE_CREDENTIALS_PATH" ]; then
  echo -e "${RED}ERROR: GOOGLE_CREDENTIALS_PATH is not set${NC}"
  missing_vars=1
else
  if [ ! -f "$GOOGLE_CREDENTIALS_PATH" ]; then
    echo -e "${RED}ERROR: Google credentials file not found at $GOOGLE_CREDENTIALS_PATH${NC}"
    missing_vars=1
  fi
fi

if [ $missing_vars -eq 1 ]; then
  echo -e "${RED}Missing required environment variables. Please set them before running the script.${NC}"
  exit 1
fi

# Create log directory
mkdir -p logs

# Run the application
echo -e "${GREEN}Starting AI Secretary...${NC}"
echo -e "${YELLOW}Logs will be saved to logs/ai_secretary_$(date +%Y%m%d_%H%M%S).log${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the application${NC}"

# Run with proper logging
python -u src/main.py 2>&1 | tee logs/ai_secretary_$(date +%Y%m%d_%H%M%S).log

# Check exit code
if [ $? -ne 0 ]; then
  echo -e "${RED}AI Secretary exited with an error. Check the logs for details.${NC}"
  exit 1
else
  echo -e "${GREEN}AI Secretary exited successfully.${NC}"
  exit 0
fi 