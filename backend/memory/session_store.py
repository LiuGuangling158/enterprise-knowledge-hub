class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = {}

    def append(self, session_id: str, role: str, content: str) -> None:
        self._sessions.setdefault(session_id, []).append({"role": role, "content": content})

    def history(self, session_id: str) -> list[dict]:
        return self._sessions.get(session_id, [])
