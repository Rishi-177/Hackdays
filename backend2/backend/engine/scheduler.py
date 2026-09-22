"""
Deadline Slack Scheduling Module for CarbonPilot.
"""

from typing import Dict, Any, Tuple


def calculate_deadline_slack(
    estimated_execution_latency: float,
    deadline_seconds: float
) -> Dict[str, Any]:
    """
    Calculates slack time between estimated execution duration and hard deadline.

    Returns decision on whether delayed execution into a cleaner carbon window is feasible.
    """
    slack = deadline_seconds - estimated_execution_latency

    if slack < 0:
        return {
            "feasible": False,
            "slack_seconds": slack,
            "delayed_minutes": 0,
            "decision": "REJECT: Execution latency exceeds hard deadline constraint."
        }

    # If slack >= 300s (5 minutes), CarbonPilot can schedule for cleaner carbon grid window
    if slack >= 300:
        delayed_mins = min(int(slack / 60) - 2, 10)  # Reserve buffer
        return {
            "feasible": True,
            "slack_seconds": slack,
            "delayed_minutes": delayed_mins,
            "decision": f"Sufficient deadline slack ({int(slack)}s). Execution delayed by {delayed_mins}m for cleaner carbon window."
        }

    return {
        "feasible": True,
        "slack_seconds": slack,
        "delayed_minutes": 0,
        "decision": f"Tight deadline slack ({int(slack)}s). Executing immediately without delay."
    }
