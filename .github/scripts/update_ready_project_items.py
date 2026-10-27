"""Fill missing User Story and Acceptance Criteria sections for Ready items."""

from __future__ import annotations

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
AI_API_URL = os.environ.get(
    "AI_API_URL", "https://api.openai.com/v1/chat/completions"
)
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
PROJECT_OWNER = os.environ["PROJECT_OWNER"]
PROJECT_NUMBER = int(os.environ.get("PROJECT_NUMBER", "2"))
READY_STATUS = os.environ.get("READY_STATUS", "Ready")


def post_json(url: str, payload: dict, token: str, user_agent: str) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": user_agent,
        },
        method="POST",
    )
    try:
        with urlopen(request) as response:
            return json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"HTTP request failed: {exc}") from exc


def github_graphql(query: str, variables: dict) -> dict:
    result = post_json(
        GITHUB_GRAPHQL_URL,
        {"query": query, "variables": variables},
        os.environ["GH_TOKEN"],
        "ready-project-item-updater",
    )
    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {result['errors']}")
    return result["data"]


def generate_content(title: str) -> dict:
    api_key = os.environ.get("AI_API_KEY")
    if not api_key:
        raise RuntimeError("AI_API_KEY is not configured")

    prompt = (
        "Based on this work item title, write a software requirement in "
        "Traditional Chinese. Return JSON only with this exact shape: "
        '{"user_story":"...","acceptance_criteria":["...","..."]}. '
        "The user_story must use the format: As a [role], I want [goal], "
        "so that [benefit]. Provide 3 to 5 concrete, testable criteria. "
        f"Work item title: {title}"
    )
    result = post_json(
        AI_API_URL,
        {
            "model": AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a product requirements assistant. "
                        "Write clear Traditional Chinese requirements."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        api_key,
        "ready-project-item-updater",
    )
    try:
        raw_content = str(result["choices"][0]["message"]["content"]).strip()
        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
        raw_content = re.sub(r"\s*```$", "", raw_content).strip()
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start < 0 or end < start:
            raise ValueError("JSON object not found")
        content = json.loads(raw_content[start : end + 1])
        user_story = str(content["user_story"]).strip()
        criteria = [str(item).strip() for item in content["acceptance_criteria"]]
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("AI provider returned an invalid response") from exc
    if not user_story or not criteria or any(not item for item in criteria):
        raise RuntimeError("AI provider returned empty requirements")
    return {"user_story": user_story, "acceptance_criteria": criteria}


def section(body: str, heading: str) -> str | None:
    match = re.search(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(?P<content>.*?)(?=^##\s+|\Z)",
        body,
    )
    return match.group("content").strip() if match else None


def update_body(body: str, generated: dict) -> tuple[str, bool]:
    current = body.strip()
    additions: list[str] = []
    if not section(current, "User Story"):
        additions.append(f"## User Story\n{generated['user_story']}")
    if not section(current, "Acceptance Criteria"):
        checklist = "\n".join(
            f"- [ ] {item}" for item in generated["acceptance_criteria"]
        )
        additions.append(f"## Acceptance Criteria\n{checklist}")
    if not additions:
        return body, False
    separator = "\n\n" if current else ""
    addition_text = "\n\n".join(additions)
    return f"{current}{separator}{addition_text}\n", True


PROJECT_QUERY = """
query($login: String!, $number: Int!, $after: String) {
  user(login: $login) {
    projectV2(number: $number) {
      items(first: 100, after: $after) {
        nodes {
          content {
            __typename
            ... on Issue { id title body url }
            ... on DraftIssue { id title body }
          }
          fieldValues(first: 50) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field {
                  ... on ProjectV2SingleSelectField { name }
                }
              }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""

UPDATE_ISSUE_MUTATION = """
mutation($id: ID!, $body: String!) {
  updateIssue(input: {id: $id, body: $body}) { issue { id } }
}
"""

UPDATE_DRAFT_MUTATION = """
mutation($id: ID!, $body: String!) {
  updateProjectV2DraftIssue(input: {draftIssueId: $id, body: $body}) {
    projectV2Item { id }
  }
}
"""


def main() -> int:
    updated = 0
    after = None
    while True:
        data = github_graphql(
            PROJECT_QUERY,
            {"login": PROJECT_OWNER, "number": PROJECT_NUMBER, "after": after},
        )
        items = data["user"]["projectV2"]["items"]
        for item in items["nodes"]:
            status = next(
                (
                    value["name"]
                    for value in item["fieldValues"]["nodes"]
                    if value.get("__typename")
                    == "ProjectV2ItemFieldSingleSelectValue"
                    and value.get("field", {}).get("name") == "Status"
                ),
                None,
            )
            content = item.get("content")
            if (
                status != READY_STATUS
                or not content
                or content["__typename"] not in {"Issue", "DraftIssue"}
            ):
                continue
            body = content.get("body") or ""
            if section(body, "User Story") and section(body, "Acceptance Criteria"):
                continue
            title = content["title"].strip()
            print(f"Generating requirements for: {title}", flush=True)
            generated = generate_content(title)
            new_body, changed = update_body(body, generated)
            if not changed:
                continue
            mutation = (
                UPDATE_ISSUE_MUTATION
                if content["__typename"] == "Issue"
                else UPDATE_DRAFT_MUTATION
            )
            github_graphql(mutation, {"id": content["id"], "body": new_body})
            updated += 1
            print(f"Updated: {content.get('url', title)}", flush=True)
        if not items["pageInfo"]["hasNextPage"]:
            break
        after = items["pageInfo"]["endCursor"]
    print(f"Ready items updated: {updated}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
