"""Identity and permissions. Resolved from outside the prompt; the LLM never decides any of this."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"


@dataclass(frozen=True)
class User:
    user_id: str
    role: Role
    claims: frozenset[str] | None = None  # None = every claim


# ponytail: hardcoded directory; replace with the corporate IdP (OIDC claims → role + scope) in production.
USERS = {
    "ana": User("ana", Role.VIEWER, frozenset({"EXP-10234", "EXP-10235"})),
    "luis": User("luis", Role.OPERATOR),
    # Workshops T-412, T-517 and T-633.
    "marta": User("marta", Role.OPERATOR, frozenset({"EXP-10237", "EXP-10238", "EXP-10240", "EXP-10241", "EXP-10242"})),
}

READ_TOOLS = frozenset({"get_claim", "get_workshop", "get_claim_events"})
ROLE_TOOLS = {
    Role.VIEWER: READ_TOOLS,
    Role.OPERATOR: READ_TOOLS | {"propose_action"},
}
ROLE_ACTIONS = {
    Role.VIEWER: frozenset(),
    Role.OPERATOR: frozenset({"REQUEST_DOCUMENT"}),
}


class UnknownUser(Exception):
    pass


def get_user(user_id: str) -> User:
    try:
        return USERS[user_id]
    except KeyError:
        raise UnknownUser(user_id) from None


def allowed_tools(user: User) -> frozenset[str]:
    return ROLE_TOOLS[user.role]


def can_read(user: User, claim_id: str) -> bool:
    return user.claims is None or claim_id in user.claims


def can_act(user: User, action: str) -> bool:
    return action in ROLE_ACTIONS[user.role]
