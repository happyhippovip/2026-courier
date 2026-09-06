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
        print("  communities                   - List communities")
        print("  exit                          - Exit console\n")
