import os
from jira import JIRA

# Initialize JIRA client with the same settings as ai_service
url = "https://ginolt.atlassian.net"
user = os.environ.get("JIRA_USER", "greey.lt@gmail.com") # fallback or we can just try to make a generic request
# Wait, I don't have the API token. I can't easily test against ginolt.atlassian.net without credentials.
