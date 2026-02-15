def approvable_department_ids(user):
    if user.is_superuser:
        return None

    department_ids = set()

    managed_departments = getattr(user, 'managed_departments', None)
    if managed_departments is not None:
        department_ids.update(managed_departments.values_list('id', flat=True))

    if user.groups.filter(name='Senior Manager').exists() and user.department_id:
        department_ids.add(user.department_id)

    return department_ids
