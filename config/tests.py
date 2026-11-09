from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .deploy import add_render_hostname, database_config

BASE_DIR = Path("/app")


class DatabaseUrlTests(SimpleTestCase):
    def test_parses_neon_style_url(self):
        env = {
            "DATABASE_URL": "postgresql://neon_user:s3cret@ep-cool-123-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
        }
        db = database_config(env, BASE_DIR)
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(db["HOST"], "ep-cool-123-pooler.ap-southeast-1.aws.neon.tech")
        self.assertEqual(db["PORT"], "5432")
        self.assertEqual(db["NAME"], "neondb")
        self.assertEqual(db["USER"], "neon_user")
        self.assertEqual(db["PASSWORD"], "s3cret")
        self.assertEqual(
            db["OPTIONS"], {"sslmode": "require", "channel_binding": "require"}
        )
        self.assertTrue(db["DISABLE_SERVER_SIDE_CURSORS"])

    def test_explicit_port_and_encoded_password(self):
        env = {"DATABASE_URL": "postgres://u:p%40ss%2Fword@db.example.com:6543/app"}
        db = database_config(env, BASE_DIR)
        self.assertEqual(db["PORT"], "6543")
        self.assertEqual(db["PASSWORD"], "p@ss/word")
        self.assertNotIn("OPTIONS", db)
        self.assertNotIn("DISABLE_SERVER_SIDE_CURSORS", db)

    def test_connection_reuse_defaults_and_override(self):
        url = "postgresql://u:p@h.example.com/d"
        db = database_config({"DATABASE_URL": url}, BASE_DIR)
        self.assertEqual(db["CONN_MAX_AGE"], 60)
        self.assertTrue(db["CONN_HEALTH_CHECKS"])
        db = database_config({"DATABASE_URL": url, "CONN_MAX_AGE": "5"}, BASE_DIR)
        self.assertEqual(db["CONN_MAX_AGE"], 5)

    def test_database_url_wins_over_db_vars(self):
        env = {"DATABASE_URL": "postgresql://u:p@url-host/d", "DB_HOST": "other-host"}
        self.assertEqual(database_config(env, BASE_DIR)["HOST"], "url-host")

    def test_rejects_non_postgres_url(self):
        with self.assertRaises(ImproperlyConfigured):
            database_config({"DATABASE_URL": "mysql://u:p@h/d"}, BASE_DIR)

    def test_falls_back_to_db_vars(self):
        env = {"DB_HOST": "db", "DB_NAME": "n", "DB_USER": "u", "DB_PASSWORD": "p", "DB_PORT": "5433"}
        db = database_config(env, BASE_DIR)
        self.assertEqual(
            (db["HOST"], db["NAME"], db["USER"], db["PASSWORD"], db["PORT"]),
            ("db", "n", "u", "p", "5433"),
        )
        self.assertNotIn("OPTIONS", db)

    def test_db_sslmode_applies_to_db_vars(self):
        db = database_config({"DB_HOST": "db", "DB_SSLMODE": "require"}, BASE_DIR)
        self.assertEqual(db["OPTIONS"], {"sslmode": "require"})

    def test_falls_back_to_sqlite(self):
        db = database_config({}, BASE_DIR)
        self.assertEqual(db["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(db["NAME"], BASE_DIR / "db.sqlite3")
        self.assertNotIn("CONN_HEALTH_CHECKS", db)


class RenderHostnameTests(SimpleTestCase):
    def test_adds_host_and_origin(self):
        hosts, origins = ["localhost"], []
        add_render_hostname({"RENDER_EXTERNAL_HOSTNAME": "bbms-abc.onrender.com"}, hosts, origins)
        self.assertEqual(hosts, ["localhost", "bbms-abc.onrender.com"])
        self.assertEqual(origins, ["https://bbms-abc.onrender.com"])

    def test_no_duplicates(self):
        hosts = ["bbms-web.onrender.com"]
        origins = ["https://bbms-web.onrender.com"]
        add_render_hostname({"RENDER_EXTERNAL_HOSTNAME": "bbms-web.onrender.com"}, hosts, origins)
        self.assertEqual(hosts, ["bbms-web.onrender.com"])
        self.assertEqual(origins, ["https://bbms-web.onrender.com"])

    def test_noop_when_unset(self):
        hosts, origins = ["localhost"], []
        add_render_hostname({}, hosts, origins)
        self.assertEqual((hosts, origins), (["localhost"], []))
