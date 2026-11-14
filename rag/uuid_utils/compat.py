
from uuid import uuid4

def uuid7():
    # Fallback UUID for environments where native uuid_utils is blocked.
    return uuid4()
