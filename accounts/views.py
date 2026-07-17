from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST

from .forms import RegisterForm
from .models import UserProfile


def _is_superadmin(user):
    try:
        return user.profile.is_superadmin
    except Exception:
        return False


def _delete_avatar_file(profile):
    if not profile.avatar:
        return
    try:
        profile.avatar.delete(save=False)
    except OSError:
        pass


def register(request):
    if request.user.is_authenticated:
        return redirect('board_list')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Bienvenido, {user.username}!')
            return redirect('board_list')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    from django.utils import timezone
    today = timezone.localdate()
    owned_count = request.user.owned_boards.count()
    member_count = request.user.board_memberships.count()
    assigned_cards = request.user.assigned_cards.select_related('list__board').order_by('due_date')
    overdue_count = assigned_cards.filter(due_date__lt=today).exclude(status='completado').count()
    completed_count = assigned_cards.filter(status='completado').count()
    return render(request, 'accounts/profile.html', {
        'owned_count':     owned_count,
        'member_count':    member_count,
        'assigned_cards':  assigned_cards,
        'overdue_count':   overdue_count,
        'completed_count': completed_count,
        'today':           today,
    })


@login_required
def profile_edit(request):
    email_saved = False
    password_saved = False
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'change_avatar' in request.POST:
            avatar = request.FILES.get('avatar')
            if avatar:
                _delete_avatar_file(request.user.profile)
                request.user.profile.avatar = avatar
                request.user.profile.save()
                messages.success(request, 'Foto de perfil actualizada.')
            else:
                messages.error(request, 'Seleccioná una imagen.')

        elif 'remove_avatar' in request.POST:
            _delete_avatar_file(request.user.profile)
            request.user.profile.avatar = None
            request.user.profile.save()
            messages.success(request, 'Foto de perfil eliminada.')

        elif 'change_username' in request.POST:
            new_username = request.POST.get('username', '').strip()
            if not new_username:
                messages.error(request, 'Ingresá un nombre de usuario.')
            elif User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
                messages.error(request, f'"{new_username}" ya está en uso por otra cuenta.')
            else:
                request.user.username = new_username
                try:
                    request.user.full_clean(exclude=['password'])
                    request.user.save()
                    messages.success(request, 'Nombre de usuario actualizado.')
                except ValidationError as e:
                    messages.error(request, ' '.join(sum(e.message_dict.values(), [])))

        elif 'change_email' in request.POST:
            new_email = request.POST.get('email', '').strip()
            if new_email:
                request.user.email = new_email
                request.user.save()
                messages.success(request, 'Correo actualizado.')
                email_saved = True
            else:
                messages.error(request, 'Ingresá un correo válido.')

        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Contraseña actualizada.')
                password_saved = True
            else:
                messages.error(request, 'Corregí los errores en el formulario.')

    return render(request, 'accounts/profile_edit.html', {
        'password_form': password_form,
    })


# ── Superadmin views ──────────────────────────────────────────────────────────

@login_required
def superadmin_dashboard(request):
    if not _is_superadmin(request.user):
        return HttpResponseForbidden('Acceso denegado.')
    users = User.objects.select_related('profile').order_by('username')
    return render(request, 'accounts/superadmin/dashboard.html', {'users': users})


@login_required
def superadmin_boards(request):
    if not _is_superadmin(request.user):
        return HttpResponseForbidden('Acceso denegado.')
    from boards.models import Board
    boards = Board.objects.select_related('owner').prefetch_related('board_members').order_by('-created_at')
    return render(request, 'accounts/superadmin/boards.html', {'boards': boards})


@login_required
def api_superadmin_stats(request):
    if not _is_superadmin(request.user):
        return JsonResponse({'error': 'Sin permiso'}, status=403)
    from boards.models import Board, Card
    data = {
        'total_users':      User.objects.count(),
        'active_users':     User.objects.filter(is_active=True).count(),
        'total_boards':     Board.objects.count(),
        'total_cards':      Card.objects.count(),
        'cards_pendiente':  Card.objects.filter(status='pendiente').count(),
        'cards_en_proceso': Card.objects.filter(status='en_proceso').count(),
        'cards_completado': Card.objects.filter(status='completado').count(),
    }
    return JsonResponse(data)


@login_required
@require_POST
def api_toggle_user_active(request, user_id):
    if not _is_superadmin(request.user):
        return JsonResponse({'error': 'Sin permiso'}, status=403)
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        return JsonResponse({'error': 'No puedes desactivarte a ti mismo.'}, status=400)
    user.is_active = not user.is_active
    user.save()
    return JsonResponse({'ok': True, 'is_active': user.is_active})


@login_required
@require_POST
def superadmin_toggle_superadmin(request, user_id):
    if not _is_superadmin(request.user):
        return HttpResponseForbidden()
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, 'No puedes modificar tu propio rol de superadmin.')
        return redirect('superadmin_dashboard')
    prof, _ = UserProfile.objects.get_or_create(user=user)
    prof.is_superadmin = not prof.is_superadmin
    prof.save()
    action = 'promovido a' if prof.is_superadmin else 'removido de'
    messages.success(request, f'{user.username} fue {action} superadmin.')
    return redirect('superadmin_dashboard')
