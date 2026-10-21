"""Match GitLab accounts to Entra ID users, to find leavers and accounts with no corporate identity.

GitLab signs in through Entra SSO, so a user's SAML/OIDC identity carries the
Entra object id, UPN or email as its extern_uid. Matching tries that first,
then the GitLab account's email against UPN and mail.
"""
from dataclasses import dataclass

SSO_PROVIDER_HINTS = ("saml", "openid", "azure", "entra", "microsoft", "oauth2")


@dataclass(frozen=True)
class Match:
    status: str  # active | disabled | missing | non_corporate | service
    entra: dict | None
    via: str  # identity | email | ""


class EntraIndex:
    def __init__(self, users: list[dict]):
        self.by_key: dict[str, dict] = {}
        for u in users:
            for k in (u.get("id"), u.get("userPrincipalName"), u.get("mail")):
                if k:
                    self.by_key.setdefault(str(k).lower(), u)

    def get(self, key: str | None) -> dict | None:
        return self.by_key.get(key.lower()) if key else None


def company_domains(facts: dict, params: dict) -> set[str]:
    configured = {d.lower().lstrip("@") for d in params.get("company_domains") or [] if d}
    return configured or {d.lower() for d in facts.get("entra.domains") or []}


def has_sso(user: dict) -> bool:
    return any(any(h in (i.get("provider") or "").lower() for h in SSO_PROVIDER_HINTS) for i in user.get("identities", []))


def classify(user: dict, index: EntraIndex, domains: set[str], service: set[str]) -> Match:
    if user["username"].lower() in service or user.get("bot"):
        return Match("service", None, "")
    for ident in user.get("identities", []):
        if any(h in (ident.get("provider") or "").lower() for h in SSO_PROVIDER_HINTS):
            hit = index.get(ident.get("extern_uid"))
            if hit:
                return Match("active" if hit.get("accountEnabled") else "disabled", hit, "identity")
    hit = index.get(user.get("email"))
    if hit:
        return Match("active" if hit.get("accountEnabled") else "disabled", hit, "email")
    domain = (user.get("email") or "").rpartition("@")[2]
    # A company address or SSO identity with no Entra user behind it: the Entra account was deleted.
    if has_sso(user) or (domain and domain in domains):
        return Match("missing", None, "")
    return Match("non_corporate", None, "")


def classify_all(facts: dict, params: dict) -> dict[str, Match]:
    index = EntraIndex(facts.get("entra.users") or [])
    domains = company_domains(facts, params)
    service = {s.lower() for s in params.get("service_accounts") or []}
    return {u["username"]: classify(u, index, domains, service) for u in facts["gitlab.users"]}
