from django.contrib.auth import get_user_model
from django.db.models import Q, F

from .models import LeaveApplication

User = get_user_model()


def get_org_approver(user):
    """
    Returns the department-based approver for `user`, or None.
    Logic: the user's department manager; if the user IS the department
    manager, the parent department's manager.
    """
    dept = getattr(user, 'department', None)
    if not dept or not dept.manager_id:
        return None
    if dept.manager_id != user.pk:
        return dept.manager
    if dept.parent_id and dept.parent.manager_id:
        return dept.parent.manager
    return None


def get_eligible_approvers(user):
    """
    Returns a QuerySet of users the applicant can pick as approver:
    the per-user configured list (LeaveApproverSetting) if a row exists,
    otherwise the department-based approver; plus all global approvers,
    excluding the applicant themselves.
    An existing setting row with an empty approver list is meaningful:
    only global approvers are eligible then (no fallback to org approver).
    """
    ids = set()
    setting = getattr(user, 'leave_approver_setting', None)
    if setting is not None:
        ids.update(setting.approvers.values_list('pk', flat=True))
    else:
        org = get_org_approver(user)
        if org:
            ids.add(org.pk)
    ids.update(
        User.objects.filter(can_approve_all_leaves=True).values_list('pk', flat=True)
    )
    ids.discard(user.pk)
    return User.objects.filter(pk__in=ids).order_by('first_name', 'username')


def get_pending_leaves_for_approver(user):
    """
    Returns a QuerySet of pending leave applications that the user can approve.
    Logic:
    1. Superusers and global approvers see all pending leaves (excluding their own).
    2. Other users see leaves assigned to them, leaves from members of
       departments they manage, and leaves from managers of child departments.
    """
    pending = LeaveApplication.objects.filter(status=LeaveApplication.STATUS_PENDING)
    if user.is_superuser:
        return pending.select_related(
            "applicant",
            "applicant__department",
            "applicant__department__manager",
            "applicant__department__parent",
            "applicant__department__parent__manager",
            "approver",
        ).prefetch_related("dates")
    if user.can_approve_all_leaves:
        return pending.exclude(applicant=user).select_related(
            "applicant",
            "applicant__department",
            "applicant__department__manager",
            "applicant__department__parent",
            "applicant__department__parent__manager",
            "approver",
        ).prefetch_related("dates")

    managed_depts = list(user.managed_departments.all())
    q = Q(approver=user)
    if managed_depts:
        q |= Q(applicant__department__in=managed_depts)
        q |= Q(applicant__department__parent__in=managed_depts) & Q(applicant__department__manager=F('applicant'))
    return pending.filter(q).exclude(applicant=user).select_related(
        "applicant",
        "applicant__department",
        "applicant__department__manager",
        "applicant__department__parent",
        "applicant__department__parent__manager",
        "approver",
    ).prefetch_related("dates")


def can_approve_application(user, application):
    """
    Checks if user can approve a specific application.
    """
    if user.is_superuser:
        return True

    if application.applicant_id == user.pk:
        return False

    if user.can_approve_all_leaves:
        return True

    # The assigned approver keeps the right even if the org structure changed later.
    if application.approver_id == user.pk:
        return True

    applicant_dept_id = application.applicant.department_id
    if not applicant_dept_id:
        return False
    dept = application.applicant.department

    # Check if user manages the applicant's department
    if dept.manager_id == user.pk:
        return True

    # Check if applicant is a manager and user manages the parent department
    if (dept.manager_id == application.applicant_id and
            dept.parent_id and
            dept.parent.manager_id == user.pk):
        return True

    return False
