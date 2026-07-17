import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserProfile


class UserProfileSignalTests(TestCase):
    def test_creating_a_user_auto_creates_a_profile_and_token(self):
        user = User.objects.create_user('someone', password='pass12345')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertTrue(hasattr(user, 'auth_token'))


class RegisterViewTests(TestCase):
    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(reverse('register'), {
            'username': 'nuevo',
            'email': 'nuevo@test.com',
            'password1': 'contraseñaSegura123',
            'password2': 'contraseñaSegura123',
        })
        self.assertTrue(User.objects.filter(username='nuevo').exists())
        self.assertEqual(response.status_code, 302)

    def test_cannot_register_duplicate_username(self):
        User.objects.create_user('existente', password='pass12345')
        response = self.client.post(reverse('register'), {
            'username': 'existente',
            'email': 'otro@test.com',
            'password1': 'contraseñaSegura123',
            'password2': 'contraseñaSegura123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username='existente').count(), 1)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alguien', password='pass12345')
        self.client.login(username='alguien', password='pass12345')

    def test_profile_page_loads(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('overdue_count', response.context)
        self.assertIn('completed_count', response.context)


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'alguien', password='pass12345', email='viejo@test.com'
        )
        self.other = User.objects.create_user('otro', password='pass12345')
        self.client.login(username='alguien', password='pass12345')

    def test_change_email(self):
        self.client.post(reverse('profile_edit'), {
            'email': 'nuevo@test.com', 'change_email': '1',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'nuevo@test.com')

    def test_change_username_success(self):
        self.client.post(reverse('profile_edit'), {
            'username': 'nuevo_nombre', 'change_username': '1',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'nuevo_nombre')

    def test_cannot_change_username_to_one_already_taken(self):
        self.client.post(reverse('profile_edit'), {
            'username': 'otro', 'change_username': '1',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'alguien')

    def test_cannot_change_username_to_invalid_characters(self):
        self.client.post(reverse('profile_edit'), {
            'username': 'nombre con espacios!!', 'change_username': '1',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'alguien')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileAvatarTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._overridden_settings['MEDIA_ROOT'], ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user('alguien', password='pass12345')
        self.client.login(username='alguien', password='pass12345')

    def _make_image(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (10, 10), color=(255, 0, 0)).save(buf, format='PNG')
        buf.seek(0)
        buf.name = 'avatar.png'
        return buf

    def test_upload_avatar(self):
        self.client.post(reverse('profile_edit'), {
            'avatar': self._make_image(), 'change_avatar': '1',
        })
        self.user.profile.refresh_from_db()
        self.assertTrue(bool(self.user.profile.avatar))

    def test_remove_avatar(self):
        self.client.post(reverse('profile_edit'), {
            'avatar': self._make_image(), 'change_avatar': '1',
        })
        self.client.post(reverse('profile_edit'), {'remove_avatar': '1'})
        self.user.profile.refresh_from_db()
        self.assertFalse(bool(self.user.profile.avatar))
