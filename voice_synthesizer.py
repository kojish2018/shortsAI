#!/usr/bin/env python3
"""
音声合成器 - VOICEVOX APIを使用
テキストからVOICEVOXサーバーを使って音声ファイルを生成
"""

import requests
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
import wave
import io


class VoiceSynthesizer:
    """VOICEVOXを使った音声合成器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初期化
        Args:
            config: 設定辞書（apis.voicevoxキーを含む）
        """
        self.config = config['apis']['voicevox']
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 50021)
        self.speaker_id = self.config.get('speaker_id', 3)  # ずんだもん（ノーマル）
        self.speed_scale = self.config.get('speed_scale', 1.0)  # 朗読スピード
        self.pitch_scale = self.config.get('pitch_scale', 1.0)  # 音程調整
        self.volume_scale = self.config.get('volume_scale', 1.0)  # 音量調整
        self.intonation_scale = self.config.get('intonation_scale', 1.0)  # 抑揚調整
        self.base_url = f"http://{self.host}:{self.port}"
        
        logging.info(f"音声合成器 - VOICEVOX: {self.base_url}, Speaker ID: {self.speaker_id}, Speed: {self.speed_scale}x, Pitch: {self.pitch_scale}x, Volume: {self.volume_scale}x, Intonation: {self.intonation_scale}x")
        
        # VOICEVOX接続テスト
        if not self._check_connection():
            logging.warning("VOICEVOXサーバーに接続できません。無音ファイルで代替します")
    
    def _check_connection(self) -> bool:
        """VOICEVOXサーバーとの接続確認"""
        try:
            response = requests.get(f"{self.base_url}/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                logging.info(f"VOICEVOX接続成功: {version_info}")
                return True
            else:
                logging.warning(f"VOICEVOXサーバーエラー: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logging.warning(f"VOICEVOX接続失敗: {e}")
            return False
    
    def synthesize_voice(self, text: str, output_path: str) -> tuple[bool, float]:
        """
        テキストを音声に変換
        Args:
            text: 入力テキスト
            output_path: 音声ファイルのパス(.wav)
        Returns:
            tuple: (成功フラグ, 音声の長さ（秒）)
        """
        if not text.strip():
            logging.warning("空のテキストが指定されました")
            return self._create_silent_audio(output_path, 1.0)
        
        try:
            # クエリの作成
            audio_query = self._create_audio_query(text)
            if not audio_query:
                logging.error("音声クエリの作成に失敗しました")
                return self._create_silent_audio(output_path, 3.0)
            
            # 音声合成
            success = self._synthesize_audio(audio_query, output_path)
            if not success:
                return self._create_silent_audio(output_path, 3.0)
            
            # 音声の長さを取得
            duration = self._get_audio_duration(output_path)
            logging.info(f"音声合成完了: {text[:30]}... -> {duration:.2f}秒")
            
            return True, duration
            
        except Exception as e:
            logging.error(f"音声合成エラー: {e}")
            return self._create_silent_audio(output_path, 3.0)
    
    def _create_audio_query(self, text: str) -> Optional[Dict[str, Any]]:
        """テキストから音声クエリを作成"""
        try:
            url = f"{self.base_url}/audio_query"
            params = {
                "text": text,
                "speaker": self.speaker_id
            }
            
            response = requests.post(url, params=params, timeout=10)
            response.raise_for_status()
            
            audio_query = response.json()
            
            # 音声パラメータの調整を適用
            if self.speed_scale != 1.0:
                audio_query["speedScale"] = self.speed_scale
                logging.debug(f"音声スピードを{self.speed_scale}倍に設定")
            
            if self.pitch_scale != 1.0:
                audio_query["pitchScale"] = self.pitch_scale
                logging.debug(f"音程を{self.pitch_scale}倍に設定")
                
            if self.volume_scale != 1.0:
                audio_query["volumeScale"] = self.volume_scale
                logging.debug(f"音量を{self.volume_scale}倍に設定")
                
            if self.intonation_scale != 1.0:
                audio_query["intonationScale"] = self.intonation_scale
                logging.debug(f"抑揚を{self.intonation_scale}倍に設定")
            
            return audio_query
            
        except requests.exceptions.RequestException as e:
            logging.error(f"音声クエリ作成エラー: {e}")
            return None
    
    def _synthesize_audio(self, audio_query: Dict[str, Any], output_path: str) -> bool:
        """音声クエリから音声ファイルを生成"""
        try:
            url = f"{self.base_url}/synthesis"
            params = {"speaker": self.speaker_id}
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(
                url,
                params=params,
                data=json.dumps(audio_query),
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # 出力ディレクトリの作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # WAVファイルの書き込み
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"音声ファイル出力完了: {output_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"音声合成エラー: {e}")
            return False
        except Exception as e:
            logging.error(f"音声ファイル出力エラー: {e}")
            return False
    
    def _get_audio_duration(self, wav_path: str) -> float:
        """WAVファイルの長さ（秒）を取得"""
        try:
            with wave.open(wav_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)
                return duration
        except Exception as e:
            logging.error(f"音声長取得エラー: {e}")
            # デフォルト値（推定テキスト長から算出）
            return 3.0
    
    def _create_silent_audio(self, output_path: str, duration: float) -> tuple[bool, float]:
        """無音のWAVファイルを作成（フォールバック用）"""
        try:
            import numpy as np
            
            sample_rate = 44100  # 44.1kHz
            samples = int(sample_rate * duration)
            
            # 無音データの作成
            audio_data = np.zeros(samples, dtype=np.int16)
            
            # 出力ディレクトリの作成
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # WAVファイルの書き込み
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # モノラル
                wav_file.setsampwidth(2)  # 16bit
                wav_file.setframerate(sample_rate)  # 44.1kHz
                wav_file.writeframes(audio_data.tobytes())
            
            logging.info(f"無音ファイル作成完了: {output_path} ({duration:.2f}秒)")
            return True, duration
            
        except Exception as e:
            logging.error(f"無音ファイル作成エラー: {e}")
            return False, duration
    
    def get_available_speakers(self) -> Optional[Dict[str, Any]]:
        """利用可能な話者一覧を取得"""
        try:
            response = requests.get(f"{self.base_url}/speakers", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"話者取得エラー: {e}")
            return None
    
    def estimate_audio_duration(self, text: str) -> float:
        """テキストから音声の長さを推定"""
        # 簡単なテキスト長ベースの推定
        # 実際のVOICEVOXを使用していない場合の推定値
        
        if not text.strip():
            return 0.5
        
        # 日本語文字1文字あたり0.3-0.5秒程度
        char_count = len(text.replace(' ', '').replace('\n', ''))
        base_duration = char_count * 0.4
        
        # 句読点での間の追加
        pause_count = text.count('、') + text.count('。') + text.count('！') + text.count('？')
        pause_duration = pause_count * 0.3
        
        # 1秒から10秒の範囲に制限
        total_duration = max(1.0, min(base_duration + pause_duration, 10.0))
        
        # スピード調整を適用（速度が速いほど短くなる）
        adjusted_duration = total_duration / self.speed_scale
        
        return adjusted_duration