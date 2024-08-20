import requests


def get_branch_detail(api_host: str, token: str, branch_id: int) -> dict:
    url = f'https://{api_host}/v2/storage/dev-branches/{branch_id}'
    headers = {
        'X-StorageApi-Token': token
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


def get_branches(api_host: str, token: str) -> dict:
    url = f'https://{api_host}/v2/storage/dev-branches'
    headers = {
        'X-StorageApi-Token': token
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()
