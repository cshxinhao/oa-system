from django.db.models import Q, F
from .models import LeaveApplication

def get_pending_leaves_for_approver(user):
    """
    Returns a QuerySet of pending leave applications that the user can approve.
    Logic:
    1. User can approve leaves for members of departments they manage.
    2. User can approve leaves for managers of departments whose parent department they manage.
    """
    if user.is_superuser:
        return (
            LeaveApplication.objects.filter(status=LeaveApplication.STATUS_PENDING)
            .select_related(
                "applicant",
                "applicant__department",
                "applicant__department__manager",
                "applicant__department__parent",
                "applicant__department__parent__manager",
                "reviewer",
            )
            .prefetch_related("dates")
        )
        
    managed_depts = getattr(user, 'managed_departments', None)
    if not managed_depts:
        return LeaveApplication.objects.none()

    # 1. Applicants in departments managed by user
    q_managed = Q(applicant__department__in=managed_depts.all())
    
    # 2. Applicants who are managers of a child department (where the parent is managed by user)
    # Check if applicant is the manager of their department AND their department's parent is managed by user
    q_child_manager = Q(applicant__department__parent__in=managed_depts.all()) & Q(applicant__department__manager=F('applicant'))
    
    return (
        LeaveApplication.objects.filter(
            Q(status=LeaveApplication.STATUS_PENDING) & (q_managed | q_child_manager)
        )
        .exclude(applicant=user)
        .select_related(
            "applicant",
            "applicant__department",
            "applicant__department__manager",
            "applicant__department__parent",
            "applicant__department__parent__manager",
            "reviewer",
        )
        .prefetch_related("dates")
    )

def can_approve_application(user, application):
    """
    Checks if user can approve a specific application.
    """
    if user.is_superuser:
        return True
    
    if application.applicant == user:
        return False
        
    applicant_dept = application.applicant.department
    if not applicant_dept:
        return False

    # Check if user manages the applicant's department
    if applicant_dept.manager == user:
        return True
        
    # Check if applicant is a manager and user manages the parent department
    if (applicant_dept.manager == application.applicant and
        applicant_dept.parent and 
        applicant_dept.parent.manager == user):
        return True
        
    return False
