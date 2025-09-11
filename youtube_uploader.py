#!/usr/bin/env python3
"""
YouTubeアップローダー - YouTube Data API v3を使用
OAuth 2.0を利用してMP4ファイルをYouTubeにアップロードする
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# YouTube APIの関連ライブラリ
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    logging.warning("YouTube APIライブラリがインストールされていません。該当機能は制限されます")
    YOUTUBE_API_AVAILABLE = False


class YouTubeUploader:
    """YouTube APIを使った動画のアップローダー"""
    
    # OAuth 2.0のスコープ
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, config: Dict[str, Any]):
        """
        初期化
        Args:
            config: 設定辞書（youtubeキーを含む）
        """
        self.config = config.get('youtube', {})
        self.default_privacy = self.config.get('default_privacy', 'private')
        self.default_category = self.config.get('default_category', '22')  # People & Blogs
        
        self.credentials_file = 'credentials/youtube_credentials.json'  # OAuth 2.0のクライアント情報ファイル
        self.token_file = 'credentials/youtube_token.json'  # アクセストークン保存ファイル
        
        self.youtube_service = None
        
        logging.info(f"YouTubeアップローダー - デフォルトプライバシー: {self.default_privacy}")
        
        if not YOUTUBE_API_AVAILABLE:
            logging.error("YouTube APIライブラリが利用できません")
    
    def authenticate(self) -> bool:
        """OAuth 2.0による認証処理"""
        if not YOUTUBE_API_AVAILABLE:
            logging.error("YouTube APIライブラリが利用できないため、認証をスキップ")
            return False
        
        try:
            creds = None
            
            # 保存済みのトークンファイルが存在するかチェック
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
            
            # 認証情報が無効または存在しない場合
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # トークンの更新
                    creds.refresh(Request())
                else:
                    # 新規認証フローの実行
                    if not os.path.exists(self.credentials_file):
                        logging.error(f"OAuth 2.0クライアント情報が見つかりません: {self.credentials_file}")
                        logging.error("Google Cloud Consoleからクライアント情報をダウンロードして配置してください")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # トークンファイルの保存
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # YouTube APIサービスの構築
            self.youtube_service = build('youtube', 'v3', credentials=creds)
            logging.info("YouTube API認証完了")
            return True
            
        except Exception as e:
            logging.error(f"YouTube認証エラー: {e}")
            return False
    
    def upload_video(self, video_path: str, title: str, description: str = "") -> Optional[str]:
        """
        動画をYouTubeにアップロード
        Args:
            video_path: アップロード対象の動画ファイルのパス
            title: 動画のタイトル
            description: 動画の説明文
        Returns:
            アップロード成功時は動画ID、失敗時はNone
        """
        if not YOUTUBE_API_AVAILABLE:
            logging.error("YouTube APIが利用できないため、アップロード処理をスキップ")
            return None
        
        if not self.youtube_service:
            logging.error("YouTube APIが認証されていません")
            return None
        
        if not Path(video_path).exists():
            logging.error(f"動画ファイルが見つかりません: {video_path}")
            return None
        
        try:
            # アップロード用のメタデータ
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': ['shorts', 'ai', 'generated'],
                    'categoryId': self.default_category
                },
                'status': {
                    'privacyStatus': self.default_privacy,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # ファイルアップロード設定
            media = MediaFileUpload(
                video_path,
                chunksize=-1,  # 一括でアップロード
                resumable=True,
                mimetype='video/mp4'
            )
            
            logging.info(f"動画アップロード開始: {title}")
            
            # アップロードリクエスト実行
            insert_request = self.youtube_service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # レジューム可能アップロード実行
            response = self._resumable_upload(insert_request)
            
            if response:
                video_id = response.get('id')
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logging.info(f"アップロード完了: {video_url}")
                return video_id
            else:
                logging.error("アップロードが失敗しました")
                return None
                
        except HttpError as e:
            logging.error(f"YouTube APIエラー: {e}")
            return None
        except Exception as e:
            logging.error(f"アップロードエラー: {e}")
            return None
    
    def _resumable_upload(self, insert_request):
        """レジューム可能アップロード処理"""
        response = None
        error = None
        retry = 0
        
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        logging.info(f"アップロード成功: ID={response['id']}")
                    else:
                        logging.error(f"アップロードが想定外の応答を返しました: {response}")
                        return None
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # サーバーエラー時
                    error = f"サーバーエラー: {e}"
                    retry += 1
                    if retry > 3:
                        logging.error("リトライ回数上限に達しました")
                        return None
                    else:
                        logging.warning(f"{error} - リトライ {retry}/3")
                        import time
                        time.sleep(2 ** retry)  # 指数バックオフ
                else:
                    # クライアントエラー時
                    logging.error(f"クライアントエラー: {e}")
                    return None
            except Exception as e:
                logging.error(f"想定外エラー: {e}")
                return None
        
        return response
    
    def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """認証されたユーザーのチャンネル情報を取得"""
        if not self.youtube_service:
            logging.error("YouTube APIが認証されていません")
            return None
        
        try:
            request = self.youtube_service.channels().list(
                part='snippet,statistics',
                mine=True
            )
            response = request.execute()
            
            if 'items' in response and response['items']:
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'subscriber_count': channel['statistics'].get('subscriberCount', 0),
                    'video_count': channel['statistics'].get('videoCount', 0)
                }
            else:
                logging.warning("チャンネル情報を取得できませんでした")
                return None
                
        except HttpError as e:
            logging.error(f"チャンネル情報取得エラー: {e}")
            return None
    
    def create_credentials_template(self) -> None:
        """OAuth 2.0クライアント設定ファイルのテンプレートを作成"""
        template = {
            "installed": {
                "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
                "project_id": "your-project-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "YOUR_CLIENT_SECRET",
                "redirect_uris": ["http://localhost"]
            }
        }
        
        if not Path(self.credentials_file).exists():
            with open(self.credentials_file, 'w') as f:
                json.dump(template, f, indent=2)
            logging.info(f"クライアント情報テンプレートを作成しました: {self.credentials_file}")
            logging.info("Google Cloud Consoleから取得した適切な値に置き換えてください")
        else:
            logging.info(f"クライアント情報は既に存在します: {self.credentials_file}")