import unittest
from datetime import datetime, timedelta
from social_platform.core.models import User, Connection, Discussion, FeedItem
from social_platform.core.feed import (
    generate_chronological_feed, generate_following_feed,
    generate_interest_matched_feed, generate_community_scoped_feed,
    generate_feed, FeedService, FeedMode
)

class TestFeed(unittest.TestCase):
    def test_chronological_feed_no_algorithm(self):
        # [MOCK] Setup mock state for testing
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        
        conn = Connection(follower_id="u1", followed_id="u2")
        
        now = datetime.utcnow()
        d1 = Discussion(id="d1", author_id="u2", content="Hello", created_at=now - timedelta(hours=2))
        d2 = Discussion(id="d2", author_id="u1", content="My post", created_at=now - timedelta(hours=1))
        d3 = Discussion(id="d3", author_id="u2", content="Newest post", created_at=now)
        
        feed = generate_chronological_feed("u1", [conn], [d1, d2, d3])
        
        self.assertEqual(len(feed), 3)
        self.assertEqual(feed[0].id, "d3")
        self.assertEqual(feed[1].id, "d2")
        self.assertEqual(feed[2].id, "d1")
        self.assertIn("mode:chronological", feed[0].explanation_tags)

    def test_following_feed(self):
        now = datetime.utcnow()
        conn = Connection(follower_id="u1", followed_id="u2")
        d1 = Discussion(id="d1", author_id="u2", content="Followed user post", created_at=now - timedelta(hours=1))
        d2 = Discussion(id="d2", author_id="u3", content="Stranger post", created_at=now)
        d3 = Discussion(id="d3", author_id="u1", content="My own post", created_at=now)

        feed = generate_following_feed("u1", [conn], [d1, d2, d3])
        self.assertEqual(len(feed), 2)
        feed_ids = [d.id for d in feed]
        self.assertIn("d1", feed_ids)
        self.assertIn("d3", feed_ids)
        self.assertNotIn("d2", feed_ids)

    def test_interest_matched_feed(self):
        now = datetime.utcnow()
        d1 = Discussion(id="d1", author_id="u2", content="Exploring quantum computing breakthroughs", created_at=now)
        d2 = Discussion(id="d2", author_id="u3", content="Web frontend development in CSS", created_at=now)
        d3 = Discussion(id="d3", author_id="u4", content="Quantum mechanics physics concepts", created_at=now, value_endorsements=5)

        feed = generate_interest_matched_feed("u1", ["quantum", "physics"], [d1, d2, d3])
        self.assertEqual(len(feed), 2)
        self.assertEqual(feed[0].id, "d3")  # Matched 2 interests + endorsements -> higher score
        self.assertEqual(feed[1].id, "d1")  # Matched 1 interest
        self.assertIn("matched_interest:quantum", feed[0].explanation_tags)
        self.assertIn("matched_interest:physics", feed[0].explanation_tags)

    def test_community_scoped_feed(self):
        now = datetime.utcnow()
        d1 = Discussion(id="d1", author_id="u2", content="Post in Comm 1", community_id="c1", created_at=now)
        d2 = Discussion(id="d2", author_id="u3", content="Post in Comm 2", community_id="c2", created_at=now)
        d3 = Discussion(id="d3", author_id="u4", content="General post without community", created_at=now)

        feed = generate_community_scoped_feed("u1", ["c1"], [d1, d2, d3])
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0].id, "d1")
        self.assertIn("mode:community_scoped", feed[0].explanation_tags)
        self.assertIn("community:c1", feed[0].explanation_tags)


if __name__ == "__main__":
    unittest.main()

