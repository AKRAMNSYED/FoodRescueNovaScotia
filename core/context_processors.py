from functools import lru_cache
from pathlib import Path

from django.conf import settings

from .models import ChangeProposal

CODE_SUFFIXES = {'.py', '.html', '.css', '.js', '.sh'}
SKIP_DIRS = {'.venv', 'venv', '.git', 'staticfiles', 'node_modules', '__pycache__', 'migrations'}


@lru_cache(maxsize=1)
def count_code_lines():
    total = 0
    for path in Path(settings.BASE_DIR).rglob('*'):
        if path.suffix not in CODE_SUFFIXES or not path.is_file():
            continue
        if SKIP_DIRS.intersection(path.relative_to(settings.BASE_DIR).parts):
            continue
        try:
            with path.open(encoding='utf-8', errors='ignore') as handle:
                total += sum(1 for _ in handle)
        except OSError:
            continue
    return total


def code_line_count(request):
    return {'code_line_count': f'{count_code_lines():,}'}


def admin_change_notifications(request):
    pending_change_count = 0
    if request.user.is_authenticated and request.user.is_superuser:
        pending_change_count = ChangeProposal.objects.filter(
            status=ChangeProposal.Status.PENDING,
        ).count()
    return {'pending_change_count': pending_change_count}