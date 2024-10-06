from github import Github
import os
from groq import Groq
import requests
import json

# Dictionary of usernames and their selected languages
with open('user_prefs.json') as f:
    user_languages = json.load(f)

# File extension to language mapping
file_extensions = {
    ".py": "python",
    ".c": "c",
    ".java": "java",
    ".cpp": "c++",
    ".txt": "text"
}

ignore_file_types = [
    '.exe',
    '.out',
    '.json',
    '.md',
]

ignore_file_names = [
    '.gitignore',
    'README.md',
    'LICENSE',

]

skip_ai = True
auto_reject = True
banned_usernames = []

def get_filtered_files(files: list):
    filtered_files = []
    for file in files:
        fname = file.filename
        if fname in ignore_file_names:
            continue
        ext = os.path.splitext(fname)[1]
        if (ext != '' and  ext not in ignore_file_types):
            filtered_files.append(file)    
    return filtered_files
        

            
def process_pull_request(payload, github_token):
    pr_number = payload['pull_request']['number']
    repo_full_name = payload['repository']['full_name']

    
    
    # Initialize GitHub client
    g = Github(github_token)
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    if auto_reject:
        pr.edit(state="closed")
        pr.create_issue_comment("Pull Request Submission has been closed.\n- GDG Bot (*This message was automated*)")
        print("PR closed due to auto-reject")
        return

    # Check number of files changed
    files_changed = list(pr.get_files())
    files_changed = get_filtered_files(files_changed)
    num_files_changed = len(files_changed)
    pr_user = payload['pull_request']['user']['login']
    user_language = user_languages.get(pr_user, "unset-language")   
    print(f"PR user: {pr_user}")
    print(f"PR number: {pr_number}")
    print(f"Files Changed: {num_files_changed}\n{files_changed}")

    if pr_user in banned_usernames:
        pr.add_to_labels("restricted")
        pr.create_issue_comment("You have been restricted from making pull requests.\n- GDG Bot (*This message was automated*)")
        pr.edit(state="closed")
        print("PR closed due to banned user")
        return

    if num_files_changed > 1:
        pr.create_issue_comment("Please make pull requests with only file changed.\n- GDG Bot (*This message was automated*)")
        pr.edit(state="closed")
        print("PR closed due to multiple files changed")
        return
    
    # Check if the file language matches the user's selected language
    if num_files_changed == 0:
        print("No files changed in this PR")
        return

    file = files_changed[0]
    file_extension = os.path.splitext(file.filename)[1]
    file_language = file_extensions.get(file_extension, "unknown-language")


    if user_language == 'unset-language':
        pr.add_to_labels("language-not-set")
        pr.create_issue_comment("You have not selected a language to solve challenges. Please contact the GDG team.\n- GDG Bot (*This message was automated*)")
        print
        return

    elif file_language != user_language:
        pr.add_to_labels("wrong-lang")
        pr.create_issue_comment("Please solve challenges in your selected language\n- GDG Bot (*This message was automated*)")
        pr.edit(state="closed")
        print("Added wrong-lang label")
        return
    
    else:
        pr.add_to_labels(file_language)
        print("Added language label to pull request")

        if not skip_ai:
            commits = list(pr.get_commits())[-1]
            commit_sha = commits.sha
            file_url = f"https://raw.githubusercontent.com/{repo_full_name}/{commit_sha}/{file.filename}"
            file_content = requests.get(file_url).text
            client = Groq(
                api_key=os.environ.get("GROQ_API_KEY"),
            )
            
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": f"""There is a code snippet in {file_language} below. The beginning of the file has the question prompt and samples and the solution is below.

                        If the code is logically and syntactically correct. Respond with "the solution is correct", if not respond with "the solution is incorrect".

                        - Only reply with the one word
                        - No yapping
                        - I will tip you 1000$ if you follow the instructions correctly.
                        
                        ----CODE SNIPPET---
                        {file_content}
                        """,

                        
                    }
                ],
                model="llama-3.1-70b-versatile",
            )
            response = chat_completion.choices[0].message.content
            ai_correct = None
            if ' correct' in response:
                ai_correct = False
            if ' incorrect' in response:
                ai_correct = True
            
            if ai_correct is None:
                pr.add_to_labels("m-r")
            else:
                if ai_correct:
                    pr.add_to_labels("a-c")
                else:
                    pr.add_to_labels("a-w")


    print("PR processed successfully")