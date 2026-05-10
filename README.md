# MCP-POC

Model Context Protocol (MCP) proof-of-concept workspace for multiple services:

- Weather MCP
- Redmine MCP
- Kibana MCP

## Project Structure

- weather/: Weather MCP server
- redmine/: Redmine MCP server
- kibana/: Kibana MCP server
- .vscode/mcp.json: Local MCP server definitions for VS Code

## Setup (Weather Example)

Weather MCP does not require an API key or .env file.

1. Install dependencies:

```bash
cd weather
pip install -r requirements.txt
```

2. Run locally:

```bash
python weather.py
```

3. Build with Podman:

```bash
podman build -t weather-mcp .
```

4. Run container:

```bash
podman run --rm -i localhost/weather-mcp:latest
```

## Setup Notes for Other Projects

### Redmine MCP

- Requires redmine/.env with REDMINE_URL and REDMINE_API_KEY.
- Template: redmine/.env.example

### Kibana MCP

- Requires kibana/.env with KIBANA_URL and KIBANA_API_KEY.
- Template: kibana/.env.example

## Connect in VS Code

* This workspace already includes MCP server entries in .vscode/mcp.json.

* After editing MCP config or rebuilding images, restart MCP servers in VS Code so new settings are applied.

## Connect in Claude Code
* Download Claude for Desktop
* Edit Claude for Desktop App configuration at Claude/claude_desktop_config.json

## Available Tools

### Weather MCP

- get_alerts: Get weather alerts for a US state.
- get_forecast: Get weather forecast by latitude and longitude.

### Redmine MCP

- get_issues: Fetch issues from Redmine.
- get_issue_details: Get details of a specific issue.
- get_projects: List all accessible projects.
- download_issue_attachments: Download attachments from an issue.

### Kibana MCP

- fetch_kibana_status: Check Kibana API health/connectivity.
- list_data_views: List available data views.
- get_data_view: Get details for a data view.
- search_kibana_logs: Search logs via Kibana.
- search_logs_by_data_view: Search logs using a data view ID.
- fetch_kibana_logs: Generate a Kibana Discover URL for logs.
- generate_kibana_discover_url: Generate Discover URL with custom parameters.

## Security

- Never commit API keys or secrets.
- Keep runtime secrets in redmine/.env and kibana/.env.
- Use .env.example files as templates.
