import sys
from typing import Optional
from .client import SocialPlatformClient
from .session import UserSession


class InteractiveConsole:
    """
    Interactive terminal console for running human user journeys.
    """

    def __init__(self, base_url: str = "http://localhost:8000", client: Optional[SocialPlatformClient] = None):
        self.client = client or SocialPlatformClient(base_url=base_url)
        self.session: Optional[UserSession] = None

    def start(self):
        """Starts interactive user console loop."""
        print("==================================================")
        print("  Next-Generation Social Platform - User Console  ")
        print("==================================================")
        print("Type 'help' for commands, 'exit' to quit.\n")

        while True:
            try:
                prompt = f"[{self.session.user_id if self.session else 'guest'}] > "
                cmd = input(prompt).strip()
                if not cmd:
                    continue
                if cmd in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break
                self._dispatch(cmd)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break
            except Exception as e:
                print(f"Error: {e}")

    def _dispatch(self, line: str):
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            self._print_help()
        elif cmd == "login":
            if not args:
                print("Usage: login <user_id>")
                return
            user_id = args[0]
            try:
                user = self.client.get_user(user_id)
                self.session = self.client.session(user_id)
                print(f"Logged in as @{user.get('username')} ({user_id})")
            except Exception as e:
                print(f"Login failed: {e}")
        elif cmd == "whoami":
            if self.session:
                print(f"Active session: {self.session.user_id}")
            else:
                print("Not logged in. Use: login <user_id>")
        elif cmd == "feed":
            if not self.session:
                print("Please login first.")
                return
            mode = args[0] if args else "chronological"
            feed = self.session.feed(mode=mode)
            print(f"\n--- Feed ({mode}) [{len(feed)} items] ---")
            for item in feed:
                content = item.get("content") or item.get("discussion", {}).get("content", "")
                author = item.get("author_id") or item.get("discussion", {}).get("author_id", "")
                disc_id = item.get("id") or item.get("discussion", {}).get("id", "")
                val = item.get("value_endorsements", item.get("discussion", {}).get("value_endorsements", 0))
                print(f"- [{disc_id}] @{author}: {content} (Value endorsements: {val})")
        elif cmd == "post":
            if not self.session:
                print("Please login first.")
                return
            if not args:
                print("Usage: post <message text>")
                return
            text = " ".join(args)
            res = self.session.post(content=text)
            print(f"Post created! ID: {res.get('id')}")
        elif cmd == "endorse":
            if not self.session:
                print("Please login first.")
                return
            if not args:
                print("Usage: endorse <discussion_id>")
                return
            self.session.endorse(args[0])
            print(f"Endorsed discussion {args[0]}")
        elif cmd == "follow":
            if not self.session:
                print("Please login first.")
                return
            if not args:
                print("Usage: follow <target_user_id>")
                return
            self.session.follow(args[0])
            print(f"Followed user {args[0]}")
        elif cmd == "dms":
            if not self.session:
                print("Please login first.")
                return
            convs = self.session.get_conversations()
            print(f"\n--- Conversations ({len(convs)}) ---")
            for c in convs:
                print(f"With @{c.get('other_user_id')}: {c.get('unread_count', 0)} unread")
        elif cmd == "msg":
            if not self.session:
                print("Please login first.")
                return
            if len(args) < 2:
                print("Usage: msg <recipient_user_id> <message text>")
                return
            recip = args[0]
            msg_text = " ".join(args[1:])
            self.session.send_message(recip, msg_text)
            print("Message sent.")
        elif cmd == "communities":
            comms = self.client.get_all_communities()
            print(f"\n--- Communities ({len(comms)}) ---")
            for c in comms:
                print(f"[{c.get('id')}] {c.get('name')}: {c.get('description', '')}")
        elif cmd in ("notifs", "notifications"):
            if not self.session:
                print("Please login first.")
                return
            unread_only = "--unread" in args or "-u" in args or (len(args) > 0 and args[0] == "unread")
            notifs = self.session.get_notifications(unread_only=unread_only)
            print(f"\n--- Notifications ({len(notifs)}) ---")
            for n in notifs:
                status = "UNREAD" if not n.get("is_read") else "READ"
                print(f"[{status}] [{n.get('id')}] Type: {n.get('type')} | From: {n.get('actor_id')} | {n.get('content')}")
        elif cmd in ("notif-prefs", "prefs"):
            if not self.session:
                print("Please login first.")
                return
            prefs = self.session.get_notification_preferences()
            print(f"\n--- Notification Preferences for {self.session.user_id} ---")
            print(f"  Mentions: {prefs.get('mentions')} | Replies: {prefs.get('replies')} | Endorsements: {prefs.get('endorsements')}")
            print(f"  DMs: {prefs.get('direct_messages')} | Connections: {prefs.get('connections')}")
            print(f"  Push Enabled: {prefs.get('push_enabled')} | In-App Enabled: {prefs.get('in_app_enabled')}")
            print(f"  Quiet Hours: {prefs.get('quiet_hours_enabled')} ({prefs.get('quiet_hours_start')} - {prefs.get('quiet_hours_end')})")
        elif cmd in ("push-reg", "push-register"):
            if not self.session:
                print("Please login first.")
                return
            if not args:
                print("Usage: push-reg <endpoint_url> [platform]")
                return
            ep = args[0]
            plat = args[1] if len(args) > 1 else "cli"
            sub = self.session.register_push_device(endpoint=ep, platform=plat)
            print(f"Push device registered! ID: {sub.get('id')}")
        elif cmd in ("push-list", "push-devices"):
            if not self.session:
                print("Please login first.")
                return
            subs = self.session.list_push_subscriptions()
            print(f"\n--- Registered Push Devices ({len(subs)}) ---")
            for s in subs:
                print(f"[{s.get('id')}] Platform: {s.get('platform')} | Endpoint: {s.get('endpoint')}")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")

    def _print_help(self):
        print("\nAvailable Commands:")
        print("  login <user_id>               - Switch active user")
        print("  whoami                        - Display active user session")
        print("  feed [mode]                   - View feed (chronological, following, interest_matched)")
        print("  post <text>                   - Publish discussion")
        print("  endorse <disc_id>             - Endorse discussion for value")
        print("  follow <user_id>              - Follow user")
        print("  dms                           - View active conversations")
        print("  msg <user_id> <text>          - Send direct message")
        print("  notifs [--unread]             - View notifications inbox")
        print("  notif-prefs                   - View user notification preferences")
        print("  push-reg <endpoint>           - Register push notification device")
        print("  push-list                     - List registered push devices")
        print("  communities                   - List communities")
        print("  exit                          - Exit console\n")
