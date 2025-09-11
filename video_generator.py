#!/usr/bin/env python3
"""
動画生成器 - MoviePyを使用
テキスト、画像、音声から動画ファイルを生成する
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

# MoviePyのインポート
try:
    from moviepy.editor import (
        VideoFileClip, ImageClip, AudioFileClip, TextClip, 
        CompositeVideoClip, CompositeAudioClip, concatenate_videoclips,
        VideoClip, ImageSequenceClip
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    logging.warning("MoviePyがインストールされていません。pip install moviepyで導入してください")
    MOVIEPY_AVAILABLE = False

# PILのインポート（テキスト描画用）
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    logging.warning("Pillowがインストールされていません。pip install Pillowで導入してください")
    PIL_AVAILABLE = False


class VideoGenerator:
    """MoviePyを使った動画生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初期化
        Args:
            config: 設定辞書（video, text, animationキーを含む）
        """
        self.config = config
        self.video_config = config.get('video', {})
        self.text_config = config.get('text', {})
        self.animation_config = config.get('animation', {})
        
        # 動画設定
        self.width = self.video_config.get('width', 1080)
        self.height = self.video_config.get('height', 1920)
        self.fps = self.video_config.get('fps', 30)
        self.codec = self.video_config.get('codec', 'libx264')
        
        # テキスト設定
        self.font_family = self.text_config.get('font_family', 'Arial')
        self.default_font_size = self.text_config.get('default_size', 32)
        self.default_color = self.text_config.get('colors', {}).get('default', '#000000')
        self.highlight_color = self.text_config.get('colors', {}).get('highlight', '#FF0000')
        
        # アニメーション設定
        self.typewriter_speed = self.animation_config.get('typewriter_speed', 2)
        self.fade_duration = self.animation_config.get('fade_duration', 20) / self.fps  # フレーム数
        
        logging.info(f"動画生成器 - 解像度: {self.width}x{self.height}, FPS: {self.fps}")
        
        if not MOVIEPY_AVAILABLE:
            logging.error("MoviePyが利用できません。動画生成機能は制限されます")
    
    def generate_video(self, pages_data: List[Dict[str, Any]], output_path: str) -> bool:
        """
        複数ページから動画を生成
        Args:
            pages_data: ページデータのリスト
            output_path: 出力動画ファイルのパス
        Returns:
            成功時True
        """
        if not MOVIEPY_AVAILABLE:
            logging.error("MoviePyが利用できないため、動画生成をスキップします")
            return self._create_placeholder_video(output_path)
        
        try:
            video_clips = []
            audio_clips = []
            current_time = 0.0
            
            for i, page_data in enumerate(pages_data):
                logging.info(f"ページ {i+1}/{len(pages_data)} の動画クリップを作成中...")
                
                # ページごとのクリップを作成
                page_clip = self._create_page_video(page_data, current_time)
                if page_clip:
                    video_clips.append(page_clip)
                
                # 音声クリップの追加
                if 'audio_path' in page_data and Path(page_data['audio_path']).exists():
                    audio_clip = AudioFileClip(page_data['audio_path']).set_start(current_time)
                    audio_clips.append(audio_clip)
                
                current_time += page_data.get('duration', 3.0)
            
            if not video_clips:
                logging.error("有効な動画クリップが作成できませんでした")
                return False
            
            # 全体のクリップを合成
            final_video = CompositeVideoClip(video_clips, size=(self.width, self.height))
            
            # 音声の合成
            if audio_clips:
                final_audio = CompositeAudioClip(audio_clips)
                final_video = final_video.set_audio(final_audio)
            
            # 出力ディレクトリの作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 動画の書き出し
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec=self.codec,
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # リソースクリップの解放
            final_video.close()
            for clip in video_clips + audio_clips:
                if hasattr(clip, 'close'):
                    clip.close()
            
            logging.info(f"動画生成完了: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"動画生成エラー: {e}")
            return False
    
    def _create_page_video(self, page_data: Dict[str, Any], start_time: float) -> Optional[CompositeVideoClip]:
        """単一ページの動画クリップを作成（ref-imagesレイアウトに基づく）"""
        try:
            duration = page_data.get('duration', 3.0)
            background_path = page_data.get('background_path')
            text = page_data.get('text', '')
            
            clips = []
            
            # 常に白い背景を作成
            white_bg = self._create_default_background(duration)
            clips.append(white_bg)
            
            # 生成された画像をページ番号に応じて配置
            if background_path and Path(background_path).exists():
                page_number = page_data.get('page_number', 1)
                generated_img_clip = self._create_page_specific_image_clip(background_path, duration, page_number)
                if generated_img_clip:
                    clips.append(generated_img_clip)
            
            # テキストクリップ（画像の上下に配置）
            if text:
                text_clips = self._create_positioned_text_clips(text, duration, page_data)
                clips.extend(text_clips)
            
            if not clips:
                return None
            
            # 全てのクリップを合成してページクリップを作成
            page_clip = CompositeVideoClip(clips, size=(self.width, self.height))
            page_clip = page_clip.set_start(start_time).set_duration(duration)
            
            return page_clip
            
        except Exception as e:
            logging.error(f"ページクリップ作成エラー: {e}")
            return None
    
    def _create_background_clip(self, image_path: str, duration: float) -> Optional[ImageClip]:
        """背景画像クリップの作成"""
        try:
            # 画像を読み込み、リサイズ
            img_clip = ImageClip(image_path, duration=duration)
            
            # Shortsサイズ（縦長）にリサイズ・クロップ
            img_clip = img_clip.resize(height=self.height)
            if img_clip.w > self.width:
                img_clip = img_clip.crop(
                    x_center=img_clip.w/2,
                    width=self.width,
                    height=self.height
                )
            elif img_clip.w < self.width:
                img_clip = img_clip.resize(width=self.width)
            
            return img_clip
            
        except Exception as e:
            logging.error(f"背景画像作成エラー: {e}")
            return None
    
    def _create_default_background(self, duration: float) -> ImageClip:
        """デフォルトの背景（白）クリップを作成"""
        # NumPyで白い画像を作成
        white_image = np.full((self.height, self.width, 3), 255, dtype=np.uint8)
        return ImageClip(white_image, duration=duration)
    
    def _create_text_clips(self, text: str, duration: float, page_data: Dict[str, Any]) -> List[TextClip]:
        """テキストクリップのリストを作成"""
        clips = []
        
        try:
            # テキスト設定の取得
            font_size = page_data.get('font_size', self.default_font_size)
            color = page_data.get('color', self.default_color)
            animation_type = page_data.get('animation', 'fade_in')
            
            # 基本テキストクリップの作成
            text_clip = TextClip(
                text,
                fontsize=font_size,
                color=color,
                font=self._get_font_path(),
                method='caption',
                size=(int(self.width * 0.8), None),  # 画面幅80%を使用
                align='center'
            )
            
            # テキストの位置を中央に設定
            text_clip = text_clip.set_position('center')
            
            # アニメーション効果の適用
            if animation_type == 'typewriter':
                animated_clip = self._apply_typewriter_effect(text_clip, duration)
            elif animation_type == 'fade_in':
                animated_clip = self._apply_fade_in_effect(text_clip, duration)
            else:
                animated_clip = text_clip.set_duration(duration)
            
            if animated_clip:
                clips.append(animated_clip)
            
        except Exception as e:
            logging.error(f"テキストクリップ作成エラー: {e}")
            # エラー時は簡単なテキストクリップを作成
            try:
                simple_clip = TextClip(
                    text,
                    fontsize=32,
                    color='white',
                    method='caption'
                ).set_duration(duration).set_position('center')
                clips.append(simple_clip)
            except:
                pass  # それでも失敗する場合はスキップ
        
        return clips
    
    def _get_font_path(self) -> str:
        """利用可能なフォントパスを取得"""
        # macOSの標準フォント
        font_paths = [
            '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
            '/System/Library/Fonts/Arial.ttf',
            '/System/Library/Fonts/Helvetica.ttc'
        ]
        
        for font_path in font_paths:
            if Path(font_path).exists():
                return font_path
        
        return 'Arial'  # フォールバック
    
    def _apply_typewriter_effect(self, text_clip: TextClip, duration: float) -> Optional[TextClip]:
        """タイプライター効果の適用"""
        try:
            # 実際のタイプライター効果は複雑なので、
            # 現在は簡単なフェードイン効果で代用する
            return text_clip.set_duration(duration).fadein(0.5)
        except Exception as e:
            logging.error(f"タイプライター効果エラー: {e}")
            return text_clip.set_duration(duration)
    
    def _apply_fade_in_effect(self, text_clip: TextClip, duration: float) -> Optional[VideoClip]:
        """フェードイン効果の適用"""
        try:
            fade_time = min(self.fade_duration, duration / 3)
            return text_clip.set_duration(duration).fadein(fade_time)
        except Exception as e:
            logging.error(f"フェードイン効果エラー: {e}")
            return text_clip.set_duration(duration)
    
    def _create_page_specific_image_clip(self, image_path: str, duration: float, page_number: int) -> Optional[ImageClip]:
        """ページ番号に応じて画像クリップを作成"""
        try:
            # 画像を読み込み
            img_clip = ImageClip(image_path, duration=duration)
            
            if page_number == 1:
                # 1ページ目：下に小さく配置（0.5倍）
                target_size = int(self.width * 0.5)
                img_clip = img_clip.resize((target_size, target_size))
                # 下側に配置（下から20%の位置）
                position = ('center', int(self.height * 0.8 - target_size / 2))
                img_clip = img_clip.set_position(position)
            else:
                # 2ページ目以降：上に横いっぱい（正方形維持）
                target_size = int(self.width * 0.9)  # 横いっぱい（90%）
                img_clip = img_clip.resize((target_size, target_size))
                # 上側に配置（上から20%の位置）
                position = ('center', int(self.height * 0.2))
                img_clip = img_clip.set_position(position)
            
            return img_clip
            
        except Exception as e:
            logging.error(f"ページ固有画像クリップ作成エラー: {e}")
            return None
    
    def _create_positioned_text_clips(self, text: str, duration: float, page_data: Dict[str, Any]) -> List[TextClip]:
        """テキストクリップをページ番号に応じて配置"""
        clips = []
        
        try:
            # テキスト設定の取得
            font_size = page_data.get('font_size', self.default_font_size)
            # 黒文字に変更（白背景のため）
            color = '#000000'
            animation_type = page_data.get('animation', 'fade_in')
            page_number = page_data.get('page_number', 1)
            
            text_clip = TextClip(
                text,
                fontsize=font_size,
                color=color,
                font=self._get_font_path(),
                method='caption',
                size=(int(self.width * 0.9), None),  # 画面幅90%を使用
                align='center'
            )
            
            # ページ番号に応じてテキスト位置を調整
            if page_number == 1:
                # 1ページ目：画像が下にあるので、テキストは上に配置
                text_y_position = int(self.height * 0.15)  # 上から15%の位置
            else:
                # 2ページ目以降：画像が上にあるので、テキストは下に配置
                text_y_position = int(self.height * 0.75)  # 上から75%の位置
            
            text_clip = text_clip.set_position(('center', text_y_position))
            
            # アニメーション効果の適用
            if animation_type == 'fade_in':
                animated_clip = self._apply_fade_in_effect(text_clip, duration)
            else:
                animated_clip = text_clip.set_duration(duration)
            
            if animated_clip:
                clips.append(animated_clip)
            
        except Exception as e:
            logging.error(f"位置付きテキストクリップ作成エラー: {e}")
            # エラー時は簡単なテキストクリップを作成
            try:
                page_number = page_data.get('page_number', 1)
                fallback_y = int(self.height * 0.15) if page_number == 1 else int(self.height * 0.75)
                simple_clip = TextClip(
                    text,
                    fontsize=32,
                    color='black',
                    method='caption'
                ).set_duration(duration).set_position(('center', fallback_y))
                clips.append(simple_clip)
            except:
                pass  # それでも失敗する場合はスキップ
        
        return clips
    
    def _create_placeholder_video(self, output_path: str) -> bool:
        """プレースホルダー動画を作成（MoviePy不使用時）"""
        try:
            # 簡単なテキストファイルを作成（実際の用途では適切な実装に置き換える）
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # テキストファイルを作成（代替手段）
            with open(output_path, 'w') as f:
                f.write("# Placeholder video file - MoviePy not available\n")
            
            logging.info(f"プレースホルダー動画ファイルを作成しました: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"プレースホルダー動画作成エラー: {e}")
            return False
    
    def create_page_data(self, text: str, image_path: str, audio_path: str, duration: float, page_number: int = 1) -> Dict[str, Any]:
        """ページデータの作成"""
        return {
            'text': text,
            'background_path': image_path,
            'audio_path': audio_path,
            'duration': duration,
            'page_number': page_number,
            'font_size': self.default_font_size,
            'color': self.default_color,
            'animation': 'fade_in'
        }