from typing import Any
import os

import httpx
from dotenv import load_dotenv
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