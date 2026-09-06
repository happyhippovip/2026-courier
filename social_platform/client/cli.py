import sys
import json
import argparse
from typing import Optional, List, Dict, Any
from .client import SocialPlatformClient, APIError, ClientError


class SocialCLI:
    """
    Command Line Interface for interacting with the Social Platform REST API.
    """

    def __init__(self, base_url: str = "http://localhost:8000", client: Optional[SocialPlatformClient] = None):
        self.client = client or SocialPlatformClient(base_url=base_url)

    def format_output(self, data: Any, as_json: bool = False) -> str:
        """Formats output for terminal display."""
        if as_json or not isinstance(data, (dict, list)):
            return json.dumps(data, indent=2, default=str)

        if isinstance(data, list):
            if not data:
                return "No items found."
            lines = []
            for i, item in enumerate(data, 1):
                if isinstance(item, dict):
                    summary_parts = []
                    for k in ("id", "username", "name", "code", "title", "content", "status", "mode", "author_id", "created_at"):
                        if k in item and item[k] is not None:
                            val = str(item[k])
                            if len(val) > 60:
                                val = val[:57] + "..."
                            summary_parts.append(f"{k}={val}")
                    lines.append(f"[{i}] " + " | ".join(summary_parts))
                else:
                    lines.append(f"[{i}] {item}")
            return "\n".join(lines)

        if isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{k}: {json.dumps(v, default=str)}")
                else:
                    lines.append(f"{k}: {v}")
            return "\n".join(lines)

        return str(data)

    def run(self, argv: Optional[List[str]] = None) -> int:
        """Parses arguments and runs the requested command."""
        parser = self._build_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2

        if not hasattr(args, "func"):
            parser.print_help()
            return 1

        if hasattr(args, "base_url") and args.base_url:
            self.client.base_url = args.base_url.rstrip("/")

        try:
            result = args.func(args)
            output = self.format_output(result, as_json=getattr(args, "json", False))
            print(output)
            return 0
        except APIError as e:
            err_dict = {"status": "error", "code": e.status_code, "message": e.message, "data": e.data}
            if getattr(args, "json", False):
                print(json.dumps(err_dict, indent=2), file=sys.stderr)
            else:
                print(f"Error ({e.status_code}): {e.message}", file=sys.stderr)
            return 1
        except ClientError as e:
            if getattr(args, "json", False):
                print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
            else:
                print(f"Client Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            if getattr(args, "json", False):
                print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
            else:
                print(f"Unexpected Error: {e}", file=sys.stderr)
            return 2

    def _build_parser(self) -> argparse.ArgumentParser:
        common = argparse.ArgumentParser(add_help=False)
        common.add_argument("--base-url", default=None, help="API server base URL")
        common.add_argument("--json", action="store_true", help="Output response in JSON format")

        parser = argparse.ArgumentParser(
            prog="social-cli",
            description="Social Platform CLI - Client Interaction Layer",
            parents=[common]
        )

        subparsers = parser.add_subparsers(dest="command", help="Command domain")

        # ----------------------------------------------------------------------
        # USER commands
        # ----------------------------------------------------------------------
        user_p = subparsers.add_parser("user", help="User and profile management", parents=[common])
        user_subs = user_p.add_subparsers(dest="user_subcommand")

        # user create
        u_create = user_subs.add_parser("create", help="Create a user account", parents=[common])
        u_create.add_argument("--username", required=True, help="Username")
        u_create.add_argument("--id", dest="user_id", help="Explicit user ID")
        u_create.add_argument("--bio", default="", help="User bio")
        u_create.add_argument("--school", default="", help="School")
        u_create.add_argument("--university", default="", help="University")
        u_create.add_argument("--class-year", default="", help="Graduation class year")
        u_create.add_argument("--interests", nargs="*", default=[], help="List of topic interests")
        u_create.add_argument("--discoverable", action="store_true", help="Opt-in to public discovery")
        u_create.add_argument("--visibility", default="public", choices=["public", "connections_only", "private"])
        u_create.add_argument("--dm-privacy", default="everyone", choices=["everyone", "connections_only", "nobody"])
        u_create.set_defaults(func=self._cmd_user_create)

        # user get
        u_get = user_subs.add_parser("get", help="Get user by ID", parents=[common])
        u_get.add_argument("user_id", help="User ID")
        u_get.set_defaults(func=lambda a: self.client.get_user(a.user_id))

        # user profile
        u_prof = user_subs.add_parser("profile", help="Get user profile", parents=[common])
        u_prof.add_argument("user_id", help="User ID")
        u_prof.set_defaults(func=lambda a: self.client.get_profile(a.user_id))

        # user update
        u_up = user_subs.add_parser("update", help="Update user profile", parents=[common])
        u_up.add_argument("user_id", help="User ID")
        u_up.add_argument("--bio", help="New bio")
        u_up.add_argument("--school", help="New school")
        u_up.add_argument("--university", help="New university")
        u_up.add_argument("--class-year", help="New class year")
        u_up.add_argument("--interests", nargs="*", help="New interests")
        u_up.set_defaults(func=self._cmd_user_update)

        # user privacy
        u_priv = user_subs.add_parser("privacy", help="View or update privacy settings", parents=[common])
        u_priv.add_argument("user_id", help="User ID")
        u_priv.add_argument("--visibility", choices=["public", "connections_only", "private"])
        u_priv.add_argument("--dm-privacy", choices=["everyone", "connections_only", "nobody"])
        u_priv.add_argument("--discoverable", dest="is_publicly_discoverable", type=lambda x: x.lower() in ("true", "1"))
        u_priv.set_defaults(func=self._cmd_user_privacy)

        # user export
        u_exp = user_subs.add_parser("export", help="Export user data bundle or dossier", parents=[common])
        u_exp.add_argument("user_id", help="User ID")
        u_exp.add_argument("--format", default="json", choices=["json", "markdown", "html", "text", "csv", "zip", "tar"], help="Export format")
        u_exp.add_argument("--type", "--dossier-type", dest="dossier_type", default="user_archive", choices=["user_archive", "user_profile", "academic_portfolio", "research_dossier", "gdpr_package"], help="Dossier type")
        u_exp.add_argument("--style", default="standard", choices=["standard", "compact", "executive", "academic"], help="Formatting style")
        u_exp.add_argument("--anonymize", action="store_true", help="Anonymize PII in export")
        u_exp.add_argument("--package", action="store_true", help="Build complete multi-format archive package")
        u_exp.add_argument("--output", "-o", help="Write output to file path")
        u_exp.set_defaults(func=self._cmd_user_export)

        # ----------------------------------------------------------------------
        # POST commands
        # ----------------------------------------------------------------------
        post_p = subparsers.add_parser("post", help="Discussion and post management", parents=[common])
        post_subs = post_p.add_subparsers(dest="post_subcommand")

        # post create
        p_create = post_subs.add_parser("create", help="Create a discussion post", parents=[common])
        p_create.add_argument("--author-id", required=True, help="Author user ID")
        p_create.add_argument("--content", required=True, help="Post content")
        p_create.add_argument("--id", dest="discussion_id", help="Explicit discussion ID")
        p_create.add_argument("--tags", nargs="*", default=[], help="Topic tags")
        p_create.add_argument("--visibility", default="public", choices=["public", "connections_only", "private"])
        p_create.add_argument("--cw", "--content-warning", nargs="*", default=[], dest="cw", help="Content warnings")
        p_create.add_argument("--community-id", help="Community ID")
        p_create.add_argument("--channel-id", help="Channel ID")
        p_create.add_argument("--course-id", help="Course ID")
        p_create.add_argument("--study-group-id", help="Study Group ID")
        p_create.set_defaults(func=self._cmd_post_create)

        # post get
        p_get = post_subs.add_parser("get", help="Get discussion by ID", parents=[common])
        p_get.add_argument("discussion_id", help="Discussion ID")
        p_get.set_defaults(func=lambda a: self.client.get_discussion(a.discussion_id))

        # post reply
        p_rep = post_subs.add_parser("reply", help="Reply to a discussion", parents=[common])
        p_rep.add_argument("parent_id", help="Parent discussion ID")
        p_rep.add_argument("--author-id", required=True, help="Author user ID")
        p_rep.add_argument("--content", required=True, help="Reply content")
        p_rep.add_argument("--tags", nargs="*", default=[], help="Tags")
        p_rep.set_defaults(func=lambda a: self.client.reply(parent_id=a.parent_id, author_id=a.author_id, content=a.content, tags=a.tags))

        # post replies
        p_reps = post_subs.add_parser("replies", help="List replies to a discussion", parents=[common])
        p_reps.add_argument("discussion_id", help="Discussion ID")
        p_reps.set_defaults(func=lambda a: self.client.get_replies(a.discussion_id))

        # post endorse
        p_end = post_subs.add_parser("endorse", help="Endorse a discussion for value", parents=[common])
        p_end.add_argument("discussion_id", help="Discussion ID")
        p_end.add_argument("--user-id", required=True, help="Endorsing user ID")
        p_end.add_argument("--weight", type=float, help="Endorsement weight")
        p_end.add_argument("--domain", help="Academic/subject domain")
        p_end.add_argument("--category", "--value-category", dest="category", help="Endorsement value category")
        p_end.add_argument("--comment", help="Endorsement review comment")
        p_end.set_defaults(func=lambda a: self.client.endorse_discussion(a.discussion_id, a.user_id, weight=a.weight, domain=a.domain, value_category=a.category, comment=a.comment))

        # post list
        p_list = post_subs.add_parser("list", help="List all discussions", parents=[common])
        p_list.set_defaults(func=lambda a: self.client.get_all_discussions())

        # ----------------------------------------------------------------------
        # FEED commands
        # ----------------------------------------------------------------------
        feed_p = subparsers.add_parser("feed", help="Feed retrieval and reading", parents=[common])
        feed_p.add_argument("user_id", help="User ID")
        feed_p.add_argument("--mode", default="chronological", choices=["chronological", "following", "interest_matched", "community_scoped", "weighted_value", "domain_reputation"])
        feed_p.add_argument("--domain", help="Domain filter/scope for domain_reputation feed")
        feed_p.add_argument("--community-id", help="Community ID for community_scoped mode")
        feed_p.add_argument("--channel-id", help="Channel ID filter")
        feed_p.add_argument("--interests", nargs="*", help="Interest topics filter")
        feed_p.add_argument("--limit", type=int, help="Limit number of items")
        feed_p.add_argument("--offset", type=int, help="Pagination offset")
        feed_p.set_defaults(func=self._cmd_feed_view)

        # ----------------------------------------------------------------------
        # SOCIAL (connections & blocks)
        # ----------------------------------------------------------------------
        soc_p = subparsers.add_parser("social", help="Social graph, follows, and blocks", parents=[common])
        soc_subs = soc_p.add_subparsers(dest="soc_subcommand")

        # follow
        s_fol = soc_subs.add_parser("follow", help="Follow a user", parents=[common])
        s_fol.add_argument("--follower", required=True, help="Follower user ID")
        s_fol.add_argument("--followed", required=True, help="Followed user ID")
        s_fol.set_defaults(func=lambda a: self.client.follow(a.follower, a.followed))

        # unfollow
        s_unf = soc_subs.add_parser("unfollow", help="Unfollow a user", parents=[common])
        s_unf.add_argument("--follower", required=True, help="Follower user ID")
        s_unf.add_argument("--followed", required=True, help="Followed user ID")
        s_unf.set_defaults(func=lambda a: self.client.unfollow(a.follower, a.followed))

        # connections
        s_con = soc_subs.add_parser("connections", help="List following connections", parents=[common])
        s_con.add_argument("user_id", help="User ID")
        s_con.set_defaults(func=lambda a: self.client.get_connections(a.user_id))

        # block
        s_blk = soc_subs.add_parser("block", help="Block a user", parents=[common])
        s_blk.add_argument("--blocker", required=True, help="Blocker user ID")
        s_blk.add_argument("--blocked", required=True, help="Blocked user ID")
        s_blk.add_argument("--reason", help="Optional block reason")
        s_blk.set_defaults(func=lambda a: self.client.block_user(a.blocker, a.blocked, reason=a.reason))

        # unblock
        s_unblk = soc_subs.add_parser("unblock", help="Unblock a user", parents=[common])
        s_unblk.add_argument("--blocker", required=True, help="Blocker user ID")
        s_unblk.add_argument("--blocked", required=True, help="Blocked user ID")
        s_unblk.set_defaults(func=lambda a: self.client.unblock_user(a.blocker, a.blocked))

        # ----------------------------------------------------------------------
        # COMMUNITY commands
        # ----------------------------------------------------------------------
        comm_p = subparsers.add_parser("community", help="Community and channel spaces", parents=[common])
        comm_subs = comm_p.add_subparsers(dest="comm_subcommand")

        # community create
        c_cre = comm_subs.add_parser("create", help="Create a community", parents=[common])
        c_cre.add_argument("--name", required=True, help="Community name")
        c_cre.add_argument("--creator", required=True, help="Creator user ID")
        c_cre.add_argument("--desc", default="", help="Description")
        c_cre.add_argument("--private", action="store_true", help="Make community private")
        c_cre.set_defaults(func=lambda a: self.client.create_community(name=a.name, creator_id=a.creator, description=a.desc, is_private=a.private))

        # community list
        c_list = comm_subs.add_parser("list", help="List all communities", parents=[common])
        c_list.set_defaults(func=lambda a: self.client.get_all_communities())

        # community get
        c_get = comm_subs.add_parser("get", help="Get community details", parents=[common])
        c_get.add_argument("community_id", help="Community ID")
        c_get.set_defaults(func=lambda a: self.client.get_community(a.community_id))

        # community join
        c_join = comm_subs.add_parser("join", help="Join a public community", parents=[common])
        c_join.add_argument("community_id", help="Community ID")
        c_join.add_argument("--user-id", required=True, help="User ID")
        c_join.set_defaults(func=lambda a: self.client.join_community(a.community_id, a.user_id))

        # community members
        c_mem = comm_subs.add_parser("members", help="List community members", parents=[common])
        c_mem.add_argument("community_id", help="Community ID")
        c_mem.add_argument("--role", help="Filter by role (owner, admin, moderator, member)")
        c_mem.set_defaults(func=lambda a: self.client.get_community_members(a.community_id, role=a.role))

        # community request-join
        c_req = comm_subs.add_parser("request-join", help="Request to join private community", parents=[common])
        c_req.add_argument("community_id", help="Community ID")
        c_req.add_argument("--user-id", required=True, help="User ID")
        c_req.add_argument("--message", default="", help="Application message")
        c_req.set_defaults(func=lambda a: self.client.request_join_community(a.community_id, a.user_id, a.message))

        # community review-request
        c_rev = comm_subs.add_parser("review-request", help="Review join request", parents=[common])
        c_rev.add_argument("request_id", help="Join Request ID")
        c_rev.add_argument("--admin-id", required=True, help="Admin user ID")
        c_rev.add_argument("--action", choices=["approve", "reject"], default="approve", help="Action")
        c_rev.set_defaults(func=lambda a: self.client.review_join_request(a.request_id, a.admin_id, action=a.action))

        # community channel-create
        c_chan_cre = comm_subs.add_parser("create-channel", help="Create a channel in community", parents=[common])
        c_chan_cre.add_argument("community_id", help="Community ID")
        c_chan_cre.add_argument("--name", required=True, help="Channel name")
        c_chan_cre.add_argument("--desc", default="", help="Description")
        c_chan_cre.set_defaults(func=lambda a: self.client.create_channel(community_id=a.community_id, name=a.name, description=a.desc))

        # community channels
        c_chans = comm_subs.add_parser("channels", help="List channels in community", parents=[common])
        c_chans.add_argument("community_id", help="Community ID")
        c_chans.set_defaults(func=lambda a: self.client.get_channels(a.community_id))

        # ----------------------------------------------------------------------
        # ACADEMIC commands
        # ----------------------------------------------------------------------
        acad_p = subparsers.add_parser("academic", help="Academic spaces and courses", parents=[common])
        acad_subs = acad_p.add_subparsers(dest="acad_subcommand")

        # create course
        a_ccre = acad_subs.add_parser("create-course", help="Create an academic course", parents=[common])
        a_ccre.add_argument("--code", required=True, help="Course code (e.g. CS101)")
        a_ccre.add_argument("--title", required=True, help="Course title")
        a_ccre.add_argument("--institution", required=True, help="University / Institution")
        a_ccre.add_argument("--term", default="", help="Term / Semester")
        a_ccre.add_argument("--instructor", default="", help="Instructor")
        a_ccre.set_defaults(func=lambda a: self.client.create_course(code=a.code, title=a.title, institution=a.institution, term=a.term, instructor=a.instructor))

        # list courses
        a_clist = acad_subs.add_parser("list-courses", help="List courses", parents=[common])
        a_clist.add_argument("--institution", help="Filter by institution")
        a_clist.add_argument("--query", help="Search query")
        a_clist.set_defaults(func=lambda a: self.client.get_courses(institution=a.institution, query=a.query))

        # enroll
        a_enr = acad_subs.add_parser("enroll", help="Enroll into course", parents=[common])
        a_enr.add_argument("course_id", help="Course ID or Code")
        a_enr.add_argument("--user-id", required=True, help="User ID")
        a_enr.add_argument("--role", default="student", help="Role")
        a_enr.set_defaults(func=lambda a: self.client.enroll_course(a.course_id, a.user_id, role=a.role))

        # resources
        a_res = acad_subs.add_parser("resources", help="List course resources", parents=[common])
        a_res.add_argument("course_id", help="Course ID")
        a_res.set_defaults(func=lambda a: self.client.get_course_resources(a.course_id))

        # add resource
        a_addres = acad_subs.add_parser("add-resource", help="Add study resource", parents=[common])
        a_addres.add_argument("course_id", help="Course ID")
        a_addres.add_argument("--uploader-id", required=True, help="Uploader ID")
        a_addres.add_argument("--title", required=True, help="Resource title")
        a_addres.add_argument("--url", required=True, help="Resource URL")
        a_addres.add_argument("--type", default="note", help="Resource type")
        a_addres.set_defaults(func=lambda a: self.client.add_course_resource(course_id=a.course_id, uploader_id=a.uploader_id, title=a.title, url=a.url, resource_type=a.type))

        # endorse resource
        a_endres = acad_subs.add_parser("endorse-resource", help="Endorse a study resource", parents=[common])
        a_endres.add_argument("resource_id", help="Resource ID")
        a_endres.add_argument("--user-id", required=True, help="Endorser user ID")
        a_endres.add_argument("--weight", type=float, help="Endorsement weight")
        a_endres.add_argument("--domain", help="Subject domain")
        a_endres.add_argument("--category", help="Value category")
        a_endres.add_argument("--comment", help="Endorsement review comment")
        a_endres.set_defaults(func=lambda a: self.client.endorse_resource(a.resource_id, a.user_id, weight=a.weight, domain=a.domain, value_category=a.category, comment=a.comment))

        # course reputation
        a_crep = acad_subs.add_parser("reputation", help="Get course reputation metrics", parents=[common])
        a_crep.add_argument("course_id", help="Course ID")
        a_crep.set_defaults(func=lambda a: self.client.get_course_reputation(a.course_id))

        # ----------------------------------------------------------------------
        # DIRECT MESSAGING (DM)
        # ----------------------------------------------------------------------
        dm_p = subparsers.add_parser("dm", help="Direct messaging and inbox", parents=[common])
        dm_subs = dm_p.add_subparsers(dest="dm_subcommand")

        # send dm
        d_snd = dm_subs.add_parser("send", help="Send a direct message", parents=[common])
        d_snd.add_argument("--sender", required=True, help="Sender user ID")
        d_snd.add_argument("--recipient", required=True, help="Recipient user ID")
        d_snd.add_argument("--content", required=True, help="Message text")
        d_snd.set_defaults(func=lambda a: self.client.send_dm(a.sender, a.recipient, a.content))

        # conversations
        d_convs = dm_subs.add_parser("conversations", help="List DM conversations", parents=[common])
        d_convs.add_argument("user_id", help="User ID")
        d_convs.set_defaults(func=lambda a: self.client.get_conversations(a.user_id))

        # thread
        d_thrd = dm_subs.add_parser("thread", help="View message thread", parents=[common])
        d_thrd.add_argument("user1", help="First user ID")
        d_thrd.add_argument("user2", help="Second user ID")
        d_thrd.set_defaults(func=lambda a: self.client.get_messages(a.user1, a.user2))

        # ----------------------------------------------------------------------
        # MODERATION & APPEALS
        # ----------------------------------------------------------------------
        mod_p = subparsers.add_parser("mod", help="Moderation reporting and appeals", parents=[common])
        mod_subs = mod_p.add_subparsers(dest="mod_subcommand")

        # report
        m_rep = mod_subs.add_parser("report", help="Report content", parents=[common])
        m_rep.add_argument("--reporter", required=True, help="Reporter user ID")
        m_rep.add_argument("--target-type", required=True, help="Target type (discussion, user, etc.)")
        m_rep.add_argument("--target-id", required=True, help="Target ID")
        m_rep.add_argument("--reason", required=True, help="Reason")
        m_rep.add_argument("--category", default="general", help="Report category")
        m_rep.set_defaults(func=lambda a: self.client.report_content(a.reporter, a.target_type, a.target_id, a.reason, a.category))

        # resolve report
        m_res = mod_subs.add_parser("resolve-report", help="Resolve moderation report", parents=[common])
        m_res.add_argument("report_id", help="Report ID")
        m_res.add_argument("--admin-id", required=True, help="Admin user ID")
        m_res.add_argument("--action", choices=["hide", "dismiss", "quarantine", "remove", "ban"], default="hide")
        m_res.add_argument("--reason", default="", help="Resolution rationale")
        m_res.set_defaults(func=lambda a: self.client.resolve_report(a.report_id, a.admin_id, a.action, a.reason))

        # appeal
        m_app = mod_subs.add_parser("appeal", help="Appeal moderation decision", parents=[common])
        m_app.add_argument("--appellant", required=True, help="Appellant user ID")
        m_app.add_argument("--target-type", required=True, help="Target type")
        m_app.add_argument("--target-id", required=True, help="Target ID")
        m_app.add_argument("--reason", required=True, help="Appeal reason")
        m_app.set_defaults(func=lambda a: self.client.appeal(a.appellant, a.target_type, a.target_id, a.reason))

        # ----------------------------------------------------------------------
        # SEARCH
        # ----------------------------------------------------------------------
        s_p = subparsers.add_parser("search", help="Discovery and search", parents=[common])
        s_p.add_argument("query", help="Search query")
        s_p.add_argument("--type", default="all", choices=["all", "discussions", "communities", "users", "courses", "study_groups"])
        s_p.add_argument("--school", help="Filter by school / university")
        s_p.add_argument("--interest", help="Filter by interest")
        s_p.set_defaults(func=lambda a: self.client.search(a.query, search_type=a.type, school=a.school, interest=a.interest))

        # ----------------------------------------------------------------------
        # NOTIFICATIONS, PREFERENCES & PUSH
        # ----------------------------------------------------------------------
        notif_p = subparsers.add_parser("notifs", help="User notifications, preferences, and push device management", parents=[common])
        notif_subs = notif_p.add_subparsers(dest="notif_subcommand")

        n_list = notif_subs.add_parser("list", help="List notifications", parents=[common])
        n_list.add_argument("user_id", help="User ID")
        n_list.add_argument("--unread-only", action="store_true", help="Only unread")
        n_list.set_defaults(func=lambda a: self.client.get_notifications(a.user_id, unread_only=a.unread_only))

        n_cnt = notif_subs.add_parser("count", help="Get unread notification count", parents=[common])
        n_cnt.add_argument("user_id", help="User ID")
        n_cnt.set_defaults(func=lambda a: {"user_id": a.user_id, "unread_count": self.client.get_unread_notification_count(a.user_id)})

        n_read = notif_subs.add_parser("read", help="Mark notification as read", parents=[common])
        n_read.add_argument("notification_id", help="Notification ID")
        n_read.set_defaults(func=lambda a: self.client.mark_notification_read(a.notification_id))

        n_read_all = notif_subs.add_parser("read-all", help="Mark all notifications as read", parents=[common])
        n_read_all.add_argument("user_id", help="User ID")
        n_read_all.set_defaults(func=lambda a: self.client.mark_all_notifications_read(a.user_id))

        # Notification Preferences
        n_pref_get = notif_subs.add_parser("prefs-get", help="Get user notification preferences", parents=[common])
        n_pref_get.add_argument("user_id", help="User ID")
        n_pref_get.set_defaults(func=lambda a: self.client.get_notification_preferences(a.user_id))

        n_pref_set = notif_subs.add_parser("prefs-set", help="Set user notification preferences", parents=[common])
        n_pref_set.add_argument("user_id", help="User ID")
        n_pref_set.add_argument("--mentions", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--replies", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--endorsements", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--dms", "--direct-messages", dest="direct_messages", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--connections", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--push", "--push-enabled", dest="push_enabled", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--email", "--email-enabled", dest="email_enabled", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--digest", "--digest-frequency", dest="digest_frequency", choices=["instant", "daily", "weekly", "none"], default=None)
        n_pref_set.add_argument("--quiet-hours", "--quiet-hours-enabled", dest="quiet_hours_enabled", type=lambda s: s.lower() in ("true", "1", "yes"), default=None)
        n_pref_set.add_argument("--quiet-start", dest="quiet_hours_start", default=None)
        n_pref_set.add_argument("--quiet-end", dest="quiet_hours_end", default=None)
        n_pref_set.add_argument("--min-weight", dest="min_endorsement_weight", type=float, default=None)
        n_pref_set.set_defaults(func=self._cmd_set_notif_prefs)

        # Push Subscriptions
        n_push_reg = notif_subs.add_parser("push-register", help="Register a push notification subscription", parents=[common])
        n_push_reg.add_argument("user_id", help="User ID")
        n_push_reg.add_argument("endpoint", help="Push Endpoint URL")
        n_push_reg.add_argument("--p256dh", help="P256DH public key")
        n_push_reg.add_argument("--auth", help="Auth secret")
        n_push_reg.add_argument("--platform", default="web", choices=["web", "ios", "android", "cli", "desktop"])
        n_push_reg.add_argument("--device-token", dest="device_token", help="Native device token")
        n_push_reg.add_argument("--device-name", dest="device_name", help="Device name description")
        n_push_reg.set_defaults(func=lambda a: self.client.register_push_subscription(
            user_id=a.user_id,
            endpoint=a.endpoint,
            p256dh=a.p256dh,
            auth=a.auth,
            platform=a.platform,
            device_token=a.device_token,
            device_name=a.device_name
        ))

        n_push_list = notif_subs.add_parser("push-list", help="List push subscriptions for user", parents=[common])
        n_push_list.add_argument("user_id", help="User ID")
        n_push_list.add_argument("--all", action="store_true", help="Include inactive")
        n_push_list.set_defaults(func=lambda a: self.client.get_push_subscriptions(a.user_id, active_only=not a.all))

        n_push_unreg = notif_subs.add_parser("push-unregister", help="Unregister push subscription", parents=[common])
        n_push_unreg.add_argument("subscription_id", help="Subscription ID or Endpoint")
        n_push_unreg.add_argument("--user-id", help="Optional user ID")
        n_push_unreg.set_defaults(func=lambda a: self.client.unregister_push_subscription(a.subscription_id, user_id=a.user_id))

        # Dispatches
        n_disp = notif_subs.add_parser("dispatches", help="View push notification dispatches", parents=[common])
        n_disp.add_argument("user_id", help="User ID")
        n_disp.set_defaults(func=lambda a: self.client.get_dispatched_notifications(user_id=a.user_id))

        # ----------------------------------------------------------------------
        # DOSSIER commands
        # ----------------------------------------------------------------------
        dossier_p = subparsers.add_parser("dossier", help="Content transformation dossier generator", parents=[common])
        dossier_subs = dossier_p.add_subparsers(dest="dossier_subcommand")

        # dossier user
        d_user = dossier_subs.add_parser("user", help="Generate user dossier", parents=[common])
        d_user.add_argument("user_id", help="User ID")
        d_user.add_argument("--format", default="markdown", choices=["markdown", "html", "json", "text", "csv"], help="Format")
        d_user.add_argument("--type", "--dossier-type", dest="dossier_type", default="user_archive", choices=["user_archive", "user_profile", "academic_portfolio", "research_dossier", "gdpr_package"])
        d_user.add_argument("--style", default="standard", choices=["standard", "compact", "executive", "academic"])
        d_user.add_argument("--anonymize", action="store_true", help="Anonymize PII")
        d_user.add_argument("--output", "-o", help="Output file path")
        d_user.set_defaults(func=self._cmd_dossier_user)

        # dossier discussion
        d_disc = dossier_subs.add_parser("discussion", help="Generate discussion thread dossier", parents=[common])
        d_disc.add_argument("discussion_id", help="Discussion ID")
        d_disc.add_argument("--format", default="markdown", choices=["markdown", "html", "json", "text", "csv"])
        d_disc.add_argument("--style", default="standard")
        d_disc.add_argument("--anonymize", action="store_true")
        d_disc.add_argument("--output", "-o", help="Output file path")
        d_disc.set_defaults(func=self._cmd_dossier_discussion)

        # dossier community
        d_comm = dossier_subs.add_parser("community", help="Generate community digest dossier", parents=[common])
        d_comm.add_argument("community_id", help="Community ID")
        d_comm.add_argument("--format", default="markdown", choices=["markdown", "html", "json", "text", "csv"])
        d_comm.add_argument("--style", default="standard")
        d_comm.add_argument("--anonymize", action="store_true")
        d_comm.add_argument("--output", "-o", help="Output file path")
        d_comm.set_defaults(func=self._cmd_dossier_community)

        # dossier transform
        d_trans = dossier_subs.add_parser("transform", help="Transform text content between formats", parents=[common])
        d_trans.add_argument("--content", required=True, help="Input content text")
        d_trans.add_argument("--format", default="markdown", choices=["markdown", "html", "text", "json", "csv"])
        d_trans.add_argument("--output", "-o", help="Output file path")
        d_trans.set_defaults(func=self._cmd_dossier_transform)

        # ----------------------------------------------------------------------
        # EXPORT commands
        # ----------------------------------------------------------------------
        export_p = subparsers.add_parser("export", help="Packaging and export tools", parents=[common])
        export_subs = export_p.add_subparsers(dest="export_subcommand")

        # export package
        e_pkg = export_subs.add_parser("package", help="Create full multi-format archive package", parents=[common])
        e_pkg.add_argument("user_id", help="User ID")
        e_pkg.add_argument("--format", default="zip", choices=["zip", "tar"], help="Archive format")
        e_pkg.add_argument("--output", "-o", help="Save archive to file path")
        e_pkg.set_defaults(func=self._cmd_export_package)

        # export formats
        e_fmt = export_subs.add_parser("formats", help="List supported export formats", parents=[common])
        e_fmt.set_defaults(func=lambda a: self.client.get_export_formats())

        # ----------------------------------------------------------------------
        # REPUTATION commands
        # ----------------------------------------------------------------------
        rep_p = subparsers.add_parser("reputation", help="Domain reputation scoring and leaderboards", parents=[common])
        rep_subs = rep_p.add_subparsers(dest="rep_subcommand")

        # user reputation
        r_usr = rep_subs.add_parser("user", help="Get user domain reputation", parents=[common])
        r_usr.add_argument("user_id", help="User ID")
        r_usr.add_argument("--domain", help="Domain (optional, returns all if omitted)")
        r_usr.set_defaults(func=lambda a: self.client.get_user_reputation(a.user_id, domain=a.domain))

        # user reputation summary
        p_repsum = rep_subs.add_parser("summary", help="Get user reputation summary", parents=[common])
        p_repsum.add_argument("user_id", help="User ID to get summary for")
        p_repsum.set_defaults(func=lambda a: self.client.get_user_reputation_summary(a.user_id))

        # domain leaderboard
        p_lead = rep_subs.add_parser("top", help="Get domain leaderboard", parents=[common])
        p_lead.add_argument("--domain", default="general", help="Domain")
        p_lead.add_argument("--limit", type=int, default=20, help="Max entries")
        p_lead.set_defaults(func=lambda a: self.client.get_domain_leaderboard(domain=a.domain, limit=a.limit))

        # course reputation
        r_crs = rep_subs.add_parser("course", help="Get course reputation metrics", parents=[common])
        r_crs.add_argument("course_id", help="Course ID")
        r_crs.set_defaults(func=lambda a: self.client.get_course_reputation(a.course_id))

        # study group reputation
        r_sg = rep_subs.add_parser("study-group", help="Get study group reputation metrics", parents=[common])
        r_sg.add_argument("study_group_id", help="Study group ID")
        r_sg.set_defaults(func=lambda a: self.client.get_study_group_reputation(a.study_group_id))

        return parser

    # Command helper methods
    def _cmd_user_create(self, args) -> Dict[str, Any]:
        return self.client.create_user(
            username=args.username,
            user_id=args.user_id,
            bio=args.bio,
            school=args.school,
            university=args.university,
            class_year=args.class_year,
            interests=args.interests,
            is_publicly_discoverable=args.discoverable,
            visibility=args.visibility,
            dm_privacy=args.dm_privacy
        )

    def _cmd_user_update(self, args) -> Dict[str, Any]:
        kwargs = {}
        if args.bio is not None:
            kwargs["bio"] = args.bio
        if args.school is not None:
            kwargs["school"] = args.school
        if args.university is not None:
            kwargs["university"] = args.university
        if args.class_year is not None:
            kwargs["class_year"] = args.class_year
        if args.interests is not None:
            kwargs["interests"] = args.interests
        return self.client.update_profile(args.user_id, **kwargs)

    def _cmd_user_privacy(self, args) -> Dict[str, Any]:
        if any(x is not None for x in (args.visibility, args.dm_privacy, args.is_publicly_discoverable)):
            return self.client.update_privacy(
                args.user_id,
                visibility=args.visibility,
                dm_privacy=args.dm_privacy,
                is_publicly_discoverable=args.is_publicly_discoverable
            )
        return self.client.get_privacy_settings(args.user_id)

    def _cmd_post_create(self, args) -> Dict[str, Any]:
        return self.client.create_discussion(
            author_id=args.author_id,
            content=args.content,
            discussion_id=getattr(args, "discussion_id", None),
            tags=args.tags,
            visibility=args.visibility,
            content_warnings=args.cw,
            community_id=args.community_id,
            channel_id=args.channel_id,
            course_id=args.course_id,
            study_group_id=args.study_group_id
        )

    def _cmd_feed_view(self, args) -> List[Dict[str, Any]]:
        return self.client.get_feed(
            user_id=args.user_id,
            mode=args.mode,
            community_id=args.community_id,
            channel_id=args.channel_id,
            interests=args.interests,
            domain=getattr(args, "domain", None),
            limit=args.limit,
            offset=args.offset
        )

    def _cmd_set_notif_prefs(self, args) -> Any:
        updates = {}
        for field in ("mentions", "replies", "endorsements", "direct_messages", "connections", "push_enabled", "email_enabled", "digest_frequency", "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end", "min_endorsement_weight"):
            val = getattr(args, field, None)
            if val is not None:
                updates[field] = val
        return self.client.update_notification_preferences(args.user_id, **updates)

    def _cmd_user_export(self, args) -> Any:
        if getattr(args, "package", False) or args.format in ("zip", "tar"):
            pkg = self.client.create_export_package(args.user_id, format=args.format if args.format in ("zip", "tar") else "zip")
            if getattr(args, "output", None):
                self.client.download_export_package(args.user_id, output_path=args.output, format=args.format if args.format in ("zip", "tar") else "zip")
                return {"status": "saved", "output_path": args.output, "package": pkg}
            return pkg
        elif args.format != "json" or getattr(args, "dossier_type", "user_archive") != "user_archive":
            dossier = self.client.get_user_dossier(
                args.user_id,
                format=args.format,
                dossier_type=getattr(args, "dossier_type", "user_archive"),
                style=getattr(args, "style", "standard"),
                anonymize_pii=getattr(args, "anonymize", False)
            )
            if getattr(args, "output", None):
                with open(args.output, "w") as f:
                    f.write(dossier.get("rendered_content", ""))
                return {"status": "saved", "output_path": args.output, "dossier_id": dossier.get("id")}
            return dossier
        else:
            data = self.client.export_user_data(args.user_id)
            if getattr(args, "output", None):
                with open(args.output, "w") as f:
                    json.dump(data, f, indent=2)
                return {"status": "saved", "output_path": args.output}
            return data

    def _cmd_dossier_user(self, args) -> Any:
        dossier = self.client.get_user_dossier(
            args.user_id,
            format=args.format,
            dossier_type=args.dossier_type,
            style=args.style,
            anonymize_pii=getattr(args, "anonymize", False)
        )
        if getattr(args, "output", None):
            with open(args.output, "w") as f:
                f.write(dossier.get("rendered_content", ""))
            return {"status": "saved", "output_path": args.output, "dossier_id": dossier.get("id"), "checksum": dossier.get("checksum")}
        return dossier

    def _cmd_dossier_discussion(self, args) -> Any:
        dossier = self.client.get_discussion_dossier(
            args.discussion_id,
            format=args.format,
            style=args.style,
            anonymize_pii=getattr(args, "anonymize", False)
        )
        if getattr(args, "output", None):
            with open(args.output, "w") as f:
                f.write(dossier.get("rendered_content", ""))
            return {"status": "saved", "output_path": args.output, "dossier_id": dossier.get("id"), "checksum": dossier.get("checksum")}
        return dossier

    def _cmd_dossier_community(self, args) -> Any:
        dossier = self.client.get_community_dossier(
            args.community_id,
            format=args.format,
            style=args.style,
            anonymize_pii=getattr(args, "anonymize", False)
        )
        if getattr(args, "output", None):
            with open(args.output, "w") as f:
                f.write(dossier.get("rendered_content", ""))
            return {"status": "saved", "output_path": args.output, "dossier_id": dossier.get("id"), "checksum": dossier.get("checksum")}
        return dossier

    def _cmd_dossier_transform(self, args) -> Any:
        res = self.client.transform_content(
            args.content,
            target_format=args.format
        )
        if getattr(args, "output", None):
            with open(args.output, "w") as f:
                f.write(res.get("rendered_content", ""))
            return {"status": "saved", "output_path": args.output, "checksum": res.get("checksum")}
        return res

    def _cmd_export_package(self, args) -> Any:
        if getattr(args, "output", None):
            out_file = self.client.download_export_package(args.user_id, output_path=args.output, format=args.format)
            return {"status": "saved", "output_path": out_file}
        return self.client.create_export_package(args.user_id, format=args.format)


def main(argv: Optional[List[str]] = None) -> int:
    cli = SocialCLI()
    return cli.run(argv)


if __name__ == "__main__":
    sys.exit(main())
