"""Source code package for the Group Balancer application.

Initializes the package-level logger with a NullHandler to ensure imports
are side-effect free.
"""

import logging

# Configure package-level logger
logger = logging.getLogger("group_balancer")
logger.addHandler(logging.NullHandler())
