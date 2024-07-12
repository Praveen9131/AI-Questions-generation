import os
import logging
from flask import Flask, request, jsonify, send_file
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image
import requests
from openai import OpenAI
from simple_mcq import generate_quiz
from simple_checkox import generate_quizc
from fill_in_the_blanks import generate_quiz1
from image_to_image_mcq import download_and_resize_image as download_and_resize_image2, generate_image as generate_image2, generate_image_options, generate_mcq_with_image_options, generate_custom_content, image_store
from images_txt import generate_custom_content1, image_store1

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.error("OPENAI_API_KEY environment variable not set")
    exit()

# Initialize OpenAI client with API key
client = OpenAI(api_key=openai_api_key)

app = Flask(__name__)

@app.route('/generate_quiz', methods=['GET'])
def generate_quiz_route():
    number = request.args.get('number', type=int)
    subject = request.args.get('subject', type=str)
    tone = request.args.get('tone', type=str)
    quiz_type = request.args.get('quiz_type', type=int)  # Ensure this matches the parameter in the URL

    if quiz_type == 100:
        response = generate_quiz(number, subject, tone)  # Simple MCQ type
    elif quiz_type == 200:
        response = generate_quizc(number, subject, tone)  # Checkbox type
    elif quiz_type == 300:
        response = generate_quiz1(number, subject, tone)  # Fill in the blanks
    elif quiz_type == 500:
        response = generate_custom_content1(number, subject, tone)
    elif quiz_type == 600:
        response = generate_custom_content(number, subject, tone)
    else:
        response = {"error": "Invalid quiz type"}

    return jsonify(response)

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Serve an image from in-memory storage based on quiz type."""
    quiz_type = request.args.get('quiz_type', type=int)
    if quiz_type == 500 and image_key in image_store1:
        return send_file(
            BytesIO(image_store1[image_key].getvalue()),
            mimetype='image/png'
        )
    elif quiz_type == 600 and image_key in image_store:
        return send_file(
            BytesIO(image_store[image_key].getvalue()),
            mimetype='image/png'
        )
    else:
        logger.error(f"Image with key {image_key} not found")
        return jsonify({"error": "Image not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
