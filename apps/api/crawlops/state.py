TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "LOST"}
ACTIVE = {"PENDING", "QUEUED", "DISPATCHING", "STARTING", "RUNNING", "CANCELLING"}
TRANSITIONS = {
    "PENDING": {"QUEUED", "CANCELLED"},
    "QUEUED": {"DISPATCHING", "CANCELLED"},
    "DISPATCHING": {"STARTING", "RUNNING", "FAILED", "CANCELLING", "LOST"},
    "STARTING": {"RUNNING", "FAILED", "CANCELLING", "LOST"},
    "RUNNING": {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLING", "LOST"},
    "CANCELLING": {"CANCELLED", "FAILED", "LOST"},
}


def transition(job, status):
    if status == job.status:
        return
    if status not in TRANSITIONS.get(job.status, set()):
        raise ValueError(f"Invalid transition {job.status} → {status}")
    job.status = status
