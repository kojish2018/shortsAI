#!/usr/bin/env python3
"""
画像生成モジュール - Flux.1 Dev API統合
fal.aiまたはReplicateを使用して1080x1920px縦型画像を生成
"""

import requests
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
import base64
from io import BytesIO


class ImageGenerator:
    """Flux.1 Dev APIを使用した画像生成クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初期化
        Args:
            config: 設定辞書（apis.flux設定を含む）
        """
        self.config = config['apis']['flux']
        self.provider = self.config.get('provider', 'fal.ai')
        self.api_key = self.config.get('api_key', '')
        self.model = self.config.get('model', 'flux-dev')
        self.steps = self.config.get('steps', 35)
        self.guidance_scale = self.config.get('guidance_scale', 3.5)
        
        if not self.api_key:
            logging.warning("Flux.1 Dev APIキーが設定されていません")
        
        logging.info(f"画像生成 - Provider: {self.provider}, Model: {self.model}")
    
    def generate_image(self, prompt: str, output_path: str) -> bool:
        """
        テキストプロンプトから画像を生成
        Args:
            prompt: 画像生成プロンプト
            output_path: 出力ファイルパス
        Returns:
            生成成功時True、失敗時False
        """
        if not self.api_key:
            logging.error("APIキーが設定されていないため、画像生成をスキップします")
            return self._create_placeholder_image(output_path, prompt)
        
        try:
            if self.provider == 'fal.ai':
                return self._generate_with_fal(prompt, output_path)
            elif self.provider == 'replicate':
                return self._generate_with_replicate(prompt, output_path)
            else:
                logging.error(f"未対応のプロバイダ: {self.provider}")
                return self._create_placeholder_image(output_path, prompt)
                
        except Exception as e:
            logging.error(f"画像生成エラー: {e}")
            return self._create_placeholder_image(output_path, prompt)
    
    def _generate_with_fal(self, prompt: str, output_path: str) -> bool:
        """fal.aiを使用して画像生成"""
        url = "https://fal.run/fal-ai/flux/dev"
        
        # 縦型ショート動画用のプロンプト拡張
        enhanced_prompt = f"{prompt}, vertical orientation, 9:16 aspect ratio, high quality, professional"
        
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "prompt": enhanced_prompt,
            "image_size": "portrait_9_16",  # 1080x1920相当
            "num_inference_steps": self.steps,
            "guidance_scale": self.guidance_scale,
            "enable_safety_checker": True
        }
        
        logging.info(f"fal.aiで画像生成中: {prompt[:50]}...")
        response = requests.post(url, json=data, headers=headers, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            if 'images' in result and result['images']:
                image_url = result['images'][0]['url']
                return self._download_image(image_url, output_path)
            else:
                logging.error("APIレスポンスに画像URLがありません")
                return False
        else:
            logging.error(f"fal.ai API エラー: {response.status_code} - {response.text}")
            return False
    
    def _generate_with_replicate(self, prompt: str, output_path: str) -> bool:
        """Replicateを使用して画像生成"""
        url = "https://api.replicate.com/v1/predictions"
        
        # 縦型ショート動画用のプロンプト拡張
        enhanced_prompt = f"{prompt}, vertical orientation, 9:16 aspect ratio, high quality, professional"
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "version": "black-forest-labs/flux-schnell",
            "input": {
                "prompt": enhanced_prompt,
                "width": 1080,
                "height": 1920,
                "num_inference_steps": self.steps,
                "guidance_scale": self.guidance_scale
            }
        }
        
        logging.info(f"Replicateで画像生成中: {prompt[:50]}...")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 201:
            prediction = response.json()
            prediction_url = prediction['urls']['get']
            
            # 処理完了まで待機
            while True:
                time.sleep(2)
                result_response = requests.get(prediction_url, headers=headers)
                result = result_response.json()
                
                if result['status'] == 'succeeded':
                    if result['output'] and len(result['output']) > 0:
                        image_url = result['output'][0]
                        return self._download_image(image_url, output_path)
                    else:
                        logging.error("Replicate APIから画像URLが取得できません")
                        return False
                elif result['status'] == 'failed':
                    logging.error(f"Replicate処理エラー: {result.get('error', 'Unknown error')}")
                    return False
                elif result['status'] in ['starting', 'processing']:
                    logging.info("処理中...")
                    continue
                else:
                    logging.error(f"予期しないステータス: {result['status']}")
                    return False
        else:
            logging.error(f"Replicate API エラー: {response.status_code} - {response.text}")
            return False
    
    def _download_image(self, image_url: str, output_path: str) -> bool:
        """画像URLから画像をダウンロード"""
        try:
            response = requests.get(image_url, timeout=60)
            response.raise_for_status()
            
            # 出力ディレクトリを作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"画像をダウンロードしました: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"画像ダウンロードエラー: {e}")
            return False
    
    def _create_placeholder_image(self, output_path: str, prompt: str) -> bool:
        """プレースホルダー画像を作成（API使用不可時）"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # 1080x1920の黒背景画像を作成
            img = Image.new('RGB', (1080, 1920), color='black')
            draw = ImageDraw.Draw(img)
            
            # テキスト描画
            try:
                # システムフォントを試行
                font = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 48)
            except:
                font = ImageFont.load_default()
            
            # プロンプトテキストを描画
            text_lines = [
                "PLACEHOLDER IMAGE",
                f"Prompt: {prompt[:30]}...",
                "API key not configured"
            ]
            
            y_offset = 800
            for line in text_lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (1080 - text_width) // 2
                draw.text((x, y_offset), line, fill='white', font=font)
                y_offset += 80
            
            # 出力ディレクトリを作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            img.save(output_path)
            logging.info(f"プレースホルダー画像を作成しました: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"プレースホルダー画像作成エラー: {e}")
            return False
    
    def generate_default_image_prompt(self, text: str) -> str:
        """テキスト内容から適切な画像プロンプトを生成"""
        # シンプルなキーワードベース画像プロンプト生成
        keywords = {
            '社長': 'professional businessman in modern office',
            '成功': 'successful person, luxury lifestyle', 
            '知性': 'intelligent person reading, library setting',
            '学習': 'person studying, books, peaceful environment',
            '仕事': 'person working at desk, professional setting'
        }
        
        for keyword, prompt_template in keywords.items():
            if keyword in text:
                return prompt_template
        
        # デフォルトプロンプト
        return 'modern professional background, clean minimal design'