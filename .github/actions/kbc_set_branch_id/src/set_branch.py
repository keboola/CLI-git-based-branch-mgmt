import json
import os

import github_action_utils as gh_utils

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


def get_current_git_branch_name() -> str:
    return gh_utils.get_env('GITHUB_REF_NAME')


def _get_kbc_branch_id_user_override() -> int:
    return gh_utils.get_env('KBC_BRANCH_ID')


def _get_branch_id_from_mapping() -> int:
    with open(BRANCH_MAPPING_PATH, 'r') as f:
        mapping = json.load(f)
        return mapping.get(get_current_git_branch_name())


def get_kbc_branch_id() -> int:
    mapped_branch_id = _get_branch_id_from_mapping()
    user_branch_id = _get_kbc_branch_id_user_override()
    if user_branch_id is not None and mapped_branch_id is not None:
        gh_utils.error(f'This branch "{get_current_git_branch_name()}" to remote branch id "{mapped_branch_id}" '
                       f'Do not specify the Branch ID parameter')
        raise Exception(f'Branch ID is already set to "{mapped_branch_id}" in the branch mapping file')

    branch_id = user_branch_id or mapped_branch_id

    if branch_id is not None:
        branch_id = int(branch_id)

    return branch_id


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


def add_branch_mapping(branch_id: int):
    with open(BRANCH_MAPPING_PATH, 'r') as f:
        mapping = json.load(f)
        mapping[get_current_git_branch_name()] = branch_id

    with open(BRANCH_MAPPING_PATH, 'w') as f:
        json.dump(mapping, f, indent=2)


# ############################### MAIN CODE ####################################

# create mapping file if not exists
if not os.path.exists(BRANCH_MAPPING_PATH):
    with open(BRANCH_MAPPING_PATH, 'w') as f:
        json.dump({}, f)

kbc_branch_id = get_kbc_branch_id()

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

add_branch_mapping(kbc_branch_id)

gh_utils.set_output('kbc_branch_id', kbc_branch_id)
print(f"::set-output name=kbc_branch_id::{kbc_branch_id}")
