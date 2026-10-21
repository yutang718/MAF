"""Canned API responses for the self-managed GitLab and M365 security collectors (tests and demo seed)."""
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

NOW = datetime.now(timezone.utc)


def ago(days: float) -> str:
    return (NOW - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def day(days: float) -> str:
    return (NOW - timedelta(days=days)).date().isoformat()


def _openssh(key) -> str:
    return key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()


WEAK_RSA = _openssh(rsa.generate_private_key(public_exponent=65537, key_size=1024))
STRONG = _openssh(ed25519.Ed25519PrivateKey.generate())

# Entra side: alice active, bob disabled, carol deleted (absent), dave active admin.
ENTRA_USERS = [
    {"id": "a1", "displayName": "Alice", "userPrincipalName": "alice@evyd.com", "mail": "alice@evyd.com",
     "accountEnabled": True, "userType": "Member", "createdDateTime": ago(400), "lastSignIn": ago(1)},
    {"id": "b2", "displayName": "Bob", "userPrincipalName": "bob@evyd.com", "mail": "bob@evyd.com",
     "accountEnabled": False, "userType": "Member", "createdDateTime": ago(400), "lastSignIn": ago(20)},
    {"id": "d4", "displayName": "Dave", "userPrincipalName": "dave@evyd.com", "mail": "dave@evyd.com",
     "accountEnabled": True, "userType": "Member", "createdDateTime": ago(400), "lastSignIn": ago(2)},
]
ENTRA_DOMAINS = ["evyd.com"]


def _identity(upn: str) -> list[dict]:
    return [{"provider": "saml", "extern_uid": upn}]


def gitlab_routes() -> dict:
    users = [
        {"id": 1, "username": "alice", "name": "Alice", "email": "alice@evyd.com", "state": "active",
         "is_admin": False, "bot": False, "two_factor_enabled": False, "last_activity_on": day(1),
         "created_at": ago(300), "identities": _identity("alice@evyd.com")},
        {"id": 2, "username": "bob", "name": "Bob", "email": "bob@evyd.com", "state": "active", "is_admin": False,
         "bot": False, "last_activity_on": day(3), "created_at": ago(300), "identities": _identity("bob@evyd.com")},
        {"id": 3, "username": "carol", "name": "Carol", "email": "carol@evyd.com", "state": "active",
         "is_admin": True, "bot": False, "last_activity_on": day(120), "created_at": ago(500),
         "identities": _identity("carol@evyd.com")},
        {"id": 4, "username": "dave", "name": "Dave", "email": "dave@evyd.com", "state": "active", "is_admin": True,
         "bot": False, "last_activity_on": day(0), "created_at": ago(500), "identities": _identity("dave@evyd.com")},
        {"id": 5, "username": "vendor-x", "name": "Vendor", "email": "x@gmail.com", "state": "active",
         "is_admin": False, "bot": False, "last_activity_on": day(5), "created_at": ago(60), "identities": []},
        {"id": 6, "username": "project_7_bot", "name": "bot", "email": "", "state": "active", "is_admin": False,
         "bot": True, "created_at": ago(60), "identities": []},
        {"id": 7, "username": "ghost", "name": "Old", "email": "old@evyd.com", "state": "blocked", "is_admin": False,
         "bot": False, "created_at": ago(900), "identities": []},
    ]
    routes = {
        "/api/v4/version": {"version": "17.3.2-ee", "revision": "abc", "enterprise": True},
        "/api/v4/application/settings": {
            "signup_enabled": True, "require_admin_approval_after_user_signup": False, "domain_allowlist": [],
            "password_authentication_enabled_for_web": True, "password_authentication_enabled_for_git": True,
            "require_two_factor_authentication": False, "max_personal_access_token_lifetime": None,
            "some_secret_setting": "should not be kept"},
        "/api/v4/users": users,
        "/api/v4/personal_access_tokens": [
            {"id": 11, "name": "laptop", "user_id": 2, "scopes": ["api"], "active": True, "revoked": False,
             "created_at": ago(200), "expires_at": None, "last_used_at": ago(2)},
            {"id": 12, "name": "automation", "user_id": 4, "scopes": ["sudo", "api"], "active": True,
             "created_at": ago(30), "expires_at": (NOW + timedelta(days=300)).date().isoformat(),
             "last_used_at": ago(1)},
            {"id": 13, "name": "old-script", "user_id": 1, "scopes": ["read_repository"], "active": True,
             "created_at": ago(200), "expires_at": (NOW + timedelta(days=100)).date().isoformat(),
             "last_used_at": ago(150)},
        ],
        "/api/v4/users/1/keys": [{"title": "work", "key": STRONG, "created_at": ago(100)}],
        "/api/v4/users/2/keys": [{"title": "home", "key": WEAK_RSA, "created_at": ago(100), "last_used_at": ago(3)}],
        "/api/v4/users/3/keys": [],
        "/api/v4/users/4/keys": [],
        "/api/v4/users/5/keys": [],
        "/api/v4/groups": [{"id": 100, "full_path": "evyd", "parent_id": None, "visibility": "private"},
                           {"id": 101, "full_path": "evyd/platform", "parent_id": 100, "visibility": "private"}],
        "/api/v4/groups/100/members": [
            {"username": u, "access_level": 50, "state": "active"} for u in ("alice", "bob", "carol", "dave")] + [
            {"username": "vendor-x", "access_level": 30, "state": "active", "expires_at": None}],
        "/api/v4/groups/101/members": [{"username": "alice", "access_level": 40, "state": "active"}],
        "/api/v4/projects": [
            {"id": 7, "path_with_namespace": "evyd/platform/api", "visibility": "internal", "default_branch": "main",
             "namespace": {"kind": "group", "full_path": "evyd/platform"}, "last_activity_at": ago(1)},
            {"id": 8, "path_with_namespace": "evyd/web", "visibility": "private", "default_branch": "main",
             "namespace": {"kind": "group", "full_path": "evyd"}, "last_activity_at": ago(1)},
            {"id": 9, "path_with_namespace": "bob/api", "visibility": "private", "default_branch": "main",
             "namespace": {"kind": "user", "full_path": "bob"},
             "forked_from_project": {"path_with_namespace": "evyd/platform/api"}},
        ],
        "/api/v4/projects/7/members": [{"username": "vendor-x", "access_level": 40, "state": "active"}],
        "/api/v4/projects/8/members": [],
        "/api/v4/projects/9/members": [],
        "/api/v4/projects/7/remote_mirrors": [{"url": "https://*****:*****@github.com/someone/api.git",
                                               "enabled": True, "last_successful_update_at": ago(1)}],
        "/api/v4/projects/8/remote_mirrors": [{"url": "https://git.evyd.com/mirror/web.git", "enabled": True}],
        "/api/v4/projects/9/remote_mirrors": [],
        "/api/v4/projects/7/protected_branches/main": {"push_access_levels": [{"access_level": 0}],
                                                       "allow_force_push": False},
        "/api/v4/projects/7/approval_rules": [{"approvals_required": 1}],
        "/api/v4/projects/8/protected_branches/main": (404, {"message": "Not found"}),
        "/api/v4/projects/9/protected_branches/main": (404, {"message": "Not found"}),
        "/api/v4/projects/7/variables": [
            {"key": "AWS_SECRET_ACCESS_KEY", "value": "SHOULD-NOT-BE-STORED", "protected": False, "masked": True,
             "variable_type": "env_var", "environment_scope": "*"},
            {"key": "APP_NAME", "value": "api", "protected": False, "masked": False, "variable_type": "env_var"}],
        "/api/v4/projects/8/variables": [],
        "/api/v4/projects/9/variables": [],
        "/api/v4/groups/100/variables": [{"key": "DEPLOY_TOKEN", "value": "x", "protected": True, "masked": True}],
        "/api/v4/groups/101/variables": [],
        "/api/v4/admin/ci/variables": [],
        "/api/v4/deploy_keys": [{"title": "ci-push", "created_at": ago(50),
                                 "projects_with_write_access": [{"path_with_namespace": "evyd/web"}],
                                 "projects_with_readonly_access": []}],
        "/api/v4/audit_events": [
            {"id": 501, "created_at": ago(0.5), "entity_type": "Group", "event_name": "member_created",
             "details": {"author_name": "dave", "add": "user_access", "as": "Owner", "target_details": "vendor-x",
                         "entity_path": "evyd"}}],
        # gitlab.com tags (path as httpx reports it, %2F decoded)
        "/api/v4/projects/gitlab-org/gitlab/repository/tags": [
            {"name": "v17.5.3-ee", "commit": {"created_at": ago(6)}},
            {"name": "v17.4.5-ee", "commit": {"created_at": ago(6)}},
            {"name": "v17.3.7-ee", "commit": {"created_at": ago(6)}},
            {"name": "v17.3.3-ee", "commit": {"created_at": ago(60)}}],
    }
    return routes


def m365_security_routes() -> dict:
    def hunt(req):
        q = req.read().decode()
        if "DeviceTvmSoftwareVulnerabilities" in q:
            return {"results": [
                {"DeviceId": "dev1", "DeviceName": "pc-alice", "CveId": "CVE-2024-0001", "SoftwareName": "chrome",
                 "SoftwareVersion": "120", "VulnerabilitySeverityLevel": "High", "IsExploitAvailable": False},
                {"DeviceId": "dev1", "DeviceName": "pc-alice", "CveId": "CVE-2023-4863", "SoftwareName": "chrome",
                 "SoftwareVersion": "120", "VulnerabilitySeverityLevel": "High", "IsExploitAvailable": False},
                {"DeviceId": "dev2", "DeviceName": "pc-bob", "CveId": "CVE-2024-0003", "SoftwareName": "openssl",
                 "SoftwareVersion": "1.1", "VulnerabilitySeverityLevel": "Medium", "IsExploitAvailable": True}]}
        if "DeviceTvmSecureConfigurationAssessment" in q:
            return {"results": [
                {"DeviceId": "dev2", "DeviceName": "pc-bob", "ConfigurationId": "scid-2003",
                 "ConfigurationName": "Turn on Tamper Protection", "ConfigurationSubcategory": "Tamper protection"},
                {"DeviceId": "dev2", "DeviceName": "pc-bob", "ConfigurationId": "scid-2012",
                 "ConfigurationName": "Turn on real-time protection", "ConfigurationSubcategory": "Antivirus"},
                {"DeviceId": "dev1", "DeviceName": "pc-alice", "ConfigurationId": "scid-2500",
                 "ConfigurationName": "Block executable content from email",
                 "ConfigurationSubcategory": "Attack Surface Reduction"}]}
        return {"results": [{"DeviceId": "dev1", "DeviceName": "pc-alice", "SoftwareName": "windows_10",
                             "SoftwareVersion": "21H2", "EndOfSupportStatus": "EOS Version"}]}

    return {
        "/v1.0/security/runHuntingQuery": hunt,
        "/sites/default/files/feeds/known_exploited_vulnerabilities.json":
            {"vulnerabilities": [{"cveID": "CVE-2023-4863"}]},
        "/v1.0/admin/sharepoint/settings": {"sharingCapability": "externalUserAndGuestSharing",
                                            "isResharingByExternalUsersEnabled": True},
        "/v1.0/roleManagement/directory/roleDefinitions": {"value": [
            {"id": "r-ga", "displayName": "Global Administrator", "templateId": "62e90394-69f5-4237-9190-012177145e10"}]},
        "/v1.0/roleManagement/directory/roleAssignmentScheduleInstances": {"value": [
            {"roleDefinitionId": "r-ga", "assignmentType": "Assigned", "endDateTime": None,
             "principal": {"userPrincipalName": "dave@evyd.com", "@odata.type": "#microsoft.graph.user"}},
            {"roleDefinitionId": "r-ga", "assignmentType": "Assigned", "endDateTime": None,
             "principal": {"userPrincipalName": "breakglass@evyd.com", "@odata.type": "#microsoft.graph.user"}}]},
        "/v1.0/servicePrincipals": lambda req: {"value": [{"appRoles": [
            {"id": "role-mail", "value": "Mail.ReadWrite"}, {"id": "role-user", "value": "User.Read.All"}]}]},
        "/v1.0/applications": {"value": [
            {"appId": "app-1", "displayName": "Mail sync tool", "requiredResourceAccess": [
                {"resourceAppId": "00000003-0000-0000-c000-000000000000",
                 "resourceAccess": [{"id": "role-mail", "type": "Role"}]}],
             "passwordCredentials": [{"startDateTime": ago(10), "endDateTime": (NOW + timedelta(days=700)).isoformat()}],
             "keyCredentials": []},
            {"appId": "app-2", "displayName": "Reader", "requiredResourceAccess": [
                {"resourceAppId": "00000003-0000-0000-c000-000000000000",
                 "resourceAccess": [{"id": "role-user", "type": "Role"}]}],
             "passwordCredentials": [], "keyCredentials": []}]},
        "/beta/security/auditLog/queries": {"id": "q1", "status": "notStarted"},
        "/beta/security/auditLog/queries/q1": {"id": "q1", "status": "succeeded"},
        "/beta/security/auditLog/queries/q1/records": {"value": [
            {"userPrincipalName": "bob@evyd.com", "operation": "FileDownloaded", "createdDateTime": ago(0.5),
             "objectId": f"https://evyd.sharepoint.com/sites/finance/doc{i}.xlsx"} for i in range(150)]},
    }
