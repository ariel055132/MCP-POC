# Redmine MCP Server

A Model Context Protocol (MCP) server for interacting with Redmine.

## Setup

1. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
2. **Edit `.env` file with your Redmine credentials:**
   ```env
   REDMINE_URL=https://your-redmine-instance.com
   REDMINE_API_KEY=your_api_key_here
   ```

## Running Locally

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server:**
   ```bash
   python redmine.py
   ```

## Running with Docker

1. **Build the Docker image:**
   ```bash
   docker build -t redmine-mcp .
   ```

2. **Run the container:**
   ```bash
   docker run -it redmine-mcp
   ```

## Available Tools

- `get_issues` - Fetch issues from Redmine
- `get_issue_details` - Get details of a specific issue
- `get_projects` - List all accessible projects
- `download_issue_attachments` - Download attachments from an issue

## Security

- The `.env` file is excluded from version control
- Never commit sensitive credentials to the repository
- Use `.env.example` as a template for required configuration
