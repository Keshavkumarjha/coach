from rest_framework.throttling import SimpleRateThrottle

class LoginRateThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        # Throttle by IP for anonymous login attempts
        ip = self.get_ident(request)
        return f"throttle_login_{ip}"

class BranchJoinRateThrottle(SimpleRateThrottle):
    scope = "branch_join"

    def get_cache_key(self, request, view):
        ip = self.get_ident(request)
        return f"throttle_branch_join_{ip}"

class OrgSignupRateThrottle(SimpleRateThrottle):
    scope = "org_signup"

    def get_cache_key(self, request, view):
        ip = self.get_ident(request)
        return f"throttle_org_signup_{ip}"