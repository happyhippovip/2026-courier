import unittest
import os
import json
import zipfile
import tarfile
import io
import tempfile
import threading
import time
from http.server import HTTPServer
from datetime import datetime

from social_platform.core.models import (
    User, Discussion, Community, Channel, Course, StudyGroup,
    CourseResource, DirectMessage, ContentInteraction,
    DossierFormat, DossierType, TransformationStyle,
    TransformationOptions, DossierSection, TransformationDossier,
    ExportPackageManifest, ExportPackage
)
from social_platform.core.database import SocialDatabase
from social_platform.core.transformer import (
    ContentTransformer, anonymize_text, compute_sha256,
    build_dossier_from_sections, package_archive
)
import social_platform.api.server as api_server
from social_platform.client.client import SocialPlatformClient
from social_platform.client.session import UserSession
from social_platform.client.cli import SocialCLI


class TestContentTransformer(unittest.TestCase):
    def test_pii_anonymization(self):
        raw = "Contact alice@university.edu or call 555-123-4567 or IP 192.168.1.1. Ask @prof_smith for details."
        anon = anonymize_text(raw, redact_names=True)
        self.assertNotIn("alice@university.edu", anon)
        self.assertIn("[REDACTED_EMAIL]", anon)
        self.assertNotIn("555-123-4567", anon)
        self.assertIn("[REDACTED_PHONE]", anon)
        self.assertNotIn("192.168.1.1", anon)
        self.assertIn("[REDACTED_IP]", anon)
        self.assertNotIn("@prof_smith", anon)
        self.assertIn("@user_anon", anon)

    def test_markdown_rendering(self):
        sec1 = DossierSection(title="Research Summary", section_type="summary", content="Investigating quantum error mitigation.", item_count=1)
        sec2 = DossierSection(title="Key Publications", section_type="publications", content="- Quantum Decoherence in 2026\n- Fault-tolerant Circuits", item_count=2)
        opts = TransformationOptions(format="markdown", dossier_type="research_dossier", include_frontmatter=True, include_toc=True)
        meta = {"target_id": "u_quantum", "author": "dr_feynman"}
        
        md = ContentTransformer.render_markdown("Quantum Computing Dossier", "Overview of recent papers", [sec1, sec2], meta, opts)
        self.assertIn("---", md)
        self.assertIn("dossier_type: \"research_dossier\"", md)
        self.assertIn("# Quantum Computing Dossier", md)
        self.assertIn("## Table of Contents", md)
        self.assertIn("## Research Summary", md)
        self.assertIn("Investigating quantum error mitigation.", md)
        self.assertIn("Dossier Verification & Metadata", md)

    def test_html_rendering(self):
        sec = DossierSection(title="Curriculum", section_type="courses", content="CS501: Advanced Systems", item_count=1)
        opts = TransformationOptions(format="html", dossier_type="academic_portfolio")
        html_out = ContentTransformer.render_html("Academic Curriculum", "Coursework list", [sec], {"target_id": "u_student"}, opts)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("<title>Academic Curriculum</title>", html_out)
        self.assertIn("CS501: Advanced Systems", html_out)
        self.assertIn("class=\"section-card\"", html_out)

    def test_text_and_csv_rendering(self):
        sec = DossierSection(title="Notes", section_type="notes", content="Important lecture note.\nReview chapter 4.", item_count=1)
        opts = TransformationOptions(format="text", dossier_type="user_archive")
        txt = ContentTransformer.render_text("User Archive", "Summary here", [sec], {"target_id": "u_1"}, opts)
        self.assertIn("USER ARCHIVE", txt)
        self.assertIn("Important lecture note.", txt)

        csv_out = ContentTransformer.render_csv([sec], {}, opts)
        self.assertIn("Section Title", csv_out)
        self.assertIn("Notes", csv_out)
        self.assertIn("Important lecture note.", csv_out)

    def test_build_dossier_from_sections(self):
        sec = DossierSection(title="Posts", section_type="posts", content="Post 1 content", item_count=1)
        dossier = build_dossier_from_sections(
            target_id="u_test",
            target_type="user",
            title="User Posts",
            dossier_type="user_archive",
            format_type="markdown",
            summary="All posts",
            sections=[sec],
            item_counts={"posts": 1},
            metadata={"user_id": "u_test"}
        )
        self.assertTrue(dossier.id.startswith("dos_"))
        self.assertEqual(dossier.format, "markdown")
        self.assertTrue(len(dossier.checksum) == 64)
        self.assertGreater(dossier.size_bytes, 0)
        d_dict = dossier.to_dict()
        self.assertEqual(d_dict["target_id"], "u_test")
        self.assertEqual(len(d_dict["sections"]), 1)


class TestDatabaseDossierEngine(unittest.TestCase):
    def setUp(self):
        self.db = SocialDatabase(":memory:")
        # Seed test user, discussions, replies, courses, communities, messages
        self.user = User(
            id="u_ada",
            username="ada_lovelace",
            bio="Pioneer of computational algorithms",
            school="School of Computing",
            university="University of Cambridge",
            class_year="1843",
            interests=["algorithms", "analytical_engine", "mathematics"]
        )
        self.db.create_user(self.user)

        self.disc1 = Discussion(
            id="d_alg1",
            author_id="u_ada",
            content="Analytical engine instruction sequencing and Bernoulli number calculation @babbage",
            tags=["algorithms", "computing"]
        )
        self.db.create_discussion(self.disc1)

        self.disc2 = Discussion(
            id="d_alg2",
            author_id="u_ada",
            content="On the distinction between calculation and general operational science",
            tags=["theory", "algorithms"]
        )
        self.db.create_discussion(self.disc2)

        self.reply = Discussion(
            id="d_rep1",
            author_id="u_ada",
            content="Indeed, the engine weaves algebraic patterns just as the Jacquard loom weaves flowers and leaves.",
            parent_id="d_alg1"
        )
        self.db.create_discussion(self.reply)

        # Course & Academic
        self.course = Course(
            id="crs_math101",
            code="MATH101",
            title="Foundations of Calculus and Analysis",
            instructor="Prof. De Morgan",
            term="Fall 1843",
            institution="University of Cambridge"
        )
        self.db.create_course(self.course)
        self.db.enroll_user_in_course("crs_math101", "u_ada", role="student")

        self.study_group = StudyGroup(
            id="sg_engineers",
            name="Analytical Engine Study Circle",
            description="Collaborative study of difference engine mechanisms",
            course_id="crs_math101",
            creator_id="u_ada"
        )
        self.db.create_study_group(self.study_group)

        self.resource = CourseResource(
            id="res_notes1",
            course_id="crs_math101",
            uploader_id="u_ada",
            title="Note G: Bernoulli Numbers Algorithm",
            url="https://archive.org/details/sketch-analytical-engine",
            resource_type="paper"
        )
        self.db.create_course_resource(self.resource)

        # Community
        self.comm = Community(
            id="c_pioneers",
            name="Early Computing Pioneers",
            creator_id="u_ada",
            description="Forum for algorithmic research and machine design"
        )
        self.db.create_community(self.comm)
        self.channel = Channel(id="ch_general", community_id="c_pioneers", name="general")
        self.db.create_channel(self.channel)

        # Direct Message
        self.peer = User(id="u_babbage", username="charles_babbage")
        self.db.create_user(self.peer)
        self.dm = DirectMessage(
            id="dm_1",
            sender_id="u_babbage",
            recipient_id="u_ada",
            content="Have you reviewed the new carriage gears design for the store and mill?"
        )
        self.db.send_direct_message(self.dm)

    def test_generate_user_archive_dossier(self):
        dossier = self.db.generate_user_dossier("u_ada", format="markdown", dossier_type="user_archive")
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier.dossier_type, "user_archive")
        self.assertEqual(dossier.target_id, "u_ada")
        self.assertIn("ada_lovelace", dossier.rendered_content)
        self.assertIn("Analytical engine", dossier.rendered_content)
        self.assertIn("MATH101", dossier.rendered_content)
        self.assertIn("Early Computing Pioneers", dossier.rendered_content)
        self.assertIn("Direct Messages", [s.title for s in dossier.sections])
        self.assertTrue(len(dossier.checksum) == 64)

    def test_generate_academic_portfolio_dossier(self):
        dossier = self.db.generate_academic_portfolio_dossier("u_ada", format="markdown")
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier.dossier_type, "academic_portfolio")
        self.assertIn("Foundations of Calculus and Analysis", dossier.rendered_content)
        self.assertIn("Analytical Engine Study Circle", dossier.rendered_content)
        self.assertIn("Note G: Bernoulli Numbers Algorithm", dossier.rendered_content)

    def test_generate_research_dossier_html(self):
        dossier = self.db.generate_research_dossier("u_ada", format="html")
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier.format, "html")
        self.assertIn("<!DOCTYPE html>", dossier.rendered_content)
        self.assertIn("Research &amp; Discussion Dossier: ada_lovelace", dossier.rendered_content)
        self.assertIn("Authored Research Publications &amp; Discussions", dossier.rendered_content)

    def test_generate_discussion_dossier(self):
        dossier = self.db.generate_discussion_dossier("d_alg1", format="markdown")
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier.dossier_type, "discussion_thread")
        self.assertIn("Analytical engine instruction sequencing", dossier.rendered_content)
        self.assertIn("Jacquard loom", dossier.rendered_content)
        self.assertEqual(dossier.item_counts["replies"], 1)

    def test_generate_community_dossier(self):
        dossier = self.db.generate_community_dossier("c_pioneers", format="markdown")
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier.dossier_type, "community_digest")
        self.assertIn("Early Computing Pioneers", dossier.rendered_content)
        self.assertIn("ch_general", dossier.rendered_content)

    def test_create_export_package_zip(self):
        pkg = self.db.create_export_package("u_ada", format="zip")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.manifest.format, "zip")
        self.assertGreater(pkg.manifest.total_files, 4)
        self.assertGreater(len(pkg.archive_bytes), 0)
        self.assertIsNotNone(pkg.archive_base64)

        # Inspect and extract in-memory zip
        with zipfile.ZipFile(io.BytesIO(pkg.archive_bytes), "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertIn("data_bundle.json", namelist)
            self.assertIn("archive_dossier.md", namelist)
            self.assertIn("archive_dossier.html", namelist)
            self.assertIn("academic_portfolio.md", namelist)
            self.assertIn("research_dossier.md", namelist)
            self.assertIn("content_index.csv", namelist)
            self.assertIn("README.txt", namelist)

            # Verify manifest matches contents
            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest_data["user_id"], "u_ada")
            raw_bundle = json.loads(zf.read("data_bundle.json").decode("utf-8"))
            self.assertEqual(raw_bundle["user"]["username"], "ada_lovelace")

    def test_create_export_package_tar(self):
        pkg = self.db.create_export_package("u_ada", format="tar")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.manifest.format, "tar")
        self.assertGreater(len(pkg.archive_bytes), 0)
        with tarfile.open(fileobj=io.BytesIO(pkg.archive_bytes), mode="r") as tf:
            names = tf.getnames()
            self.assertIn("manifest.json", names)
            self.assertIn("data_bundle.json", names)
            self.assertIn("archive_dossier.md", names)

    def test_transform_content_utility(self):
        res = self.db.transform_content(
            content="Linear algebra and differential equations.",
            target_format="html"
        )
        self.assertEqual(res["target_format"], "html")
        self.assertIn("<!DOCTYPE html>", res["rendered_content"])
        self.assertIn("Linear algebra and differential equations.", res["rendered_content"])
        self.assertTrue(len(res["checksum"]) == 64)


class TestAPIAndClientDossierEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure fresh in-memory database for API server
        cls.db = SocialDatabase(":memory:")
        api_server.db = cls.db

        # Seed data in cls.db
        cls.u = User(id="u_turing", username="alan_turing", university="Cambridge", interests=["cryptanalysis", "morphogenesis"])
        cls.db.create_user(cls.u)

        cls.disc = Discussion(id="d_turing1", author_id="u_turing", content="On Computable Numbers with an Application to the Entscheidungsproblem")
        cls.db.create_discussion(cls.disc)

        cls.comm = Community(id="c_crypto", name="Cryptanalysis Space", creator_id="u_turing", description="Bletchley Park research")
        cls.db.create_community(cls.comm)

        # Start background server
        cls.server = HTTPServer(('127.0.0.1', 0), api_server.SocialAPIHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

        cls.client = SocialPlatformClient(base_url=f"http://127.0.0.1:{cls.port}")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_api_export_formats(self):
        formats = self.client.get_export_formats()
        self.assertIn("supported_formats", formats)
        self.assertIn("markdown", formats["supported_formats"])
        self.assertIn("zip", formats["supported_formats"])
        self.assertIn("supported_dossier_types", formats)
        self.assertIn("academic_portfolio", formats["supported_dossier_types"])

    def test_api_user_dossier_get_and_post(self):
        # GET
        dossier = self.client.get_user_dossier("u_turing", format="markdown", dossier_type="research_dossier")
        self.assertEqual(dossier["target_id"], "u_turing")
        self.assertEqual(dossier["dossier_type"], "research_dossier")
        self.assertIn("Computable Numbers", dossier["rendered_content"])

        # POST /users/<id>/dossier
        post_dossier = self.client._request("POST", "/users/u_turing/dossier", json_data={
            "format": "html",
            "dossier_type": "user_profile"
        })
        self.assertEqual(post_dossier["format"], "html")
        self.assertIn("<!DOCTYPE html>", post_dossier["rendered_content"])

    def test_api_discussion_and_community_dossiers(self):
        d_dossier = self.client.get_discussion_dossier("d_turing1", format="markdown")
        self.assertEqual(d_dossier["target_id"], "d_turing1")
        self.assertIn("Computable Numbers", d_dossier["rendered_content"])

        c_dossier = self.client.get_community_dossier("c_crypto", format="markdown")
        self.assertEqual(c_dossier["target_id"], "c_crypto")
        self.assertIn("Cryptanalysis Space", c_dossier["rendered_content"])

    def test_api_export_package_and_download(self):
        pkg = self.client.create_export_package("u_turing", format="zip")
        self.assertIn("manifest", pkg)
        self.assertEqual(pkg["manifest"]["user_id"], "u_turing")
        self.assertIn("archive_base64", pkg)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "turing_export.zip")
            saved = self.client.download_export_package("u_turing", output_path=out_file, format="zip")
            self.assertTrue(os.path.exists(saved))
            self.assertGreater(os.path.getsize(saved), 0)
            with zipfile.ZipFile(saved, "r") as zf:
                self.assertIn("manifest.json", zf.namelist())
                self.assertIn("archive_dossier.md", zf.namelist())

    def test_api_transform_content(self):
        res = self.client.transform_content("Automata theory and state machines.", target_format="markdown")
        self.assertEqual(res["target_format"], "markdown")
        self.assertIn("Automata theory and state machines.", res["rendered_content"])

    def test_fluent_user_session_dossier(self):
        session = UserSession("u_turing", self.client)
        dossier = session.get_dossier(format="markdown", dossier_type="user_archive")
        self.assertEqual(dossier["target_id"], "u_turing")
        
        res_dos = session.get_research_dossier(format="markdown")
        self.assertEqual(res_dos["dossier_type"], "research_dossier")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_zip = os.path.join(tmpdir, "session_pack.zip")
            saved_path = session.export_package(format="zip", output_path=out_zip)
            self.assertTrue(os.path.exists(saved_path))

    def test_cli_dossier_and_export_commands(self):
        cli = SocialCLI(base_url=f"http://127.0.0.1:{self.port}")
        
        # Test dossier user
        ret = cli.run(["dossier", "user", "u_turing", "--format", "json", "--json"])
        self.assertEqual(ret, 0)

        # Test dossier discussion
        ret = cli.run(["dossier", "discussion", "d_turing1", "--format", "markdown", "--json"])
        self.assertEqual(ret, 0)

        # Test dossier community
        ret = cli.run(["dossier", "community", "c_crypto", "--format", "html", "--json"])
        self.assertEqual(ret, 0)

        # Test dossier transform
        ret = cli.run(["dossier", "transform", "--content", "Sample text", "--format", "markdown", "--json"])
        self.assertEqual(ret, 0)

        # Test export package
        ret = cli.run(["export", "package", "u_turing", "--format", "zip", "--json"])
        self.assertEqual(ret, 0)

        # Test export formats
        ret = cli.run(["export", "formats", "--json"])
        self.assertEqual(ret, 0)

        # Test user export with --format markdown
        ret = cli.run(["user", "export", "u_turing", "--format", "markdown", "--json"])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
