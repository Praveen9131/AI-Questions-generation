import os
import logging
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from openai import OpenAI
import requests
from io import BytesIO
from PIL import Image
import random

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.error("OPENAI_API_KEY environment variable not set")

# Initialize OpenAI client with API key
client = OpenAI(api_key=openai_api_key)

# In-memory storage for images
image_store = {}

def generate_image(prompt: str):
    """Generate an image using DALL-E 3 based on a given prompt."""
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        response = client.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024")
        image_url = response.data[0].url
        logger.info(f"Generated image URL: {image_url}")
        return image_url
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

def download_and_resize_image(image_url, target_size):
    """Download and resize the image from the given URL."""
    try:
        logger.info(f"Downloading image from URL: {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))

        original_size = image.size
        logger.info(f"Original image size: {original_size}")

        resized_image = image.resize(target_size, Image.LANCZOS)
        resized_size = resized_image.size
        logger.info(f"Resized image size: {resized_size}")

        output = BytesIO()
        resized_image.save(output, format='PNG')
        output.seek(0)

        # Generate a unique key for storing the image in memory
        image_key = f"image_{len(image_store) + 1}.png"
        image_store[image_key] = output

        return image_key
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return None

def generate_image_options(subject, tone):
    """Generate multiple image options for a given subject and tone."""
    prompts = [
        f"An illustrative image depicting the main concept of {subject} in a {tone} tone.",
        f"An image showing a common application of {subject} in real life.",
        f"An image representing a common misconception about {subject}.",
        f"An abstract or metaphorical representation related to {subject}."
    ]
    image_urls = [generate_image(prompt) for prompt in prompts]
    return image_urls

def get_user_inputs(num_questions, subject, tone):
    """Generate MCQ questions with image options."""
    images_and_questions = []
    for _ in range(num_questions):
        option_images = generate_image_options(subject, tone)
        if not all(option_images):
            return jsonify({"error": "Failed to generate one or more option images"}), 500
        
        correct_answer_image = random.choice(option_images)  # Randomly choose one as the correct answer
        question = f"Select the image that best represents {subject}."
        
        images_and_questions.append({
            "question": question,
            "options": option_images,
            "correct_answer": option_images.index(correct_answer_image) + 1  # 1-indexed
        })
    return jsonify(images_and_questions)

@app.route('/generate_content', methods=['GET'])
def generate_content():
    """Route to generate content based on user input."""
    num_questions = int(request.args.get('number', 1))
    subject = request.args.get('subject', 'Science')
    tone = request.args.get('tone', 'informative')
    
    return get_user_inputs(num_questions, subject, tone)

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Serve images stored in memory."""
    if image_key in image_store:
        logger.info(f"Serving image with key: {image_key}")
        return send_file(BytesIO(image_store[image_key].getvalue()), mimetype='image/png')
    else:
        logger.error(f"Image with key {image_key} not found")
        return jsonify({"error": "Image not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
