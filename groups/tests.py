from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import GroupMember, Notification, WorkGroup
from .utils import notify_user


class WorkGroupModelTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user('creator', password='pass12345')
        self.group = WorkGroup.objects.create(name='Grupo', created_by=self.creator)

    def test_creator_is_not_automatically_admin_without_membership(self):
        self.assertFalse(self.group.is_member(self.creator))

    def test_is_admin_requires_approved_admin_membership(self):
        member = User.objects.create_user('member', password='pass12345')
        GroupMember.objects.create(group=self.group, user=member, role='admin', status='pending')
        self.assertFalse(self.group.is_admin(member))

        GroupMember.objects.filter(user=member).update(status='approved')
        self.assertTrue(self.group.is_admin(member))

    def test_has_pending_reflects_pending_status(self):
        member = User.objects.create_user('member', password='pass12345')
        GroupMember.objects.create(group=self.group, user=member, role='member', status='pending')
        self.assertTrue(self.group.has_pending(member))
        self.assertFalse(self.group.is_member(member))


class GroupJoinApprovalFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pass12345')
        self.applicant = User.objects.create_user('applicant', password='pass12345')
        self.group = WorkGroup.objects.create(name='Grupo', created_by=self.admin)
        GroupMember.objects.create(group=self.group, user=self.admin, role='admin', status='approved')

    def test_join_creates_pending_membership_and_notifies_admins(self):
        self.client.login(username='applicant', password='pass12345')
        self.client.post(reverse('group_join', args=[self.group.pk]))

        membership = GroupMember.objects.get(group=self.group, user=self.applicant)
        self.assertEqual(membership.status, 'pending')
        self.assertTrue(
            Notification.objects.filter(user=self.admin, title__icontains='unirse').exists()
        )

    def test_cannot_join_twice(self):
        self.client.login(username='applicant', password='pass12345')
        self.client.post(reverse('group_join', args=[self.group.pk]))
        self.client.post(reverse('group_join', args=[self.group.pk]))
        self.assertEqual(GroupMember.objects.filter(group=self.group, user=self.applicant).count(), 1)

    def test_approve_notifies_applicant_and_flips_status(self):
        GroupMember.objects.create(group=self.group, user=self.applicant, role='member', status='pending')
        membership = GroupMember.objects.get(group=self.group, user=self.applicant)

        self.client.login(username='admin', password='pass12345')
        self.client.post(reverse('group_approve', args=[self.group.pk, membership.pk]))

        membership.refresh_from_db()
        self.assertEqual(membership.status, 'approved')
        self.assertTrue(
            Notification.objects.filter(user=self.applicant, title__icontains='aprobada').exists()
        )

    def test_non_admin_cannot_approve(self):
        GroupMember.objects.create(group=self.group, user=self.applicant, role='member', status='pending')
        membership = GroupMember.objects.get(group=self.group, user=self.applicant)
        outsider = User.objects.create_user('outsider', password='pass12345')

        self.client.login(username='outsider', password='pass12345')
        response = self.client.post(reverse('group_approve', args=[self.group.pk, membership.pk]))
        self.assertEqual(response.status_code, 403)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'pending')

    def test_creator_cannot_be_removed_by_another_admin(self):
        other_admin = User.objects.create_user('other_admin', password='pass12345')
        GroupMember.objects.create(group=self.group, user=other_admin, role='admin', status='approved')

        self.client.login(username='other_admin', password='pass12345')
        self.client.post(reverse('group_remove_member', args=[self.group.pk, GroupMember.objects.get(user=self.admin).pk]))

        self.assertTrue(GroupMember.objects.filter(group=self.group, user=self.admin).exists())


class NotifyUserUtilTests(TestCase):
    def test_notify_user_creates_notification_row(self):
        user = User.objects.create_user('someone', password='pass12345')
        notify_user(user, 'Un aviso', '/algun/link/')
        self.assertEqual(user.notifications.count(), 1)
        self.assertEqual(user.notifications.first().title, 'Un aviso')


class NotificationsListViewTests(TestCase):
    def test_visiting_notifications_marks_them_as_read(self):
        user = User.objects.create_user('someone', password='pass12345')
        notify_user(user, 'Un aviso', '/algun/link/')
        self.assertEqual(user.notifications.filter(is_read=False).count(), 1)

        self.client.login(username='someone', password='pass12345')
        self.client.get(reverse('notifications_list'))

        self.assertEqual(user.notifications.filter(is_read=False).count(), 0)
