# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ShortsAI is a YouTube Shorts auto-generation tool that creates vertical videos (1080x1920px) from simple text scripts. The system integrates AI image generation, voice synthesis, text animation, and video compilation to produce complete short-form videos automatically.

## Common Commands

### Running the Application
```bash
# Generate video from simple text script
python main.py simple_script.txt

# Generate and upload to YouTube
python main.py simple_script.txt --upload

# Schedule upload for later
python main.py simple_script.txt --upload --schedule "2024-12-25 08:00"

# Generate as regular video (not YouTube Shorts)
python main.py simple_script.txt --upload --no-shorts
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run basic test
python test/image_gen_test.py
```

### Configuration
The main configuration is in `config.yaml`. Key settings:
- API keys for image generation (Pollinations.ai, DeepL)
- VOICEVOX settings for voice synthesis
- Video resolution and quality settings
- Animation timing parameters

## Core Architecture

### Main Processing Pipeline (`main.py`)
1. **Script Parsing**: Converts simple text files (split by empty lines) into page data
2. **Translation**: Uses DeepL API to translate Japanese text to English for image prompts
3. **Image Generation**: Creates background images using Pollinations.ai API
4. **Voice Synthesis**: Generates audio using VOICEVOX API
5. **Video Assembly**: Combines images, audio, and text animations using MoviePy
6. **YouTube Upload**: Optionally uploads to YouTube with scheduling support

### Core Components

#### `video_generator.py` - Video Assembly Engine
- **Page-based Layout**: Page 1 has image at bottom, text at top. Page 2+ has image at top with panning animation, text at bottom
- **Text Rendering**: Supports highlighted text with gray backgrounds for `=enclosed=` text on page 1
- **Animation System**: Typewriter effects, fade-in/out, text positioning
- **Font Management**: Prioritizes ExtraBold fonts (NotoSansJP-ExtraBold) with fallbacks

#### `image_generator.py` - AI Image Generation
- **Provider**: Pollinations.ai (free image generation service)
- **Format**: Generates images via URL-based API calls
- **Specifications**: Configurable dimensions, supports various models (flux, sdxl, etc.)

#### `voice_synthesizer.py` - Audio Generation
- **Engine**: VOICEVOX local API integration
- **Features**: Configurable speakers, audio duration estimation
- **Output**: WAV format audio files

#### `youtube_uploader.py` - Upload Management
- **Authentication**: OAuth 2.0 with local credential storage
- **Features**: Scheduled uploads, Shorts vs regular video detection
- **Metadata**: Auto-generated titles and descriptions

### Input Formats

#### Simple Script Format (`simple_script.txt`)
```
Text block 1
More text for page 1
=Highlighted text=

Text for page 2
Another line

Text for page 3
```
- Empty lines separate pages
- `=text=` creates gray background highlights on page 1 only

#### Advanced YAML Format (`sample_script.yaml`)
Full scene-by-scene control with timing, animations, and custom prompts.

### Video Specifications
- **Resolution**: 1080x1920px (9:16 aspect ratio)
- **Frame Rate**: 30fps
- **Format**: MP4 with H.264 codec
- **Duration**: Up to 60 seconds (YouTube Shorts limit)

### Text Animation Features
- **Page 1**: Special handling for `=enclosed=` text with gray backgrounds
- **Typewriter Effect**: Character-by-character reveal animation
- **Fade Effects**: Smooth opacity transitions
- **Positioning**: Different layouts per page number
- **Font Rendering**: Multi-language support with emphasis on bold/extra-bold weights

### Key Integration Points
- **DeepL Translation**: Japanese → English for AI image prompts
- **VOICEVOX**: Local voice synthesis server (runs on localhost:50021)
- **Pollinations.ai**: URL-based image generation
- **MoviePy**: Video composition and effects
- **YouTube API**: Upload with metadata and scheduling

### Configuration Management
All settings centralized in `config.yaml`:
- API endpoints and keys
- Video quality parameters  
- Animation timing settings
- Output directories
- Font preferences

### Error Handling
- Graceful degradation when APIs fail
- Fallback font rendering
- Temporary file cleanup
- Detailed logging throughout pipeline

## File Structure
- `main.py` - Entry point and orchestration
- `video_generator.py` - Core video assembly with page-specific layouts
- `image_generator.py` - AI image generation via Pollinations.ai
- `voice_synthesizer.py` - VOICEVOX integration
- `youtube_uploader.py` - YouTube API integration
- `config.yaml` - Main configuration file
- `requirements.txt` - Python dependencies
- `simple_script.txt` - Example simple input format
- `sample_script.yaml` - Example advanced input format