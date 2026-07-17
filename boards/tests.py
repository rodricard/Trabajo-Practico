from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from groups.models import Notification

from .consumers import BoardConsumer
from .models import Activity, Board, BoardMember, Card, ChecklistItem, Comment, Label, List


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


class ChecklistTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.outsider = User.objects.create_user('outsider', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.client.login(username='owner', password='pass12345')

    def test_add_item(self):
        self.client.post(reverse('checklist_item_add', args=[self.card.pk]), {'text': 'Paso uno'})
        self.assertEqual(self.card.checklist_items.count(), 1)
        self.assertEqual(self.card.checklist_items.first().text, 'Paso uno')

    def test_blank_text_is_ignored(self):
        self.client.post(reverse('checklist_item_add', args=[self.card.pk]), {'text': '   '})
        self.assertEqual(self.card.checklist_items.count(), 0)

    def test_toggle_flips_done_state(self):
        item = ChecklistItem.objects.create(card=self.card, text='Paso', position=0)
        self.client.post(reverse('checklist_item_toggle', args=[item.pk]))
        item.refresh_from_db()
        self.assertTrue(item.is_done)
        self.client.post(reverse('checklist_item_toggle', args=[item.pk]))
        item.refresh_from_db()
        self.assertFalse(item.is_done)

    def test_delete_removes_item(self):
        item = ChecklistItem.objects.create(card=self.card, text='Paso', position=0)
        self.client.post(reverse('checklist_item_delete', args=[item.pk]))
        self.assertFalse(ChecklistItem.objects.filter(pk=item.pk).exists())

    def test_outsider_cannot_modify_checklist(self):
        item = ChecklistItem.objects.create(card=self.card, text='Paso', position=0)
        self.client.logout()
        self.client.login(username='outsider', password='pass12345')

        response = self.client.post(reverse('checklist_item_toggle', args=[item.pk]))
        self.assertEqual(response.status_code, 403)
        item.refresh_from_db()
        self.assertFalse(item.is_done)


class CommentLabelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.member = User.objects.create_user('member', password='pass12345')
        self.outsider = User.objects.create_user('outsider', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        BoardMember.objects.create(board=self.board, user=self.member, role='member')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.client.login(username='owner', password='pass12345')

    def test_add_comment(self):
        self.client.post(reverse('comment_add', args=[self.card.pk]), {'content': 'Hola equipo'})
        self.assertEqual(self.card.comments.count(), 1)
        self.assertEqual(self.card.comments.first().author, self.owner)

    def test_author_can_delete_own_comment(self):
        comment = Comment.objects.create(card=self.card, author=self.owner, content='Borrame')
        self.client.post(reverse('comment_delete', args=[comment.pk]))
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_non_author_non_admin_cannot_delete_comment(self):
        comment = Comment.objects.create(card=self.card, author=self.owner, content='No me borres')
        self.client.logout()
        self.client.login(username='member', password='pass12345')
        response = self.client.post(reverse('comment_delete', args=[comment.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_outsider_cannot_comment(self):
        self.client.logout()
        self.client.login(username='outsider', password='pass12345')
        response = self.client.post(reverse('comment_add', args=[self.card.pk]), {'content': 'Colado'})
        self.assertEqual(response.status_code, 403)

    def test_label_create_requires_board_admin(self):
        self.client.logout()
        self.client.login(username='member', password='pass12345')
        response = self.client.post(reverse('label_create', args=[self.board.pk]), {
            'name': 'Urgente', 'color': 'urgente',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.board.labels.count(), 0)

    def test_board_admin_can_create_label(self):
        self.client.post(reverse('label_create', args=[self.board.pk]), {
            'name': 'Urgente', 'color': 'urgente',
        })
        self.assertEqual(self.board.labels.count(), 1)

    def test_label_toggle_adds_and_removes(self):
        label = Label.objects.create(name='Urgente', color='urgente', board=self.board)
        self.client.post(reverse('label_toggle', args=[self.card.pk]), {'label_id': label.pk})
        self.assertIn(label, self.card.labels.all())
        self.client.post(reverse('label_toggle', args=[self.card.pk]), {'label_id': label.pk})
        self.assertNotIn(label, self.card.labels.all())


class MentionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.member = User.objects.create_user('mariagomez', password='pass12345')
        self.outsider = User.objects.create_user('outsider', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        BoardMember.objects.create(board=self.board, user=self.member, role='member')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.client.login(username='owner', password='pass12345')

    def test_mentioning_a_board_member_notifies_them(self):
        self.client.post(reverse('comment_add', args=[self.card.pk]), {
            'content': 'Che @mariagomez, revisá esto por favor',
        })
        self.assertTrue(
            Notification.objects.filter(user=self.member, title__icontains='mencionó').exists()
        )

    def test_mentioning_yourself_does_not_notify(self):
        self.client.post(reverse('comment_add', args=[self.card.pk]), {
            'content': 'Nota para mí: @owner',
        })
        self.assertFalse(Notification.objects.filter(user=self.owner).exists())

    def test_mentioning_a_non_member_does_not_notify_or_crash(self):
        response = self.client.post(reverse('comment_add', args=[self.card.pk]), {
            'content': 'Hola @outsider, no formás parte del tablero',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Notification.objects.filter(user=self.outsider).exists())

    def test_mentioning_same_user_twice_notifies_only_once(self):
        self.client.post(reverse('comment_add', args=[self.card.pk]), {
            'content': '@mariagomez posta @mariagomez mirá esto',
        })
        self.assertEqual(
            Notification.objects.filter(user=self.member, title__icontains='mencionó').count(), 1
        )

    def test_comment_without_mention_does_not_notify(self):
        self.client.post(reverse('comment_add', args=[self.card.pk]), {
            'content': 'Comentario normal sin arrobas',
        })
        self.assertFalse(Notification.objects.exists())


class ActivityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.outsider = User.objects.create_user('outsider', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.client.login(username='owner', password='pass12345')

    def test_creating_a_list_logs_activity(self):
        self.client.post(reverse('list_create', args=[self.board.pk]), {'title': 'Nueva'})
        self.assertTrue(self.board.activities.filter(text__icontains='creó la lista').exists())

    def test_creating_a_card_logs_activity(self):
        self.client.post(reverse('card_create', args=[self.lst.pk]), {'title': 'Nueva tarjeta'})
        self.assertTrue(self.board.activities.filter(text__icontains='creó la tarjeta').exists())

    def test_archiving_a_card_logs_activity(self):
        self.client.post(reverse('card_delete', args=[self.card.pk]))
        self.assertTrue(self.board.activities.filter(text__icontains='archivó la tarjeta').exists())

    def test_commenting_logs_activity(self):
        self.client.post(reverse('comment_add', args=[self.card.pk]), {'content': 'Hola'})
        self.assertTrue(self.board.activities.filter(text__icontains='comentó').exists())

    def test_moving_card_between_lists_logs_activity(self):
        other_list = List.objects.create(title='B', board=self.board, position=1)
        self.client.post(reverse('card_move', args=[self.card.pk]), {'list_id': other_list.pk, 'position': 0})
        self.assertTrue(self.board.activities.filter(text__icontains='movió la tarjeta').exists())

    def test_reordering_within_same_list_does_not_log_activity(self):
        Card.objects.create(title='C2', list=self.lst, position=1)
        self.client.post(reverse('card_move', args=[self.card.pk]), {'list_id': self.lst.pk, 'position': 1})
        self.assertFalse(self.board.activities.filter(text__icontains='movió la tarjeta').exists())

    def test_outsider_cannot_view_activity(self):
        self.client.logout()
        self.client.login(username='outsider', password='pass12345')
        response = self.client.get(reverse('board_activity', args=[self.board.pk]))
        self.assertEqual(response.status_code, 403)

    def test_member_can_view_activity(self):
        Activity.objects.create(board=self.board, user=self.owner, text='hizo algo')
        response = self.client.get(reverse('board_activity', args=[self.board.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hizo algo')


class PresenceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.member = User.objects.create_user('mariagomez', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        BoardMember.objects.create(board=self.board, user=self.member, role='member')

    async def _connect(self, user):
        communicator = WebsocketCommunicator(BoardConsumer.as_asgi(), f'/ws/boards/{self.board.pk}/')
        communicator.scope['user'] = user
        communicator.scope['url_route'] = {'kwargs': {'board_id': str(self.board.pk)}}
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        return communicator

    async def test_connecting_broadcasts_presence_to_self(self):
        comm = await self._connect(self.owner)
        payload = await comm.receive_json_from()
        self.assertEqual(payload['event'], 'presence_update')
        self.assertEqual(payload['viewers'], ['owner'])
        await comm.disconnect()

    async def test_second_viewer_appears_for_first(self):
        comm1 = await self._connect(self.owner)
        await comm1.receive_json_from()

        comm2 = await self._connect(self.member)
        await comm2.receive_json_from()

        payload = await comm1.receive_json_from()
        self.assertEqual(payload['event'], 'presence_update')
        self.assertEqual(sorted(payload['viewers']), ['mariagomez', 'owner'])

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_disconnect_removes_viewer(self):
        comm1 = await self._connect(self.owner)
        await comm1.receive_json_from()
        comm2 = await self._connect(self.member)
        await comm2.receive_json_from()
        await comm1.receive_json_from()

        await comm2.disconnect()
        payload = await comm1.receive_json_from()
        self.assertEqual(payload['viewers'], ['owner'])

        await comm1.disconnect()


class LabelDeleteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.member = User.objects.create_user('member', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        BoardMember.objects.create(board=self.board, user=self.member, role='member')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.label = Label.objects.create(name='Urgente', color='urgente', board=self.board)
        self.card.labels.add(self.label)

    def test_admin_can_delete_label(self):
        self.client.login(username='owner', password='pass12345')
        self.client.post(reverse('label_delete', args=[self.label.pk]))
        self.assertFalse(Label.objects.filter(pk=self.label.pk).exists())

    def test_deleting_label_removes_it_from_cards(self):
        self.client.login(username='owner', password='pass12345')
        self.client.post(reverse('label_delete', args=[self.label.pk]))
        self.assertEqual(self.card.labels.count(), 0)

    def test_non_admin_cannot_delete_label(self):
        self.client.login(username='member', password='pass12345')
        response = self.client.post(reverse('label_delete', args=[self.label.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Label.objects.filter(pk=self.label.pk).exists())


class CommentEditTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.other = User.objects.create_user('other', password='pass12345')
        self.board = Board.objects.create(title='Board', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        BoardMember.objects.create(board=self.board, user=self.other, role='member')
        self.lst = List.objects.create(title='A', board=self.board, position=0)
        self.card = Card.objects.create(title='C1', list=self.lst, position=0)
        self.comment = Comment.objects.create(card=self.card, author=self.owner, content='Original')

    def test_author_can_edit_own_comment(self):
        self.client.login(username='owner', password='pass12345')
        self.client.post(reverse('comment_edit', args=[self.comment.pk]), {'content': 'Editado'})
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Editado')

    def test_blank_edit_is_ignored(self):
        self.client.login(username='owner', password='pass12345')
        self.client.post(reverse('comment_edit', args=[self.comment.pk]), {'content': '   '})
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Original')

    def test_non_author_cannot_edit_comment(self):
        self.client.login(username='other', password='pass12345')
        response = self.client.post(reverse('comment_edit', args=[self.comment.pk]), {'content': 'Hackeado'})
        self.assertEqual(response.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Original')


class SearchImprovementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pass12345')
        self.board = Board.objects.create(title='Proyecto Escuela', owner=self.owner)
        BoardMember.objects.create(board=self.board, user=self.owner, role='owner')
        self.lst = List.objects.create(title='Backlog', board=self.board, position=0)
        self.card = Card.objects.create(
            title='Tarea sin pistas', description='Revisar el modulo de pagos', list=self.lst, position=0,
        )
        self.client.login(username='owner', password='pass12345')

    def test_search_matches_description(self):
        response = self.client.get(reverse('search'), {'q': 'pagos'})
        self.assertIn(self.card, list(response.context['results']))

    def test_search_matches_list_title(self):
        response = self.client.get(reverse('search'), {'q': 'Backlog'})
        self.assertIn(self.card, list(response.context['results']))

    def test_search_matches_board_title(self):
        response = self.client.get(reverse('search'), {'q': 'Proyecto Escuela'})
        self.assertIn(self.card, list(response.context['results']))
