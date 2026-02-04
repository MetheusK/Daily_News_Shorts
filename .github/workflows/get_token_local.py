# get_token_local.py (로컬에서만 실행)
from google_auth_oauthlib.flow import InstalledAppFlow

def get_refresh_token():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',
        ['https://www.googleapis.com/auth/youtube.upload']
    )
    creds = flow.run_local_server(port=0)
    print("Refresh Token:", creds.refresh_token) # 이걸 복사해서 GitHub Secret에 저장!

if __name__ == "__main__":
    get_refresh_token()