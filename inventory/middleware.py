from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Redirect users to a password-change page when required.

    Users are forced to update their password either when they log in for the
    first time (a fresh account) or whenever their password has been reset.  A
    simple boolean flag stored on a lightweight profile model keeps track of
    the requirement; the flag is set via signals whenever a User's password
    changes.  After a successful password change the flag is cleared.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            # Don't loop; allow access to the change-password view itself.
            change_path = reverse('inventory:change_password')
            if request.path != change_path and not request.path.startswith('/admin/'):
                profile = getattr(user, 'profile', None)
                # redirect if first login (last_login is None) or flag is set
                if (profile and profile.force_password_change) or user.last_login is None:
                    return redirect('inventory:change_password')
        return self.get_response(request)
