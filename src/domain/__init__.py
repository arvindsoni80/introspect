"""Domain models for the sales call analysis system."""

from .sales_rep import SalesRep
from .account import Account, AccountRepHistory, StageTransition
from .call import Call, StageClassificationResult
from .scores import (
    MEDDPICCScores,
    CallMEDDPICCScores,
    TrialScores,
    CallTrialScores,
    CloseScores,
    CallCloseScores,
    WinLossAnalysis,
    CallWinLossAnalysis,
)

__all__ = [
    # Sales rep
    'SalesRep',
    # Account
    'Account',
    'AccountRepHistory',
    'StageTransition',
    # Call
    'Call',
    'StageClassificationResult',
    # MEDDPICC scores
    'MEDDPICCScores',
    'CallMEDDPICCScores',
    # Trial scores
    'TrialScores',
    'CallTrialScores',
    # Close scores
    'CloseScores',
    'CallCloseScores',
    # Win/Loss
    'WinLossAnalysis',
    'CallWinLossAnalysis',
]
