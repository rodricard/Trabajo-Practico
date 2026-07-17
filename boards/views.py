from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Prefetch
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Board, BoardMember, List, Card
from .forms import BoardForm, ListForm, CardForm, CardQuickForm, BoardMemberForm
from .realtime import broadcast_board_event
from groups.utils import notify_user, broadcast_user_event


def _is_member(user, board):
    return board.board_members.filter(user=user).exists()


def _is_owner(user, board):
    return board.owner == user


def _is_board_admin(user, board):
    return board.board_members.filter(user=user, role__in=['owner', 'admin']).exists()


def _reindex(queryset):
    for index, obj in enumerate(queryset):
        if obj.position != index:
            type(obj).objects.filter(pk=obj.pk).update(position=index)


@login_required
def board_list(request):
    owned = Board.objects.filter(owner=request.user)
    member_of = Board.objects.filter(board_members__user=request.user).exclude(owner=request.user)

    today = timezone.localdate()
    mis_cards = Card.objects.filter(assigned_to=request.user, is_archived=False)

    total       = mis_cards.count()
    pendientes  = mis_cards.filter(status='pendiente').count()
    en_proceso  = mis_cards.filter(status='en_proceso').count()
    completados = mis_cards.filter(status='completado').count()

    today_cards = mis_cards.filter(
        due_date=today
    ).select_related('list__board').order_by('list__board__title')

    pending_cards = mis_cards.filter(
        due_date__gt=today
    ).select_related('list__board').order_by('due_date')[:10]

    return render(request, 'boards/board_list.html', {
        'owned_boards':  owned,
        'member_boards': member_of,
        'today_cards':   today_cards,
        'pending_cards': pending_cards,
        'today':         today,
        'total':         total,
        'pendientes':    pendientes,
        'en_proceso':    en_proceso,
        'completados':   completados,
    })


@login_required
def board_create(request):
    if request.method == 'POST':
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save(commit=False)
            board.owner = request.user
            board.save()
            BoardMember.objects.create(board=board, user=request.user, role='owner')
            return redirect('board_detail', pk=board.pk)
    else:
        form = BoardForm()
    return render(request, 'boards/board_form.html', {'form': form, 'action_label': 'Crear tablero'})


@login_required
def board_detail(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_member(request.user, board):
        return HttpResponseForbidden('No tienes acceso a este tablero.')
    lists = board.lists.filter(is_archived=False).prefetch_related(
        Prefetch('cards', queryset=Card.objects.filter(is_archived=False).select_related('assigned_to'))
    )
    archived_count = (
        board.lists.filter(is_archived=True).count()
        + Card.objects.filter(list__board=board, is_archived=True).count()
    )
    return render(request, 'boards/board_detail.html', {
        'board':          board,
        'lists':          lists,
        'list_form':      ListForm(),
        'card_form':      CardQuickForm(),
        'is_owner':       _is_owner(request.user, board),
        'is_board_admin': _is_board_admin(request.user, board),
        'archived_count': archived_count,
    })


@login_required
def board_update(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_board_admin(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = BoardForm(request.POST, instance=board)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tablero actualizado.')
            return redirect('board_detail', pk=board.pk)
    else:
        form = BoardForm(instance=board)
    return render(request, 'boards/board_form.html', {
        'form':         form,
        'board':        board,
        'action_label': 'Guardar cambios',
    })


@login_required
def board_delete(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_owner(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        board.delete()
        messages.success(request, 'Tablero eliminado.')
        return redirect('board_list')
    return render(request, 'boards/board_confirm_delete.html', {'board': board})


@login_required
def board_archived(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    archived_lists = board.lists.filter(is_archived=True).order_by('title')
    archived_cards = Card.objects.filter(list__board=board, is_archived=True) \
        .select_related('list').order_by('title')
    return render(request, 'boards/board_archived.html', {
        'board': board,
        'archived_lists': archived_lists,
        'archived_cards': archived_cards,
    })


@login_required
def board_members(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_board_admin(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = BoardMemberForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            try:
                user = User.objects.get(username=username)
                if user == board.owner:
                    messages.error(request, 'El propietario ya tiene acceso.')
                elif BoardMember.objects.filter(board=board, user=user).exists():
                    messages.warning(request, f'"{username}" ya es miembro.')
                else:
                    BoardMember.objects.create(board=board, user=user, role='member')
                    notify_user(user, f'{request.user.username} te agregó al tablero "{board.title}"', f'/boards/{board.pk}/')
                    broadcast_user_event(
                        user.id, 'board_added',
                        board_id=board.pk, title=board.title,
                        color=board.background_color, owner=board.owner.username,
                    )
                    messages.success(request, f'"{username}" agregado al tablero.')
            except User.DoesNotExist:
                messages.error(request, f'Usuario "{username}" no encontrado.')
    else:
        form = BoardMemberForm()
    members = board.board_members.select_related('user').all()
    return render(request, 'boards/board_members.html', {
        'board':          board,
        'members':        members,
        'form':           form,
        'is_owner':       _is_owner(request.user, board),
    })


@login_required
def board_member_search(request, board_pk):
    board = get_object_or_404(Board, pk=board_pk)
    if not _is_board_admin(request.user, board):
        return JsonResponse({'error': 'No autorizado.'}, status=403)

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    existing_ids = board.board_members.values_list('user_id', flat=True)
    users = User.objects.filter(username__icontains=query) \
        .exclude(pk__in=existing_ids).exclude(pk=board.owner_id) \
        .order_by('username')[:8]

    return JsonResponse({'results': [u.username for u in users]})


@login_required
def board_member_remove(request, board_pk, member_pk):
    board = get_object_or_404(Board, pk=board_pk)
    if not _is_board_admin(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        member = get_object_or_404(BoardMember, pk=member_pk, board=board)
        if member.role == 'owner':
            messages.error(request, 'No puedes eliminar al propietario.')
        elif member.role == 'admin' and not _is_owner(request.user, board):
            messages.error(request, 'Solo el propietario puede eliminar administradores.')
        else:
            member.delete()
            messages.success(request, 'Miembro eliminado.')
    return redirect('board_members', pk=board_pk)


@login_required
@require_POST
def api_member_set_role(request, board_pk, member_pk):
    board = get_object_or_404(Board, pk=board_pk)
    if not _is_owner(request.user, board):
        return JsonResponse({'error': 'Solo el propietario puede cambiar roles.'}, status=403)
    member = get_object_or_404(BoardMember, pk=member_pk, board=board)
    if member.role == 'owner':
        return JsonResponse({'error': 'No puedes cambiar el rol del propietario.'}, status=400)
    role = request.POST.get('role')
    if role not in ['admin', 'member']:
        return JsonResponse({'error': 'Rol inválido.'}, status=400)
    member.role = role
    member.save()
    return JsonResponse({'ok': True, 'role': role, 'role_display': member.get_role_display()})


@login_required
def list_create(request, board_pk):
    board = get_object_or_404(Board, pk=board_pk)
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = ListForm(request.POST)
        if form.is_valid():
            lst = form.save(commit=False)
            lst.board = board
            lst.position = board.lists.count()
            lst.save()
            broadcast_board_event(board.pk, 'list_created', list_id=lst.pk, title=lst.title, position=lst.position)
    return redirect('board_detail', pk=board_pk)


@login_required
def list_delete(request, pk):
    lst = get_object_or_404(List, pk=pk)
    board = lst.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        lst.is_archived = True
        lst.save(update_fields=['is_archived'])
        lst.cards.filter(is_archived=False).update(is_archived=True)
        broadcast_board_event(board.pk, 'list_deleted', list_id=lst.pk)
        messages.success(request, f'Lista "{lst.title}" archivada.')
    return redirect('board_detail', pk=board.pk)


@login_required
def list_unarchive(request, pk):
    lst = get_object_or_404(List, pk=pk)
    board = lst.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        lst.is_archived = False
        lst.position = board.lists.filter(is_archived=False).count()
        lst.save(update_fields=['is_archived', 'position'])
        broadcast_board_event(board.pk, 'list_created', list_id=lst.pk, title=lst.title, position=lst.position)
        messages.success(request, f'Lista "{lst.title}" restaurada.')
    return redirect('board_archived', pk=board.pk)


@login_required
def list_delete_permanent(request, pk):
    lst = get_object_or_404(List, pk=pk, is_archived=True)
    board = lst.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        lst.delete()
        messages.success(request, 'Lista eliminada definitivamente.')
    return redirect('board_archived', pk=board.pk)


@login_required
@require_POST
def list_reorder(request, pk):
    lst = get_object_or_404(List, pk=pk)
    board = lst.board
    if not _is_member(request.user, board):
        return JsonResponse({'error': 'No tienes acceso a este tablero.'}, status=403)
    try:
        new_position = int(request.POST.get('position', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Posición inválida.'}, status=400)

    lists = list(board.lists.filter(is_archived=False).exclude(pk=lst.pk).order_by('position'))
    new_position = max(0, min(new_position, len(lists)))
    lists.insert(new_position, lst)
    _reindex(lists)
    broadcast_board_event(board.pk, 'list_reordered', list_id=lst.pk, position=new_position)

    return JsonResponse({'ok': True, 'list_id': lst.pk, 'position': new_position})


@login_required
def card_create(request, list_pk):
    lst = get_object_or_404(List, pk=list_pk)
    if not _is_member(request.user, lst.board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = CardQuickForm(request.POST)
        if form.is_valid():
            card = form.save(commit=False)
            card.list = lst
            card.position = lst.cards.filter(is_archived=False).count()
            card.save()
            broadcast_board_event(lst.board.pk, 'card_created', card_id=card.pk, list_id=lst.pk, title=card.title, position=card.position)
    return redirect('board_detail', pk=lst.board.pk)


@login_required
@require_POST
def card_move(request, pk):
    card = get_object_or_404(Card, pk=pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return JsonResponse({'error': 'No tienes acceso a este tablero.'}, status=403)

    target_list = get_object_or_404(List, pk=request.POST.get('list_id'), board=board)
    try:
        new_position = int(request.POST.get('position', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Posición inválida.'}, status=400)

    source_list = card.list

    target_cards = list(target_list.cards.filter(is_archived=False).exclude(pk=card.pk).order_by('position'))
    new_position = max(0, min(new_position, len(target_cards)))
    target_cards.insert(new_position, card)
    _reindex(target_cards)

    if source_list.pk != target_list.pk:
        card.list = target_list
        card.save(update_fields=['list'])
        _reindex(source_list.cards.filter(is_archived=False).order_by('position'))

    broadcast_board_event(board.pk, 'card_moved', card_id=card.pk, list_id=target_list.pk, position=new_position)

    return JsonResponse({'ok': True, 'card_id': card.pk, 'list_id': target_list.pk, 'position': new_position})


@login_required
def card_detail(request, pk):
    card = get_object_or_404(Card, pk=pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    board_users = User.objects.filter(board_memberships__board=board)
    if request.method == 'POST':
        prev_assigned = card.assigned_to
        form = CardForm(request.POST, instance=card)
        form.fields['assigned_to'].queryset = board_users
        if form.is_valid():
            updated = form.save()
            broadcast_board_event(board.pk, 'card_updated', card_id=updated.pk, list_id=updated.list_id)
            new_assigned = updated.assigned_to
            if new_assigned and new_assigned != prev_assigned and new_assigned != request.user:
                notify_user(new_assigned, f'{request.user.username} te asignó la tarjeta "{card.title}"', f'/boards/cards/{card.pk}/')
            messages.success(request, 'Tarjeta actualizada.')
            return redirect('card_detail', pk=card.pk)
    else:
        form = CardForm(instance=card)
        form.fields['assigned_to'].queryset = board_users
    return render(request, 'boards/card_detail.html', {
        'card':     card,
        'board':    board,
        'form':     form,
        'is_owner': _is_owner(request.user, board),
    })


@login_required
def card_delete(request, pk):
    card = get_object_or_404(Card, pk=pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        card.is_archived = True
        card.save(update_fields=['is_archived'])
        broadcast_board_event(board.pk, 'card_deleted', card_id=card.pk)
        messages.success(request, f'Tarjeta "{card.title}" archivada.')
    return redirect('board_detail', pk=board.pk)


@login_required
def card_unarchive(request, pk):
    card = get_object_or_404(Card, pk=pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        card.is_archived = False
        card.position = card.list.cards.filter(is_archived=False).count()
        card.save(update_fields=['is_archived', 'position'])
        if card.list.is_archived:
            card.list.is_archived = False
            card.list.position = board.lists.filter(is_archived=False).count()
            card.list.save(update_fields=['is_archived', 'position'])
        broadcast_board_event(
            board.pk, 'card_created',
            card_id=card.pk, list_id=card.list.pk, title=card.title, position=card.position,
        )
        messages.success(request, f'Tarjeta "{card.title}" restaurada.')
    return redirect('board_archived', pk=board.pk)


@login_required
def card_delete_permanent(request, pk):
    card = get_object_or_404(Card, pk=pk, is_archived=True)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        card.delete()
        messages.success(request, 'Tarjeta eliminada definitivamente.')
    return redirect('board_archived', pk=board.pk)
