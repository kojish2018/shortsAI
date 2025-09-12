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
from datetime import datetime
import pytz

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
    
    def upload_video(self, video_path: str, title: str, description: str = "", 
                     schedule_datetime: Optional[str] = None, is_shorts: bool = True) -> Optional[str]:
        """
        動画をYouTubeにアップロード
        Args:
            video_path: アップロード対象の動画ファイルのパス
            title: 動画のタイトル
            description: 動画の説明文
            schedule_datetime: スケジュール投稿日時 (ISO 8601形式: "2024-12-25T08:00:00Z")
            is_shorts: YouTube Shortsとしてアップロードするか
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
            # Shortsハッシュタグをタイトルまたは説明文に追加
            if is_shorts:
                if '#Shorts' not in title and '#Shorts' not in description:
                    title = f"{title} #Shorts"
                
                # Shortsのデフォルトタグを追加
                shorts_tags = ['shorts', 'ai', 'generated', 'vertical']
            else:
                shorts_tags = ['ai', 'generated']
            
            # スケジュール投稿の場合はプライバシーをprivateに設定
            privacy_status = 'private' if schedule_datetime else self.default_privacy
            
            # アップロード用のメタデータ
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': shorts_tags,
                    'categoryId': self.default_category
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # スケジュール投稿日時を設定
            if schedule_datetime:
                body['status']['publishAt'] = schedule_datetime
                logging.info(f"スケジュール投稿設定: {schedule_datetime}")
            
            # ファイルアップロード設定
            media = MediaFileUpload(
                video_path,
                chunksize=-1,  # 一括でアップロード
                resumable=True,
                mimetype='video/mp4'
            )
            
            upload_type = "スケジュール投稿" if schedule_datetime else "即座投稿"
            shorts_type = "YouTube Shorts" if is_shorts else "通常動画"
            logging.info(f"{shorts_type} {upload_type}開始: {title}")
            
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
                if status:
                    logging.info(f"アップロード進捗: {int(status.progress() * 100)}%")
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
    
    def parse_schedule_datetime(self, schedule_str: str) -> Optional[str]:
        """
        スケジュール投稿日時を解析してISO 8601形式に変換
        Args:
            schedule_str: 日時文字列 (例: "2024-12-25 08:00", "2024-12-25T08:00:00+09:00")
        Returns:
            ISO 8601形式の日時文字列、または無効な場合はNone
        """
        if not schedule_str:
            return None
            
        try:
            # 既にISO 8601形式の場合
            if 'T' in schedule_str and ('+' in schedule_str or 'Z' in schedule_str):
                # バリデーション
                datetime.fromisoformat(schedule_str.replace('Z', '+00:00'))
                return schedule_str
            
            # 簡単な形式をパース (例: "2024-12-25 08:00")
            if len(schedule_str.split()) == 2:
                date_part, time_part = schedule_str.split()
                # 日本時間と仮定してUTCに変換
                jst = pytz.timezone('Asia/Tokyo')
                dt_str = f"{date_part} {time_part}"
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                dt_jst = jst.localize(dt)
                dt_utc = dt_jst.astimezone(pytz.UTC)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            # その他の形式をパース
            dt = datetime.fromisoformat(schedule_str)
            if dt.tzinfo is None:
                # タイムゾーン情報がない場合は日本時間と仮定
                jst = pytz.timezone('Asia/Tokyo')
                dt_jst = jst.localize(dt)
                dt_utc = dt_jst.astimezone(pytz.UTC)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            else:
                # タイムゾーン情報がある場合はUTCに変換
                dt_utc = dt.astimezone(pytz.UTC)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                
        except Exception as e:
            logging.error(f"日時パースエラー '{schedule_str}': {e}")
            logging.error("使用可能な形式: '2024-12-25 08:00' または '2024-12-25T08:00:00+09:00'")
            return None
    
    def validate_schedule_datetime(self, schedule_str: str) -> bool:
        """
        スケジュール投稿日時が有効かチェック
        Args:
            schedule_str: ISO 8601形式の日時文字列
        Returns:
            有効な場合True
        """
        if not schedule_str:
            return False
            
        try:
            # 日時をパース
            dt = datetime.fromisoformat(schedule_str.replace('Z', '+00:00'))
            
            # 現在時刻と比較（未来の日時であることを確認）
            now_utc = datetime.now(pytz.UTC)
            if dt <= now_utc:
                logging.warning(f"スケジュール日時が過去または現在です: {schedule_str}")
                logging.warning("過去の日時の場合、動画は即座に公開されます")
            
            return True
            
        except Exception as e:
            logging.error(f"日時バリデーションエラー: {e}")
            return False