from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST

from .models import WorkGroup, GroupMember, Notification
from .forms import WorkGroupForm


def _log(group, text):
    pass


def _notify(user, title, link=''):
    Notification.objects.create(user=user, title=title, link=link)


# ── Grupos ────────────────────────────────────────────────────────────────────

@login_required
def group_list(request):
    my_groups = WorkGroup.objects.filter(
        group_members__user=request.user,
        group_members__status='approved'
    ).distinct()
    pending_groups = WorkGroup.objects.filter(
        group_members__user=request.user,
        group_members__status='pending'
    ).distinct()
    all_groups = WorkGroup.objects.exclude(
        group_members__user=request.user
    ).distinct()
    return render(request, 'groups/group_list.html', {
        'my_groups': my_groups,
        'pending_groups': pending_groups,
        'all_groups': all_groups,
    })


@login_required
def group_create(request):
    if request.method == 'POST':
        form = WorkGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            GroupMember.objects.create(group=group, user=request.user, role='admin', status='approved')
            _log(group, f'{request.user.username} creó el grupo.')
            messages.success(request, f'Grupo "{group.name}" creado.')
            return redirect('group_detail', pk=group.pk)
    else:
        form = WorkGroupForm()
    return render(request, 'groups/group_form.html', {'form': form})


@login_required
def group_detail(request, pk):
    group = get_object_or_404(WorkGroup, pk=pk)
    if not group.is_member(request.user):
        return HttpResponseForbidden('No sos miembro de este grupo.')
    is_admin = group.is_admin(request.user)
    members = group.group_members.filter(status='approved').select_related('user')
    pending = group.group_members.filter(status='pending').select_related('user') if is_admin else []
    return render(request, 'groups/group_detail.html', {
        'group': group,
        'is_admin': is_admin,
        'members': members,
        'pending': pending,
    })


@login_required
@require_POST
def group_join(request, pk):
    group = get_object_or_404(WorkGroup, pk=pk)
    if group.is_member(request.user) or group.has_pending(request.user):
        messages.warning(request, 'Ya tenés una solicitud enviada o ya sos miembro.')
        return redirect('group_list')
    GroupMember.objects.create(group=group, user=request.user, role='member', status='pending')
    for admin in group.group_members.filter(role='admin', status='approved').select_related('user'):
        _notify(admin.user, f'{request.user.username} quiere unirse a "{group.name}".',
                f'/groups/{group.pk}/')
    messages.success(request, 'Solicitud enviada. Esperá que un admin la apruebe.')
    return redirect('group_list')


@login_required
@require_POST
def group_approve(request, pk, member_pk):
    group = get_object_or_404(WorkGroup, pk=pk)
    if not group.is_admin(request.user):
        return HttpResponseForbidden()
    member = get_object_or_404(GroupMember, pk=member_pk, group=group, status='pending')
    member.status = 'approved'
    member.save()
    _log(group, f'{member.user.username} se unió al grupo.')
    _notify(member.user, f'Tu solicitud para unirte a "{group.name}" fue aprobada.', f'/groups/{group.pk}/')
    messages.success(request, f'{member.user.username} aprobado.')
    return redirect('group_detail', pk=group.pk)


@login_required
@require_POST
def group_reject(request, pk, member_pk):
    group = get_object_or_404(WorkGroup, pk=pk)
    if not group.is_admin(request.user):
        return HttpResponseForbidden()
    member = get_object_or_404(GroupMember, pk=member_pk, group=group, status='pending')
    username = member.user.username
    member.delete()
    messages.success(request, f'Solicitud de {username} rechazada.')
    return redirect('group_detail', pk=group.pk)


@login_required
@require_POST
def group_remove_member(request, pk, member_pk):
    group = get_object_or_404(WorkGroup, pk=pk)
    if not group.is_admin(request.user):
        return HttpResponseForbidden()
    member = get_object_or_404(GroupMember, pk=member_pk, group=group)
    if member.user == group.created_by:
        messages.error(request, 'No podés expulsar al creador del grupo.')
        return redirect('group_detail', pk=group.pk)
    username = member.user.username
    member.delete()
    _log(group, f'{username} fue removido del grupo.')
    messages.success(request, f'{username} removido del grupo.')
    return redirect('group_detail', pk=group.pk)


@login_required
@require_POST
def group_set_role(request, pk, member_pk):
    group = get_object_or_404(WorkGroup, pk=pk)
    if not group.is_admin(request.user):
        return HttpResponseForbidden()
    member = get_object_or_404(GroupMember, pk=member_pk, group=group, status='approved')
    if member.user == group.created_by:
        messages.error(request, 'No podés cambiar el rol del creador.')
        return redirect('group_detail', pk=group.pk)
    new_role = request.POST.get('role')
    if new_role in ('admin', 'member'):
        member.role = new_role
        member.save()
        label = 'Administrador' if new_role == 'admin' else 'Miembro'
        _log(group, f'{member.user.username} ahora es {label}.')
        _notify(member.user, f'Tu rol en "{group.name}" cambió a {label}.', f'/groups/{group.pk}/')
    return redirect('group_detail', pk=group.pk)


# ── Notificaciones ────────────────────────────────────────────────────────────

@login_required
def notifications_list(request):
    notifs = request.user.notifications.all()
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'groups/notifications.html', {'notifications': notifs})
