import json
import os

import github_action_utils as gh_utils
from github import Github

import kbc_cli

MANIFEST_PATH = '.keboola/manifest.json'


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


def get_current_git_branch_name() -> str:
    return gh_utils.get_env('GITHUB_REF_NAME')


def _get_kbc_branch_id_user_override() -> int:
    branch_id = gh_utils.get_env('KBC_BRANCH_ID')
    return int(branch_id) if branch_id is not None else None


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
        gh = Github(gh_utils.get_env('GITHUB_TOKEN'))
        current_repo = gh.get_repo(gh_utils.get_env('GITHUB_REPOSITORY'))
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


class BranchMapping:
    def __init__(self):
        self._mapping = download_mapping_artifact()

    def get_branch_id(self, branch_name: str) -> int:
        return self._mapping.get(branch_name)

    def add_branch_mapping(self, branch_name: str, branch_id: int):
        self._mapping[branch_name] = branch_id
        upload_mapping_artifact(self._mapping)
        gh_utils.notice(f'Branch ID "{branch_id}" added to mapping file, new content is: {self._mapping}',
                        title='Branch ID added to mapping file')


def get_kbc_branch_id(branch_mapping: BranchMapping) -> int:
    mapped_branch_id = branch_mapping.get_branch_id(get_current_git_branch_name())
    user_branch_id = _get_kbc_branch_id_user_override()
    
    if user_branch_id is not None and mapped_branch_id is not None:
        gh_utils.error(f'This branch "{get_current_git_branch_name()}" to remote branch id "{mapped_branch_id}" '
                       f'Do not specify the Branch ID parameter')
        raise Exception(f'Branch ID is already set to "{mapped_branch_id}" in the branch mapping file')

    return user_branch_id or mapped_branch_id


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


# ############################### MAIN CODE ####################################

branch_mapping = BranchMapping()
kbc_branch_id = get_kbc_branch_id(branch_mapping)

try:
    if kbc_branch_id is None and create_new_branch_if_not_exists():
        gh_utils.warning(f'Keboola Branch ID not found for branch "{get_current_git_branch_name()}, '
                         f'creating new one"',
                         title='Keboola Branch not found in mapping, creating new remote branch')
        kbc_branch_id = kbc_cli.create_new_kbc_branch(get_api_host(), get_token(), get_current_git_branch_name())
        gh_utils.warning(f'New remote branch ID "{kbc_branch_id}" '
                         f'created for branch "{get_current_git_branch_name()}"',
                         title='New Keboola Dev branch created')

    # double check that the branch exists
    if not check_if_branch_exists(kbc_branch_id):
        if kbc_branch_id is None:
            message = ('Branch ID not found in mapping file, please initialize the branch '
                       'using PUSH (Branch) or PULL (Branch) action')
        else:
            message = f'Branch ID "{kbc_branch_id}" does not exist in KBC'
        gh_utils.error(message,
                       title='Branch ID not found')
        raise Exception(f'Branch ID "{kbc_branch_id}" does not exist in KBC')

    branch_mapping.add_branch_mapping(get_current_git_branch_name(), kbc_branch_id)
    gh_utils.set_output('kbc_branch_id', kbc_branch_id)
except Exception as e:
    gh_utils.error(str(e))
    exit(1)
