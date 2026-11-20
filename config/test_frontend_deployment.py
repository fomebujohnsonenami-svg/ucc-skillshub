"""Smoke tests for a single-domain Vercel deployment."""
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


class FrontendDeploymentTests(SimpleTestCase):
    def test_landing_page_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"UCC SKILLSHUB", response.content)

    def test_existing_sign_in_page_is_preserved(self):
        response = self.client.get("/ucc_skillshub_sign_in/code.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sign In", response.content)

    def test_api_route_is_not_intercepted(self):
        response = self.client.get("/api/v1/schema/")
        self.assertNotEqual(response.status_code, 302)

    def test_secret_paths_are_not_public(self):
        for path in ("/config/settings.py", "/.env", "/.env.example", "/requirements.txt"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_frontend_css_and_js_are_collectable(self):
        for path in ("responsive.css", "skillshub-api.js", "skillbridge_student_portfolio/portfolio.js"):
            with self.subTest(path=path):
                self.assertTrue(finders.find(path))

    def test_frontend_assets_are_served_directly(self):
        for path, mime in (
            ("/responsive.css", "text/css"),
            ("/skillbridge_public_landing_page/assets/ucc-students-computer-lab.png", "image/png"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], mime)
                self.assertTrue(response.streaming)
                response.close()

    def test_login_page_has_redirect_and_verification_handler(self):
        response = self.client.get("/ucc_skillshub_sign_in/code.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"window.location.assign(DASHBOARD_PATH)", response.content)
        self.assertIn(b"async function completeOAuthLogin(", response.content)
        self.assertIn(b"saveAuthenticatedUser(response.access, response.refresh", response.content)
