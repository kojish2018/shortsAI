import yaml
import sys
import os
import logging

# Add project root to the Python path to allow module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from image_generator import ImageGenerator

# Basic logging setup
logging.basicConfig(level="INFO", format='%(levelname)s: %(message)s')

# Load config
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    logging.error(f"Could not load config.yaml: {e}")
    exit()

# Prepare for test
output_dir = 'test'
output_path = os.path.join(output_dir, 'test_image.png')
prompt = "a cute cat"

# Initialize ImageGenerator
logging.info("Initializing ImageGenerator...")
image_generator = ImageGenerator(config)

# Run test
logging.info(f"Attempting to generate an image with prompt: '{prompt}'")
success = image_generator.generate_image(prompt, output_path)

if success and os.path.exists(output_path):
    logging.info(f"Image generation successful! Image saved to: {output_path}")
else:
    logging.error("Image generation failed. Please check your API key in config.yaml and the console for errors.")
