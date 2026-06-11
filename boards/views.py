from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Board, BoardMember, List, Card
from .forms import BoardForm, ListForm, CardForm, CardQuickForm, BoardMemberForm


def _is_member(user, board):
    return board.board_members.filter(user=user).exists()


def _is_owner(user, board):
    return board.owner == user


def _is_board_admin(user, board):
    return board.board_members.filter(user=user, role__in=['owner', 'admin']).exists()


@login_required
def board_list(request):
    owned = Board.objects.filter(owner=request.user)
    member_of = Board.objects.filter(board_members__user=request.user).exclude(owner=request.user)

    today = timezone.localdate()
    mis_cards = Card.objects.filter(assigned_to=request.user)

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
    lists = board.lists.prefetch_related('cards__assigned_to').all()
    return render(request, 'boards/board_detail.html', {
        'board':          board,
        'lists':          lists,
        'list_form':      ListForm(),
        'card_form':      CardQuickForm(),
        'is_owner':       _is_owner(request.user, board),
        'is_board_admin': _is_board_admin(request.user, board),
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
    return redirect('board_detail', pk=board_pk)


@login_required
def list_delete(request, pk):
    lst = get_object_or_404(List, pk=pk)
    board = lst.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    if request.method == 'POST':
        lst.delete()
    return redirect('board_detail', pk=board.pk)


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
            card.position = lst.cards.count()
            card.save()
    return redirect('board_detail', pk=lst.board.pk)


@login_required
def card_detail(request, pk):
    card = get_object_or_404(Card, pk=pk)
    board = card.list.board
    if not _is_member(request.user, board):
        return HttpResponseForbidden()
    board_users = User.objects.filter(board_memberships__board=board)
    if request.method == 'POST':
        form = CardForm(request.POST, instance=card)
        form.fields['assigned_to'].queryset = board_users
        if form.is_valid():
            form.save()
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
        card.delete()
    return redirect('board_detail', pk=board.pk)
