"""Source code package for the Group Balancer application.

Initializes the global logging configuration for professional standards.
"""

import logging
import sys

# Configure global logger
logger = logging.getLogger("group_balancer")
logger.setLevel(logging.INFO)

# Create console handler with a professional format
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)
