from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from groups.models import Notification

from .models import Board, BoardMember, Card, Label, List


class BoardModelTests(TestCase):
    def test_list_ordering_respects_position(self):
        owner = User.objects.create_user('owner', password='pass12345')
        board = Board.objects.create(title='Board', owner=owner)
        second = List.objects.create(title='Second', board=board, position=1)
        first = List.objects.create(title='First', board=board, position=0)
        self.assertEqual(list(board.lists.all()), [first, second])

    def test_label_hex_color_known_and_unknown(self):
        owner = User.objects.create_user('owner', password='pass12345')
        board = Board.objects.create(title='Board', owner=owner)
        label = Label.objects.create(name='Urgente', color='urgente', board=board)
        self.assertEqual(label.hex_color, '#eb5a46')
        label.color = 'no-existe'
        self.assertEqual(label.hex_color, '#dfe1e6')


class BoardAccessControlTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.outsider = User.objects.create_user('outsider', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')

    def test_non_member_cannot_view_board(self):
        self.client.login(username='outsider', password='pass12345')
        response = self.client.get(reverse('board_detail', args=[self.board.pk]))
        self.assertEqual(response.status_code, 403)

    def test_member_can_view_board(self):
        self.client.login(username='owner', password='pass12345')
        response = self.client.get(reverse('board_detail', args=[self.board.pk]))
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_manage_members(self):
        member = User.objects.create_user('member', password='pass12345')
        BoardMember.objects.create(board=self.board, user=member, role='member')
        self.client.login(username='member', password='pass12345')
        response = self.client.get(reverse('board_members', args=[self.board.pk]))
        self.assertEqual(response.status_code, 403)


class CardMoveReorderTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        self.list_a = List.objects.create(title='A', board=self.board, position=0)
        self.list_b = List.objects.create(title='B', board=self.board, position=1)
        self.card1 = Card.objects.create(title='C1', list=self.list_a, position=0)
        self.card2 = Card.objects.create(title='C2', list=self.list_a, position=1)
        self.card3 = Card.objects.create(title='C3', list=self.list_b, position=0)
        self.client.login(username='owner', password='pass12345')

    def test_move_card_to_another_list_reindexes_both_lists(self):
        url = reverse('card_move', args=[self.card2.pk])
        response = self.client.post(url, {'list_id': self.list_b.pk, 'position': 0})
        self.assertEqual(response.status_code, 200)

        self.card1.refresh_from_db()
        self.card2.refresh_from_db()
        self.card3.refresh_from_db()

        self.assertEqual(self.card1.position, 0)
        self.assertEqual(self.card1.list_id, self.list_a.pk)

        self.assertEqual(self.card2.list_id, self.list_b.pk)
        self.assertEqual(self.card2.position, 0)

        self.assertEqual(self.card3.list_id, self.list_b.pk)
        self.assertEqual(self.card3.position, 1)

    def test_list_reorder_updates_positions(self):
        url = reverse('list_reorder', args=[self.list_b.pk])
        response = self.client.post(url, {'position': 0})
        self.assertEqual(response.status_code, 200)

        self.list_a.refresh_from_db()
        self.list_b.refresh_from_db()
        self.assertEqual(self.list_b.position, 0)
        self.assertEqual(self.list_a.position, 1)

    def test_outsider_cannot_move_card(self):
        outsider = User.objects.create_user('outsider', password='pass12345')
        self.client.logout()
        self.client.login(username='outsider', password='pass12345')
        url = reverse('card_move', args=[self.card1.pk])
        response = self.client.post(url, {'list_id': self.list_b.pk, 'position': 0})
        self.assertEqual(response.status_code, 403)


class NotificationTriggerTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.assignee = User.objects.create_user('assignee', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        BoardMember.objects.create(board=self.board, user=self.assignee, role='member')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.client.login(username='owner', password='pass12345')

    def test_assigning_card_to_other_user_creates_notification(self):
        url = reverse('card_detail', args=[self.card.pk])
        self.client.post(url, {
            'title': self.card.title,
            'description': '',
            'due_date': '',
            'assigned_to': self.assignee.pk,
            'list': self.lst.pk,
        })
        self.assertTrue(
            Notification.objects.filter(user=self.assignee, title__icontains='asignó').exists()
        )

    def test_assigning_card_to_self_does_not_notify(self):
        url = reverse('card_detail', args=[self.card.pk])
        self.client.post(url, {
            'title': self.card.title,
            'description': '',
            'due_date': '',
            'assigned_to': self.owner.pk,
            'list': self.lst.pk,
        })
        self.assertFalse(Notification.objects.filter(user=self.owner).exists())

    def test_adding_member_notifies_them(self):
        newcomer = User.objects.create_user('newcomer', password='pass12345')
        url = reverse('board_members', args=[self.board.pk])
        self.client.post(url, {'username': 'newcomer'})
        self.assertTrue(
            Notification.objects.filter(user=newcomer, title__icontains='agregó').exists()
        )


class BoardMemberSearchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        User.objects.create_user('juanperez', password='pass12345')
        User.objects.create_user('mariagomez', password='pass12345')
        self.client.login(username='owner', password='pass12345')

    def test_search_matches_partial_username(self):
        url = reverse('board_member_search', args=[self.board.pk])
        response = self.client.get(url, {'q': 'juan'})
        self.assertEqual(response.json()['results'], ['juanperez'])

    def test_search_requires_minimum_length(self):
        url = reverse('board_member_search', args=[self.board.pk])
        response = self.client.get(url, {'q': 'j'})
        self.assertEqual(response.json()['results'], [])

    def test_search_excludes_existing_members(self):
        BoardMember.objects.create(
            board=self.board, user=User.objects.get(username='juanperez'), role='member'
        )
        url = reverse('board_member_search', args=[self.board.pk])
        response = self.client.get(url, {'q': 'juan'})
        self.assertEqual(response.json()['results'], [])


class ArchiveInsteadOfDeleteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card1 = Card.objects.create(title='C1', list=self.lst, position=0)
        self.card2 = Card.objects.create(title='C2', list=self.lst, position=1)
        self.client.login(username='owner', password='pass12345')

    def test_deleting_a_card_archives_it_instead_of_removing_it(self):
        self.client.post(reverse('card_delete', args=[self.card2.pk]))
        self.card2.refresh_from_db()
        self.assertTrue(self.card2.is_archived)
        self.assertTrue(Card.objects.filter(pk=self.card2.pk).exists())

    def test_archived_card_disappears_from_board_but_stays_in_archived_view(self):
        self.client.post(reverse('card_delete', args=[self.card2.pk]))

        board_response = self.client.get(reverse('board_detail', args=[self.board.pk]))
        self.assertNotContains(board_response, f'data-card-id="{self.card2.pk}"')

        archived_response = self.client.get(reverse('board_archived', args=[self.board.pk]))
        self.assertContains(archived_response, 'C2')

    def test_deleting_a_list_cascades_archive_to_its_cards(self):
        self.client.post(reverse('list_delete', args=[self.lst.pk]))
        self.lst.refresh_from_db()
        self.card1.refresh_from_db()
        self.assertTrue(self.lst.is_archived)
        self.assertTrue(self.card1.is_archived)

    def test_restoring_a_card_also_restores_its_archived_list(self):
        self.client.post(reverse('list_delete', args=[self.lst.pk]))
        self.client.post(reverse('card_unarchive', args=[self.card1.pk]))

        self.lst.refresh_from_db()
        self.card1.refresh_from_db()
        self.assertFalse(self.lst.is_archived)
        self.assertFalse(self.card1.is_archived)

    def test_cannot_permanently_delete_a_card_that_is_not_archived(self):
        response = self.client.post(reverse('card_delete_permanent', args=[self.card1.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Card.objects.filter(pk=self.card1.pk).exists())

    def test_permanently_deleting_an_archived_card_removes_it(self):
        self.client.post(reverse('card_delete', args=[self.card2.pk]))
        self.client.post(reverse('card_delete_permanent', args=[self.card2.pk]))
        self.assertFalse(Card.objects.filter(pk=self.card2.pk).exists())

    def test_archived_cards_excluded_from_search(self):
        self.client.post(reverse('card_delete', args=[self.card2.pk]))
        response = self.client.get(reverse('search'), {'q': 'C2'})
        self.assertNotIn(self.card2, list(response.context['results']))
