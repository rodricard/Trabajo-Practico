from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import RegisterForm


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
    owned_count = request.user.owned_boards.count()
    member_count = request.user.board_memberships.count()
    assigned_cards = request.user.assigned_cards.select_related('list__board').order_by('due_date')
    return render(request, 'accounts/profile.html', {
        'owned_count': owned_count,
        'member_count': member_count,
        'assigned_cards': assigned_cards,
    })
