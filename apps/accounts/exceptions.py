from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    resp = exception_handler(exc, context)
    if resp is None:
        return Response(
            {"detail": "Something went wrong. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return resp