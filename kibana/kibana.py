from typing import Optional, Any
import os
from datetime import datetime
import json

import httpx
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
KIBANA_URL = os.getenv("KIBANA_URL", "")
KIBANA_USERNAME = os.getenv("KIBANA_USERNAME", "")
KIBANA_PASSWORD = os.getenv("KIBANA_PASSWORD", "")


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


def search_elasticsearch_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: Optional[list[str]] = None,
    sort_field: str = "@timestamp",
    sort_order: str = "desc",
    size: int = 100,
    client: Optional[Elasticsearch] = None,
) -> dict[str, Any]:
    """Search Elasticsearch for logs with specified criteria.
    
    This function queries Elasticsearch using parameters typically found in
    Kibana Discover views, making it easy to programmatically fetch the same
    data you see in the Kibana UI.
    
    Args:
        index_pattern: Index pattern or data view to search.
                      Example: "logs-*" or specific index name.
        time_from: Start time for the search range.
                  Supports Elasticsearch date math (e.g., "now-15m", "now-1d")
                  or ISO 8601 format (e.g., "2026-02-09T08:03:03.314Z").
                  Default: "now-15m".
        time_to: End time for the search range.
                Default: "now".
        query: KQL (Kibana Query Language) or Lucene query string.
              Example: "log.level:ERROR" or "k8s.deployment.name:my-app".
              Default: "" (all documents).
        fields: List of field names to return in results.
               Example: ["logback.mdc.guid", "message", "log.level"].
               If None, returns all fields. Default: None.
        sort_field: Field name to sort results by.
                   Default: "@timestamp".
        sort_order: Sort order, either "desc" or "asc".
                   Default: "desc".
        size: Maximum number of documents to return.
             Default: 100.
        client: Existing Elasticsearch client instance.
               If None, creates a new client. Default: None.
    
    Returns:
        dict: Search results containing:
            - hits: List of matching documents
            - total: Total number of matches
            - took: Search execution time in milliseconds
    
    Raises:
        ValueError: If invalid sort_order provided.
        Exception: If Elasticsearch query fails.
    
    Examples:
        >>> # Basic search with default time range (last 15 minutes)
        >>> results = search_elasticsearch_logs(
        ...     index_pattern="logs-*",
        ...     query="log.level:ERROR"
        ... )
        
        >>> # Search with specific fields and time range
        >>> results = search_elasticsearch_logs(
        ...     index_pattern="logs-app-*",
        ...     time_from="2026-02-09T08:00:00.000Z",
        ...     time_to="now",
        ...     fields=["logback.mdc.guid", "message", "log.level"],
        ...     size=500
        ... )
        
        >>> # Search from Kibana Discover URL parameters
        >>> results = search_elasticsearch_logs(
        ...     index_pattern="logs-*",
        ...     time_from="2026-02-09T08:03:03.314Z",
        ...     time_to="now",
        ...     query="",
        ...     fields=[
        ...         "logback.mdc.guid",
        ...         "logback.mdc.txnCode",
        ...         "message",
        ...         "log.level",
        ...         "k8s.deployment.name"
        ...     ]
        ... )
    """
    # Validate sort order
    if sort_order not in ["desc", "asc"]:
        raise ValueError(f"Invalid sort_order: {sort_order}. Must be 'desc' or 'asc'.")
    
    # Create client if not provided
    if client is None:
        client = create_elasticsearch_client()
    
    # Build the query body
    query_body: dict[str, Any] = {
        "query": {
            "bool": {
                "must": [],
                "filter": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": time_from,
                                "lte": time_to,
                                "format": "strict_date_optional_time"
                            }
                        }
                    }
                ]
            }
        },
        "sort": [
            {sort_field: {"order": sort_order}}
        ],
        "size": size
    }
    
    # Add query string if provided
    if query:
        query_body["query"]["bool"]["must"].append({
            "query_string": {
                "query": query,
                "analyze_wildcard": True
            }
        })
    else:
        # Match all documents if no query specified
        query_body["query"]["bool"]["must"].append({
            "match_all": {}
        })
    
    # Add source filtering if fields specified
    if fields:
        query_body["_source"] = fields
    
    try:
        logger.info(
            f"Searching Elasticsearch: index={index_pattern}, "
            f"time_range={time_from} to {time_to}, query='{query}', size={size}"
        )
        
        # Execute search
        response = client.search(index=index_pattern, body=query_body)
        
        # Format response
        result = {
            "total": response["hits"]["total"]["value"],
            "took": response["took"],
            "hits": [
                {
                    "_index": hit["_index"],
                    "_id": hit["_id"],
                    "_score": hit.get("_score"),
                    "_source": hit["_source"]
                }
                for hit in response["hits"]["hits"]
            ]
        }
        
        logger.info(f"Search completed: found {result['total']} documents in {result['took']}ms")
        return result
        
    except Exception as e:
        logger.error(f"Elasticsearch search failed: {e}")
        raise


async def search_kibana_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: Optional[list[str]] = None,
    sort_field: str = "@timestamp",
    sort_order: str = "desc",
    size: int = 100,
    kibana_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Search logs via Kibana API (for environments without direct Elasticsearch access).
    
    This function queries Elasticsearch through Kibana's API proxy, useful when
    you only have Kibana access and not direct Elasticsearch connectivity.
    
    Args:
        index_pattern: Index pattern or data view to search.
                      Example: "logs-*" or specific index name.
        time_from: Start time for the search range.
                  Supports Elasticsearch date math (e.g., "now-15m", "now-1d")
                  or ISO 8601 format (e.g., "2026-02-09T08:03:03.314Z").
                  Default: "now-15m".
        time_to: End time for the search range.
                Default: "now".
        query: KQL (Kibana Query Language) or Lucene query string.
              Example: "log.level:ERROR" or "k8s.deployment.name:my-app".
              Default: "" (all documents).
        fields: List of field names to return in results.
               Example: ["logback.mdc.guid", "message", "log.level"].
               If None, returns all fields. Default: None.
        sort_field: Field name to sort results by.
                   Default: "@timestamp".
        sort_order: Sort order, either "desc" or "asc".
                   Default: "desc".
        size: Maximum number of documents to return.
             Default: 100.
        kibana_url: Kibana base URL (e.g., "https://localhost/kibana").
                   If None, uses KIBANA_URL from environment. Default: None.
        username: Kibana username for basic auth.
                 If None, uses KIBANA_USERNAME from environment. Default: None.
        password: Kibana password for basic auth.
                 If None, uses KIBANA_PASSWORD from environment. Default: None.
        api_key: API key for authentication (alternative to username/password).
                If None, uses ELASTIC_API_KEY from environment. Default: None.
    
    Returns:
        dict: Search results containing:
            - hits: List of matching documents
            - total: Total number of matches
            - took: Search execution time in milliseconds
    
    Raises:
        ValueError: If invalid parameters or missing configuration.
        Exception: If Kibana API request fails.
    
    Examples:
        >>> # Search with basic auth
        >>> results = await search_kibana_logs(
        ...     index_pattern="logs-*",
        ...     query="log.level:ERROR",
        ...     kibana_url="https://localhost/kibana",
        ...     username="elastic",
        ...     password="changeme"
        ... )
        
        >>> # Search with API key
        >>> results = await search_kibana_logs(
        ...     index_pattern="logs-*",
        ...     time_from="2026-02-09T08:00:00.000Z",
        ...     fields=["message", "log.level"],
        ...     api_key="your_api_key"
        ... )
    """
    # Validate sort order
    if sort_order not in ["desc", "asc"]:
        raise ValueError(f"Invalid sort_order: {sort_order}. Must be 'desc' or 'asc'.")
    
    # Get configuration from environment if not provided
    kibana_url = kibana_url or KIBANA_URL
    username = username or KIBANA_USERNAME
    password = password or KIBANA_PASSWORD
    api_key = api_key or ELASTIC_API_KEY
    
    if not kibana_url:
        raise ValueError(
            "No Kibana URL configured. "
            "Provide kibana_url parameter or set KIBANA_URL in environment variables."
        )
    
    # Remove trailing slash from Kibana URL
    kibana_url = kibana_url.rstrip("/")
    
    # Build the Elasticsearch query body
    query_body: dict[str, Any] = {
        "query": {
            "bool": {
                "must": [],
                "filter": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": time_from,
                                "lte": time_to,
                                "format": "strict_date_optional_time"
                            }
                        }
                    }
                ]
            }
        },
        "sort": [
            {sort_field: {"order": sort_order}}
        ],
        "size": size
    }
    
    # Add query string if provided
    if query:
        query_body["query"]["bool"]["must"].append({
            "query_string": {
                "query": query,
                "analyze_wildcard": True
            }
        })
    else:
        query_body["query"]["bool"]["must"].append({
            "match_all": {}
        })
    
    # Add source filtering if fields specified
    if fields:
        query_body["_source"] = fields
    
    # Prepare authentication headers
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true"
    }
    
    auth = None
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif username and password:
        auth = (username, password)
    
    # Kibana's internal Elasticsearch proxy endpoint
    search_url = f"{kibana_url}/api/console/proxy?path={index_pattern}/_search&method=POST"
    
    try:
        logger.info(
            f"Searching via Kibana API: index={index_pattern}, "
            f"time_range={time_from} to {time_to}, query='{query}', size={size}"
        )
        
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.post(
                search_url,
                json=query_body,
                headers=headers,
                auth=auth
            )
            response.raise_for_status()
            data = response.json()
        
        # Format response
        result = {
            "total": data["hits"]["total"]["value"] if isinstance(data["hits"]["total"], dict) else data["hits"]["total"],
            "took": data["took"],
            "hits": [
                {
                    "_index": hit["_index"],
                    "_id": hit["_id"],
                    "_score": hit.get("_score"),
                    "_source": hit["_source"]
                }
                for hit in data["hits"]["hits"]
            ]
        }
        
        logger.info(f"Search completed: found {result['total']} documents in {result['took']}ms")
        return result
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Kibana API request failed with status {e.response.status_code}: {e.response.text}")
        raise Exception(f"Kibana API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Kibana search failed: {e}")
        raise


@mcp.tool(description="Search Elasticsearch logs with Kibana Discover-like parameters")
def fetch_elasticsearch_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: str = "",
    size: int = 100
) -> str:
    """Fetch logs from Elasticsearch/Kibana using Discover-style parameters.
    
    Automatically detects whether to use direct Elasticsearch or Kibana API
    based on available environment configuration.
    
    Args:
        index_pattern: Index pattern to search (e.g., "logs-*")
        time_from: Start time (e.g., "now-15m", "2026-02-09T08:03:03.314Z")
        time_to: End time (default: "now")
        query: KQL/Lucene query string (e.g., "log.level:ERROR")
        fields: Comma-separated list of fields to return (e.g., "message,log.level")
        size: Maximum number of results (default: 100)
    
    Returns:
        str: JSON formatted search results
    """
    import asyncio
    
    # Parse fields if provided
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    
    # Determine which method to use based on available configuration
    use_kibana = bool(KIBANA_URL)
    
    try:
        if use_kibana:
            # Use Kibana API
            logger.info("Using Kibana API for search")
            results = asyncio.run(search_kibana_logs(
                index_pattern=index_pattern,
                time_from=time_from,
                time_to=time_to,
                query=query,
                fields=field_list,
                size=size
            ))
        else:
            # Use direct Elasticsearch
            logger.info("Using direct Elasticsearch for search")
            results = search_elasticsearch_logs(
                index_pattern=index_pattern,
                time_from=time_from,
                time_to=time_to,
                query=query,
                fields=field_list,
                size=size
            )
        
        return json.dumps(results, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return json.dumps({
            "error": str(e),
            "message": "Failed to fetch logs. Check configuration and credentials."
        }, indent=2)


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()