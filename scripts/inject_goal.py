import sys
from idea_inbox import IdeaInbox

def main():
    if len(sys.argv) < 2:
        print("Usage: python inject_goal.py <goal_text>")
        sys.exit(1)
    
    goal_text = sys.argv[1]
    inbox = IdeaInbox()
    idea = inbox.add_idea(raw_text=goal_text)
    print(f"Goal injected successfully. ID: {idea['idea_id']}")

if __name__ == "__main__":
    main()
