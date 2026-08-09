from django.conf import settings

ALL_MODULES = {"finance", "trading", "hr", "admin_office", "docs", "meeting"}


def enabled_modules(request):
    """Inject the set of enabled module keys into every template context."""
    disabled = set(settings.DISABLED_MODULES)
    return {"enabled_modules": ALL_MODULES - disabled}
