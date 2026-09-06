import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from .models import Discussion, Connection, FeedItem


class FeedMode:
    CHRONOLOGICAL = "chronological"
    FOLLOWING = "following"
    FOLLOWING_ONLY = "following_only"
    INTEREST_MATCHED = "interest_matched"
    INTERESTS = "interests"
    COMMUNITY_SCOPED = "community_scoped"
    COMMUNITY = "community"


def extract_interest_matches(content: str, interests: List[str]) -> List[str]:
    """
    Finds which user interests match keywords in the discussion content.
    Matches are case-insensitive and transparent.
    """
    if not content or not interests:
        return []
    
    content_lower = content.lower()
    matched = []
    for interest in interests:
        if not interest or not isinstance(interest, str):
            continue
        term = interest.strip().lower()
        if not term:
            continue
        
        # Word boundary or substring match (handling hyphens and underscores)
        pattern = r'(?:\b|_)' + re.escape(term) + r'(?:\b|_)'
        if re.search(pattern, content_lower) or term in content_lower:
            if interest not in matched:
                matched.append(interest)
    return matched


def generate_chronological_feed(
    user_id: str,
    connections: List[Connection],
    all_discussions: List[Discussion],
    include_all: bool = False
) -> List[Discussion]:
    """
    Generates a chronological feed.
    By default for backwards compatibility, includes own posts and posts of followed users.
    If include_all is True, includes all accessible network discussions.
    Attaches transparent explainability tags to each item.
    """
    followed_ids = {conn.followed_id for conn in connections if conn.follower_id == user_id} if connections else set()
    
    feed_discussions = []
    for d in all_discussions:
        if include_all or d.author_id in followed_ids or d.author_id == user_id:
            tags = ["mode:chronological"]
            if d.author_id == user_id:
                tags.append("author:self")
                explanation = "Your own post in chronological feed"
            elif d.author_id in followed_ids:
                tags.extend(["following", f"following:{d.author_id}"])
                explanation = f"Author {d.author_id} is followed by you"
            else:
                tags.append("public_network")
                explanation = "Public post in chronological feed"

            d.explanation_tags = tags
            d.explanation = explanation
            feed_discussions.append(d)
    
    feed_discussions.sort(key=lambda d: d.created_at, reverse=True)
    return feed_discussions


def generate_following_feed(
    user_id: str,
    connections: List[Connection],
    all_discussions: List[Discussion]
) -> List[Discussion]:
    """
    Generates a following-only feed containing only posts from followed creators and the user.
    Transparent explainability tags indicate exact follow relationship.
    """
    followed_ids = {conn.followed_id for conn in connections if conn.follower_id == user_id} if connections else set()
    
    feed_discussions = []
    for d in all_discussions:
        if d.author_id in followed_ids or d.author_id == user_id:
            tags = ["mode:following"]
            if d.author_id == user_id:
                tags.append("author:self")
                explanation = "Your own post in following feed"
            else:
                tags.extend(["following", f"following:{d.author_id}"])
                explanation = f"Author {d.author_id} is followed by you"

            d.explanation_tags = tags
            d.explanation = explanation
            feed_discussions.append(d)
            
    feed_discussions.sort(key=lambda d: d.created_at, reverse=True)
    return feed_discussions


def generate_interest_matched_feed(
    user_id: str,
    interests: List[str],
    all_discussions: List[Discussion]
) -> List[Discussion]:
    """
    Generates an interest-matched feed ranking discussions matching the user's explicit topic interests.
    Transparent explainability tags reveal exact matched topics and scoring rationale.
    """
    feed_discussions = []
    scored_items = []
    
    for d in all_discussions:
        matches = extract_interest_matches(d.content, interests)
        if matches:
            tags = ["mode:interest_matched", "interest_match"]
            for m in matches:
                tags.append(f"matched_interest:{m}")
            
            explanation = f"Matched your interests: {', '.join(matches)}"
            d.explanation_tags = tags
            d.explanation = explanation
            
            # Transparent ranking score: match count + normalized endorsement boost
            match_score = len(matches) * 10.0 + (d.value_endorsements * 1.0)
            scored_items.append((match_score, d.created_at, d))

    # Rank primarily by match score, secondarily by recency
    scored_items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in scored_items]


def generate_community_scoped_feed(
    user_id: str,
    community_ids: List[str],
    all_discussions: List[Discussion],
    community_id: Optional[str] = None
) -> List[Discussion]:
    """
    Generates a community-scoped feed from communities the user belongs to,
    or scoped to a single specified community.
    """
    feed_discussions = []
    target_community_ids = {community_id} if community_id else set(community_ids or [])
    
    for d in all_discussions:
        if d.community_id and d.community_id in target_community_ids:
            tags = ["mode:community_scoped"]
            if community_id:
                tags.extend(["community", f"community:{d.community_id}"])
                explanation = f"Discussion scoped to community {d.community_id}"
            else:
                tags.extend(["community_member", f"community:{d.community_id}"])
                explanation = f"Discussion from your joined community {d.community_id}"

            if d.channel_id:
                tags.append(f"channel:{d.channel_id}")

            d.explanation_tags = tags
            d.explanation = explanation
            feed_discussions.append(d)
            
    feed_discussions.sort(key=lambda d: d.created_at, reverse=True)
    return feed_discussions


def generate_feed(
    user_id: str,
    all_discussions: List[Discussion],
    connections: Optional[List[Connection]] = None,
    interests: Optional[List[str]] = None,
    community_ids: Optional[List[str]] = None,
    mode: str = "chronological",
    community_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    blocked_user_ids: Optional[List[str]] = None,
    content_filters: Optional[Any] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[FeedItem]:
    """
    Unified multi-mode feed generation with explainability tags and transparent ranking.
    """
    blocked_set = set(blocked_user_ids or [])
    
    # Filter out blocked users, hidden discussions, and content matching user filter preferences
    candidate_discussions = []
    for d in all_discussions:
        if d.author_id in blocked_set or getattr(d, "is_hidden", False):
            continue
        if content_filters and d.author_id != user_id:
            if hasattr(content_filters, "matches_filters"):
                if content_filters.matches_filters(
                    text=d.content,
                    tags=getattr(d, "tags", []),
                    content_warnings=getattr(d, "content_warnings", [])
                ):
                    if getattr(content_filters, "filter_level", "hide") == "hide":
                        continue
        candidate_discussions.append(d)

    # Filter by specific channel if requested
    if channel_id:
        candidate_discussions = [d for d in candidate_discussions if d.channel_id == channel_id]

    norm_mode = (mode or "chronological").lower().replace("-", "_")

    if norm_mode in ("following", "following_only"):
        raw_feed = generate_following_feed(user_id, connections or [], candidate_discussions)
        actual_mode = FeedMode.FOLLOWING
    elif norm_mode in ("interest_matched", "interest", "interests"):
        raw_feed = generate_interest_matched_feed(user_id, interests or [], candidate_discussions)
        actual_mode = FeedMode.INTEREST_MATCHED
    elif norm_mode in ("community_scoped", "community", "communities"):
        raw_feed = generate_community_scoped_feed(user_id, community_ids or [], candidate_discussions, community_id=community_id)
        actual_mode = FeedMode.COMMUNITY_SCOPED
    else:  # chronological / all
        raw_feed = generate_chronological_feed(user_id, connections or [], candidate_discussions)
        actual_mode = FeedMode.CHRONOLOGICAL

    # Wrap in FeedItem dataclasses
    feed_items = []
    for d in raw_feed:
        matched_ints = extract_interest_matches(d.content, interests or []) if interests else []
        score = float(len(matched_ints) * 10.0 + (d.value_endorsements * 1.0)) if actual_mode == FeedMode.INTEREST_MATCHED else float(d.value_endorsements)
        
        feed_item = FeedItem(
            discussion=d,
            explanation_tags=list(getattr(d, "explanation_tags", [])),
            explanation=getattr(d, "explanation", "") or "",
            mode=actual_mode,
            score=score,
            matched_interests=matched_ints
        )
        if content_filters and d.author_id != user_id:
            if hasattr(content_filters, "matches_filters") and content_filters.matches_filters(
                text=d.content, tags=getattr(d, "tags", []), content_warnings=getattr(d, "content_warnings", [])
            ):
                feed_item.is_filtered = True
                reasons = []
                if hasattr(content_filters, "is_text_muted") and content_filters.is_text_muted(d.content):
                    reasons.append("mute_keyword")
                if hasattr(content_filters, "has_matching_warning") and content_filters.has_matching_warning(getattr(d, "tags", []) + getattr(d, "content_warnings", [])):
                    reasons.append("content_warning")
                feed_item.filter_reasons = reasons or ["filtered"]

        feed_items.append(feed_item)

    if offset is not None and offset > 0:
        feed_items = feed_items[offset:]
    if limit is not None and limit > 0:
        feed_items = feed_items[:limit]

    return feed_items


class FeedService:
    """
    FeedService provides multi-mode feed generation and filtering with full transparent explainability.
    """
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def get_feed(
        self,
        user_id: str,
        mode: str = "chronological",
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        interests: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_hidden: bool = False
    ) -> List[FeedItem]:
        """
        Fetches and generates a multi-mode feed for a given user from the database.
        """
        if not self.db:
            return []

        user = self.db.get_user(user_id)
        connections = self.db.get_connections(user_id)
        
        # User blocklist (both directions)
        blocked_ids = set(self.db.get_blocked_user_ids(user_id))
        
        # User communities
        user_comms = [c.id for c in self.db.get_user_communities(user_id)]
        
        # User interests (explicit parameter overrides profile interests)
        active_interests = interests
        if active_interests is None and user:
            active_interests = getattr(user, "interests", []) or getattr(user, "topic_interests", [])
            
        all_discussions = self.db.get_all_discussions(include_hidden=include_hidden)
        if hasattr(self.db, "can_user_view_discussion"):
            accessible_discussions = [d for d in all_discussions if self.db.can_user_view_discussion(user_id, d)]
        else:
            accessible_discussions = all_discussions
        filter_prefs = self.db.get_content_filter_preferences(user_id) if hasattr(self.db, "get_content_filter_preferences") else None
        
        return generate_feed(
            user_id=user_id,
            all_discussions=accessible_discussions,
            connections=connections,
            interests=active_interests,
            community_ids=user_comms,
            mode=mode,
            community_id=community_id,
            channel_id=channel_id,
            blocked_user_ids=list(blocked_ids),
            content_filters=filter_prefs,
            limit=limit,
            offset=offset
        )

    def get_chronological_feed(self, user_id: str, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id=user_id, mode=FeedMode.CHRONOLOGICAL, **kwargs)

    def get_following_feed(self, user_id: str, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id=user_id, mode=FeedMode.FOLLOWING, **kwargs)

    def get_interest_matched_feed(self, user_id: str, interests: Optional[List[str]] = None, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id=user_id, mode=FeedMode.INTEREST_MATCHED, interests=interests, **kwargs)

    def get_community_scoped_feed(self, user_id: str, community_id: Optional[str] = None, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id=user_id, mode=FeedMode.COMMUNITY_SCOPED, community_id=community_id, **kwargs)
