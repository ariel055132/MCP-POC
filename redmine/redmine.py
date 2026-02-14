from typing import Any
import os

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Redmine Server")
logger = get_logger(__name__)
logger.info("Redmine MCP server initialized.")

# Constants
REDMINE_URL = os.getenv("REDMINE_URL", "")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY", "")


async def make_redmine_request(endpoint: str) -> dict[str, Any] | None:
    """Make a request to the Redmine API with proper error handling."""
    url = f"{REDMINE_URL}/{endpoint}"
    headers = {
        'X-Redmine-API-Key': REDMINE_API_KEY,
        'Content-Type': 'application/json',
    }
    async with httpx.AsyncClient(verify=False) as client:  # verify=False for self-signed certs
        try: 
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error making Redmine request: {e}")
            return None


async def download_file(url: str, output_path: str) -> bool:
    """Download a file from Redmine to the specified path.
    
    Args:
        url: The URL of the file to download
        output_path: The local path where the file will be saved
        
    Returns:
        True if download successful, False otherwise
    """
    headers = {
        'X-Redmine-API-Key': REDMINE_API_KEY,
    }
    
    try:
        # Convert to absolute path
        output_path = os.path.abspath(output_path)
        output_dir = os.path.dirname(output_path)
        
        # Create directory if it doesn't exist
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Ensured directory exists: {output_dir}")
        
        logger.info(f"Downloading from {url} to {output_path}")
        
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, headers=headers, timeout=60.0)
            response.raise_for_status()
            
            content = response.content
            logger.info(f"Downloaded {len(content)} bytes")
            
            # Write file with explicit flush
            with open(output_path, 'wb') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            
            # Verify file was written
            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                logger.info(f"File written successfully: {output_path} ({actual_size} bytes)")
                return True
            else:
                logger.error(f"File not found after write: {output_path}")
                return False
                
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def format_issue(issue: dict) -> str:
    """Format an issue into a readable string."""
    return f"""
Issue #{issue.get("id")}
Subject: {issue.get("subject", "N/A")}
Status: {issue.get("status", {}).get("name", "N/A")}
Priority: {issue.get("priority", {}).get("name", "N/A")}
Assigned to: {issue.get("assigned_to", {}).get("name", "Unassigned")}
Author: {issue.get("author", {}).get("name", "N/A")}
Created: {issue.get("created_on", "N/A")}
Updated: {issue.get("updated_on", "N/A")}
Description: {issue.get("description", "No description")}
"""


@mcp.tool(description="Fetch issues from redmine" )
async def get_issues(project_id: str = "", status: str = "open", limit: int = 25) -> str:
    """Get issues from Redmine.

    Args:
        project_id: Project identifier (optional, if empty returns all projects)
        status: Issue status - "open", "closed", or "*" for all (default: "open")
        limit: Maximum number of issues to return (default: 25, max: 100)
    """
    # Build query parameters
    params = []
    if project_id:
        endpoint = f"projects/{project_id}/issues.json"
    else:
        endpoint = "issues.json"
    
    params.append(f"status_id={status}")
    params.append(f"limit={min(limit, 100)}")
    
    endpoint = f"{endpoint}?{'&'.join(params)}"
    
    data = await make_redmine_request(endpoint)
    
    if not data or "issues" not in data:
        return "Unable to fetch issues or no issues found."
    
    if not data["issues"]:
        logger.info(f"No {status} issues found for project '{project_id}'." if project_id else f"No {status} issues found.")
        return f"No {status} issues found."
    
    issues = [format_issue(issue) for issue in data["issues"]]
    total = data.get("total_count", len(issues))
    
    result = f"Found {total} total issues (showing {len(issues)}):\n"
    result += "\n" + "="*50 + "\n"
    result += "\n---\n".join(issues)
    
    return result


@mcp.tool(name="get_issue_details", 
          description="Fetch details of a specific issue by ID",
          meta={"example": "get_issue_details(issue_id=123)"},
          )
async def get_issue(issue_id: int) -> str:
    """Get details of a specific issue.

    Args:
        issue_id: The issue ID number
    """
    endpoint = f"issues/{issue_id}.json?include=journals,attachments"
    data = await make_redmine_request(endpoint)
    
    if not data or "issue" not in data:
        return f"Unable to fetch issue #{issue_id}."
    
    issue = data["issue"]
    result = format_issue(issue)
    
    # Add journals (comments/history)
    if "journals" in issue:
        result += "\n" + "="*50 + "\n"
        result += "History/Comments:\n"
        for journal in issue["journals"]:
            if journal.get("notes"):
                user = journal.get("user", {}).get("name", "Unknown")
                created = journal.get("created_on", "N/A")
                result += f"\n[{created}] {user}:\n{journal['notes']}\n"
    
    return result


@mcp.tool()
async def get_projects() -> str:
    """Get list of all accessible projects in Redmine."""
    all_projects = []
    offset = 0
    limit = 100
    
    while True:
        endpoint = f"projects.json?limit={limit}&offset={offset}"
        data = await make_redmine_request(endpoint)
        
        if not data or "projects" not in data:
            break
        
        projects = data["projects"]
        if not projects:
            break
            
        all_projects.extend(projects)
        
        # Check if we've fetched all projects
        total_count = data.get("total_count", 0)
        if len(all_projects) >= total_count:
            break
            
        offset += limit
    
    if not all_projects:
        return "No projects found."
    
    result = f"Found {len(all_projects)} projects:\n\n"
    
    for project in all_projects:
        result += f"• [{project.get('identifier')}] {project.get('name')}\n"
        if project.get('description'):
            result += f"  Description: {project.get('description')}\n"
    
    return result


@mcp.tool()
async def download_issue_attachments(issue_id: int, output_dir: str = "./downloads") -> str:
    """Download all attachments from a Redmine issue.
    
    Args:
        issue_id: The issue ID number
        output_dir: Directory where attachments will be saved (default: ./downloads)
        
    Returns:
        Status message with download results
    """
    
    # Convert to absolute path
    output_dir = os.path.abspath(output_dir)
    logger.info(f"Output directory (absolute): {output_dir}")
    
    # Get issue details with attachments
    endpoint = f"issues/{issue_id}.json?include=attachments"
    data = await make_redmine_request(endpoint)
    
    if not data or "issue" not in data:
        return f"Unable to fetch issue #{issue_id}."
    
    issue = data["issue"]
    attachments = issue.get("attachments", [])
    
    if not attachments:
        return f"Issue #{issue_id} has no attachments."
    
    logger.info(f"Found {len(attachments)} attachment(s) for issue #{issue_id}")
    
    # Create issue-specific directory
    issue_dir = os.path.join(output_dir, f"issue_{issue_id}")
    try:
        os.makedirs(issue_dir, exist_ok=True)
        logger.info(f"Created directory: {issue_dir}")
        # Verify directory exists
        if not os.path.isdir(issue_dir):
            return f"Error: Failed to create directory {issue_dir}"
    except OSError as e:
        logger.error(f"Failed to create directory {issue_dir}: {e}")
        return f"Error: Unable to create directory {issue_dir}. {e}"
    
    results = []
    success_count = 0
    
    for i, attachment in enumerate(attachments, 1):
        filename = attachment.get("filename", "unknown")
        content_url = attachment.get("content_url")
        filesize = attachment.get("filesize", 0)
        
        logger.info(f"Processing attachment {i}/{len(attachments)}: {filename}")
        
        if not content_url:
            msg = f"{filename}: No download URL available"
            results.append(msg)
            logger.warning(msg)
            continue
        
        output_path = os.path.join(issue_dir, filename)
        logger.info(f"Will save to: {output_path}")
        
        # Download the file
        if await download_file(content_url, output_path):
            success_count += 1
            # Verify file exists and get actual size
            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                msg = f"{filename} ({filesize} bytes) → {output_path} [Verified: {actual_size} bytes]"
                results.append(msg)
                logger.info(f"Successfully downloaded: {filename}")
            else:
                msg = f"{filename}: Downloaded but file not found on disk"
                results.append(msg)
                logger.error(msg)
        else:
            msg = f"{filename}: Download failed"
            results.append(msg)
            logger.error(msg)
    
    summary = f"Downloaded {success_count}/{len(attachments)} attachments from issue #{issue_id}\n\n"
    summary += "\n".join(results)
    
    # Final verification
    logger.info(f"Download complete: {success_count}/{len(attachments)} successful")
    logger.info(f"Files should be in: {issue_dir}")
    
    return summary



def main():
    # Initialize and run the server
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()