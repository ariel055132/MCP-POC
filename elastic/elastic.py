from typing import Optional
import os

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Elastic Server")
logger = get_logger(__name__)
logger.info("Elastic MCP server initialized.")

# Constants
ELASTIC_URL = os.getenv("ELASTIC_URL", "")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")


def create_elasticsearch_client(
    api_key: Optional[str] = None,
    hosts: Optional[list[str]] = None,
) -> Elasticsearch:
    """Create and return an Elasticsearch client instance.
    
    Args:
        api_key: API key for authentication.
                If not provided, uses ELASTIC_API_KEY from environment.
        hosts: List of Elasticsearch host URLs for self-hosted deployments.
              Example: ["http://localhost:9200"]
              If not provided, uses ELASTIC_URL from environment.
    
    Returns:
        Elasticsearch: Configured Elasticsearch client instance.
    
    Raises:
        ValueError: If no hosts/URL are provided or configured.
    
    Examples:
        >>> # With explicit parameters
        >>> client = create_elasticsearch_client(
        ...     api_key="VnVhQ2ZHY0JDZGJrU...",
        ...     hosts=["http://localhost:9200"]
        ... )
        
        >>> # Using environment variables
        >>> client = create_elasticsearch_client()
    """
    # Use provided values or fall back to environment variables
    api_key = api_key or ELASTIC_API_KEY
    
    if hosts:
        # Explicit hosts provided
        logger.info(f"Creating Elasticsearch client for hosts: {hosts}")
        client = Elasticsearch(hosts=hosts, api_key=api_key) if api_key else Elasticsearch(hosts=hosts)
    elif ELASTIC_URL:
        # Use URL from environment variable
        logger.info(f"Creating Elasticsearch client for URL: {ELASTIC_URL}")
        client = Elasticsearch(hosts=[ELASTIC_URL], api_key=api_key) if api_key else Elasticsearch(hosts=[ELASTIC_URL])
    else:
        logger.error("No Elasticsearch connection configuration found.")
        raise ValueError(
            "No Elasticsearch connection configuration found. "
            "Provide hosts parameter or set ELASTIC_URL in environment variables."
        )
    
    return client


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()