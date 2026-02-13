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

## Running with Docker

1. **Build the Docker image:**
   ```bash
   docker build -t redmine-mcp .
   ```

2. **Run the container:**
   ```bash
   docker run -it redmine-mcp
   ```

## Connecting to VS Code

### Using GitHub Copilot (Recommended)

GitHub Copilot now supports MCP servers! The configuration is already set up in `.vscode/settings.json`:

```json
{
  "github.copilot.chat.mcp.servers": {
    "redmine": {
      "command": "python",
      "args": ["${workspaceFolder}/redmine.py"]
    }
  }
}
```

**How to use:**
1. Open GitHub Copilot Chat (Cmd+Shift+I or click the chat icon)
2. The Redmine MCP server will be automatically available
3. Ask Copilot to use the Redmine tools, for example:
   - "Get all projects from Redmine"
   - "Show me open issues"
   - "Get details of issue #123"

### Using Cline Extension (Alternative)

1. **Install Cline extension:**
   - Open VS Code Extensions (Cmd+Shift+X)
   - Search for "Cline" by saoudrizwan
   - Click Install

2. **Configure MCP Server:**
   - Open Cline settings
   - Go to MCP Servers section
   - Add the following configuration:
   ```json
   {
     "mcpServers": {
       "redmine": {
         "command": "python",
         "args": ["${workspaceFolder}/redmine.py"]
       }
     }
   }
   ```

3. **Or configure globally** (already set up for you):
   Located at: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

### Using Claude Code Extension

1. Install "Claude Code for VS Code" by Anthropic
2. Configure MCP servers in extension settings
3. Point to the local Python script

## Available Tools

- `get_issues` - Fetch issues from Redmine
- `get_issue_details` - Get details of a specific issue
- `get_projects` - List all accessible projects
- `download_issue_attachments` - Download attachments from an issue

## Security

- The `.env` file is excluded from version control
- Never commit sensitive credentials to the repository
- Use `.env.example` as a template for required configuration
