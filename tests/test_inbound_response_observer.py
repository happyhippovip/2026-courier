#!/usr/bin/env python3
"""Test suite for InboundResponseObserver & 11-State Classifier."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.inbound_response_observer import InboundResponseObserver, ResponseClassification


class TestInboundResponseObserver(unittest.TestCase):
    def setUp(self):
        self.observer = InboundResponseObserver()

    def test_01_classification_positive_interest(self):
        """Positive buyer signals classify as POSITIVE_INTEREST."""
        cls, conf = self.observer.classify_message_text("Re: Reliability Check", "Sounds good, please send invoice and payment link.")
        self.assertEqual(cls, ResponseClassification.POSITIVE_INTEREST)
        self.assertGreaterEqual(conf, 0.9)

    def test_02_classification_question_and_scope(self):
        """Questions and scope modifications classify accurately."""
        cls_q, _ = self.observer.classify_message_text("Question", "How does it work and what do you need from us?")
        self.assertEqual(cls_q, ResponseClassification.QUESTION)

        cls_s, _ = self.observer.classify_message_text("Scope", "Can we include multi-repo workflows in the check?")
        self.assertEqual(cls_s, ResponseClassification.SCOPE_REQUEST)

    def test_03_classification_bounce_and_autoreply_ignored(self):
        """Bounces and auto-replies classify correctly and are not buyer interest."""
        cls_b, _ = self.observer.classify_message_text("Delivery Status Notification (Failure)", "Undeliverable mail to recipient.")
        self.assertEqual(cls_b, ResponseClassification.BOUNCE)

        cls_a, _ = self.observer.classify_message_text("Automatic reply: Out of Office", "I am away from my email until next week.")
        self.assertEqual(cls_a, ResponseClassification.AUTO_REPLY)

    def test_04_classification_unsubscribe_and_objections(self):
        """Opt-outs, price objections, and not-now classify accurately."""
        cls_u, _ = self.observer.classify_message_text("Stop", "Please unsubscribe and remove me.")
        self.assertEqual(cls_u, ResponseClassification.UNSUBSCRIBE_OR_STOP)

        cls_p, _ = self.observer.classify_message_text("Re: Offer", "It is too expensive for our current budget.")
        self.assertEqual(cls_p, ResponseClassification.PRICE_OBJECTION)

        cls_n, _ = self.observer.classify_message_text("Re: Offer", "Not right now, please check back next quarter.")
        self.assertEqual(cls_n, ResponseClassification.NOT_NOW)


if __name__ == "__main__":
    unittest.main()
