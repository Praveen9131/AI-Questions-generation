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
image_store1 = {}

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
        image_key = f"image_{len(image_store1) + 1}.png"
        image_store1[image_key] = output
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
        {"role": "user", "content": f"Generate a clear and understandable multiple-choice question with exactly four options based on the subject '{subject}'. Each option should be related to the concept in the subject and in a '{tone}' tone. Ensure the correct answer is provided. Use the following format:\n\n**Question:** [Question based on the subject]\n\n**Options:**\n1. [Option 1]\n2. [Option 2]\n3. [Option 3]\n4. [Option 4]\n\n**Correct Answer:** [Correct Option]\n\nEnsure that all four options are provided."}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=description_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        content = response.choices[0].message.content

        question_section = content.split("**Question:**")[1].split("**Options:**")[0].strip()
        options_section = content.split("**Options:**")[1].split("**Correct Answer:**")[0].strip()
        correct_answer = content.split("**Correct Answer:**")[1].strip()

        options = options_section.split('\n')
        if len(options) != 4:
            raise ValueError("Generated options do not contain exactly 4 items")

        option_prompts = [option.split('. ')[1] for option in options]

        return {
            "question": question_section,
            "options": {
                f"Option {i+1}": option for i, option in enumerate(option_prompts)
            },
            "correct_answer": correct_answer
        }
    except Exception as e:
        logger.error(f"Error generating MCQ with text options: {e}")
        return {"error": "Failed to generate MCQ"}

def generate_custom_content1(number, subject, tone):
    """Generate custom content based on user-provided parameters."""
    try:
        if number < 1 or number > 100:
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

        result = generate_custom_content1(number, subject, tone)
        
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

        result = generate_custom_content1(number, subject, tone)
        
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict) and 'error' in result[0]:
            return jsonify(result[0]), result[1]

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/image/<image_key>', methods=['GET'])
def get_image(image_key):
    """Serve an image from in-memory storage."""
    if image_key in image_store1:
        return send_file(
            BytesIO(image_store1[image_key].getvalue()),
            mimetype='image/png'
        )
    else:
        logger.error(f"Image with key {image_key} not found")
        return jsonify({"error": "Image not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
