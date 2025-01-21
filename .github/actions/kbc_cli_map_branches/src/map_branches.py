import json
import os

import github_action_utils as gh_utils
from github import Github, Repository

import kbc_cli

MANIFEST_PATH = '.keboola/manifest.json'
BRANCH_MAPPING_PATH = '.keboola/branch-mapping.json'


def get_api_host() -> str:
    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)
        return manifest['project']['apiHost']


def get_token() -> str:
    return gh_utils.get_env('KBC_STORAGE_API_TOKEN')


def list_files(startpath):
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print('{}{}/'.format(indent, os.path.basename(root)))
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print('{}{}'.format(subindent, f))


def get_mapping_file_as_base64_hash() -> str:
    with open(BRANCH_MAPPING_PATH, 'r') as f:
        return f.read()


def sanitize_branch_name(branch_name: str) -> str:
    """
    Sanitizes branch name to be valid for Git:
    - Replaces spaces with hyphens
    - Removes special characters
    - Ensures it doesn't begin or end with '/'
    """
    # Replace spaces with hyphens
    sanitized = branch_name.replace(' ', '-')
    # Remove any special characters that aren't allowed in Git branch names
    sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '-_/')
    # Remove leading/trailing slashes
    sanitized = sanitized.strip('/')
    return sanitized


def download_mapping_artifact():
    """
    Downloads the branch mapping artifact from the previous workflow run.
    Returns the mapping dict or empty dict if no artifact exists.
    Creates a new mapping file if none exists.
    """
    # Create a new mapping file if it doesn't exist
    if not os.path.exists('branch-mapping.json'):
        with open('branch-mapping.json', 'w') as f:
            json.dump({}, f, indent=2)

    try:
        artifacts = current_repo.get_artifacts()
        for artifact in artifacts:
            if artifact.name == "branch-mapping":
                # Download and extract the artifact
                download_url = artifact.archive_download_url
                headers = {
                    "Authorization": f"token {gh_utils.get_env('GITHUB_TOKEN')}"}
                import requests
                import io
                import zipfile

                response = requests.get(download_url, headers=headers)
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                    zip_ref.extractall('temp_artifact')

                # Read the downloaded mapping
                with open('temp_artifact/branch-mapping.json', 'r') as f:
                    mapping = json.load(f)

                # Cleanup
                import shutil
                shutil.rmtree('temp_artifact')

                # Write the downloaded mapping to the file
                with open('branch-mapping.json', 'w') as f:
                    json.dump(mapping, f, indent=2)

                return mapping

        # If no artifact found, return empty dict but file already exists
        return {}
    except Exception as e:
        gh_utils.warning(f"Failed to download artifact: {str(e)}")
        return {}


def upload_mapping_artifact(mapping: dict):
    """
    Uploads the branch mapping as an artifact by writing to the expected location
    """
    # Save mapping to the file that will be picked up by the upload-artifact action
    with open('branch-mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)


def branch_is_mapped(mapping: dict, branch_name: str, branch_id: int, repo: Repository.Repository) -> bool:
    """
    Checks if branch exists in the mapping artifact or in the repository itself.
    """
    branch_exist = False
    sanitized_name = sanitize_branch_name(branch_name)

    # Get mapping from artifact
    mapped_in_artifact = branch_id in mapping.values()

    refs = repo.get_git_refs()
    for ref in refs:
        if ref.ref == f'refs/heads/{sanitized_name}':
            branch_exist = True
            break

    return mapped_in_artifact or branch_exist


def create_new_branch_if_not_exists() -> bool:
    create_new = gh_utils.get_env('KBC_CREATE_NEW_BRANCH')
    if create_new is not None:
        return create_new.lower() == 'true'
    else:
        return False


def check_if_branch_exists(branch_id: int) -> bool:
    try:
        return kbc_cli.get_branch_detail(get_api_host(), get_token(), branch_id) is not None
    except Exception:
        return False


def add_branch_mapping(mapping: dict, branch_id: int, branch_name: str):
    mapping[branch_name] = branch_id


# ############################### MAIN CODE ####################################

remote_branches = kbc_cli.get_branches(get_api_host(), get_token())

gh_utils.notice(f'Found {len(remote_branches)} branches in total.')
gh = Github(gh_utils.get_env('GITHUB_TOKEN'))
current_repo = gh.get_repo(gh_utils.get_env('GITHUB_REPOSITORY'))
current_ref = gh_utils.get_env('GITHUB_REF').replace('refs/', '')
gh_utils.warning(f'Current branch: {current_ref}')
current_branch_sha = current_repo.get_git_ref(current_ref).object.sha
# retrieve mapping artifact
mapping = download_mapping_artifact()
gh_utils.notice(f'Current mapping artifact: {mapping}')

for branch in remote_branches:
    sanitized_branch_name = sanitize_branch_name(branch['name'])
    if not branch_is_mapped(mapping, branch['name'], branch['id'], current_repo) and branch['name'] != 'Main':
        gh_utils.notice(f'New remote Keboola Dev Branch found, creating new git branch: {sanitized_branch_name}',
                        title=f'New git branch {sanitized_branch_name} created')
        add_branch_mapping(mapping, branch['id'], branch['name'])
        new_ref = current_repo.create_git_ref(
            ref=f'refs/heads/{sanitized_branch_name}', sha=current_branch_sha)

upload_mapping_artifact(mapping)
