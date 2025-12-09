"""Group Balancer - A tool for creating balanced groups from participant data."""

from .models import Participant, Group, GroupResult
from .balance_engine import BalanceEngine
from .group_optimizer import GroupOptimizer
from .excel_reader import ExcelReader
from .result_formatter import ResultFormatter

__version__ = "1.0.0"

__all__ = [
    'Participant',
    'Group', 
    'GroupResult',
    'BalanceEngine',
    'GroupOptimizer',
    'ExcelReader',
    'ResultFormatter'
]