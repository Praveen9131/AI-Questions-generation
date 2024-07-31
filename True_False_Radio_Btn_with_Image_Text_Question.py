import os
import logging
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from PIL import Image
import requests
from io import BytesIO
from openai import OpenAI

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

# In-memory storage for images
image_store_true = {}

def download_and_resize_image(image_url, target_size):
    """Download an image from the given URL, resize it, and store it in-memory."""
    try:
        logger.info(f"Downloading image from URL: {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        resized_image = image.resize(target_size, Image.LANCZOS)
        output = BytesIO()
        resized_image.save(output, format='PNG')
        output.seek(0)
        image_key = f"image_{len(image_store_true) + 1}.png"
        image_store_true[image_key] = output
        return image_key
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return None

def generate_image(prompt: str):
    """Generate an image using the DALL-E model from OpenAI."""
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        safe_prompt = f"Simple, non-offensive illustration of {prompt}"
        response = client.images.generate(
            model="dall-e-3",
            prompt=safe_prompt,
            n=1,
            size="1024x1024"
        )
        return response.data[0].url
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

def generate_mcq_with_text_options(subject: str, tone: str):
    """Generate a multiple-choice question with text options based on the subject."""
    description_prompt = [
        {"role": "system", "content": "You are an expert in generating educational content."},
        {"role": "user", "content": (
            f"Generate five statements related to the subject '{subject}' and provide the options 'True', 'False', and 'Cannot Tell' for each statement. "
            f"Also, provide the correct answer for each statement in the format 'optionX', where X corresponds to the option number. "
            f"Format the output as follows:\n\n"
            f"**Statements:**\n"
            f"1. Statement 1\n"
            f"2. Statement 2\n"
            f"3. Statement 3\n"
            f"4. Statement 4\n"
            f"5. Statement 5\n\n"
            f"**Options:**\n"
            f"1. True\n"
            f"2. False\n"
            f"3. Cannot Tell\n\n"
            f"**Correct Answers:**\n"
            f"1. optionX\n"
            f"2. optionX\n"
            f"3. optionX\n"
            f"4. optionX\n"
            f"5. optionX"
        )}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=description_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        content = response.choices[0].message.content

        # Ensure the response is split correctly
        if "**Statements:**" in content and "**Options:**" in content and "**Correct Answers:**" in content:
            statements_section = content.split("**Statements:**")[1].split("**Options:**")[0].strip()
            options_section = content.split("**Options:**")[1].split("**Correct Answers:**")[0].strip()
            correct_answers_section = content.split("**Correct Answers:**")[1].strip()

            statements = [s.strip() for s in statements_section.split('\n')]
            options = [o.strip() for o in options_section.split('\n')]
            correct_answers = [a.split(": ")[0].strip() for a in correct_answers_section.split('\n')]

            # Ensure the correct number of statements, options, and answers
            if len(options) == 3 and len(statements) == 5 and len(correct_answers) == 5:
                return {
                    "statements": statements,
                    "options": options,
                    "correct_answers": correct_answers
                }
            else:
                logger.error("Error: Mismatch in the number of statements, options, or correct answers")
                return {"error": "Failed to generate MCQ"}
        else:
            logger.error("Error: Expected format not found in the response")
            return {"error": "Failed to generate MCQ"}
    except Exception as e:
        logger.error(f"Error generating MCQ with text options: {e}")
        return {"error": "Failed to generate MCQ"}


def generate_custom_content_true(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 10:
            return {"error": "Number of questions must be between 1 and 10"}, 400

        images_and_questions = []
        for _ in range(number):
            image_prompt = f"High-quality, detailed illustration representing the subject: {subject} in a {tone} tone"
            question_image_url = generate_image(image_prompt)
            if not question_image_url:
                question_image_url = "placeholder_image_url"

            mcq_with_text = generate_mcq_with_text_options(subject, tone)
            if "error" in mcq_with_text:
                return {"error": "Failed to generate MCQ"}, 500

            mcq_with_text["question_image_url"] = question_image_url
            images_and_questions.append(mcq_with_text)

        for item in images_and_questions:
            question_image_url = item["question_image_url"]
            question_image_key = download_and_resize_image(question_image_url, (750, 319)) if question_image_url != "placeholder_image_url" else "placeholder_image_url"
            if question_image_key:
                item["question_image_url"] = f"/image/{question_image_key}"

        return images_and_questions
    except Exception as e:
        logger.error(f"Error generating custom content: {e}")
        return {"error": "Internal server error"}, 500

@app.route('/custom', methods=['POST'])
def custom_content():
    """Endpoint to generate custom content based on user-provided parameters."""
    try:
        data = request.json
        number = int(data.get('number', 1))
        subject = data.get('subject', 'default subject').strip('"')
        tone = data.get('tone', 'neutral')

        result = generate_custom_content_true(number, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in custom content generation: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/', methods=['GET', 'POST'])
def generate_content():
    """Endpoint to generate content based on user-set parameters."""
    try:
        if request.method == 'POST':
            data = request.json
            number = int(data.get('number', 1))
            subject = data.get('subject', 'default subject').strip('"')
            tone = data.get('tone', 'neutral')
        else:
            number = int(request.args.get('number', 1))
            subject = request.args.get('subject', 'default subject').strip('"')
            tone = request.args.get('tone', 'neutral')

        if number < 1 or number > 10:
            return jsonify({"error": "Number of questions must be between 1 and 10"}), 400

        result = generate_custom_content_true(number, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Serve an image from in-memory storage."""
    if image_key in image_store_true:
        return send_file(
            BytesIO(image_store_true[image_key].getvalue()),
            mimetype='image/png'
        )
    else:
        logger.error(f"Image with key {image_key} not found")
        return jsonify({"error": "Image not found"}), 404


