#!/usr/bin/env python3
"""
ShortsAI MVP - YouTube Shorts自動生成ツール
シンプルなテキストファイルから縦型ショート動画を完全自動生成

使用方法:
    python main.py script.txt [--upload] [--config config.yaml]
"""

import argparse
import sys
import yaml
import logging
import requests # Added for DeepL
from typing import List, Dict, Any
from pathlib import Path

# 実装済みのモジュール
from image_generator import ImageGenerator
from voice_synthesizer import VoiceSynthesizer
from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader


def setup_logging(log_level: str = "INFO") -> None:
    """ログ設定を初期化"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_config(config_path: str) -> Dict[str, Any]:
    """設定ファイルを読み込み"""
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logging.error(f"設定ファイルが見つかりません: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logging.error(f"設定ファイルの読み込みエラー: {e}")
        sys.exit(1)


def parse_simple_script(script_path: str) -> List[str]:
    """
    シンプルスクリプト形式を解析
    空行で区切られた各ブロックを1ページとして返す
    """
    try:
        with open(script_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()

        # 空行で分割してページを作成
        pages = [page.strip() for page in content.split('\n\n') if page.strip()]

        if not pages:
            logging.error("有効なページが見つかりません")
            sys.exit(1)

        logging.info(f"スクリプトを{len(pages)}ページに分割しました")
        return pages

    except FileNotFoundError:
        logging.error(f"スクリプトファイルが見つかりません: {script_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"スクリプト読み込みエラー: {e}")
        sys.exit(1)

def translate_text(text: str, api_key: str) -> str:
    """DeepL APIを使ってテキストを英語に翻訳する"""
    if not api_key:
        logging.warning("DeepL APIキーが設定されていません。翻訳をスキップします。")
        return text

    url = "https://api-free.deepl.com/v2/translate"
    headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
    data = {
        "text": text,
        "target_lang": "EN"
    }
    try:
        response = requests.post(url, headers=headers, data=data, timeout=20)
        response.raise_for_status()
        translated_text = response.json()["translations"][0]["text"]
        logging.info(f"翻訳完了: '{text[:20]}...' -> '{translated_text[:20]}...' ")
        return translated_text
    except requests.exceptions.RequestException as e:
        logging.error(f"DeepL APIへのリクエストに失敗しました: {e}")
        return text # エラー時は元のテキストを返す
    except Exception as e:
        logging.error(f"翻訳処理中に予期せぬエラー: {e}")
        return text


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(description='ShortsAI MVP - YouTube Shorts自動生成ツール')
    parser.add_argument('script', help='入力スクリプトファイル (.txt)')
    parser.add_argument('--config', default='config.yaml', help='設定ファイル (デフォルト: config.yaml)')
    parser.add_argument('--upload', action='store_true', help='生成後にYouTubeにアップロード')
    parser.add_argument('--output', help='出力ディレクトリ (config.yamlの設定を上書き)')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])

    args = parser.parse_args()

    # ログ設定
    setup_logging(args.log_level)
    logging.info("ShortsAI MVP を開始します")

    # 設定ファイル読み込み
    config = load_config(args.config)
    
    # DeepL APIキー取得
    deepl_api_key = config.get('apis', {}).get('deepl', {}).get('api_key', '')

    # 出力ディレクトリの設定
    if args.output:
        config['output']['directory'] = args.output

    # スクリプト解析
    pages = parse_simple_script(args.script)

    logging.info("=== ShortsAI 動画生成開始 ===")
    logging.info(f"処理対象ページ数: {len(pages)}ページ")

    # 出力ディレクトリを作成
    output_dir = Path(config['output']['directory'])
    temp_dir = Path(config['output']['temp_directory'])
    output_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)

    # 各モジュールを初期化
    image_generator = ImageGenerator(config)
    voice_synthesizer = VoiceSynthesizer(config)
    video_generator = VideoGenerator(config)

    # YouTube アップローダー（必要時のみ）
    youtube_uploader = None
    if args.upload:
        youtube_uploader = YouTubeUploader(config)
        if not youtube_uploader.authenticate():
            logging.warning("YouTube認証に失敗しました。アップロードはスキップされます")
            youtube_uploader = None

    try:
        # 各ページの処理
        pages_data = []
        total_duration = 0.0

        for i, page_text in enumerate(pages, 1):
            logging.info(f"ページ {i}/{len(pages)} を処理中: '{page_text[:30]}...' ")

            # 1. 画像生成 (DeepL翻訳を追加)
            image_path = temp_dir / f"page_{i:02d}.png"
            
            # 日本語テキストを英語に翻訳
            english_prompt = translate_text(page_text, deepl_api_key)
            
            logging.info(f"画像生成プロンプト ({i}/{len(pages)}): {english_prompt}")

            if not image_generator.generate_image(english_prompt, str(image_path)):
                logging.warning(f"ページ {i} の画像生成に失敗しました")

            # 2. 音声合成
            audio_path = temp_dir / f"page_{i:02d}.wav"
            logging.info(f"音声合成中 ({i}/{len(pages)}): {page_text[:20]}...")

            success, duration = voice_synthesizer.synthesize_voice(page_text, str(audio_path))
            if not success:
                logging.warning(f"ページ {i} の音声合成に失敗しました")
                duration = voice_synthesizer.estimate_audio_duration(page_text)

            # 簡単モードでの音声長ベースの継続時間計算
            if config.get('simple_mode', {}).get('duration_mode') == 'voice':
                padding = config.get('simple_mode', {}).get('padding_seconds', 0.5)
                page_duration = duration + (padding * 2)
            else:
                page_duration = duration

            total_duration += page_duration

            # ページデータを保存（ページ番号を含める）
            page_data = video_generator.create_page_data(
                text=page_text,
                image_path=str(image_path),
                audio_path=str(audio_path),
                duration=page_duration,
                page_number=i
            )
            pages_data.append(page_data)

            logging.info(f"ページ {i} 処理完了: {page_duration:.1f}秒")

        # 3. 動画生成
        video_filename = f"shorts_{len(pages)}pages_{int(total_duration)}s.mp4"
        video_path = output_dir / video_filename

        logging.info(f"最終動画生成中... (総時間: {total_duration:.1f}秒)")
        success = video_generator.generate_video(pages_data, str(video_path))

        if success:
            logging.info(f"動画生成完了: {video_path}")

            # 4. YouTube アップロード（オプション）
            if youtube_uploader and video_path.exists():
                script_title = Path(args.script).stem
                title = f"AI Generated Short: {script_title}"
                description = f"AI生成ショート動画 ({len(pages)}ページ, {total_duration:.1f}秒)"

                logging.info("YouTube アップロード中...")
                video_id = youtube_uploader.upload_video(str(video_path), title, description)

                if video_id:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    logging.info(f"YouTubeアップロード完了: {video_url}")
                else:
                    logging.warning("YouTubeアップロードに失敗しました")

            logging.info("=== 処理完了 ===")
        else:
            logging.error("動画生成に失敗しました")

    except KeyboardInterrupt:
        logging.info("処理が中断されました")
    except Exception as e:
        logging.error(f"処理中にエラーが発生しました: {e}")
    finally:
        # 一時ファイルの削除（設定による）
        if not config.get('output', {}).get('keep_temp_files', False):
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                logging.info("一時ファイルを削除しました")


if __name__ == "__main__":
    main()