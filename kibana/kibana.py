from typing import Optional, Any, Dict, List
import os
import json

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Kibana Server")
logger = get_logger(__name__)
logger.info("Kibana MCP server initialized.")

# Constants
KIBANA_URL = os.getenv("KIBANA_URL", "")
KIBANA_API_KEY = os.getenv("KIBANA_API_KEY", "")
DATA_VIEW_ID = os.getenv("DATA_VIEW_ID", "86091596-a33a-4b4b-b825-d387bb6e3c5e")


def _validate_sort_order(sort_order: str) -> None:
    """Validate sort order parameter.
    
    Args:
        sort_order: Sort order to validate
        
    Raises:
        ValueError: If sort order is not 'asc' or 'desc'
    """
    if sort_order not in ["desc", "asc"]:
        raise ValueError(f"Invalid sort_order: {sort_order}. Must be 'desc' or 'asc'.")


def _build_elasticsearch_query(
    time_from: str,
    time_to: str, 
    query: str,
    sort_field: str,
    sort_order: str,
    size: int,
    fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build Elasticsearch query body.
    
    Args:
        time_from: Start time for search range
        time_to: End time for search range
        query: KQL or Lucene query string
        sort_field: Field to sort by
        sort_order: Sort direction ('asc' or 'desc')
        size: Maximum number of documents to return
        fields: List of field names to return
        
    Returns:
        Elasticsearch query body dictionary
    """
    query_body: Dict[str, Any] = {
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
        "sort": [{sort_field: {"order": sort_order}}],
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
        query_body["query"]["bool"]["must"].append({"match_all": {}})
    
    # Add source filtering if fields specified
    if fields:
        query_body["_source"] = fields
    
    return query_body


def _format_search_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format Elasticsearch response into standardized structure.
    
    Args:
        data: Raw Elasticsearch response data
        
    Returns:
        Formatted response dictionary
    """
    total_hits = data["hits"]["total"]
    total_value = total_hits["value"] if isinstance(total_hits, dict) else total_hits
    
    return {
        "total": total_value,
        "took": data.get("took", 0),
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


async def search_kibana_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: Optional[List[str]] = None,
    sort_field: str = "@timestamp",
    sort_order: str = "desc",
    size: int = 100,
    kibana_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Search logs via Kibana internal bsearch API.
    
    Queries Elasticsearch through Kibana's internal search API to retrieve log documents
    matching specified criteria. This endpoint requires proper authentication via API key.
    
    Args:
        index_pattern: Index pattern to search (e.g., "logs-*", "*")
        time_from: Start time - supports date math (e.g., "now-15m", "now-1d") 
                   or ISO 8601 format (e.g., "2026-02-06T16:00:00.000Z")
        time_to: End time - date math or ISO 8601 format (default: "now")
        query: KQL or Lucene query string (e.g., "log.level:ERROR AND k8s.deployment.name:myapp")
        fields: List of specific field names to return in results 
                (e.g., ["logback.mdc.guid", "message", "log.level"])
                Returns all fields if None
        sort_field: Field name to sort results by (default: "@timestamp")
        sort_order: Sort direction - "desc" or "asc" (default: "desc")
        size: Maximum number of documents to return (default: 100)
        kibana_url: Kibana base URL (uses KIBANA_URL env var if None)
        api_key: API key for authentication (uses KIBANA_API_KEY env var if None)
    
    Returns:
        Dictionary containing:
            - total (int): Total number of matching documents
            - took (int): Search execution time in milliseconds
            - hits (list): List of matching documents, each containing:
                - _index: Index name
                - _id: Document ID
                - _score: Relevance score (may be None)
                - _source: Document fields
    
    Raises:
        ValueError: If required configuration is missing or parameters are invalid
        Exception: If Kibana API request fails or returns unexpected format
    
    Examples:
        >>> # Search error logs from the last hour
        >>> results = await search_kibana_logs(
        ...     index_pattern="logs-*",
        ...     query="log.level:ERROR",
        ...     time_from="now-1h"
        ... )
        >>> print(f"Found {results['total']} errors")
        
        >>> # Search with specific time range and fields
        >>> results = await search_kibana_logs(
        ...     index_pattern="logs-*",
        ...     time_from="2026-02-06T16:00:00.000Z",
        ...     time_to="2026-02-16T23:59:59.000Z",
        ...     fields=["logback.mdc.guid", "logback.mdc.txnCode", "message", "log.level"],
        ...     query="k8s.deployment.name:backend-service",
        ...     size=500
        ... )
    """
    # Validate parameters
    _validate_sort_order(sort_order)
    
    # Get configuration from environment if not provided
    kibana_url = kibana_url or KIBANA_URL
    api_key = api_key or KIBANA_API_KEY
    
    if not kibana_url:
        logger.error("Missing Kibana URL configuration")
        raise ValueError(
            "No Kibana URL configured. "
            "Set KIBANA_URL environment variable or provide kibana_url parameter."
        )
    
    if not api_key:
        logger.error("Missing Kibana API key configuration")
        raise ValueError(
            "No API key configured. "
            "Set KIBANA_API_KEY environment variable or provide api_key parameter."
        )
    
    # Prepare request
    kibana_url = kibana_url.rstrip("/")
    
    query_body = _build_elasticsearch_query(
        time_from=time_from,
        time_to=time_to,
        query=query,
        sort_field=sort_field,
        sort_order=sort_order,
        size=size,
        fields=fields
    )
    
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true",
        "Authorization": f"ApiKey {api_key}"
    }
    
    # Try multiple API endpoints as fallbacks
    endpoints_to_try = [
        # Test Kibana API connectivity first
        {
            "url": f"{kibana_url}/api/status",
            "payload": {},
            "name": "kibana status (connectivity test)",
            "method": "GET"
        },
        # Kibana internal bsearch (preferred but may be disabled)
        {
            "url": f"{kibana_url}/internal/bsearch",
            "payload": {
                "params": {
                    "index": index_pattern,
                    "body": query_body,
                    "rest_total_hits_as_int": True
                }
            },
            "name": "internal bsearch",
            "method": "POST"
        }
    ]
    
    # Execute search with fallback mechanism
    last_error = None
    connectivity_test_passed = False
    
    for endpoint in endpoints_to_try:
        try:
            method = endpoint.get("method", "POST")
            logger.info(
                f"Trying {endpoint['name']} ({method} {endpoint['url']})"
            )
            
            # Configure httpx with more permissive settings
            async with httpx.AsyncClient(
                verify=False,
                timeout=30.0,
                http2=False,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2)
            ) as client:
                # Use GET or POST depending on endpoint
                if method == "GET":
                    response = await client.get(
                        endpoint["url"],
                        headers=headers
                    )
                else:
                    response = await client.post(
                        endpoint["url"],
                        json=endpoint["payload"],
                        headers=headers
                    )
                
                response.raise_for_status()
                
                # Connectivity test - just verify it works
                if endpoint["name"] == "kibana status (connectivity test)":
                    connectivity_test_passed = True
                    logger.info("✓ Kibana API connectivity verified")
                    continue
                
                response_json = response.json()
                
                # Extract Elasticsearch response from Kibana wrapper or use direct response
                es_response = response_json.get("rawResponse", response_json)
            
            result = _format_search_response(es_response)
            logger.info(
                f"Search successful via {endpoint['name']}: "
                f"{result['total']} documents found in {result['took']}ms"
            )
            return result
            
        except httpx.HTTPStatusError as e:
            last_error = f"{endpoint['name']} failed: {e.response.status_code} - {e.response.text}"
            logger.warning(last_error)
            continue
        except httpx.RequestError as e:
            last_error = f"{endpoint['name']} request failed: {str(e)}"
            logger.warning(last_error)
            if endpoint["name"] == "kibana status (connectivity test)":
                logger.error("Cannot connect to Kibana - check if host.containers.internal resolves correctly")
            continue
        except KeyError as e:
            last_error = f"{endpoint['name']} unexpected response format: {str(e)}"
            logger.warning(last_error)
            continue
        except Exception as e:
            last_error = f"{endpoint['name']} error: {str(e)}"
            logger.warning(last_error)
            continue
    
    # If all endpoints failed, raise the last error with more context
    connectivity_msg = "Connectivity test passed but " if connectivity_test_passed else "Cannot connect to Kibana. "
    error_msg = f"{connectivity_msg}All search endpoints failed. Last error: {last_error}"
    logger.error(error_msg)
    raise Exception(error_msg)


@mcp.tool(description="Fetch api status of Kibana to verify connectivity")
async def fetch_kibana_status(
    kibana_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> str:
    """Fetch Kibana API status to verify connectivity and health.
    
    Queries the Kibana status API endpoint to check if the service is accessible
    and retrieve current status information including version and overall health.
    
    Args:
        kibana_url: Kibana base URL (uses KIBANA_URL env var if None)
        api_key: API key for authentication (uses KIBANA_API_KEY env var if None)
    
    Returns:
        JSON string containing Kibana status information including:
            - version: Kibana version information
            - status: Overall status object with state
            - metrics: Various system metrics
        Or error message if the request fails
        
    Examples:
        Check Kibana connectivity:
        - No parameters needed (uses environment variables)
        
        Check with explicit URL:
        - kibana_url: "https://localhost/kibana"
    """
    # Get configuration from environment if not provided
    kibana_url = kibana_url or KIBANA_URL
    api_key = api_key or KIBANA_API_KEY
    
    if not kibana_url:
        logger.error("Missing Kibana URL configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured. Set KIBANA_URL environment variable or provide kibana_url parameter."
        }, indent=2)
    
    if not api_key:
        logger.error("Missing Kibana API key configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No API key configured. Set KIBANA_API_KEY environment variable or provide api_key parameter."
        }, indent=2)
    
    # Prepare request
    kibana_url = kibana_url.rstrip("/")
    status_url = f"{kibana_url}/api/status"
    
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "kbn-xsrf": "true"
    }
    
    try:
        logger.info(f"Fetching Kibana status from {status_url}")
        
        async with httpx.AsyncClient(
            verify=False,
            timeout=10.0,
            follow_redirects=True
        ) as client:
            response = await client.get(status_url, headers=headers)
            response.raise_for_status()
            
            status_data = response.json()
            logger.info("✓ Kibana API status retrieved successfully")
            
            return json.dumps(status_data, indent=2, default=str)
            
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        logger.error(f"Kibana status request failed: {error_msg}")
        return json.dumps({
            "error": "HTTPError",
            "message": "Failed to fetch Kibana status",
            "details": error_msg
        }, indent=2)
    except httpx.RequestError as e:
        error_msg = str(e)
        logger.error(f"Kibana connection failed: {error_msg}")
        return json.dumps({
            "error": "ConnectionError",
            "message": "Cannot connect to Kibana. Check if the URL is correct and the service is running.",
            "details": error_msg
        }, indent=2)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error: {error_msg}")
        return json.dumps({
            "error": "UnexpectedError",
            "message": "An unexpected error occurred",
            "details": error_msg
        }, indent=2)


@mcp.tool(description="Search logs from Kibana using Discover-style parameters")
async def fetch_kibana_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: str = "",
    size: int = 100
) -> str:
    """Fetch logs from Kibana with Discover-like filtering.
    
    Searches log documents from Kibana/Elasticsearch indices with time-based filtering,
    KQL queries, and field selection.
    
    Args:
        index_pattern: Index pattern to search (e.g., "logs-*", "*")
        time_from: Start time - date math (e.g., "now-15m", "now-1d") or ISO 8601
        time_to: End time - date math or ISO 8601 (default: "now")
        query: KQL or Lucene query string (e.g., "log.level:ERROR")
        fields: Comma-separated field names to return (e.g., "message,log.level")
        size: Maximum number of results (default: 100, max: 10000)
    
    Returns:
        JSON string containing search results or error message
        
    Examples:
        Search all logs from past hour:
        - index_pattern: "logs-*"
        - time_from: "now-1h"
        
        Search errors with specific fields:
        - index_pattern: "logs-*"
        - query: "log.level:ERROR"
        - fields: "logback.mdc.guid,message,log.level"
        - time_from: "2026-02-06T16:00:00"
    """
    # Parse comma-separated fields into list
    field_list: Optional[List[str]] = None
    if fields:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]
    
    try:
        logger.info("Initiating Kibana log search via MCP tool")
        results = await search_kibana_logs(
            index_pattern=index_pattern,
            time_from=time_from,
            time_to=time_to,
            query=query,
            fields=field_list,
            size=size
        )
        
        return json.dumps(results, indent=2, default=str)
        
    except ValueError as e:
        # Configuration or validation errors
        logger.error(f"Validation error: {e}")
        return json.dumps({
            "error": "ValidationError",
            "message": str(e)
        }, indent=2)
    except Exception as e:
        # API or unexpected errors
        logger.error(f"Search failed: {e}")
        return json.dumps({
            "error": "SearchError",
            "message": "Failed to fetch logs. Check Kibana configuration and credentials.",
            "details": str(e)
        }, indent=2)


def main() -> None:
    """Initialize and run the MCP server."""
    logger.info("Starting Kibana MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()