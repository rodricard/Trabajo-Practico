import re

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Board, BoardMember, List, Card, ChecklistItem, Comment, Label, BoardMessage, Activity
from .forms import BoardForm, ListForm, CardForm, CardQuickForm, BoardMemberForm, CommentForm, LabelForm, BoardMessageForm
from .realtime import broadcast_board_event
from groups.utils import notify_user, broadcast_user_event


MENTION_RE = re.compile(r'@(\w+)')


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


def _log_activity(board, user, text):
    Activity.objects.create(board=board, user=user, text=text)


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
    is_admin = _is_board_admin(request.user, board)
    can_write = is_admin or not board.is_chat_locked
    lists = board.lists.filter(is_archived=False).prefetch_related(
        Prefetch('cards', queryset=Card.objects.filter(is_archived=False).select_related('assigned_to'))
    )
    chat_messages = board.chat_messages.select_related('user').all()
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
        'is_board_admin': is_admin,
        'chat_messages':  chat_messages,
        'message_form':   BoardMessageForm() if can_write else None,
        'can_write':      can_write,
        'today':          timezone.localdate(),
        'archived_count': archived_count,
    })


@login_required
@require_POST
def board_message_send(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if board.is_chat_locked and not _is_board_admin(request.user, board):
        messages.error(request, 'El chat está bloqueado.')
        return redirect('board_detail', pk=pk)
    form = BoardMessageForm(request.POST)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.board = board
        msg.user = request.user
        msg.save()
    return redirect('board_detail', pk=pk)


@login_required
@require_POST
def board_toggle_chat_lock(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_board_admin(request.user, board):
        return HttpResponseForbidden()
    board.is_chat_locked = not board.is_chat_locked
    board.save()
    BoardMessage.objects.create(
        board=board, user=None, is_system=True,
        content=f'{request.user.username} {"bloqueó" if board.is_chat_locked else "desbloqueó"} el chat.'
    )
    estado = 'bloqueado' if board.is_chat_locked else 'desbloqueado'
    messages.success(request, f'Chat {estado}.')
    return redirect('board_detail', pk=pk)


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
def board_activity(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    activities = board.activities.select_related('user')[:100]
    return render(request, 'boards/board_activity.html', {
        'board': board,
        'activities': activities,
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
                    _log_activity(board, request.user, f'agregó a {user.username} al tablero')
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
            _log_activity(board, request.user, f'creó la lista "{lst.title}"')
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
        _log_activity(board, request.user, f'archivó la lista "{lst.title}"')
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
            _log_activity(lst.board, request.user, f'creó la tarjeta "{card.title}" en "{lst.title}"')
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
        _log_activity(
            board, request.user,
            f'movió la tarjeta "{card.title}" de "{source_list.title}" a "{target_list.title}"',
        )

    broadcast_board_event(board.pk, 'card_moved', card_id=card.pk, list_id=target_list.pk, position=new_position)

    return JsonResponse({'ok': True, 'card_id': card.pk, 'list_id': target_list.pk, 'position': new_position})


@login_required
def card_detail(request, pk):
    card = get_object_or_404(Card, pk=pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    checklist_items = card.checklist_items.all()
    checklist_total = checklist_items.count()
    checklist_done = checklist_items.filter(is_done=True).count()
    checklist_percent = round(checklist_done * 100 / checklist_total) if checklist_total else 0
    board_users = User.objects.filter(board_memberships__board=board)
    board_labels = board.labels.all()
    mentionable_usernames = list(
        board_users.exclude(pk=request.user.pk).values_list('username', flat=True)
    )
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
            if new_assigned != prev_assigned:
                _log_activity(board, request.user, f'asignó "{card.title}" a {new_assigned.username if new_assigned else "nadie"}')
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
        'is_board_admin': _is_board_admin(request.user, board),
        'checklist_items': checklist_items,
        'checklist_done_count': checklist_done,
        'checklist_percent': checklist_percent,
        'comment_form': CommentForm(),
        'comments':     card.comments.select_related('author').all(),
        'board_labels': board_labels,
        'mentionable_usernames': mentionable_usernames,
    })


@login_required
@require_POST
def comment_add(request, card_pk):
    card = get_object_or_404(Card, pk=card_pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    form = CommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.card = card
        c.author = request.user
        c.save()
        _log_activity(board, request.user, f'comentó en la tarjeta "{card.title}"')

        mentioned_usernames = set(MENTION_RE.findall(c.content))
        if mentioned_usernames:
            mentioned_members = User.objects.filter(
                board_memberships__board=board, username__in=mentioned_usernames,
            ).exclude(pk=request.user.pk).distinct()
            for member in mentioned_members:
                notify_user(
                    member,
                    f'{request.user.username} te mencionó en un comentario en "{card.title}"',
                    f'/boards/cards/{card.pk}/',
                )
    return redirect('card_detail', pk=card_pk)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    card = comment.card
    if comment.author != request.user and not _is_board_admin(request.user, card.list.board):
        return HttpResponseForbidden()
    comment.delete()
    return redirect('card_detail', pk=card.pk)


@login_required
@require_POST
def comment_edit(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.author != request.user:
        return HttpResponseForbidden()
    content = request.POST.get('content', '').strip()
    if content:
        comment.content = content
        comment.save(update_fields=['content'])
    return redirect('card_detail', pk=comment.card_id)


@login_required
@require_POST
def label_toggle(request, card_pk):
    card = get_object_or_404(Card, pk=card_pk)
    if not _is_member(request.user, card.list.board):
        return HttpResponseForbidden()
    label_id = request.POST.get('label_id')
    label = get_object_or_404(Label, pk=label_id, board=card.list.board)
    if label in card.labels.all():
        card.labels.remove(label)
    else:
        card.labels.add(label)
        _log_activity(card.list.board, request.user, f'etiquetó "{card.title}" con "{label.name}"')
    return redirect('card_detail', pk=card_pk)


@login_required
def search(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        user_boards = Board.objects.filter(board_members__user=request.user)
        results = Card.objects.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(list__title__icontains=query)
            | Q(list__board__title__icontains=query),
            list__board__in=user_boards,
            is_archived=False,
        ).select_related('list__board', 'assigned_to').distinct().order_by('list__board__title', 'title')
    return render(request, 'boards/search_results.html', {
        'query':   query,
        'results': results,
    })


@login_required
def label_create(request, board_pk):
    board = get_object_or_404(Board, pk=board_pk)
    if not _is_board_admin(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = LabelForm(request.POST)
        if form.is_valid():
            label = form.save(commit=False)
            label.board = board
            label.save()
            messages.success(request, 'Etiqueta creada.')
            return redirect('board_detail', pk=board_pk)
    else:
        form = LabelForm()
    return render(request, 'boards/label_form.html', {'form': form, 'board': board})


@login_required
@require_POST
def label_delete(request, pk):
    label = get_object_or_404(Label, pk=pk)
    board = label.board
    if not _is_board_admin(request.user, board):
        return HttpResponseForbidden()
    label.delete()
    messages.success(request, 'Etiqueta eliminada.')
    return redirect('board_detail', pk=board.pk)


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
        _log_activity(board, request.user, f'archivó la tarjeta "{card.title}"')
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


@login_required
@require_POST
def checklist_item_add(request, card_pk):
    card = get_object_or_404(Card, pk=card_pk)
    if not _is_member(request.user, card.list.board):
        return HttpResponseForbidden()
    text = request.POST.get('text', '').strip()
    if text:
        ChecklistItem.objects.create(
            card=card, text=text, position=card.checklist_items.count()
        )
    return redirect('card_detail', pk=card_pk)


@login_required
@require_POST
def checklist_item_toggle(request, pk):
    item = get_object_or_404(ChecklistItem, pk=pk)
    if not _is_member(request.user, item.card.list.board):
        return HttpResponseForbidden()
    item.is_done = not item.is_done
    item.save(update_fields=['is_done'])
    return redirect('card_detail', pk=item.card_id)


@login_required
@require_POST
def checklist_item_delete(request, pk):
    item = get_object_or_404(ChecklistItem, pk=pk)
    card_id = item.card_id
    if not _is_member(request.user, item.card.list.board):
        return HttpResponseForbidden()
    item.delete()
    return redirect('card_detail', pk=card_id)
