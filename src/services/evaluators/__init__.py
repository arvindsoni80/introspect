"""Stage-specific evaluators."""

from .base_evaluator import BaseEvaluator
from .meddpicc_evaluator import MEDDPICCEvaluator
from .trial_evaluator import TrialEvaluator
from .close_evaluator import CloseEvaluator
from .winloss_analyzer import WinLossAnalyzer

__all__ = [
    'BaseEvaluator',
    'MEDDPICCEvaluator',
    'TrialEvaluator',
    'CloseEvaluator',
    'WinLossAnalyzer',
]
