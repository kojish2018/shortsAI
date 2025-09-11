#!/usr/bin/env python3
"""
画像生成モジュール - Pollinations.ai 統合
URLベースで画像を生成
"""

import requests
import logging
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlencode, quote

class ImageGenerator:
    """Pollinations.aiを使用した画像生成クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初期化
        Args:
            config: 設定辞書（apis.pollinations設定を含む）
        """
        self.config = config.get('apis', {}).get('pollinations', {})
        self.model = self.config.get('model', 'flux')
        self.width = self.config.get('width', 1080)
        self.height = self.config.get('height', 1920)
        
        logging.info(f"画像生成 - Provider: Pollinations.ai, Model: {self.model}")
    
    def generate_image(self, prompt: str, output_path: str) -> bool:
        """
        テキストプロンプトから画像を生成
        Args:
            prompt: 画像生成プロンプト
            output_path: 出力ファイルパス
        Returns:
            生成成功時True、失敗時False
        """
        base_url = "https://image.pollinations.ai/prompt/"
        
        # URLエンコードされたプロンプト
        encoded_prompt = quote(prompt)
        
        # クエリパラメータ
        params = {
            'model': self.model,
            'width': self.width,
            'height': self.height,
        }
        query_string = urlencode(params)
        
        full_url = f"{base_url}{encoded_prompt}?{query_string}"
        
        logging.info(f"Pollinations.aiで画像生成中: {prompt[:50]}...")
        logging.debug(f"Request URL: {full_url}")
        
        try:
            # 30秒のタイムアウトを設定
            response = requests.get(full_url, timeout=120, allow_redirects=True)
            response.raise_for_status()  # ステータスコードが200番台でなければ例外を発生
            
            # 出力ディレクトリを作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"画像をダウンロードしました: {output_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Pollinations.ai APIエラー: {e}")
            return False
        except Exception as e:
            logging.error(f"画像生成中に予期せぬエラーが発生しました: {e}")
            return False

    
