from .models import ChangeProposal


def admin_change_notifications(request):
    pending_change_count = 0
    if request.user.is_authenticated and request.user.is_superuser:
        pending_change_count = ChangeProposal.objects.filter(
            status=ChangeProposal.Status.PENDING,
        ).count()
    return {'pending_change_count': pending_change_count}