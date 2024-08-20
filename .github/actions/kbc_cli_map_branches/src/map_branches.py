import json
import os

import github_action_utils as gh_utils
from github import Github

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


def is_branch_mapped(branch_id: int) -> bool:
    with open(BRANCH_MAPPING_PATH, 'r') as f:
        mapping = json.load(f)
        return branch_id in mapping.values()


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


def add_branch_mapping(branch_id: int, branch_name: str):
    with open(BRANCH_MAPPING_PATH, 'r') as b_file:
        mapping = json.load(b_file)
        mapping[branch_name] = branch_id

    with open(BRANCH_MAPPING_PATH, 'w') as b_file:
        json.dump(mapping, b_file, indent=2)


# ############################### MAIN CODE ####################################

# create mapping file if not exists
if not os.path.exists(BRANCH_MAPPING_PATH):
    with open(BRANCH_MAPPING_PATH, 'w') as f:
        json.dump({}, f)

remote_branches = kbc_cli.get_branches(get_api_host(), get_token())

gh = Github(gh_utils.get_env('GITHUB_TOKEN'))
current_repo = gh.get_repo(gh_utils.get_env('GITHUB_REPOSITORY'))

current_repo.get_workflow('pull_branch.yml').create_dispatch(ref='master')
for branch in remote_branches:
    if not is_branch_mapped(branch['id']):
        gh_utils.notice(f'New remote Keboola Dev Branch found, creating new git branch: {branch["name"]}')
        current_repo.create_git_ref(ref=f'refs/heads/{branch["name"]}', sha='master')
        add_branch_mapping(branch['id'], branch['name'])
