from openai import OpenAI
import argparse
import json
import os
import requests
import glob
from github import Github
from tools.claude_retriever.client import extract_between_tags
from tools.utils import read_file


REPO_NAME = "1712n/dn-institute"
SYSTEM_PROMPT_FILE = 'tools/market_health_reporter_doc/prompts/system_prompt.txt'
HUMAN_PROMPT_FILE = 'tools/market_health_reporter_doc/prompts/prompt1.txt'
ARTICLE_EXAMPLE_FILE = 'content/market-health/posts/2023-08-14-huobi/index.md'
OUTPUT_DIR = 'content/market-health/posts'
DATA_DIR = 'tools/market_health_reporter_doc/data'


def parse_cli_args():
    """
    Parse CLI arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm-api-key", dest="API_key", help="LLM API key", required=True
    )
    parser.add_argument(
        "--issue", dest="issue", help="Issue number", required=True
    )
    parser.add_argument(
        "--comment-body", dest="comment_body", help="Comment body", required=True
    )
    parser.add_argument(
        "--github-token", dest="github_token", help="Github token", required=True
    )
    parser.add_argument(
        "--rapid-api", dest="rapid_api", help="Rapid API key", required=True
    )
    return parser.parse_args()


def extract_data_from_comment(comment: str) -> tuple:
    """
    Extract data from the comment.
    """
    parts = comment.split(',')
    marketvenueid = parts[1].strip().lower()
    pairid = parts[0].strip().lower()  
    start, end = parts[2].strip(), parts[3].strip()
    return marketvenueid, pairid, start, end


def save_output(output: str, directory: str, marketvenueid: str, pairid: str, start: str, end: str) -> None:
    """
    Saves the output to a markdown file in the specified directory.
    If a file with the same base name already exists, appends a sequential number to the file name.
    """
    safe_start = start.replace(":", "-")
    safe_end = end.replace(":", "-")
    base_file_name = f"{marketvenueid}_{pairid}_{safe_start}_{safe_end}"
    file_path = os.path.join(directory, base_file_name)
    
    existing_files = glob.glob(f"{file_path}*.md")
    if existing_files:
        numbers = [int(file_name.split('-')[-1].split('.md')[0]) for file_name in existing_files if file_name.split('-')[-1].split('.md')[0].isdigit()]
        file_number = max(numbers, default=0) + 1
        full_path = f"{file_path}-{file_number}.md"
    else:
        full_path = f"{file_path}.md"
    
    with open(full_path, 'w', encoding='utf-8') as file:
        file.write(output)
    print(f"Output saved to: {full_path}")


def save_data(data: str, directory: str, marketvenueid: str, pairid: str, start: str, end: str) -> None:
    """
    Saves data to a JSON file in the specified directory.
    """
    new_file_name = f'{directory}{marketvenueid}_{pairid}_{start.replace(":", "-")}_{end.replace(":", "-")}.json'
    with open(new_file_name, 'w', encoding='utf-8') as file:
        file.write(data)


def file_exists(directory: str, marketvenueid: str, pairid: str, start: str, end: str) -> str:
    """
    Checks if a file with the specified parameters exists.
    Returns the path to the file if found, otherwise returns None.
    """
    pattern = f"{directory}/{marketvenueid}_{pairid}_{start.replace(':', '-')}_{end.replace(':', '-')}.json"
    matching_files = glob.glob(pattern)
    return matching_files[0] if matching_files else None

    
def post_comment_to_issue(github_token, issue_number, repo_name, comment):
    """
    Post a comment to a GitHub issue.
    """
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    issue = repo.get_issue(number=issue_number)
        # only post comment if running on Github Actions
    if os.environ.get("GITHUB_ACTIONS") == "true":
        issue.create_comment(comment)


def main():
    args = parse_cli_args()

    with open('tools/market_health_reporter_doc/data/data1.json', 'r') as data_file:
        data = json.load(data_file)

    with open('tools/market_health_reporter_doc/prompts/system_prompt.txt', 'r') as file:
        SYSTEM_PROMPT = file.read()

    with open('tools/market_health_reporter_doc/prompts/prompt1.txt', 'r') as file:
        HUMAN_PROMPT_CONTENT = file.read()

    with open('content/market-health/posts/2023-08-14-huobi/index.md', 'r') as file:
        article_example = file.read()


    HUMAN_PROMPT_CONTENT = f"""
    <example> %s </example>
    {HUMAN_PROMPT_CONTENT}
    <data> %s </data>
    """
    
    prompt = f"{HUMAN_PROMPT_CONTENT%(article_example, data)}"
    print('This is a prompt: ', prompt)

    client = OpenAI(api_key=args.API_key)

    completion = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"{SYSTEM_PROMPT}"},
        {"role": "user", "content": f"{prompt}"}
    ]
    )

    output = completion.choices[0].message.content
    
    output = extract_between_tags("article", output)

    print("This is an answer: ", output)

    #with open('tools/market_health_reporter_doc/openai/outputs/output1.md', 'w', encoding='utf-8') as file:
        #file.write(output)   

    post_comment_to_issue(args.github_token, int(args.issue), repo_name, output)
    
    