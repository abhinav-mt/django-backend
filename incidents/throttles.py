from rest_framework.throttling import UserRateThrottle


class IncidentCreateThrottle(UserRateThrottle):
    scope = 'incident_create'
