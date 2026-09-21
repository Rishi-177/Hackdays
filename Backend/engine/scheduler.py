"""
CarbonPilot Deadline Slack & Window Scheduler
"""

from typing import Any, Dict


def calculate_deadline_slack(deadline_seconds: float, estimated_latency: float) -> float:
    """Calculates available deadline slack in seconds."""
    return max(0.0, float(deadline_seconds) - float(estimated_latency))


def evaluate_slack_scheduling(
    deadline_seconds: float,
    estimated_latency: float,
    desired_delay_seconds: float = 300.0,
) -> Dict[str, Any]:
    """
    Evaluates whether execution can be delayed for a cleaner carbon window.

    Returns dict with delay_recommended, wait_seconds, and reasoning string.
    """
    slack = calculate_deadline_slack(deadline_seconds, estimated_latency)
    if slack >= desired_delay_seconds:
        return {
            "delay_recommended": True,
            "wait_seconds": desired_delay_seconds,
            "slack_seconds": round(slack, 2),
            "reasoning": f"Execution delayed by {int(desired_delay_seconds // 60)} minutes because sufficient deadline slack ({int(slack // 60)} min) exists.",
        }
    return {
        "delay_recommended": False,
        "wait_seconds": 0.0,
        "slack_seconds": round(slack, 2),
        "reasoning": "Immediate execution required due to tight deadline slack.",
    }
