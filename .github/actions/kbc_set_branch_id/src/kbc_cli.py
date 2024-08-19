import requests
from kbcstorage.jobs import Jobs

def create_new_kbc_branch(api_host: str, token: str, branch_name: str) -> int:
    """

    Args:
        branch_name:

    Returns:

    """
    url = f'https://{api_host}/v2/storage/dev-branches/'
    headers = {
        'Content-Type': 'application/json',
        'X-StorageApi-Token': token
    }
    payload = {
        'name': branch_name
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 202:
        job_id = response.json().get('id')
        jobs = Jobs(f'https://{api_host}', token)
        job_successful = jobs.block_for_success(job_id)
        job_detail = jobs.detail(job_id)
        if job_successful:
            return job_detail['results']['id']
        else:
            raise Exception(f'Branch creation failed: {job_detail}')

    else:
        raise Exception(response.json())




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
