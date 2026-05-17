"""Source code package for the Group Balancer application.

Initializes the global logging configuration for professional standards.
"""

import logging
import sys

# Configure global logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("group_balancer")
