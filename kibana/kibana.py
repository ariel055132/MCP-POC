from typing import Optional, Any, Dict, List, Union
import os
import json
from urllib.parse import quote

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
# 86091596-a33a-4b4b-b825-d387bb6e3c5e
DATA_VIEW_ID = os.getenv("DATA_VIEW_ID", "MID")


def _encode_rison(obj: Union[Dict, List, str, int, float, bool, None]) -> str:
    """Encode Python objects to rison format for Kibana URLs.
    
    Rison is a URL-friendly data format similar to JSON but more compact.
    
    Args:
        obj: Python object to encode (dict, list, str, int, float, bool, None)
        
    Returns:
        Rison-encoded string
        
    Examples:
        >>> _encode_rison({"key": "value"})
        '(key:value)'
        >>> _encode_rison([1, 2, 3])
        '!(1,2,3)'
        >>> _encode_rison(True)
        '!t'
    """
    if obj is None:
        return "!n"
    elif obj is True:
        return "!t"
    elif obj is False:
        return "!f"
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, str):
        # Check if string needs quoting (contains special characters)
        # Note: dots are NOT special in RISON, but hyphens and underscores can be
        special_chars = set("':!,()@- ")
        if any(c in special_chars for c in obj) or obj == "":
            # Escape single quotes and wrap in quotes
            escaped = obj.replace("'", "!'")
            return f"'{escaped}'"
        return obj
    elif isinstance(obj, list):
        if not obj:
            return "!()"
        items = ",".join(_encode_rison(item) for item in obj)
        return f"!({items})"
    elif isinstance(obj, dict):
        if not obj:
            return "()"
        pairs = ",".join(f"{key}:{_encode_rison(value)}" for key, value in obj.items())
        return f"({pairs})"
    else:
        # Fallback to string representation
        return str(obj)


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


@mcp.tool(description="Get data view details including index pattern and field mappings")
async def get_data_view(
    view_id: Optional[str] = None
) -> str:
    """Get details of a Kibana data view (index pattern).
    
    Retrieves comprehensive information about a data view, including the underlying
    Elasticsearch index pattern, field mappings, and configuration. This is useful
    for understanding what indices are being queried.
    
    Args:
        view_id: Data view ID (uses DATA_VIEW_ID env var if None)
    
    Returns:
        JSON string containing data view details including:
            - id: Data view identifier
            - title: Index pattern string
            - fields: Available fields and their types
            - timeFieldName: Time field used for filtering
        
    Examples:
        Get default data view:
        - No parameters needed (uses DATA_VIEW_ID from environment)
        
        Get specific data view:
        - view_id: "86091596-a33a-4b4b-b825-d387bb6e3c5e"
    """
    kibana_url = KIBANA_URL
    api_key = KIBANA_API_KEY
    view_id = view_id or DATA_VIEW_ID
    
    if not kibana_url:
        logger.error("Missing Kibana URL configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured. Set KIBANA_URL environment variable."
        }, indent=2)
    
    if not api_key:
        logger.error("Missing Kibana API key configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No API key configured. Set KIBANA_API_KEY environment variable."
        }, indent=2)
    
    kibana_url = kibana_url.rstrip("/")
    data_view_url = f"{kibana_url}/api/data_views/data_view/{view_id}"
    
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "kbn-xsrf": "true"
    }
    
    try:
        logger.info(f"Fetching data view: {view_id}")
        
        async with httpx.AsyncClient(
            verify=False,
            timeout=10.0,
            follow_redirects=True
        ) as client:
            response = await client.get(data_view_url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✓ Data view retrieved: {data.get('data_view', {}).get('title', 'N/A')}")
            
            return json.dumps(data, indent=2, default=str)
            
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        logger.error(f"Failed to fetch data view: {error_msg}")
        return json.dumps({
            "error": "HTTPError",
            "message": f"Failed to fetch data view {view_id}",
            "details": error_msg
        }, indent=2)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error fetching data view: {error_msg}")
        return json.dumps({
            "error": "DataViewError",
            "message": "Failed to fetch data view",
            "details": error_msg
        }, indent=2)


@mcp.tool(description="List all available data views in Kibana")
async def list_data_views() -> str:
    """List all available data views (index patterns) in Kibana.
    
    Retrieves a list of all data views configured in Kibana. Useful for discovering
    what data sources are available to query.
    
    Returns:
        JSON string with array of data views, each containing:
            - id: Data view identifier
            - title: Index pattern
            - name: Human-readable name
            - timeFieldName: Time field used for filtering
        
    Examples:
        List all data views:
        - No parameters needed
    """
    kibana_url = KIBANA_URL
    api_key = KIBANA_API_KEY
    
    if not kibana_url:
        logger.error("Missing Kibana URL configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured."
        }, indent=2)
    
    if not api_key:
        logger.error("Missing Kibana API key configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No API key configured."
        }, indent=2)
    
    kibana_url = kibana_url.rstrip("/")
    data_views_url = f"{kibana_url}/api/data_views"
    
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "kbn-xsrf": "true"
    }
    
    try:
        logger.info("Fetching all data views")
        
        async with httpx.AsyncClient(
            verify=False,
            timeout=10.0,
            follow_redirects=True
        ) as client:
            response = await client.get(data_views_url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            data_views = data.get("data_view", [])
            
            logger.info(f"✓ Found {len(data_views)} data views")
            
            # Format for easier reading
            formatted_views = []
            for dv in data_views:
                formatted_views.append({
                    "id": dv.get("id"),
                    "title": dv.get("title"),
                    "name": dv.get("name"),
                    "timeFieldName": dv.get("timeFieldName")
                })
            
            return json.dumps({
                "total": len(formatted_views),
                "data_views": formatted_views
            }, indent=2, default=str)
            
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        logger.error(f"Failed to list data views: {error_msg}")
        return json.dumps({
            "error": "HTTPError",
            "message": "Failed to list data views",
            "details": error_msg
        }, indent=2)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error listing data views: {error_msg}")
        return json.dumps({
            "error": "DataViewError",
            "message": "Failed to list data views",
            "details": error_msg
        }, indent=2)


@mcp.tool(description="Search and retrieve actual log data from Elasticsearch via Kibana")
async def search_kibana_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: str = "",
    size: int = 100
) -> str:
    """Search and retrieve actual log documents from Elasticsearch via Kibana API.
    
    Directly queries Elasticsearch through Kibana to fetch log data matching the 
    specified criteria. Returns the actual log documents as JSON.
    
    This function attempts multiple API approaches:
    1. Direct Elasticsearch _search via console proxy
    2. Fallback to alternative endpoints if available
    
    Args:
        index_pattern: Index pattern or dataViewId to search
                      Use get_data_view tool first to resolve data view to index pattern
        time_from: Start time - date math or ISO 8601 format
        time_to: End time - date math or ISO 8601 format  
        query: KQL or Lucene query string
        fields: Comma-separated field names to return (returns all if empty)
        size: Maximum number of documents to return (default: 100, max: 500)
    
    Returns:
        JSON string with log documents and metadata
        
    Examples:
        Search last hour of logs:
        - index_pattern: "logs-*"
        - time_from: "now-1h"
        
        Search with data view ID (resolve first with get_data_view):
        - index_pattern: "86091596-a33a-4b4b-b825-d387bb6e3c5e"
        - time_from: "2026-02-22T09:30:00.000Z"
        - time_to: "2026-02-26T16:30:00.000Z"
        
        Search errors with specific fields:
        - index_pattern: "logs-*"
        - query: "log.level:ERROR"
        - fields: "message,log.level,@timestamp"
    """
    kibana_url = KIBANA_URL
    api_key = KIBANA_API_KEY
    
    if not kibana_url:
        logger.error("Missing Kibana URL configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured. Set KIBANA_URL environment variable."
        }, indent=2)
    
    if not api_key:
        logger.error("Missing Kibana API key configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No API key configured. Set KIBANA_API_KEY environment variable."
        }, indent=2)
    
    # Parse fields
    field_list: Optional[List[str]] = None
    if fields:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]
    
    # Use dataViewId if provided, otherwise use as index pattern
    if not index_pattern:
        index_pattern = DATA_VIEW_ID
    
    # Limit size to reasonable maximum
    size = min(size, 500)
    
    # Build Elasticsearch query
    es_query = {
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
        "sort": [{"@timestamp": {"order": "desc"}}],
        "size": size
    }
    
    # Add query string if provided
    if query:
        es_query["query"]["bool"]["must"].append({
            "query_string": {
                "query": query,
                "analyze_wildcard": True
            }
        })
    else:
        es_query["query"]["bool"]["must"].append({"match_all": {}})
    
    # Add field filtering
    if field_list:
        es_query["_source"] = field_list
    
    kibana_url = kibana_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true",
        "Authorization": f"ApiKey {api_key}"
    }
    
    # Try multiple approaches
    attempts = [
        # Approach 1: Console proxy with index pattern
        {
            "url": f"{kibana_url}/api/console/proxy?path=/{index_pattern}/_search&method=POST",
            "method": "POST",
            "data": es_query,
            "name": "Console Proxy"
        },
        # Approach 2: Try with wildcard pattern if it looks like a data view ID
        {
            "url": f"{kibana_url}/api/console/proxy?path=/*/_search&method=POST",
            "method": "POST",
            "data": es_query,
            "name": "Console Proxy (all indices)"
        }
    ]
    
    last_error = None
    
    for attempt in attempts:
        try:
            logger.info(f"Attempting search via {attempt['name']}: {attempt['url']}")
            
            async with httpx.AsyncClient(
                verify=False,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    attempt['url'],
                    json=attempt['data'],
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                result = _format_search_response(data)
                
                logger.info(f"✓ Search successful via {attempt['name']}: {result['total']} documents found in {result['took']}ms")
                
                return json.dumps(result, indent=2, default=str)
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.warning(f"{attempt['name']} failed: {error_msg}")
            last_error = {
                "error": "HTTPError",
                "message": f"Failed to search logs via {attempt['name']}",
                "details": error_msg
            }
            continue
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"{attempt['name']} failed: {error_msg}")
            last_error = {
                "error": "SearchError",
                "message": f"Failed to search logs via {attempt['name']}",
                "details": error_msg
            }
            continue
    
    # All attempts failed
    logger.error("All search attempts failed")
    return json.dumps(last_error or {
        "error": "SearchError",
        "message": "Failed to search logs using all available methods",
        "suggestion": "1. Verify API key permissions. 2. Try using get_data_view to resolve the index pattern. 3. Check Kibana logs for details."
    }, indent=2)


@mcp.tool(description="Search logs using data view ID with automatic index resolution")
async def search_logs_by_data_view(
    view_id: Optional[str] = None,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: str = "",
    size: int = 100
) -> str:
    """Search logs using a data view ID, automatically resolving to index patterns.
    
    This is a higher-level search function that:
    1. Fetches the data view to get the actual index pattern
    2. Uses that index pattern to search Elasticsearch  
    3. Returns formatted results
    
    Recommended for most use cases as it handles data view resolution automatically.
    
    Args:
        view_id: Data view ID (uses DATA_VIEW_ID env var if None)
        time_from: Start time - date math or ISO 8601 format
        time_to: End time - date math or ISO 8601 format
        query: KQL or Lucene query string
        fields: Comma-separated field names to return
        size: Maximum documents to return (default: 100, max: 500)
    
    Returns:
        JSON string with log documents, data view info, and metadata
        
    Examples:
        Search last hour with default data view:
        - time_from: "now-1h"
        
        Search specific time range:
        - view_id: "86091596-a33a-4b4b-b825-d387bb6e3c5e"
        - time_from: "2026-02-22T09:30:00.000Z"
        - time_to: "2026-02-26T16:30:00.000Z"
        
        Search with filters:
        - query: "log.level:ERROR AND k8s.deployment.name:my-app"
        - fields: "message,log.level,@timestamp"
    """
    kibana_url = KIBANA_URL
    api_key = KIBANA_API_KEY
    view_id = view_id or DATA_VIEW_ID
    
    if not kibana_url:
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured."
        }, indent=2)
    
    if not api_key:
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No API key configured."
        }, indent=2)
    
    # Step 1: Get data view details
    logger.info(f"Resolving data view: {view_id}")
    data_view_result = await get_data_view(view_id)
    
    try:
        data_view_data = json.loads(data_view_result)
        if "error" in data_view_data:
            return data_view_result  # Return error from data view fetch
        
        data_view = data_view_data.get("data_view", {})
        index_pattern = data_view.get("title", "")
        time_field = data_view.get("timeFieldName", "@timestamp")
        
        if not index_pattern:
            return json.dumps({
                "error": "DataViewError",
                "message": "Could not resolve index pattern from data view",
                "data_view_id": view_id
            }, indent=2)
        
        logger.info(f"✓ Resolved data view to index pattern: {index_pattern}")
        
        # Step 2: Search using resolved index pattern
        search_result = await search_kibana_logs(
            index_pattern=index_pattern,
            time_from=time_from,
            time_to=time_to,
            query=query,
            fields=fields,
            size=size
        )
        
        # Parse and enhance result with data view info
        result = json.loads(search_result)
        result["data_view"] = {
            "id": view_id,
            "title": index_pattern,
            "timeFieldName": time_field
        }
        
        return json.dumps(result, indent=2, default=str)
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse data view response: {e}")
        return json.dumps({
            "error": "ParseError",
            "message": "Failed to parse data view response",
            "details": str(e)
        }, indent=2)
    except Exception as e:
        logger.error(f"Search by data view failed: {e}")
        return json.dumps({
            "error": "SearchError",
            "message": "Failed to search logs by data view",
            "details": str(e)
        }, indent=2)


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


@mcp.tool(description="Generate Kibana Discover URL to view logs in browser (does not fetch actual logs)")
async def fetch_kibana_logs(
    index_pattern: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    fields: str = "",
    size: int = 100,
    discover_view_id: str = "a67db0ea-ad22-42af-813f-ffefb7ad1f4f"
) -> str:
    """Generate Kibana Discover URL for viewing logs with specified filters.
    
    Creates a browser-accessible URL to view logs in Kibana Discover with time-based
    filtering, KQL queries, custom columns, and index pattern selection.
    
    Args:
        index_pattern: Index pattern or dataViewId (e.g., "86091596-a33a-4b4b-b825-d387bb6e3c5e", "logs-*")
        time_from: Start time - date math (e.g., "now-15m", "now-1d") or ISO 8601
                   (e.g., "2026-02-06T00:00:00.000Z")
        time_to: End time - date math or ISO 8601 (default: "now")
        query: KQL or Lucene query string (e.g., "log.level:ERROR")
        fields: Comma-separated field names to display as columns 
                (e.g., "logback.mdc.guid,message,log.level")
                Default columns will be used if not specified
        size: Maximum results (unused, kept for compatibility)
        discover_view_id: Kibana Discover saved search view ID
    
    Returns:
        JSON string containing the Discover URL and parameters
        
    Examples:
        Generate URL for logs from past hour:
        - index_pattern: "86091596-a33a-4b4b-b825-d387bb6e3c5e"
        - time_from: "now-1h"
        - time_to: "now"
        
        Generate URL with custom columns and query:
        - index_pattern: "86091596-a33a-4b4b-b825-d387bb6e3c5e"
        - query: "log.level:ERROR"
        - fields: "logback.mdc.guid,logback.mdc.txnCode,message,log.level"
        - time_from: "2026-02-06T00:00:00.000Z"
        - time_to: "2026-02-16T23:59:59.000Z"
    """
    logger.info(f"Generating Kibana Discover URL for index pattern: {index_pattern}")
    
    # Get base URL from environment
    base_url = KIBANA_URL
    
    if not base_url:
        logger.error("Missing Kibana URL configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured. Set KIBANA_URL environment variable."
        }, indent=2)
    
    # Replace host.containers.internal with localhost for browser access
    if "host.containers.internal" in base_url:
        base_url = base_url.replace("host.containers.internal", "localhost")
        logger.info(f"Converted container URL to browser-accessible URL: {base_url}")
    
    # Parse comma-separated fields into list for columns
    columns_list: Optional[List[str]] = None
    if fields:
        columns_list = [f.strip() for f in fields.split(",") if f.strip()]
    
    try:
        discover_url = _build_discover_url(
            kibana_base_url=base_url,
            view_id=discover_view_id,
            time_from=time_from,
            time_to=time_to,
            query=query,
            index_pattern=index_pattern,
            columns=columns_list
        )
        
        logger.info(f"✓ Discover URL generated successfully")
        
        result = {
            "discover_url": discover_url,
            "parameters": {
                "index_pattern": index_pattern or DATA_VIEW_ID,
                "time_from": time_from,
                "time_to": time_to,
                "query": query or "(all)",
                "columns": columns_list or "default",
                "view_id": discover_view_id
            },
            "message": "Open this URL in your browser to view logs in Kibana Discover"
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to generate Discover URL: {error_msg}")
        return json.dumps({
            "error": "URLGenerationError",
            "message": "Failed to generate Discover URL",
            "details": error_msg
        }, indent=2)


def _build_discover_url(
    kibana_base_url: str,
    view_id: str,
    time_from: str,
    time_to: str,
    query: str = "",
    index_pattern: str = "",
    columns: Optional[List[str]] = None
) -> str:
    """Build Kibana Discover URL with query parameters.
    
    Creates a URL that opens Kibana Discover with pre-populated search criteria including
    time range, query filters, index pattern, and column display settings.
    
    Args:
        kibana_base_url: Base Kibana URL (e.g., "https://localhost/kibana")
        view_id: Discover view ID (e.g., "a67db0ea-ad22-42af-813f-ffefb7ad1f4f")
        time_from: Start time - date math or ISO 8601 format
        time_to: End time - date math or ISO 8601 format
        query: KQL or Lucene query string
        index_pattern: Index pattern to search (dataViewId if available)
        columns: List of field names to display as columns
        
    Returns:
        Complete Kibana Discover URL with encoded parameters
    """
    kibana_base_url = kibana_base_url.rstrip("/")
    
    # Use DATA_VIEW_ID from environment if no index_pattern provided
    data_view_id = index_pattern or DATA_VIEW_ID
    
    # Build global state (_g) with time range and filters
    global_state = {
        "filters": [],
        "refreshInterval": {
            "pause": True,
            "value": 60000
        },
        "time": {
            "from": time_from,
            "to": time_to
        }
    }
    
    # Default columns if none provided
    if columns is None:
        columns = [
            "logback.mdc.guid",
            "logback.mdc.txnCode",
            "message",
            "log.level",
            "k8s.deployment.name"
        ]
    
    # Build app state (_a) with dataSource, query, columns, and view settings
    app_state: Dict[str, Any] = {
        "columns": columns,
        "dataSource": {
            "dataViewId": data_view_id,
            "type": "dataView"
        },
        "filters": [],
        "hideChart": False,
        "interval": "auto",
        "query": {
            "language": "kuery",
            "query": query
        },
        "sort": [["@timestamp", "desc"]],
        "viewMode": "documents"
    }
    
    # Encode states to rison format and URL-encode
    g_param = quote(_encode_rison(global_state))
    a_param = quote(_encode_rison(app_state))
    
    # Build final URL
    discover_url = f"{kibana_base_url}/app/discover#/view/{view_id}?_g={g_param}&_a={a_param}"
    
    return discover_url


@mcp.tool(description="Generate Kibana Discover URL with time range and query parameters")
async def generate_kibana_discover_url(
    view_id: str,
    time_from: str = "now-15m",
    time_to: str = "now",
    query: str = "",
    index_pattern: str = "",
    columns: str = "",
    kibana_url: Optional[str] = None
) -> str:
    """Generate a Kibana Discover URL with pre-populated search parameters.
    
    Creates a URL that can be opened in a browser to view logs in Kibana Discover
    with specified time range, query filters, columns, and index pattern.
    
    Args:
        view_id: Discover saved search view ID (e.g., "a67db0ea-ad22-42af-813f-ffefb7ad1f4f")
        time_from: Start time - supports date math (e.g., "now-15m", "now-1h", "now-1d")
                   or ISO 8601 format (e.g., "2026-02-06T16:00:00.000Z")
        time_to: End time - date math or ISO 8601 format (default: "now")
        query: KQL or Lucene query string (e.g., "log.level:ERROR AND k8s.deployment.name:myapp")
        index_pattern: Index pattern or dataViewId (e.g., "86091596-a33a-4b4b-b825-d387bb6e3c5e")
        columns: Comma-separated field names to display (e.g., "field1,field2,field3")
        kibana_url: Kibana base URL (uses KIBANA_URL env var if None)
                    Note: Use "https://localhost/kibana" not "host.containers.internal"
    
    Returns:
        JSON string containing the generated Discover URL or error message
        
    Examples:
        Generate URL for last 1 hour:
        - view_id: "a67db0ea-ad22-42af-813f-ffefb7ad1f4f"
        - time_from: "now-1h"
        - time_to: "now"
        
        Generate URL with query and custom columns:
        - view_id: "a67db0ea-ad22-42af-813f-ffefb7ad1f4f"
        - time_from: "2026-02-16T00:00:00.000Z"
        - time_to: "2026-02-16T23:59:59.000Z"
        - query: "log.level:ERROR"
        - index_pattern: "86091596-a33a-4b4b-b825-d387bb6e3c5e"
        - columns: "logback.mdc.guid,message,log.level"
    """
    # Get base URL from environment if not provided
    base_url = kibana_url or KIBANA_URL
    
    if not base_url:
        logger.error("Missing Kibana URL configuration")
        return json.dumps({
            "error": "ConfigurationError",
            "message": "No Kibana URL configured. Set KIBANA_URL environment variable or provide kibana_url parameter."
        }, indent=2)
    
    # Replace host.containers.internal with localhost for browser access
    if "host.containers.internal" in base_url:
        base_url = base_url.replace("host.containers.internal", "localhost")
        logger.info(f"Converted container URL to browser-accessible URL: {base_url}")
    
    # Parse comma-separated columns into list
    columns_list: Optional[List[str]] = None
    if columns:
        columns_list = [c.strip() for c in columns.split(",") if c.strip()]
    
    try:
        discover_url = _build_discover_url(
            kibana_base_url=base_url,
            view_id=view_id,
            time_from=time_from,
            time_to=time_to,
            query=query,
            index_pattern=index_pattern,
            columns=columns_list
        )
        
        logger.info(f"Generated Discover URL: {discover_url}")
        
        return json.dumps({
            "discover_url": discover_url,
            "parameters": {
                "view_id": view_id,
                "time_from": time_from,
                "time_to": time_to,
                "query": query or "(all)",
                "index_pattern": index_pattern or DATA_VIEW_ID,
                "columns": columns_list or "default"
            }
        }, indent=2)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to generate Discover URL: {error_msg}")
        return json.dumps({
            "error": "URLGenerationError",
            "message": "Failed to generate Discover URL",
            "details": error_msg
        }, indent=2)


def main() -> None:
    """Initialize and run the MCP server."""
    logger.info("Starting Kibana MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()