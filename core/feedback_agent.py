"""FeedbackAgent

This agent is responsible for collecting human feedback (approval or rejection) on the generated incident report.
It exposes a simple `record_feedback` method that writes the boolean decision into the shared memory under the
key `feedback`.  The UI layer (`app.py`) calls this method when the user clicks the *Approve* or *Reject* button.
"""

from typing import Dict

class FeedbackAgent:
    def __init__(self, shared_memory: Dict):
        self.shared_memory = shared_memory
        # default to None until user acts
        self.shared_memory.setdefault('feedback', None)

    def record_feedback(self, approved: bool) -> None:
        """Store the user's approval flag.

        Args:
            approved: ``True`` if the user approves the report, ``False`` otherwise.
        """
        self.shared_memory['feedback'] = approved
        # Reset fix status when new feedback arrives
        self.shared_memory['fix_status'] = None
