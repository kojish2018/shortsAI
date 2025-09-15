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
        CompositeVideoClip, CompositeAudioClip, concatenate_videoclips, concatenate_audioclips,
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
        self.bgm_config = config.get('bgm', {})
        
        # 動画設定
        self.width = self.video_config.get('width', 1080)
        self.height = self.video_config.get('height', 1920)
        self.fps = self.video_config.get('fps', 30)
        self.codec = self.video_config.get('codec', 'libx264')
        
        # テキスト設定
        self.font_family = self.text_config.get('font_family', 'Arial')
        self.default_font_size = self.text_config.get('default_size', 48)
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
                
                # 音声クリップの追加（音圧アップ適用）
                if 'audio_path' in page_data and Path(page_data['audio_path']).exists():
                    audio_clip = AudioFileClip(page_data['audio_path']).set_start(current_time)
                    # ナレーション音圧アップ
                    narration_boost = self.bgm_config.get('narration_boost', 1.3)
                    audio_clip = audio_clip.volumex(narration_boost)
                    audio_clips.append(audio_clip)
                
                current_time += page_data.get('duration', 3.0)
            
            if not video_clips:
                logging.error("有効な動画クリップが作成できませんでした")
                return False
            
            # 全体のクリップを合成
            final_video = CompositeVideoClip(video_clips, size=(self.width, self.height))
            
            # 音声の合成（BGM含む）
            if audio_clips:
                final_audio = self._create_final_audio_with_bgm(audio_clips, current_time)
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
        """利用可能なフォントパスを取得（ExtraBold優先、同梱フォントを優先）"""
        # 同梱フォントのパス
        bundled_extrabold_font_path = Path(__file__).parent / "fonts" / "NotoSansJP-ExtraBold.ttf" # または .otf
        if bundled_extrabold_font_path.exists():
            return str(bundled_extrabold_font_path)

        bundled_bold_font_path = Path(__file__).parent / "fonts" / "NotoSansJP-Bold.ttf" # または .otf
        if bundled_bold_font_path.exists():
            return str(bundled_bold_font_path)

        # macOSのシステムフォント
        system_font_paths = [
            '/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc', # ヒラギノ角ゴシックのExtraBold相当
            '/System/Library/Fonts/NotoSansJP-ExtraBold.otf', # Noto Sans JP ExtraBold (一般的なパス)
            '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', # ヒラギノ角ゴシックの太字
            '/System/Library/Fonts/NotoSansJP-Bold.otf', # Noto Sans JP Bold (一般的なパス)
            '/System/Library/Fonts/Arial Black.ttf', # Arial Black (ExtraBold相当)
            '/System/Library/Fonts/Arial Bold.ttf', # Arial Bold
            '/System/Library/Fonts/Helvetica Bold.ttf' # Helvetica Bold
        ]
        
        for font_path in system_font_paths:
            if Path(font_path).exists():
                return font_path
        
        logging.warning("太字フォントが見つかりません。デフォルトフォント（Arial）を試します。")
        return 'Arial'  # フォールバック
    
    def _apply_typewriter_effect(self, text_clip: TextClip, duration: float) -> Optional[VideoClip]:
        """
        アニメーション効果（現在は無効化され、静的クリップを返す）
        """
        # 安定した状態に戻すため、アニメーションを無効化
        return text_clip.set_duration(duration)

    def _create_reveal_mask_frame(self, t: float, width: int, height: int, duration: float) -> np.ndarray:
        """リヴィール効果のためのマスクフレームを生成する"""
        revealed_width = width
        if duration > 0:
            revealed_width = int(width * (t / duration))
        
        # マスク用の黒い画像を作成 (0が透明)
        mask_frame = np.zeros((height, width), dtype=np.uint8)
        
        # 表示する部分を白くする (255が不透明)
        if revealed_width > 0:
            mask_frame[:, :revealed_width] = 255
            
        return mask_frame

    def _apply_fade_in_effect(self, text_clip: TextClip, duration: float) -> Optional[VideoClip]:
        """フェードイン効果の適用（現在は無効化）"""
        # 安定化のため、エフェクトを無効化し静的クリップを返す
        return text_clip.set_duration(duration)
    
    def _create_page_specific_image_clip(self, image_path: str, duration: float, page_number: int) -> Optional[ImageClip]:
        """ページ番号に応じて画像クリップを作成"""
        try:
            # 画像を読み込み
            img_clip = ImageClip(image_path, duration=duration)
            
            if page_number == 1:
                # 1ページ目：下に小さく配置（0.55倍）
                target_size = int(self.width * 0.55)
                img_clip = img_clip.resize((target_size, target_size))
                # 下側に配置（下のマージンが約15%になるように）
                position = ('center', int(self.height * 0.7 - target_size / 2))
                img_clip = img_clip.set_position(position)
            else:
                # 2ページ目以降：1300pxの正方形にリサイズ後、上下を900pxにクロップしてパン
                
                # 1300x1300pxの正方形にリサイズ
                square_size = 1300
                square_clip = img_clip.resize((square_size, square_size))

                # 上下を均等にクロップして、高さを900pxにする
                crop_height = 900
                cropped_clip = square_clip.crop(
                    y_center=square_clip.h / 2,
                    height=crop_height
                )

                # y座標を画面上部10%の位置に固定
                y_position = int(self.height * 0.1)

                # 右から左にパンするアニメーション関数
                def move_func(t):
                    # 開始x座標（画像の右端が画面の右端に揃う）
                    start_x = self.width - cropped_clip.w
                    # 終了x座標（画像の左端が画面の左端に揃う）
                    end_x = 0
                    # 線形補間でx座標を計算
                    current_x = start_x + (end_x - start_x) * (t / duration)
                    return (current_x, y_position)
                
                # アニメーションを適用
                img_clip = cropped_clip.set_position(move_func).set_duration(duration)
            
            return img_clip
            
        except Exception as e:
            logging.error(f"ページ固有画像クリップ作成エラー: {e}")
            return None
    
    def _create_positioned_text_clips(self, text: str, duration: float, page_data: Dict[str, Any]) -> List[TextClip]:
        """テキストクリップをページ番号に応じて配置"""
        clips = []
        
        try:
            # テキスト設定の取得
            font_size = 48
            color = '#000000'
            animation_type = page_data.get('animation', 'fade_in')
            page_number = page_data.get('page_number', 1)
            
            # ページ番号に応じてテキスト位置を調整
            if page_number == 1:
                # 1ページ目：画像が下にあるので、テキストは上に配置
                text_y_position = int(self.height * 0.15)  # 上から15%の位置
            else:
                # 2ページ目以降：画像が上にあるので、テキストは下に配置
                text_y_position = int(self.height * 0.65)  # 上から65%の位置
            
            # 1ページ目のみ=で囲まれたテキストをグレー背景で処理
            if page_number == 1:
                text_clips = self._create_text_clips_with_highlights(
                    text, font_size, color, text_y_position, duration, animation_type
                )
                clips.extend(text_clips)
            else:
                # 2ページ目以降も##記号のテキストを赤色で処理
                text_clips = self._parse_and_create_colored_text(
                    text, font_size, color, '#FF0000', text_y_position, duration, animation_type
                )
                clips.extend(text_clips)
            
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
    
    def _parse_and_create_colored_text(self, text: str, font_size: int, normal_color: str, 
                                     highlight_color: str, text_y_position: int, duration: float, 
                                     animation_type: str) -> List[TextClip]:
        """##で囲まれたテキストを赤色で表示するテキストクリップを作成（超シンプル版）"""
        clips = []
        
        try:
            import re
            
            # ##で囲まれた部分があるかチェック
            if '##' not in text:
                # ##がない場合は通常のテキストクリップを作成
                normal_clip = TextClip(
                    text,
                    fontsize=font_size,
                    color=normal_color,
                    font=self._get_font_path(),
                    method='caption',
                    size=(int(self.width * 0.9), None),
                    align='center',
                    bg_color='transparent',
                    interline=40 if font_size == 60 else 20
                )
                normal_clip = normal_clip.set_position(('center', text_y_position))
                
                if animation_type == 'fade_in':
                    normal_clip = self._apply_fade_in_effect(normal_clip, duration)
                else:
                    normal_clip = normal_clip.set_duration(duration)
                
                clips.append(normal_clip)
                return clips
            
            # 超シンプル方式：##部分を空白に置き換えて通常色で表示
            normal_text = re.sub(r'##([^#]*)##', lambda m: ' ' * len(m.group(1)), text)
            normal_clip = TextClip(
                normal_text,
                fontsize=font_size,
                color=normal_color,
                font=self._get_font_path(),
                method='caption',
                size=(int(self.width * 0.9), None),
                align='center',
                bg_color='transparent',
                interline=40 if font_size == 60 else 20
            )
            normal_clip = normal_clip.set_position(('center', text_y_position))
            
            if animation_type == 'fade_in':
                normal_clip = self._apply_fade_in_effect(normal_clip, duration)
            else:
                normal_clip = normal_clip.set_duration(duration)
            clips.append(normal_clip)
            
            # ##部分だけを赤色で表示（超シンプル方式）
            red_matches = list(re.finditer(r'##([^#]*)##', text))
            if red_matches:
                # 元のテキストをベースに、##部分以外を空白にした赤テキストを作成
                red_text = list(text)  # 文字配列に変換
                
                # まず全ての文字を空白に
                for i, char in enumerate(red_text):
                    if char != '\n':  # 改行は保持
                        red_text[i] = ' '
                
                # ##で囲まれた部分だけを元の文字に戻す
                for match in red_matches:
                    start = match.start() + 2  # ##の後から
                    content = match.group(1)   # ##内の文字
                    
                    for i, char in enumerate(content):
                        if start + i < len(red_text):
                            red_text[start + i] = char
                
                red_text_str = ''.join(red_text)
                
                if red_text_str.strip():
                    red_clip = TextClip(
                        red_text_str,
                        fontsize=font_size,
                        color=highlight_color,
                        font=self._get_font_path(),
                        method='caption',
                        size=(int(self.width * 0.9), None),
                        align='center',
                        bg_color='transparent',
                        interline=40 if font_size == 60 else 20
                    )
                    red_clip = red_clip.set_position(('center', text_y_position))
                    
                    if animation_type == 'fade_in':
                        red_clip = self._apply_fade_in_effect(red_clip, duration)
                    else:
                        red_clip = red_clip.set_duration(duration)
                    clips.append(red_clip)
            
        except Exception as e:
            logging.error(f"カラーテキスト解析エラー: {e}")
            # エラー時は##を除去した通常のテキストクリップを作成
            fallback_clip = TextClip(
                text.replace('##', ''),
                fontsize=font_size,
                color=normal_color,
                font=self._get_font_path(),
                method='caption',
                size=(int(self.width * 0.9), None),
                align='center',
                bg_color='transparent',
                interline=40 if font_size == 60 else 20
            )
            fallback_clip = fallback_clip.set_position(('center', text_y_position)).set_duration(duration)
            clips.append(fallback_clip)
        
        return clips
    
    def _create_final_audio_with_bgm(self, audio_clips: List[AudioFileClip], total_duration: float) -> CompositeAudioClip:
        """ナレーションとBGMをミックスした最終音声を作成"""
        try:
            # ナレーション音声の合成
            narration_audio = CompositeAudioClip(audio_clips)
            final_clips = [narration_audio]
            
            # BGM設定の取得
            bgm_path = self.bgm_config.get('file_path', 'music/motivation-music3.mp3')
            bgm_volume = self.bgm_config.get('volume', 0.3)  # ナレーションより小さく
            
            # BGMファイルの存在確認
            if Path(bgm_path).exists():
                try:
                    # BGMを読み込み
                    bgm_audio = AudioFileClip(bgm_path)
                    
                    # 最初の3秒をカット（無音部分の除去）
                    if bgm_audio.duration > 3:
                        bgm_audio = bgm_audio.subclip(3)
                    
                    # 動画の長さに合わせてBGMをトリミング
                    if bgm_audio.duration > total_duration:
                        bgm_audio = bgm_audio.subclip(0, total_duration)
                    elif bgm_audio.duration < total_duration:
                        # BGMが短い場合はループ
                        loops_needed = int(total_duration / bgm_audio.duration) + 1
                        bgm_loops = [bgm_audio] * loops_needed
                        bgm_audio = concatenate_audioclips(bgm_loops).subclip(0, total_duration)
                    
                    # BGM音量と音圧を調整
                    bgm_boost = self.bgm_config.get('bgm_boost', 1.2)
                    bgm_audio = bgm_audio.volumex(bgm_volume * bgm_boost)
                    
                    final_clips.append(bgm_audio)
                    logging.info(f"BGMを追加しました: {bgm_path} (音量: {bgm_volume})")
                    
                except Exception as e:
                    logging.warning(f"BGM処理エラー: {e}。BGMなしで続行します。")
            else:
                logging.warning(f"BGMファイルが見つかりません: {bgm_path}")
            
            return CompositeAudioClip(final_clips)
            
        except Exception as e:
            logging.error(f"音声ミックスエラー: {e}")
            # エラー時はナレーションのみ返す
            return CompositeAudioClip(audio_clips)
    
    
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
    
    def _create_text_clips_with_highlights(self, text: str, font_size: int, color: str, 
                                         text_y_position: int, duration: float, animation_type: str) -> List[TextClip]:
        """=で囲まれたテキストをハイライトせず、##で囲まれたテキストを赤色で表示するテキストクリップを作成"""
        clips = []
        
        try:
            # =記号を単純に除去して##記号のテキストを処理
            processed_text = text.replace('=', '')
            text_clips = self._parse_and_create_colored_text(
                processed_text, 60, color, '#FF0000', text_y_position, duration, animation_type
            )
            clips.extend(text_clips)
            
        except Exception as e:
            logging.error(f"ハイライト付きテキストクリップ作成エラー: {e}")
            # エラー時はフォールバック処理
            fallback_clip = TextClip(
                text,
                fontsize=font_size,
                color=color,
                font=self._get_font_path(),
                method='caption',
                size=(int(self.width * 0.9), None),
                align='center',
                bg_color='transparent',
                interline=20
            )
            fallback_clip = fallback_clip.set_position(('center', text_y_position)).set_duration(duration)
            clips.append(fallback_clip)
        
        return clips