# Automated Code Review using the ChatGPT language model

# Imports
import os
import openai
import argparse
import requests
from github import Github

# CLI arguments
parser = argparse.ArgumentParser()
parser.add_argument("--openai_api_key", help="Your OpenAI API Key")
parser.add_argument("--github_token", help="Your Github Token")
parser.add_argument("--github_pr_id", help="Your Github PR ID")
parser.add_argument(
    "--openai_engine",
    default="gpt-3.5-turbo",
    help="GPT-3 model to use. Options: gpt-3.5-turbo, text-davinci-002, text-babbage-001, text-curie-001, text-ada-001",
)
parser.add_argument(
    "--openai_temperature",
    default=0.5,
    help="Sampling temperature to use. Higher values means the model will take more risks. Recommended: 0.5",
)
parser.add_argument(
    "--openai_max_tokens", default=4096, help="The maximum number of tokens to generate in the completion."
)
parser.add_argument("--mode", default="files", help="PR interpretation form. Options: files, patch")
args = parser.parse_args()

# OpenAI API authentication
openai.api_key = args.openai_api_key

# Github API authentication
g = Github(args.github_token)


def files():
    repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
    pull_request = repo.get_pull(int(args.github_pr_id))

    # Loop through the commits in the pull request
    commits = pull_request.get_commits()
    for commit in commits:
        print("COMMIT : ", commit)
        statuses = commit.get_statuses()

        if statuses.totalCount == 0 or statuses[0].state != "success":
            print("CHATGPT...")
            # do the chatgpt task

            # Getting the modified files in the commit
            files = commit.files
            for file in files:
                # Getting the file name and content
                filename = file.filename
                content = repo.get_contents(filename, ref=commit.sha).decoded_content

                # Sending the code to ChatGPT
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are an AI language model, capable of providing comprehensive code reviews for code changes in GitHub pull requests.
                                        Your primary areas of focus include: purpose, functionality, code quality, performance, security, compatibility, testing, and documentation.
                                        Your outputs should be formatted as markdown for readability and clarity.""",
                        },
                        {
                            "role": "user",
                            "content": f"""Please conduct a thorough code review on the following code changes in this GitHub pull request. The code is provided within triple backticks below.
                                        I'd like you to provide feedback on the following aspects:

                            1. Purpose: What is the main goal and potential impact of these changes?
                            2. Functionality: Do these changes fulfill their intended purpose? Does the code logic reflect the function name? Identify any potential issues or bugs.
                            3. Code Quality: How readable and modular is the code? Does it adhere to coding standards? Are variable and function naming conventions followed?
                            4. Performance: Are there any opportunities for optimization or performance enhancements in the code?
                            5. Security: Are there any potential security vulnerabilities or risks associated with these changes?
                            6. Compatibility: Does this code introduce any breaking changes or incompatibilities with the existing codebase?
                            7. Testing: Have appropriate tests been added or modified to cover these changes?
                            8. Documentation: How is the quality and completeness of comments, commit messages, and documentation updates?

                            ```{content}```

                            I would also like you to highlight any major vulnerabilities in the code and suggest possible solutions for those.
                            If there are no major vulnerabilities, kindly rate the vulnerability score out of 10.
                            Further, provide feedback on the variable and function naming conventions used in the code, evaluating for clarity and consistency.""",
                        },
                    ],
                    temperature=float(args.openai_temperature),
                    max_tokens=int(args.openai_max_tokens),
                )

                print("usage", response["usage"])

                # Adding a comment to the pull request with ChatGPT's response
                pull_request.create_issue_comment(
                    f"ChatGPT's response about `{file.filename}`:\n {response['choices'][0]['message']['content']}"
                )

                # save the state
                commit.create_status(state="success")
        else:
            print("DONE")


def patch():
    repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
    pull_request = repo.get_pull(int(args.github_pr_id))

    content = get_content_patch()

    if len(content) == 0:
        pull_request.create_issue_comment(f"Patch file does not contain any changes")
        return

    parsed_text = content.split("diff")

    for diff_text in parsed_text:
        if len(args.openai_max_tokens) == 0:
            continue

        try:
            file_name = diff_text.split("b/")[1].splitlines()[0]
            print(file_name)
            parts = [
                diff_text[i : i + args.openai_max_tokens] for i in range(0, len(diff_text), args.openai_max_tokens)
            ]
            full_response = ""
            text_parts = []
            for part in parts:
                response = openai.Completion.create(
                    engine=args.openai_engine,
                    prompt=(f"Summarize what was done in this diff:\n```{part}```"),
                    max_tokens=int(args.openai_max_tokens),
                    n=1,
                    stop=None,
                    temperature=float(args.openai_temperature),
                )
            text_parts.append(response.choices[0].text)
            full_response = "".join(text_parts)
            print(full_response)
            print(full_response["choices"][0]["text"])

            pull_request.create_issue_comment(
                f"ChatGPT's response about ``{file_name}``:\n {full_response['choices'][0]['text']}"
            )
        except Exception as e:
            error_message = str(e)
            print(error_message)
            pull_request.create_issue_comment(f"ChatGPT was unable to process the response about {file_name}")


def get_content_patch():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/pulls/{args.github_pr_id}"
    print(url)

    headers = {"Authorization": f"token {args.github_token}", "Accept": "application/vnd.github.v3.diff"}

    response = requests.request("GET", url, headers=headers)

    if response.status_code != 200:
        raise Exception(response.text)

    return response.text


if args.mode == "files":
    files()

if args.mode == "patch":
    patch()
