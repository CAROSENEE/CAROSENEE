"""
Approximate "GitHub worth" updater.

NOTE: This is NOT the github-worth.vercel.app calculation (that site has no
documented public API). It is a separate estimate based on public stats:

    worth = 0.5 * contributions + 0.1 * followers + 0.3 * stars

Only the text between <!--WORTH:START--> and <!--WORTH:END--> in README.md is
changed. Everything else in the README is left untouched.
"""
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GH_USER", "CAROSENEE")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.environ.get("README_PATH", "README.md")

W_CONTRIB, W_FOLLOWER, W_STAR = 0.5, 0.1, 0.3


def request(url, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "worth-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def get_followers():
    return request(f"https://api.github.com/users/{USER}")["followers"]


def get_stars():
    """Total stars on public, non-fork repos owned by the user."""
    total, page = 0, 1
    while True:
        repos = request(
            f"https://api.github.com/users/{USER}/repos"
            f"?type=owner&per_page=100&page={page}"
        )
        if not repos:
            break
        total += sum(r["stargazers_count"] for r in repos if not r["fork"])
        page += 1
    return total


def get_contributions():
    """Contributions in the last year (GitHub contribution calendar)."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar { totalContributions }
        }
      }
    }"""
    res = request(
        "https://api.github.com/graphql",
        {"query": query, "variables": {"login": USER}},
    )
    if "errors" in res:
        raise RuntimeError(f"GraphQL error: {res['errors']}")
    return res["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["totalContributions"]


def main():
    followers = get_followers()
    stars = get_stars()
    contributions = get_contributions()

    worth = (
        contributions * W_CONTRIB + followers * W_FOLLOWER + stars * W_STAR
    )
    value = f"{worth:.2f}"
    print(
        f"contributions={contributions} followers={followers} "
        f"stars={stars} -> worth=${value}"
    )

    badge = (
        f"https://img.shields.io/badge/GitHub%20Worth-%24{value}-blue"
        f"?style=flat"
    )
    block = f'<!--WORTH:START--> <img src="{badge}" alt="GitHub Worth (estimate)" /> <!--WORTH:END-->'

    with open(README, "r", encoding="utf-8") as f:
        text = f.read()

    pattern = re.compile(r"<!--WORTH:START-->.*?<!--WORTH:END-->", re.S)
    if not pattern.search(text):
        sys.exit(
            "README.md-তে <!--WORTH:START--> ... <!--WORTH:END--> marker পাওয়া যায়নি."
        )

    new_text = pattern.sub(lambda _: block, text, count=1)
    if new_text != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_text)
        print("README updated.")
    else:
        print("No change.")


if __name__ == "__main__":
    main()
