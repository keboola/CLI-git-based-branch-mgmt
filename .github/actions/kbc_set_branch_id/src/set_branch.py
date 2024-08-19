import json
import os

import github_action_utils as gh_utils

MANIFEST_PATH = '.keboola/manifest.json'
BRANCH_MAPPING_PATH = '.keboola/branch-mapping.json'


def get_api_host() -> str:
    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)
        return manifest['project']['apiHost']


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


list_files('.')
print(os.environ)
print(gh_utils.get_workflow_environment_variables())
