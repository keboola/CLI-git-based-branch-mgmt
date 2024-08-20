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


def branch_is_mapped(branch_name: str, branch_id: int, repo: Repository.Repository) -> bool:
    """
    Checks if branch exists in the current branch file mapping or in the repository itself.
    Args:
        branch_name:
        branch_id:
        repo:

    Returns:

    """

    branch_exist = False
    with open(BRANCH_MAPPING_PATH, 'r') as f:
        mapping = json.load(f)
        mapped_in_mapping_file = branch_id in mapping.values()

    refs = repo.get_git_refs()
    for ref in refs:
        if ref.ref == f'refs/heads/{branch_name}':
            branch_exist = True
            break

    return mapped_in_mapping_file or branch_exist


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
current_ref = gh_utils.get_env('GITHUB_REF').replace('refs/', '')
gh_utils.warning(f'Current branch: {current_ref}')
current_branch_sha = current_repo.get_git_ref(current_ref).object.sha

# current_repo.get_workflow('pull_branch.yml').create_dispatch(ref='master')
for branch in remote_branches:
    if not branch_is_mapped(branch['name'], branch['id'], current_repo) and branch['name'] != 'Main':
        gh_utils.notice(f'New remote Keboola Dev Branch found, creating new git branch: {branch["name"]}',
                        title=f'New git branch {branch["name"]} created')
        add_branch_mapping(branch['id'], branch['name'])
        new_ref = current_repo.create_git_ref(ref=f'refs/heads/{branch["name"]}', sha=current_branch_sha)

        tree = current_repo.get_git_tree(new_ref.object.sha, recursive=True)
        blobs = tree
        manifest_file = [b for b in blobs.tree if b.path == BRANCH_MAPPING_PATH]
        if not manifest_file:
            file_sha = None
        else:
            file_sha = manifest_file[0].sha

        if not file_sha:
            current_repo.create_file(path=BRANCH_MAPPING_PATH, message='Add new branch mapping',
                                     content=get_mapping_file_as_base64_hash(),
                                     branch=branch["name"])
        else:
            current_repo.update_file(path=BRANCH_MAPPING_PATH, message='Add new branch mapping',
                                     content=get_mapping_file_as_base64_hash(),
                                     sha=file_sha,
                                     branch=branch["name"])
        # gh_utils.warning(f'Triggering pull branch workflow for branch: {branch["name"]}',
        #                  title=f'Triggering workflow "pull_branch.yml@{branch["name"]}"')
        # current_repo.get_workflow('pull_branch.yml').create_dispatch(ref=branch["name"],
        #                                                              inputs={"kbcSapiToken": get_token(),
        #                                                                      "kbcBranchId": branch["id"],
        #                                                                      "createBranchIfNotExists": "true"})
